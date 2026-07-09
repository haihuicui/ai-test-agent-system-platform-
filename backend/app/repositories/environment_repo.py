"""
项目环境配置仓储

处理 ProjectEnvironment 相关的数据库操作
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base import BaseRepository
from app.models.environment import ProjectEnvironment


class EnvironmentRepository(BaseRepository[ProjectEnvironment]):
    """
    项目环境配置仓储类

    提供环境配置相关的数据库操作
    """

    def __init__(self, session: AsyncSession):
        super().__init__(ProjectEnvironment, session)

    async def list_by_project(self, project_id: UUID) -> list[ProjectEnvironment]:
        """
        获取项目的所有环境配置

        Args:
            project_id: 项目 ID

        Returns:
            list[ProjectEnvironment]: 环境配置列表
        """
        result = await self.session.execute(
            select(ProjectEnvironment)
            .where(ProjectEnvironment.project_id == project_id)
            .order_by(ProjectEnvironment.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_default_by_project(self, project_id: UUID) -> Optional[ProjectEnvironment]:
        """
        获取项目的默认环境配置

        Args:
            project_id: 项目 ID

        Returns:
            Optional[ProjectEnvironment]: 默认环境配置或 None
        """
        result = await self.session.execute(
            select(ProjectEnvironment)
            .where(
                ProjectEnvironment.project_id == project_id,
                ProjectEnvironment.is_default.is_(True)
            )
        )
        return result.scalar_one_or_none()

    async def unset_default_for_project(self, project_id: UUID) -> None:
        """
        取消项目的所有默认环境标记

        Args:
            project_id: 项目 ID
        """
        await self.session.execute(
            select(ProjectEnvironment)
            .where(
                ProjectEnvironment.project_id == project_id,
                ProjectEnvironment.is_default.is_(True)
            )
        )
        # 使用 update 语句批量更新
        from sqlalchemy import update
        await self.session.execute(
            update(ProjectEnvironment)
            .where(
                ProjectEnvironment.project_id == project_id,
                ProjectEnvironment.is_default.is_(True)
            )
            .values(is_default=False)
        )

    async def get_by_project_and_name(
        self,
        project_id: UUID,
        name: str
    ) -> Optional[ProjectEnvironment]:
        """
        根据项目名称获取环境配置

        Args:
            project_id: 项目 ID
            name: 环境名称

        Returns:
            Optional[ProjectEnvironment]: 环境配置或 None
        """
        result = await self.session.execute(
            select(ProjectEnvironment)
            .where(
                ProjectEnvironment.project_id == project_id,
                ProjectEnvironment.name == name
            )
        )
        return result.scalar_one_or_none()
