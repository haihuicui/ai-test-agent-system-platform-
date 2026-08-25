"""Web Agent 接口调用工具。

为 web agent 提供直接的 HTTP 接口调用能力，主要用于接口造数场景：
- 用户在需求中提供造数接口（如「造数接口：POST /api/xxx」），或探索期通过
  browser_network_requests 抓包发现端点后，agent 用本工具实测验证端点可用性
  （确认请求字段、响应结构、id 提取路径），再写入测试计划的 API Data Setup。
- 鉴权自动注入（项目环境配置 → storageState token 回退），模型无需也不应
  处理凭证；敏感头在日志与返回值中脱敏。

安全边界：URL 域名必须与项目默认环境 base_url 一致（防止误指其他环境）。
"""

import json
import logging
from typing import Optional
from urllib.parse import urlparse

import httpx
from langchain_core.tools import tool

from app.config import settings
from app.config.database import async_session_factory
from app.repositories.environment_repo import EnvironmentRepository
from app.repositories.project_repo import ProjectRepository
from app.utils.sync_executor import run_sync
from app.utils.web_mcp_storage_state import (
    extract_credentials_from_storage_state_data,
    resolve_effective_storage_state,
)

logger = logging.getLogger(__name__)

_MAX_RESPONSE_BODY_CHARS = 2000
_REQUEST_TIMEOUT_SECONDS = 30.0
_ALLOWED_METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"}


def _redact_headers(headers: dict) -> dict:
    """脱敏请求头：敏感头只保留键名，值替换为 ***。"""
    sensitive = {h.lower() for h in settings.api_test_sensitive_headers}
    return {
        k: ("***" if k.lower() in sensitive else v) for k, v in headers.items()
    }


async def _resolve_project_env(project_identifier: str):
    """解析项目及其默认环境配置。返回 (project, env)，查不到则为 None。"""
    if not project_identifier:
        return None, None
    try:
        async with async_session_factory() as session:
            project = await ProjectRepository(session).get_by_identifier(
                project_identifier
            )
            if project is None:
                return None, None
            env = await EnvironmentRepository(session).get_default_by_project(
                project.id
            )
            return project, env
    except Exception as exc:
        logger.warning("[web_api_request] 解析项目环境失败: %s", exc)
        return None, None


async def _build_auth(
    project_identifier: str, env
) -> "tuple[dict, list[dict], str]":
    """构建鉴权头与 cookies。

    优先级：
      1. 项目环境配置（resolve_auth_credentials：bearer/api_key/dynamic_bearer 等）
      2. storageState 回退（form_login 类项目）：localStorage/cookie 中的 token
         作为 Bearer 头，同时携带全部 cookies

    Returns:
        (headers, cookies, auth_source)。
    """
    headers: dict = {}
    cookies: list[dict] = []
    auth_source = "none"

    if env is not None:
        try:
            # 延迟 import，避免模块加载顺序问题
            from app.utils.auth_resolver import resolve_auth_credentials

            creds = await resolve_auth_credentials(env)
            if creds.headers:
                headers.update(creds.headers)
                auth_source = f"env({env.auth_type})"
        except Exception as exc:
            logger.warning("[web_api_request] 环境鉴权解析失败，尝试 storageState: %s", exc)

    if not headers and project_identifier:
        try:
            ss_path = await resolve_effective_storage_state(project_identifier)
            if ss_path:
                from pathlib import Path

                ss_data = json.loads(
                    await run_sync(Path(ss_path).read_text, encoding="utf-8")
                )
                token, cookies = extract_credentials_from_storage_state_data(ss_data)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    auth_source = "storage_state"
        except Exception as exc:
            logger.warning("[web_api_request] storageState 鉴权提取失败: %s", exc)

    return headers, cookies, auth_source


def _build_httpx_cookies(cookie_dicts: list[dict]) -> httpx.Cookies:
    """把 Playwright storageState cookie 格式转换为 httpx.Cookies。"""
    jar = httpx.Cookies()
    for c in cookie_dicts:
        name = c.get("name")
        value = c.get("value")
        if not name or value is None:
            continue
        try:
            jar.set(name, value, domain=c.get("domain", ""), path=c.get("path", "/"))
        except Exception:
            # 个别 cookie 属性不兼容（如 domain 前缀点）不阻塞整体请求
            logger.debug("[web_api_request] cookie 跳过: %s", name)
    return jar


