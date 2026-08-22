"""Web MCP 项目级 storageState 解析工具。

为 agent 层提供与 service 层解耦的 storageState 路径解析能力，
避免 agent 直接导入 StorageStateService / WebTestService 造成循环依赖。
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Optional
from uuid import UUID

UUIDValueError = ValueError

from sqlalchemy import select

from app.config.database import async_session_factory
from app.models.environment import AuthType
from app.models.project import Project
from app.models.storage_state_job import StorageStateJob
from app.repositories.environment_repo import EnvironmentRepository
from app.repositories.project_repo import ProjectRepository
from app.utils.storage_state_validator import validate_storage_state
from app.utils.sync_executor import run_sync

logger = logging.getLogger(__name__)


async def resolve_project_storage_state_path(
    project_identifier: str,
    env_id: Optional[UUID | str] = None,
) -> Optional[str]:
    """
    解析当前项目最近一次成功生成的 storageState.json 本地路径。

    返回 None 的场景：
      - project_identifier 为空
      - 项目不存在
      - 项目下没有已完成的 StorageStateJob
      - job.output_path 指向的文件在磁盘上不存在
      - storageState 静态校验判定为过期或损坏

    查询优先级：
      1. 指定 env_id 对应环境的最新成功记录
      2. 项目级记录（environment_id IS NULL）作为向后兼容回退

    Args:
        project_identifier: 项目标识符（如 PR-1234）或项目 ID（UUID 字符串）。
        env_id: 可选环境配置 ID；传入时优先查找环境隔离记录。

    Returns:
        storageState 文件的绝对路径；不存在或无效时返回 None。
    """
    if not project_identifier:
        return None

    try:
        async with async_session_factory() as session:
            project = await _resolve_project(session, project_identifier)
            if project is None:
                logger.warning(
                    "[WebMCPStorage] 无法解析项目标识符: %s", project_identifier
                )
                return None

            env_id_value = UUID(str(env_id)) if env_id else None

            base_query = (
                select(StorageStateJob)
                .where(
                    StorageStateJob.project_id == project.id,
                    StorageStateJob.status == "completed",
                    StorageStateJob.output_path.isnot(None),
                )
                .order_by(StorageStateJob.completed_at.desc())
            )

            job = None
            if env_id_value:
                result = await session.execute(
                    base_query.where(
                        StorageStateJob.environment_id == env_id_value
                    ).limit(1)
                )
                job = result.scalar_one_or_none()

            if job is None:
                result = await session.execute(
                    base_query.where(
                        StorageStateJob.environment_id.is_(None)
                    ).limit(1)
                )
                job = result.scalar_one_or_none()

            if job is None:
                logger.info(
                    "[WebMCPStorage] 项目 %s 没有已完成的 storageState 任务",
                    project.identifier,
                )
                return None

            path = Path(job.output_path)
            if not await run_sync(path.exists):
                logger.warning(
                    "[WebMCPStorage] storageState 文件不存在，job=%s path=%s",
                    job.id,
                    path,
                )
                return None

            validation = await run_sync(validate_storage_state, path)
            if not validation.is_valid:
                logger.warning(
                    "[WebMCPStorage] storageState 校验无效，job=%s path=%s reason=%s",
                    job.id,
                    path,
                    validation.reason,
                )
                return None

            return str(await run_sync(path.resolve))
    except Exception as exc:
        logger.exception(
            "[WebMCPStorage] 解析项目 %s 的 storageState 失败: %s",
            project_identifier,
            exc,
        )
        return None


async def _resolve_project(session, project_identifier: str) -> Optional[Project]:
    """先按项目标识符解析，失败再尝试按 UUID 解析。"""
    repo = ProjectRepository(session)
    project = await repo.get_by_identifier(project_identifier)
    if project is not None:
        return project
    try:
        project_id = UUID(project_identifier)
        return await repo.get_by_id(project_id)
    except (UUIDValueError, ValueError):
        return None


# =============================================================================
# 项目登录态解析缓存：每 run 查 project/env 两张表，langgraph 侧
# 是 NullPool，每条会话还要付一次 PG SCRAM 建连（~0.5-1s）。60s TTL 足够
# 新鲜（storageState 续期后路径变化最多滞后 60s）。
# =============================================================================

_LOGIN_STATE_CACHE_TTL_SECONDS = 60.0
_login_state_cache: dict[str, tuple[float, bool, "str | None"]] = {}

# 默认「业务层登录失效」响应特征：很多应用在 token 过期时返回 HTTP 200 +
# 业务错误码包络（如 {"code":"4003","message":"登陆已过期"}），而不是 401——
# xmetrix-sit 实证（2026-08-22）：带过期 token 的请求返回 200/4003，
# 只有完全不带凭据才返回 401。仅看 HTTP 状态码的探针会对死 token 放行。
# 可用 env.auth_config["probe_invalid_pattern"] 按项目覆盖。
DEFAULT_PROBE_INVALID_PATTERN = re.compile(
    r"(登陆|登录).{0,4}(过期|失效)|未(登陆|登录)|invalid.?token|token.{0,10}expired",
    re.IGNORECASE,
)


def judge_probe_response(
    status_code: int,
    body_text: str,
    invalid_pattern: "re.Pattern[str] | None" = None,
) -> tuple[bool, str]:
    """判定探针响应是否表明登录态有效。供注入时探针与生成时探针共用。

    判失效（False）：HTTP 401/403，或 2xx 响应体命中失效特征正则。
    其余（2xx/3xx/404/5xx）均不判失效——404 可能只是探针路径不存在，
    5xx 是服务端问题，都与 token 有效性无关。
    """
    if status_code in (401, 403):
        return False, f"HTTP {status_code}"
    if 200 <= status_code < 300:
        pattern = invalid_pattern or DEFAULT_PROBE_INVALID_PATTERN
        if pattern.search(body_text or ""):
            return False, f"响应体命中失效特征: {pattern.pattern!r}"
    return True, f"status={status_code}"


async def probe_storage_state_liveness(
    storage_state_path: str,
    base_url: str,
    probe_path: "str | None" = None,
    probe_method: str = "GET",
    probe_body: "dict | None" = None,
    probe_invalid_pattern: "str | None" = None,
) -> tuple[bool, str]:
    """运行时探针：用 storageState 中的 token 访问需登录 API，判定是否已失效。

    与 StorageStateService._probe_storage_state（生成时探针）互补：本探针在
    run 注入存量 storageState 时执行——存量 token 可能在生成后、本次 run
    开始前已被服务端踢出（thread 681b9d01 实证：run 中途 401 → 目标站返回
    ``WWW-Authenticate: Basic`` 触发浏览器原生登录弹窗，MCP 调用全部卡死）。

    判失效（返回 False）仅当：探针明确返回 401/403，或 2xx 响应体命中
    失效特征正则（业务层 token 过期常返回 200 + 错误码包络）。
    网络异常、5xx、路径 404 等不确定情况一律放行（fail-open），
    避免探针基础设施问题误杀登录态。

    探针目标可用 per-env 覆盖（auth_config 的 probe_path/probe_method/
    probe_body/probe_invalid_pattern），默认 settings.web_mcp_storage_state_probe_path。

    Returns:
        (是否可用, 原因说明)。
    """
    try:
        ss_data = json.loads(
            await run_sync(Path(storage_state_path).read_text, encoding="utf-8")
        )
        token: Optional[str] = None
        for origin_entry in ss_data.get("origins", []):
            for item in origin_entry.get("localStorage", []):
                if item.get("name") == "token":
                    token = item.get("value")
                    break
            if token:
                break
        if not token:
            for cookie in ss_data.get("cookies", []):
                if cookie.get("name") == "Authorization":
                    token = cookie.get("value")
                    break
        if not token:
            # 无 token 可探（可能走其他认证形式），不据此判失效
            return True, "storageState 中无 token/Authorization，跳过运行时探针"

        from app.config import settings  # 延迟 import，避免循环依赖

        path = probe_path or settings.web_mcp_storage_state_probe_path
        probe_url = f"{base_url.rstrip('/')}{path}"
        pattern = (
            re.compile(probe_invalid_pattern, re.IGNORECASE)
            if probe_invalid_pattern
            else None
        )

        import httpx

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            resp = await client.request(
                probe_method.upper(),
                probe_url,
                headers={"Authorization": f"Bearer {token}"},
                json=probe_body,
            )
        ok, reason = judge_probe_response(resp.status_code, resp.text, pattern)
        return ok, f"{reason}: {probe_method.upper()} {probe_url}"
    except Exception as exc:
        logger.warning("[WebMCPStorage] 运行时探针异常（放行登录态）: %s", exc)
        return True, f"探针异常（放行）: {type(exc).__name__}: {exc}"


async def resolve_project_login_state(
    project_identifier: str,
) -> tuple[bool, "str | None"]:
    """解析项目登录态，返回 (has_login_config, storage_state 路径)。

    成功结果按 project_identifier 缓存 60s；异常不缓存（下次重试）。
    """
    now = asyncio.get_running_loop().time()
    cached = _login_state_cache.get(project_identifier)
    if cached and now - cached[0] < _LOGIN_STATE_CACHE_TTL_SECONDS:
        return cached[1], cached[2]

    has_login_config = False
    storage_state: str | None = None
    env = None
    try:
        async with async_session_factory() as session:
            project = await ProjectRepository(session).get_by_identifier(
                project_identifier
            )
            if project is not None:
                env = await EnvironmentRepository(
                    session
                ).get_default_by_project(project.id)
                if env is not None:
                    if env.auth_type == AuthType.FORM_LOGIN.value:
                        has_login_config = True
                    else:
                        auth_config = env.auth_config or {}
                        has_login_config = bool(
                            auth_config.get("form_login")
                            or auth_config.get("storage_state")
                        )
                if has_login_config:
                    storage_state = await resolve_project_storage_state_path(
                        project_identifier, env.id if env else None
                    )
                    if storage_state:
                        # 运行时探针：存量 token 可能在生成后已被服务端踢出。
                        # 明确 401/403 才判失效（降级为无登录态，走 UI 登录路径）；
                        # 探针异常/网络问题放行，结果随登录态缓存 60s。
                        from app.config import settings  # 延迟 import，避免循环依赖

                        if settings.web_mcp_storage_state_probe_enabled and (
                            env is not None and env.base_url
                        ):
                            env_cfg = env.auth_config or {}
                            alive, reason = await probe_storage_state_liveness(
                                storage_state,
                                env.base_url,
                                probe_path=env_cfg.get("probe_path"),
                                probe_method=env_cfg.get("probe_method", "GET"),
                                probe_body=env_cfg.get("probe_body"),
                                probe_invalid_pattern=env_cfg.get(
                                    "probe_invalid_pattern"
                                ),
                            )
                            if not alive:
                                logger.warning(
                                    "[WebMCPAgent] 项目 %s storageState 运行时探针"
                                    "判定失效（%s），本 run 不注入登录态，"
                                    "将依赖 UI 登录路径。",
                                    project_identifier,
                                    reason,
                                )
                                storage_state = None
                    if storage_state:
                        logger.info(
                            "[WebMCPAgent] 使用项目级 storageState: %s",
                            storage_state,
                        )
                    else:
                        logger.warning(
                            "[WebMCPAgent] 项目 %s 已配置 Web 登录但无有效项目级 "
                            "storageState，不使用全局 fallback，将依赖脚本自身登录逻辑。",
                            project_identifier,
                        )
                elif project is not None:
                    logger.info(
                        "[WebMCPAgent] 项目 %s 未配置 Web 登录，不使用 storageState。",
                        project_identifier,
                    )
    except Exception as exc:
        logger.warning(
            "[WebMCPAgent] 解析项目默认环境登录态失败: %s", exc
        )
        return False, None

    _login_state_cache[project_identifier] = (now, has_login_config, storage_state)
    return has_login_config, storage_state


async def resolve_effective_storage_state(project_identifier: str) -> "str | None":
    """解析当前 run 生效的 storageState 路径（MCP 探索与脚本执行必须一致）。

    优先级：项目/环境级 storageState → 全局 ``settings.web_mcp_storage_state``
    （仅当项目未配置登录态时回退，且需校验有效）。返回 ``None`` 表示本 run
    不带登录态。
    """
    storage_state: str | None = None
    has_login_config = False
    if project_identifier:
        has_login_config, storage_state = await resolve_project_login_state(
            project_identifier
        )

    if not storage_state and not has_login_config:
        # 延迟 import，避免与配置加载产生循环依赖
        from app.config import settings

        global_ss = settings.web_mcp_storage_state
        if global_ss:
            validation = validate_storage_state(global_ss)
            if validation.is_valid:
                logger.info("[WebMCPStorage] 使用全局 storageState: %s", global_ss)
                return global_ss
            logger.warning(
                "[WebMCPStorage] 全局 storageState 无效，跳过注入: %s",
                validation.reason,
            )
    return storage_state
