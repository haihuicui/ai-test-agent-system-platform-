"""
项目仓储

处理项目相关的数据库操作
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.repositories.base import BaseRepository
from app.models.project import Project
from app.models.folder import Folder
from app.models.test_case import TestCase
from app.models.attachment import Attachment

# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkhKUE9BPT06Njg5YTIxYzA=

class ProjectRepository(BaseRepository[Project]):
    """
    项目仓储类
    
    提供项目相关的数据库操作
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(Project, session)
    
    async def get_by_identifier(self, identifier: str) -> Optional[Project]:
        """
        根据标识符获取项目
        
        Args:
            identifier: 项目标识符，如 PR-1234
            
        Returns:
            Optional[Project]: 项目实例或 None
        """
        result = await self.session.execute(
            select(Project)
            .options(selectinload(Project.teams))
            .where(Project.identifier == identifier)
        )
        return result.scalar_one_or_none()
    
    async def get_by_id_with_relations(self, id: UUID) -> Optional[Project]:
        """
        根据 ID 获取项目（包含关联数据）
        
        Args:
            id: 项目 ID
            
        Returns:
            Optional[Project]: 项目实例或 None
        """
        result = await self.session.execute(
            select(Project)
            .options(selectinload(Project.teams))
            .options(selectinload(Project.creator))
            .where(Project.id == id)
        )
        return result.scalar_one_or_none()
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkhKUE9BPT06Njg5YTIxYzA=
    
    async def get_all_with_counts(
        self,
        offset: int = 0,
        limit: int = 30,
    ) -> list[dict]:
        """
        获取所有项目及其统计信息

        使用标量子查询一次性返回测试用例/文件夹数量，避免 2N+1 查询。

        Args:
            offset: 偏移量
            limit: 限制数量

        Returns:
            list[dict]: 项目列表及统计信息
        """
        test_cases_count = (
            select(func.count(TestCase.id))
            .where(TestCase.project_id == Project.id)
            .correlate(Project)
            .scalar_subquery()
            .label("test_cases_count")
        )
        folders_count = (
            select(func.count(Folder.id))
            .where(Folder.project_id == Project.id)
            .correlate(Project)
            .scalar_subquery()
            .label("folders_count")
        )

        result = await self.session.execute(
            select(Project, test_cases_count, folders_count)
            .options(selectinload(Project.teams))
            .options(selectinload(Project.creator))
            .offset(offset)
            .limit(limit)
            .order_by(Project.created_at.desc())
        )

        return [
            {
                "project": project,
                "test_cases_count": tc_count,
                "folders_count": folder_count,
            }
            for project, tc_count, folder_count in result.all()
        ]

    async def get_by_identifier_with_counts(
        self,
        identifier: str,
    ) -> Optional[dict]:
        """
        根据标识符获取项目及其统计信息

        Args:
            identifier: 项目标识符，如 PR-1234

        Returns:
            Optional[dict]: 项目及统计信息，项目不存在时返回 None
        """
        result = await self.session.execute(
            select(Project)
            .options(selectinload(Project.teams))
            .options(selectinload(Project.creator))
            .where(Project.identifier == identifier)
        )
        project = result.scalar_one_or_none()
        if not project:
            return None

        tc_count = await self.session.scalar(
            select(func.count(TestCase.id)).where(TestCase.project_id == project.id)
        )
        folder_count = await self.session.scalar(
            select(func.count(Folder.id)).where(Folder.project_id == project.id)
        )

        return {
            "project": project,
            "test_cases_count": tc_count or 0,
            "folders_count": folder_count or 0,
        }

    async def get_next_sequence(self) -> int:
        """
        获取下一个项目序号
        
        Returns:
            int: 下一个序号
        """
        result = await self.session.execute(
            select(func.count()).select_from(Project)
        )
        count = result.scalar_one()
        return count + 1
    
    async def identifier_exists(self, identifier: str) -> bool:
        """
        检查标识符是否已存在

        Args:
            identifier: 项目标识符

        Returns:
            bool: 是否存在
        """
        result = await self.session.execute(
            select(func.count()).select_from(Project)
            .where(Project.identifier == identifier)
        )
        return result.scalar_one() > 0

    async def delete(self, instance: Project) -> None:
        """
        删除项目及相关数据

        Args:
            instance: 要删除的项目
        """
        project_id = instance.id

        # 先删除与项目相关的所有附件
        # 这比依赖数据库级联更安全，因为 attachments 通过 entity_id 关联到不同实体
        await self.session.execute(
            delete(Attachment).where(Attachment.project_id == project_id)
        )

        # 删除项目（数据库级联会自动删除 folders, test_cases 等其他关联）
        await self.session.delete(instance)
        await self.session.flush()
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WkhKUE9BPT06Njg5YTIxYzA=

