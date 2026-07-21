"""Web MCP 项目级 storageState 解析工具。

为 agent 层提供与 service 层解耦的 storageState 路径解析能力，
避免 agent 直接导入 StorageStateService / WebTestService 造成循环依赖。
"""

import logging
from pathlib import Path
from typing import Optional
from uuid import UUID, ValueError as UUIDValueError

from sqlalchemy import select

from app.config.database import async_session_factory
from app.models.project import Project
from app.models.storage_state_job import StorageStateJob
from app.repositories.project_repo import ProjectRepository

logger = logging.getLogger(__name__)


async def resolve_project_storage_state_path(project_identifier: str) -> Optional[str]:
    """
    解析当前项目最近一次成功生成的 storageState.json 本地路径。

    返回 None 的场景：
      - project_identifier 为空
      - 项目不存在
      - 项目下没有已完成的 StorageStateJob
      - job.output_path 指向的文件在磁盘上不存在

    Args:
        project_identifier: 项目标识符（如 PR-1234）或项目 ID（UUID 字符串）。

    Returns:
        storageState 文件的绝对路径；不存在时返回 None。
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

            result = await session.execute(
                select(StorageStateJob)
                .where(
                    StorageStateJob.project_id == project.id,
                    StorageStateJob.status == "completed",
                    StorageStateJob.output_path.isnot(None),
                )
                .order_by(StorageStateJob.completed_at.desc())
                .limit(1)
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