@tool
async def web_api_request(
    method: str,
    url: str,
    purpose: str,
    body: Optional[dict] = None,
    headers: Optional[dict] = None,
    project_identifier: str = "",
) -> str:
    """直接向目标环境发起 HTTP 接口调用（主要用于接口造数的探索期验证）。

    使用场景：
    - 用户需求中提供了造数接口（如「造数接口：POST /api/xxx，body: {...}」），
      用本工具实测验证端点可用性、确认响应结构与 id 提取路径
    - 探索期通过 browser_network_requests 抓包发现候选造数端点后，实测验证

    鉴权自动注入（项目环境配置 → 项目 storageState token 回退），
    无需也不应在 headers 中手动传 Authorization/Cookie。
    URL 域名必须与项目默认环境 base_url 一致，否则拒绝执行。

    Args:
        method: HTTP 方法（GET/POST/PUT/PATCH/DELETE）
        url: 完整 URL（必须带协议与域名，如 https://example.com/api/orders）
        purpose: 调用目的说明（如「验证采样点造数端点」），用于审计日志
        body: JSON 请求体（可选）
        headers: 额外请求头（可选，会合并到自动注入的鉴权头之上）
        project_identifier: 项目标识符（系统自动注入，不要询问用户提供）

    Returns:
        JSON 字符串：success / status / body（截断 2000 字符）/ auth_source 等。
    """
    method_upper = (method or "").upper()
    if method_upper not in _ALLOWED_METHODS:
        return json.dumps(
            {"success": False, "error": f"不支持的 HTTP 方法: {method}"},
            ensure_ascii=False,
        )
    if not url or not urlparse(url).netloc:
        return json.dumps(
            {"success": False, "error": f"URL 不完整（必须带协议与域名）: {url}"},
            ensure_ascii=False,
        )

    _project, env = await _resolve_project_env(project_identifier)

    # 域名校验：必须与项目默认环境 base_url 同域，防止误指其他环境
    if env is not None and env.base_url:
        env_netloc = urlparse(env.base_url).netloc
        req_netloc = urlparse(url).netloc
        if env_netloc and req_netloc.lower() != env_netloc.lower():
            return json.dumps(
                {
                    "success": False,
                    "error": (
                        f"URL 域名 {req_netloc} 与项目环境 {env.name} 的 "
                        f"base_url 域名 {env_netloc} 不一致，拒绝执行。"
                        "如需调用其他域名，请检查项目环境配置。"
                    ),
                },
                ensure_ascii=False,
            )

    auth_headers, cookie_dicts, auth_source = await _build_auth(
        project_identifier, env
    )
    # 用户显式传入的 headers 优先级最高（脱敏后入日志）
    merged_headers = {**auth_headers, **(headers or {})}

    try:
        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT_SECONDS,
            follow_redirects=False,  # 302 跳登录页是重要失效信号，需原样暴露
            cookies=_build_httpx_cookies(cookie_dicts),
        ) as client:
            resp = await client.request(
                method_upper, url, headers=merged_headers, json=body
            )
    except httpx.TimeoutException:
        return json.dumps(
            {
                "success": False,
                "error": f"请求超时（{_REQUEST_TIMEOUT_SECONDS:.0f}s）: {method_upper} {url}",
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {"success": False, "error": f"请求异常: {type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )

    body_text = resp.text or ""
    truncated = len(body_text) > _MAX_RESPONSE_BODY_CHARS
    if truncated:
        body_text = body_text[:_MAX_RESPONSE_BODY_CHARS]

    logger.info(
        "[web_api_request] %s %s purpose=%r project=%s auth=%s -> %s",
        method_upper,
        url,
        purpose,
        project_identifier,
        auth_source,
        resp.status_code,
    )

    return json.dumps(
        {
            "success": 200 <= resp.status_code < 400,
            "status": resp.status_code,
            "auth_source": auth_source,
            "request_headers_sent": _redact_headers(merged_headers),
            "body": body_text,
            "body_truncated": truncated,
            "hint": (
                "2xx/3xx 表示端点可用。请在测试计划的 API Data Setup 中记录："
                "具体 JSON Body（真实字段名）、Response 的 id 提取路径（如 $.data.id）。"
                if 200 <= resp.status_code < 400
                else "非 2xx/3xx 响应：分析响应体调整请求（字段/鉴权/路径），或改用 UI 造数并在计划中标注原因。"
            ),
        },
        ensure_ascii=False,
        indent=2,
    )
