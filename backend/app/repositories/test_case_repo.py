"""
测试用例仓储

处理测试用例相关的数据库操作
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.repositories.base import BaseRepository
from app.models.test_case import TestCase, TestStep, Tag, TestCaseTag


class TestCaseRepository(BaseRepository[TestCase]):
    """
    测试用例仓储类
    
    提供测试用例相关的数据库操作
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(TestCase, session)
    
    async def get_by_identifier(self, identifier: str) -> Optional[TestCase]:
        """
        根据标识符或 UUID 获取测试用例

        Args:
            identifier: 测试用例标识符 (TC-xxx) 或 UUID

        Returns:
            Optional[TestCase]: 测试用例实例或 None
        """
        # 尝试解析为 UUID
        try:
            uuid_val = UUID(identifier)
            result = await self.session.execute(
                select(TestCase)
                .options(selectinload(TestCase.steps))
                .options(selectinload(TestCase.tags))
                .where(TestCase.id == uuid_val)
            )
            tc = result.scalar_one_or_none()
            if tc:
                return tc
        except (ValueError, AttributeError):
            pass

        # 按标识符查询
        result = await self.session.execute(
            select(TestCase)
            .options(selectinload(TestCase.steps))
            .options(selectinload(TestCase.tags))
            .where(TestCase.identifier == identifier)
        )
        return result.scalar_one_or_none()
    
    async def get_by_id_with_relations(self, id: UUID) -> Optional[TestCase]:
        """根据 ID 获取测试用例（包含关联数据）"""
        result = await self.session.execute(
            select(TestCase)
            .options(selectinload(TestCase.steps))
            .options(selectinload(TestCase.tags))
            .options(selectinload(TestCase.owner))
            .options(selectinload(TestCase.creator))
            .where(TestCase.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_project(
        self,
        project_id: UUID,
        offset: int = 0,
        limit: int = 30,
        folder_id: Optional[UUID] = None,
        updated_after: Optional[datetime] = None,
        updated_before: Optional[datetime] = None,
    ) -> list[TestCase]:
        """
        获取项目下的测试用例列表
        
        Args:
            project_id: 项目 ID
            offset: 偏移量
            limit: 限制数量
            folder_id: 文件夹 ID（可选）
            updated_after: 更新时间晚于（可选）
            updated_before: 更新时间早于（可选）
            
        Returns:
            list[TestCase]: 测试用例列表
        """
        query = (
            select(TestCase)
            .options(selectinload(TestCase.steps))
            .options(selectinload(TestCase.tags))
            .where(TestCase.project_id == project_id)
        )
        
        if folder_id:
            query = query.where(TestCase.folder_id == folder_id)
        
        if updated_after:
            query = query.where(TestCase.updated_at >= updated_after)
        
        if updated_before:
            query = query.where(TestCase.updated_at <= updated_before)
        
        query = query.offset(offset).limit(limit).order_by(TestCase.created_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkV0ek9RPT06ZDVmZTNlZTA=
    
    async def count_by_project(
        self,
        project_id: UUID,
        folder_id: Optional[UUID] = None,
    ) -> int:
        """获取项目下测试用例总数"""
        query = (
            select(func.count())
            .select_from(TestCase)
            .where(TestCase.project_id == project_id)
        )
        if folder_id:
            query = query.where(TestCase.folder_id == folder_id)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_by_project_with_filters(
        self,
        project_id: UUID,
        offset: int = 0,
        limit: int = 30,
        test_case_ids: Optional[list[str]] = None,
        folder_ids: Optional[list[str]] = None,
        statuses: Optional[list[str]] = None,
        priorities: Optional[list[str]] = None,
        case_types: Optional[list[str]] = None,
        owners: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        issue_ids: Optional[list[str]] = None,
        issue_type: Optional[str] = None,
        custom_fields: Optional[dict[str, list[str]]] = None,
        updated_after: Optional[datetime] = None,
        updated_before: Optional[datetime] = None,
        search: Optional[str] = None,
    ) -> list[TestCase]:
        """
        获取项目下的测试用例列表（支持高级过滤）

        同一参数内的多个值为 OR 关系，不同参数之间为 AND 关系
        """
        from ..models.user import User

        query = (
            select(TestCase)
            .options(selectinload(TestCase.steps))
            .options(selectinload(TestCase.tags))
            .options(selectinload(TestCase.owner))
            .options(selectinload(TestCase.creator))
            .where(TestCase.project_id == project_id)
        )

        # 按测试用例 ID 过滤
        if test_case_ids:
            query = query.where(TestCase.identifier.in_(test_case_ids))

        # 按文件夹过滤
        if folder_ids:
            folder_uuids = [UUID(fid) for fid in folder_ids]
            query = query.where(TestCase.folder_id.in_(folder_uuids))

        # 按状态过滤
        if statuses:
            query = query.where(TestCase.state.in_(statuses))

        # 按优先级过滤
        if priorities:
            query = query.where(TestCase.priority.in_(priorities))

        # 按类型过滤
        if case_types:
            query = query.where(TestCase.test_case_type.in_(case_types))

        # 按负责人过滤
        if owners:
            query = query.join(User, TestCase.owner_id == User.id)
            query = query.where(User.email.in_(owners))

        # 按标签过滤
        if tags:
            query = query.join(TestCase.tags).where(Tag.name.in_(tags))

        # 按 issue_ids 过滤（JSONB 数组包含）
        if issue_ids:
            from sqlalchemy import or_
            issue_conditions = []
            for issue_id in issue_ids:
                issue_conditions.append(
                    TestCase.issues.contains([{"id": issue_id}])
                )
            query = query.where(or_(*issue_conditions))

        # 按 issue_type 过滤
        if issue_type:
            query = query.where(
                TestCase.issues.contains([{"type": issue_type}])
            )

        # 按自定义字段过滤
        if custom_fields:
            for field_name, field_values in custom_fields.items():
                from sqlalchemy import or_
                cf_conditions = []
                for val in field_values:
                    cf_conditions.append(
                        TestCase.custom_fields[field_name].astext == val
                    )
                if cf_conditions:
                    query = query.where(or_(*cf_conditions))

        # 关键字搜索
        if search and search.strip():
            from sqlalchemy import or_
            search_term = (
                f"%{search.strip().replace('%', r'\%').replace('_', r'\_')}%"
            )
            query = query.where(
                or_(
                    TestCase.name.ilike(search_term, escape="\\"),
                    TestCase.identifier.ilike(search_term, escape="\\"),
                    TestCase.case_number.ilike(search_term, escape="\\"),
                    TestCase.module.ilike(search_term, escape="\\"),
                    TestCase.description.ilike(search_term, escape="\\"),
                )
            )

        # 时间过滤
        if updated_after:
            query = query.where(TestCase.updated_at >= updated_after)
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkV0ek9RPT06ZDVmZTNlZTA=

        if updated_before:
            query = query.where(TestCase.updated_at <= updated_before)

        query = query.offset(offset).limit(limit).order_by(TestCase.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().unique().all())

    async def count_by_project_with_filters(
        self,
        project_id: UUID,
        test_case_ids: Optional[list[str]] = None,
        folder_ids: Optional[list[str]] = None,
        statuses: Optional[list[str]] = None,
        priorities: Optional[list[str]] = None,
        case_types: Optional[list[str]] = None,
        owners: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        issue_ids: Optional[list[str]] = None,
        issue_type: Optional[str] = None,
        custom_fields: Optional[dict[str, list[str]]] = None,
        updated_after: Optional[datetime] = None,
        updated_before: Optional[datetime] = None,
        search: Optional[str] = None,
    ) -> int:
        """获取项目下测试用例总数（支持高级过滤）"""
        from ..models.user import User

        query = (
            select(func.count(func.distinct(TestCase.id)))
            .select_from(TestCase)
            .where(TestCase.project_id == project_id)
        )

        if test_case_ids:
            query = query.where(TestCase.identifier.in_(test_case_ids))

        if folder_ids:
            folder_uuids = [UUID(fid) for fid in folder_ids]
            query = query.where(TestCase.folder_id.in_(folder_uuids))

        if statuses:
            query = query.where(TestCase.state.in_(statuses))

        if priorities:
            query = query.where(TestCase.priority.in_(priorities))

        if case_types:
            query = query.where(TestCase.test_case_type.in_(case_types))

        if owners:
            query = query.join(User, TestCase.owner_id == User.id)
            query = query.where(User.email.in_(owners))

        if tags:
            query = query.join(TestCase.tags).where(Tag.name.in_(tags))

        if issue_ids:
            from sqlalchemy import or_
            issue_conditions = []
            for issue_id in issue_ids:
                issue_conditions.append(
                    TestCase.issues.contains([{"id": issue_id}])
                )
            query = query.where(or_(*issue_conditions))

        if issue_type:
            query = query.where(
                TestCase.issues.contains([{"type": issue_type}])
            )

        if custom_fields:
            for field_name, field_values in custom_fields.items():
                from sqlalchemy import or_
                cf_conditions = []
                for val in field_values:
                    cf_conditions.append(
                        TestCase.custom_fields[field_name].astext == val
                    )
                if cf_conditions:
                    query = query.where(or_(*cf_conditions))

        # 关键字搜索
        if search and search.strip():
            from sqlalchemy import or_
            search_term = (
                f"%{search.strip().replace('%', r'\%').replace('_', r'\_')}%"
            )
            query = query.where(
                or_(
                    TestCase.name.ilike(search_term, escape="\\"),
                    TestCase.identifier.ilike(search_term, escape="\\"),
                    TestCase.case_number.ilike(search_term, escape="\\"),
                    TestCase.module.ilike(search_term, escape="\\"),
                    TestCase.description.ilike(search_term, escape="\\"),
                )
            )

        if updated_after:
            query = query.where(TestCase.updated_at >= updated_after)
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkV0ek9RPT06ZDVmZTNlZTA=

        if updated_before:
            query = query.where(TestCase.updated_at <= updated_before)
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkV0ek9RPT06ZDVmZTNlZTA=

        result = await self.session.execute(query)
        return result.scalar_one()
    
    async def get_next_sequence(self, project_id: UUID) -> int:
        """获取下一个测试用例序号（已废弃，保留以兼容旧代码）"""
        result = await self.session.execute(
            select(func.count()).select_from(TestCase)
            .where(TestCase.project_id == project_id)
        )
        count = result.scalar_one()
        return count + 1

    async def identifier_exists(self, identifier: str) -> bool:
        """
        检查标识符是否已存在

        Args:
            identifier: 测试用例标识符

        Returns:
            bool: 是否存在
        """
        result = await self.session.execute(
            select(func.count()).select_from(TestCase)
            .where(TestCase.identifier == identifier)
        )
        return result.scalar_one() > 0
    
    async def add_step(
        self,
        test_case_id: UUID,
        step_number: int,
        action: str,
        expected_result: Optional[str] = None,
    ) -> TestStep:
        """添加测试步骤"""
        step = TestStep(
            test_case_id=test_case_id,
            step_number=step_number,
            action=action,
            expected_result=expected_result,
        )
        self.session.add(step)
        await self.session.flush()
        await self.session.refresh(step)
        return step
    
    async def get_or_create_tag(
        self, project_id: UUID, name: str
    ) -> Tag:
        """获取或创建标签"""
        result = await self.session.execute(
            select(Tag).where(
                and_(Tag.project_id == project_id, Tag.name == name)
            )
        )
        tag = result.scalar_one_or_none()

        if not tag:
            tag = Tag(project_id=project_id, name=name)
            self.session.add(tag)
            await self.session.flush()
            await self.session.refresh(tag)

        return tag

    async def add_tag_to_test_case(
        self, test_case_id: UUID, tag: Tag
    ) -> None:
        """添加标签到测试用例（通过中间表）"""
        from app.models.test_case import TestCaseTag

        # 检查关系是否已存在
        result = await self.session.execute(
            select(TestCaseTag).where(
                and_(
                    TestCaseTag.test_case_id == test_case_id,
                    TestCaseTag.tag_id == tag.id
                )
            )
        )
        existing = result.scalar_one_or_none()

        if not existing:
            # 创建新的关联
            test_case_tag = TestCaseTag(
                test_case_id=test_case_id,
                tag_id=tag.id
            )
            self.session.add(test_case_tag)
            await self.session.flush()

    async def remove_tag_from_test_case(
        self, test_case_id: UUID, tag_id: UUID
    ) -> None:
        """从测试用例中移除标签"""
        from app.models.test_case import TestCaseTag

        await self.session.execute(
            delete(TestCaseTag).where(
                and_(
                    TestCaseTag.test_case_id == test_case_id,
                    TestCaseTag.tag_id == tag_id
                )
            )
        )
        await self.session.flush()

    async def clear_test_case_tags(self, test_case_id: UUID) -> None:
        """清除测试用例的所有标签"""
        from app.models.test_case import TestCaseTag

        await self.session.execute(
            delete(TestCaseTag).where(
                TestCaseTag.test_case_id == test_case_id
            )
        )
        await self.session.flush()

    async def get_test_case_tags(self, test_case_id: UUID) -> list[Tag]:
        """获取测试用例的所有标签"""
        result = await self.session.execute(
            select(Tag)
            .join(TestCaseTag, TestCaseTag.tag_id == Tag.id)
            .where(TestCaseTag.test_case_id == test_case_id)
        )
        return list(result.scalars().all())

