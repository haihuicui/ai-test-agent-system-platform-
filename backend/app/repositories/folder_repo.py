"""
文件夹仓储

处理文件夹相关的数据库操作
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.repositories.base import BaseRepository
from app.models.folder import Folder
from app.models.test_case import TestCase


class FolderRepository(BaseRepository[Folder]):
    """
    文件夹仓储类
    
    提供文件夹相关的数据库操作
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(Folder, session)
    
    async def get_by_project(
        self,
        project_id: UUID,
        offset: int = 0,
        limit: int = 30,
        folder_type: Optional[str] = None,
    ) -> list[Folder]:
        """
        获取项目下的文件夹列表

        Args:
            project_id: 项目 ID
            offset: 偏移量
            limit: 限制数量
            folder_type: 文件夹类型过滤

        Returns:
            list[Folder]: 文件夹列表
        """
        query = select(Folder).where(Folder.project_id == project_id)

        if folder_type:
            from app.models.folder_type import FolderType
            query = query.where(Folder.folder_type == FolderType(folder_type))

        result = await self.session.execute(
            query
            .offset(offset)
            .limit(limit)
            .order_by(Folder.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_root_folders(
        self,
        project_id: UUID,
        offset: int = 0,
        limit: int = 30,
        folder_type: Optional[str] = None,
    ) -> list[Folder]:
        """
        获取项目下的根文件夹列表

        Args:
            project_id: 项目 ID
            offset: 偏移量
            limit: 限制数量
            folder_type: 文件夹类型过滤

        Returns:
            list[Folder]: 根文件夹列表
        """
        query = select(Folder).where(Folder.project_id == project_id).where(Folder.parent_id.is_(None))
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VTAweVJBPT06OGNjMmM5YjE=

        if folder_type:
            from app.models.folder_type import FolderType
            query = query.where(Folder.folder_type == FolderType(folder_type))

        result = await self.session.execute(
            query
            .offset(offset)
            .limit(limit)
            .order_by(Folder.name)
        )
        return list(result.scalars().all())
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VTAweVJBPT06OGNjMmM5YjE=
    
    async def get_sub_folders(
        self,
        folder_id: UUID,
        offset: int = 0,
        limit: int = 30,
        folder_type: Optional[str] = None,
    ) -> list[Folder]:
        """
        获取子文件夹列表

        Args:
            folder_id: 父文件夹 ID
            offset: 偏移量
            limit: 限制数量
            folder_type: 文件夹类型过滤

        Returns:
            list[Folder]: 子文件夹列表
        """
        query = select(Folder).where(Folder.parent_id == folder_id)

        if folder_type:
            from app.models.folder_type import FolderType
            query = query.where(Folder.folder_type == FolderType(folder_type))

        result = await self.session.execute(
            query
            .offset(offset)
            .limit(limit)
            .order_by(Folder.name)
        )
        return list(result.scalars().all())
    
    async def get_with_counts(self, folder_id: UUID) -> Optional[dict]:
        """
        获取文件夹及其统计信息

        显示格式: 直接用例数(总用例数)
        - direct_cases_count: 直接在该文件夹中的用例数量
        - cases_count: 该文件夹及所有子文件夹的总用例数（递归统计）
        - sub_folders_count: 直接子文件夹数量

        Args:
            folder_id: 文件夹 ID

        Returns:
            Optional[dict]: 文件夹信息及统计
        """
        folder = await self.get_by_id(folder_id)
        if not folder:
            return None

        # 获取直接子文件夹数量
        sub_count = await self.session.execute(
            select(func.count()).select_from(Folder)
            .where(Folder.parent_id == folder_id)
        )

        # 获取直接用例数量（只在当前文件夹）
        direct_cases = await self.session.execute(
            select(func.count()).select_from(TestCase)
            .where(TestCase.folder_id == folder_id)
        )

        # 使用递归 CTE 获取总用例数（包括所有子文件夹）
        total_cases = await self._get_total_cases_count(folder_id)

        return {
            "folder": folder,
            "direct_cases_count": direct_cases.scalar_one(),
            "cases_count": total_cases,
            "sub_folders_count": sub_count.scalar_one(),
        }

    async def _get_total_cases_count(self, folder_id: UUID) -> int:
        """
        递归统计文件夹及其所有子文件夹的总用例数

        Args:
            folder_id: 文件夹 ID

        Returns:
            int: 总用例数
        """
        from sqlalchemy import literal_column, union_all
        from sqlalchemy.sql import text

        # 使用递归 CTE 查询所有子文件夹
        # PostgreSQL 递归 CTE
        recursive_cte = text("""
            WITH RECURSIVE folder_tree AS (
                SELECT id FROM folders WHERE id = :folder_id
                UNION ALL
                SELECT f.id FROM folders f
                INNER JOIN folder_tree ft ON f.parent_id = ft.id
            )
            SELECT COUNT(*) FROM test_cases WHERE folder_id IN (SELECT id FROM folder_tree)
        """)

        result = await self.session.execute(recursive_cte, {"folder_id": folder_id})
        return result.scalar_one()
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VTAweVJBPT06OGNjMmM5YjE=
    
    async def count_by_project(self, project_id: UUID, folder_type: Optional[str] = None) -> int:
        """获取项目下文件夹总数"""
        query = select(func.count()).select_from(Folder).where(Folder.project_id == project_id)

        if folder_type:
            from app.models.folder_type import FolderType
            query = query.where(Folder.folder_type == FolderType(folder_type))

        result = await self.session.execute(query)
        return result.scalar_one()
    
    async def move_folder(
        self, folder: Folder, new_parent_id: Optional[UUID]
    ) -> Folder:
        """
        移动文件夹到新位置

        Args:
            folder: 要移动的文件夹
            new_parent_id: 新的父文件夹 ID

        Returns:
            Folder: 移动后的文件夹
        """
        folder.parent_id = new_parent_id
        await self.session.flush()
        await self.session.refresh(folder)
        return folder

    async def copy_folder(
        self, folder: Folder, new_name: str
    ) -> Folder:
        """
        复制文件夹及其所有子文件夹和测试用例

        Args:
            folder: 要复制的文件夹
            new_name: 新文件夹名称

        Returns:
            Folder: 新创建的文件夹
        """
        # 创建新文件夹
        new_folder = Folder(
            name=new_name,
            description=folder.description,
            project_id=folder.project_id,
            parent_id=folder.parent_id,
        )
        self.session.add(new_folder)
        await self.session.flush()
        await self.session.refresh(new_folder)

        # 递归复制子文件夹
        await self._copy_children(folder.id, new_folder.id, folder.project_id)

        return new_folder

    async def _copy_children(
        self,
        source_parent_id: UUID,
        target_parent_id: UUID,
        project_id: UUID,
    ) -> None:
        """
        递归复制子文件夹和测试用例
        """
        # 获取源文件夹的子文件夹
        result = await self.session.execute(
            select(Folder).where(Folder.parent_id == source_parent_id)
        )
        child_folders = result.scalars().all()

        for child in child_folders:
            # 复制子文件夹
            new_child = Folder(
                name=child.name,
                description=child.description,
                project_id=project_id,
                parent_id=target_parent_id,
            )
            self.session.add(new_child)
            await self.session.flush()

            # 递归复制子文件夹的内容
            await self._copy_children(child.id, new_child.id, project_id)

        # 复制测试用例
        from app.models.test_case import TestCase, TestStep
        from app.utils.identifier import generate_test_case_identifier
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VTAweVJBPT06OGNjMmM5YjE=

        result = await self.session.execute(
            select(TestCase)
            .options(selectinload(TestCase.steps))
            .where(TestCase.folder_id == source_parent_id)
        )
        test_cases = result.scalars().all()

        for tc in test_cases:
            # 生成新标识符（使用随机数，确保唯一性）
            max_retries = 10
            new_identifier = None
            for _ in range(max_retries):
                new_identifier = generate_test_case_identifier()
                # 检查标识符是否已存在
                check_result = await self.session.execute(
                    select(func.count()).select_from(TestCase)
                    .where(TestCase.identifier == new_identifier)
                )
                if check_result.scalar_one() == 0:
                    break

            if new_identifier is None:
                # 如果无法生成唯一标识符，跳过这个测试用例
                continue

            new_tc = TestCase(
                project_id=tc.project_id,
                folder_id=target_parent_id,
                identifier=new_identifier,
                name=tc.name,
                description=tc.description,
                preconditions=tc.preconditions,
                template=tc.template,
                feature=tc.feature,
                scenario=tc.scenario,
                background=tc.background,
                priority=tc.priority,
                state=tc.state,
                test_case_type=tc.test_case_type,
                automation_status=tc.automation_status,
                owner_id=tc.owner_id,
                created_by=tc.created_by,
            )
            self.session.add(new_tc)
            await self.session.flush()

            # 复制测试步骤
            for step in tc.steps:
                new_step = TestStep(
                    test_case_id=new_tc.id,
                    step_number=step.step_number,
                    action=step.action,
                    expected_result=step.expected_result,
                )
                self.session.add(new_step)
