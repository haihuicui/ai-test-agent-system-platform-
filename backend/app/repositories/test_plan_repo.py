"""
测试计划仓储

处理测试计划相关的数据库操作
"""

from typing import Optional
from uuid import UUID
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDFCeE13PT06YmUzMDdhODY=

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.repositories.base import BaseRepository
from app.models.test_plan import TestPlan
from app.models.test_run import TestRun
from ..models.project import Project


class TestPlanRepository(BaseRepository[TestPlan]):
    """
    测试计划仓储类
    
    提供测试计划相关的数据库操作
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(TestPlan, session)
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDFCeE13PT06YmUzMDdhODY=
    
    async def get_by_identifier(self, identifier: str) -> Optional[TestPlan]:
        """
        根据标识符获取测试计划
        
        Args:
            identifier: 测试计划标识符，如 TP-123
            
        Returns:
            Optional[TestPlan]: 测试计划实例或 None
        """
        result = await self.session.execute(
            select(TestPlan)
            .options(selectinload(TestPlan.project))
            .options(selectinload(TestPlan.test_runs))
            .where(TestPlan.identifier == identifier)
        )
        return result.scalar_one_or_none()
    
    async def get_by_project_id(
        self,
        project_id: UUID,
        offset: int = 0,
        limit: int = 30,
    ) -> list[TestPlan]:
        """
        根据项目 ID 获取测试计划列表
        
        Args:
            project_id: 项目 ID
            offset: 偏移量
            limit: 限制数量
            
        Returns:
            list[TestPlan]: 测试计划列表
        """
        result = await self.session.execute(
            select(TestPlan)
            .options(selectinload(TestPlan.test_runs))
            .where(TestPlan.project_id == project_id)
            .offset(offset)
            .limit(limit)
            .order_by(TestPlan.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def count_by_project_id(self, project_id: UUID) -> int:
        """
        获取项目下测试计划总数
        
        Args:
            project_id: 项目 ID
            
        Returns:
            int: 测试计划总数
        """
        result = await self.session.execute(
            select(func.count()).select_from(TestPlan)
            .where(TestPlan.project_id == project_id)
        )
        return result.scalar_one()
    
    async def get_next_sequence(self) -> int:
        """
        获取下一个测试计划序号
        
        Returns:
            int: 下一个序号
        """
        result = await self.session.execute(
            select(func.count()).select_from(TestPlan)
        )
        count = result.scalar_one()
        return count + 1
    
    async def identifier_exists(self, identifier: str) -> bool:
        """
        检查标识符是否已存在
        
        Args:
            identifier: 测试计划标识符
            
        Returns:
            bool: 是否存在
        """
        result = await self.session.execute(
            select(func.count()).select_from(TestPlan)
            .where(TestPlan.identifier == identifier)
        )
        return result.scalar_one() > 0
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDFCeE13PT06YmUzMDdhODY=
    
    async def get_test_runs_count(self, test_plan_id: UUID) -> dict:
        """
        获取测试计划下测试运行的状态计数
        
        Args:
            test_plan_id: 测试计划 ID
            
        Returns:
            dict: {"active": int, "closed": int}
        """
        from ..schemas.enums import TestRunActiveState
        
        active_result = await self.session.execute(
            select(func.count()).select_from(TestRun)
            .where(TestRun.test_plan_id == test_plan_id)
            .where(TestRun.active_state == TestRunActiveState.ACTIVE)
        )
        closed_result = await self.session.execute(
            select(func.count()).select_from(TestRun)
            .where(TestRun.test_plan_id == test_plan_id)
            .where(TestRun.active_state == TestRunActiveState.CLOSED)
        )
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VDFCeE13PT06YmUzMDdhODY=
        
        return {
            "active": active_result.scalar_one(),
            "closed": closed_result.scalar_one()
        }

