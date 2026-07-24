"""Web MCP 项目级 storageState 解析工具。

为 agent 层提供与 service 层解耦的 storageState 路径解析能力，
避免 agent 直接导入 StorageStateService / WebTestService 造成循环依赖。
"""

import logging
from pathlib import Path
from typing import Optional
from uuid import UUID

UUIDValueError = ValueError

from sqlalchemy import select

from app.config.database import async_session_factory
from app.models.project import Project
from app.models.storage_state_job import StorageStateJob
from app.repositories.project_repo import ProjectRepository
from app.utils.storage_state_validator import validate_storage_state

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
            if not path.exists():
                logger.warning(
                    "[WebMCPStorage] storageState 文件不存在，job=%s path=%s",
                    job.id,
                    path,
                )
                return None

            validation = validate_storage_state(path)
            if not validation.is_valid:
                logger.warning(
                    "[WebMCPStorage] storageState 校验无效，job=%s path=%s reason=%s",
                    job.id,
                    path,
                    validation.reason,
                )
                return None

            return str(path.resolve())
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
