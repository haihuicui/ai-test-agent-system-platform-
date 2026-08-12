"""Web MCP 项目级 storageState 解析工具。

为 agent 层提供与 service 层解耦的 storageState 路径解析能力，
避免 agent 直接导入 StorageStateService / WebTestService 造成循环依赖。
"""

import asyncio
import logging
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
