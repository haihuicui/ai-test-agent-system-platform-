"""
认证解析工具模块

将项目环境配置中的认证信息解析为可复用的 HTTP Headers 和 Token。
被 EnvironmentService 与场景执行引擎共同使用。
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

import httpx
from jsonpath_ng import parse as jsonpath_parse

from app.models.environment import AuthType, ProjectEnvironment
from app.utils.exceptions import BadRequestException

logger = logging.getLogger(__name__)


class DynamicTokenError(Exception):
    """动态 token 获取失败"""
    pass


class _TokenCache:
    """
    简单的内存 TTL 缓存，用于缓存动态获取的 token。

    注意：这是单进程缓存。多实例部署时各实例会独立刷新 token，
    如需共享请后续替换为 Redis。
    """

    def __init__(self, default_ttl: int = 300):
        self._store: dict[str, tuple[str, float]] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(env_id: UUID, config: dict) -> str:
        config_hash = hashlib.sha256(
            json.dumps(config, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]
        return f"{env_id}:{config_hash}"

    async def get(self, env_id: UUID, config: dict) -> Optional[str]:
        async with self._lock:
            key = self._key(env_id, config)
            token, expires_at = self._store.get(key, (None, 0.0))
            if token and time.time() < expires_at:
                return token
            self._store.pop(key, None)
            return None

    async def set(self, env_id: UUID, config: dict, token: str, ttl: Optional[int] = None) -> None:
        async with self._lock:
            ttl = ttl if ttl is not None and ttl > 0 else self._default_ttl
            key = self._key(env_id, config)
            self._store[key] = (token, time.time() + ttl)

    async def clear(self, env_id: UUID, config: dict) -> None:
        async with self._lock:
            self._store.pop(self._key(env_id, config), None)


# 全局 token 缓存实例
_dynamic_token_cache = _TokenCache()


def render_template(value: Any, variables: dict[str, str]) -> Any:
    """
    递归渲染模板变量 {{key}}。

    Args:
        value: 需要渲染的值（字符串、字典、列表等）
        variables: 变量字典

    Returns:
        渲染后的值
    """
    if isinstance(value, str):
        result = value
        for key, val in variables.items():
            result = result.replace(f"{{{{{key}}}}}", str(val))
        return result
    if isinstance(value, dict):
        return {k: render_template(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [render_template(v, variables) for v in value]
    return value


def extract_by_path(data: Any, path: str) -> Any:
    """
    从 JSON 数据中提取字段。

    支持两种格式：
    - JSONPath: 以 $ 开头，如 $.data.token
    - 点路径: 不以 $ 开头，如 data.token（兼容简单场景）

    Args:
        data: JSON 数据
        path: 提取路径

    Returns:
        提取到的值

    Raises:
        DynamicTokenError: 提取失败
    """
    try:
        if path.startswith("$"):
            jsonpath_expr = jsonpath_parse(path)
            matches = jsonpath_expr.find(data)
            if not matches:
                raise DynamicTokenError(f"JSONPath '{path}' 未匹配到任何值")
            return matches[0].value

        # 点路径解析
        current = data
        for part in path.split("."):
            if isinstance(current, dict):
                if part not in current:
                    raise DynamicTokenError(f"路径 '{path}' 提取失败：字段 '{part}' 不存在")
                current = current[part]
            else:
                raise DynamicTokenError(f"路径 '{path}' 提取失败：'{current}' 不是对象")
        return current
    except DynamicTokenError:
        raise
    except Exception as e:
        raise DynamicTokenError(f"从响应中提取 token 失败: {e}") from e


@dataclass
class AuthCredentials:
    """解析后的认证凭据"""

    headers: dict[str, str]
    """需要注入到 HTTP 请求头的键值对"""

    token: Optional[str]
    """解析到的 token（若有）"""

    auth_type: str
    """认证类型"""


def build_auth_headers(
    auth_type: str,
    auth_secret: Optional[str],
    auth_config: Optional[dict[str, Any]] = None,
) -> dict[str, str]:
    """
    根据认证类型构建请求头。

    Args:
        auth_type: AuthType 值
        auth_secret: 认证密钥/静态 token
        auth_config: 认证扩展配置（api_key 等需要）

    Returns:
        需要加入 HTTP 请求头的键值对；dynamic_bearer 类型返回空字典，
        因为 token 需要异步获取。
    """
    auth_config = auth_config or {}
    headers: dict[str, str] = {}

    if auth_type == AuthType.NONE.value or not auth_secret:
        return headers

    if auth_type in (AuthType.BEARER.value, AuthType.OAUTH2.value):
        headers["Authorization"] = f"Bearer {auth_secret}"
    elif auth_type == AuthType.API_KEY.value:
        key_name = auth_config.get("api_key_header", "X-API-Key")
        headers[key_name] = auth_secret
    elif auth_type == AuthType.DYNAMIC_BEARER.value:
        # 动态 token 需要异步获取，这里无法直接返回
        logger.debug("build_auth_headers: dynamic_bearer 需要异步解析 token")
    else:
        logger.warning("未知的认证类型: %s", auth_type)

    return headers


async def fetch_dynamic_bearer_token(auth_config: dict[str, Any]) -> str:
    """
    根据 auth_config 实际发起请求并提取动态 token。

    不读取/写入缓存，只负责网络请求、模板渲染和 token 解析。

    Args:
        auth_config: 动态 bearer 认证配置，需包含 token_url 等字段

    Returns:
        获取到的 token

    Raises:
        BadRequestException: 配置缺失或无效
        DynamicTokenError: token 获取失败
    """
    cfg = auth_config or {}
    token_url = cfg.get("token_url")
    if not token_url:
        raise BadRequestException("动态认证未配置 token_url")

    method = (cfg.get("token_method") or "POST").upper()
    token_path = cfg.get("token_path") or "$.data.token"

    # 渲染 headers / body 模板
    # 注：按业务要求，用户名密码等直接写在 token_body 中，不再单独维护凭据字段
    variables = {
        str(k): str(v)
        for k, v in cfg.items()
        if k not in ["token_url", "token_method", "token_path", "token_ttl_seconds", "token_headers"]
    }
    headers = render_template(cfg.get("token_headers", {}), variables)
    body = render_template(cfg.get("token_body", {}), variables)

    # 发送请求
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                response = await client.get(
                    str(token_url),
                    headers=headers,
                    params=body if isinstance(body, dict) else None,
                )
            else:
                response = await client.request(
                    method,
                    str(token_url),
                    headers=headers,
                    json=body if isinstance(body, dict) else None,
                    content=body if isinstance(body, str) else None,
                )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        raise DynamicTokenError(
            f"获取动态 token 失败，接口返回 {e.response.status_code}: "
            f"{e.response.text[:200]}"
        ) from e
    except httpx.RequestError as e:
        raise DynamicTokenError(f"请求动态 token 接口失败: {e}") from e
    except json.JSONDecodeError as e:
        raise DynamicTokenError(f"动态 token 接口返回非 JSON: {e}") from e

    # 提取 token
    try:
        token = extract_by_path(data, token_path)
    except DynamicTokenError:
        raise

    if not isinstance(token, str) or not token:
        raise DynamicTokenError(
            f"从 token 接口响应中提取到的值不是有效字符串: {token!r}"
        )

    return token


async def resolve_dynamic_bearer_token(
    env: ProjectEnvironment,
    *,
    force_refresh: bool = False,
) -> str:
    """
    解析动态 Bearer Token。

    根据 env.auth_config 中配置的 token_url、token_method、token_body、
    token_path 等，调用接口并提取 token。

    Args:
        env: 项目环境配置
        force_refresh: 是否强制刷新缓存

    Returns:
        获取到的 token

    Raises:
        BadRequestException: 配置缺失或无效
        DynamicTokenError: token 获取失败
    """
    if env.auth_type != AuthType.DYNAMIC_BEARER.value:
        raise BadRequestException(
            f"环境 '{env.name}' 的认证类型不是 dynamic_bearer，无法解析动态 token"
        )

    cfg = env.auth_config or {}
    token_ttl = cfg.get("token_ttl_seconds") or 0

    # 1. 尝试读缓存
    if not force_refresh:
        cached = await _dynamic_token_cache.get(env.id, cfg)
        if cached:
            logger.debug("[auth_resolver] 命中动态 token 缓存: env=%s", env.id)
            return cached

    # 2. 请求并解析 token
    token = await fetch_dynamic_bearer_token(cfg)

    # 3. 写入缓存
    if token_ttl > 0:
        await _dynamic_token_cache.set(env.id, cfg, token, ttl=token_ttl)
        logger.info(
            "[auth_resolver] 动态 token 获取成功并已缓存: env=%s ttl=%ss",
            env.id,
            token_ttl,
        )
    else:
        logger.info("[auth_resolver] 动态 token 获取成功（未缓存）: env=%s", env.id)

    return token


async def resolve_auth_credentials(env: ProjectEnvironment) -> AuthCredentials:
    """
    解析项目环境的完整认证凭据。

    Args:
        env: 项目环境配置

    Returns:
        AuthCredentials，包含应注入的请求头和 token
    """
    if env.auth_type == AuthType.DYNAMIC_BEARER.value:
        token = await resolve_dynamic_bearer_token(env)
        return AuthCredentials(
            headers={"Authorization": f"Bearer {token}"},
            token=token,
            auth_type=env.auth_type,
        )

    headers = build_auth_headers(env.auth_type, env.auth_secret, env.auth_config)
    return AuthCredentials(
        headers=headers,
        token=env.auth_secret,
        auth_type=env.auth_type,
    )
