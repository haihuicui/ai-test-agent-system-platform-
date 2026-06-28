"""
测试结果仓储

提供测试结果数据访问层
参考: https://www.browserstack.com/docs/test-management/api-reference/test-results
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_result import TestResult, TestStepResult
from app.models.test_case import TestCase
from app.schemas.enums import TestResultStatus


class TestResultRepository:
    """测试结果数据仓储"""
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0VWSlp3PT06ODJmMTQ3MmE=
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, result_id: UUID) -> Optional[TestResult]:
        """根据 ID 获取测试结果"""
        stmt = (
            select(TestResult)
            .options(selectinload(TestResult.step_results))
            .where(TestResult.id == result_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0VWSlp3PT06ODJmMTQ3MmE=
    
    async def get_list(
        self,
        test_run_id: UUID,
        test_case_id: Optional[UUID] = None,
        status: Optional[TestResultStatus] = None,
        configuration_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[TestResult], int]:
        """获取测试结果列表"""
        conditions = [TestResult.test_run_id == test_run_id]
        
        if test_case_id:
            conditions.append(TestResult.test_case_id == test_case_id)
        if status:
            conditions.append(TestResult.status == status)
        if configuration_id is not None:
            conditions.append(TestResult.configuration_id == configuration_id)
        
        stmt = (
            select(TestResult)
            .options(joinedload(TestResult.test_case))
            .where(and_(*conditions))
            .order_by(TestResult.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        
        count_stmt = (
            select(func.count())
            .select_from(TestResult)
            .where(and_(*conditions))
        )
        
        result = await self.session.execute(stmt)
        count_result = await self.session.execute(count_stmt)
        
        return list(result.scalars().unique().all()), count_result.scalar() or 0
    
    async def get_history(
        self,
        test_run_id: UUID,
        test_case_id: UUID,
        configuration_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[TestResult], int]:
        """获取测试用例在测试运行中的历史结果"""
        conditions = [
            TestResult.test_run_id == test_run_id,
            TestResult.test_case_id == test_case_id,
        ]
        if configuration_id is not None:
            conditions.append(TestResult.configuration_id == configuration_id)
        
        stmt = (
            select(TestResult)
            .where(and_(*conditions))
            .order_by(TestResult.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0VWSlp3PT06ODJmMTQ3MmE=
        
        count_stmt = (
            select(func.count())
            .select_from(TestResult)
            .where(and_(*conditions))
        )
        
        result = await self.session.execute(stmt)
        count_result = await self.session.execute(count_stmt)
        
        return list(result.scalars().all()), count_result.scalar() or 0
    
    async def get_latest(
        self,
        test_run_id: UUID,
        test_case_id: UUID,
        configuration_id: Optional[int] = None,
    ) -> Optional[TestResult]:
        """获取最新的测试结果"""
        conditions = [
            TestResult.test_run_id == test_run_id,
            TestResult.test_case_id == test_case_id,
        ]
        if configuration_id is not None:
            conditions.append(TestResult.configuration_id == configuration_id)
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0VWSlp3PT06ODJmMTQ3MmE=
        
        stmt = (
            select(TestResult)
            .options(selectinload(TestResult.step_results))
            .where(and_(*conditions))
            .order_by(TestResult.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def create(self, test_result: TestResult) -> TestResult:
        """创建测试结果"""
        self.session.add(test_result)
        await self.session.flush()
        return test_result
    
    async def create_bulk(self, test_results: list[TestResult]) -> list[TestResult]:
        """批量创建测试结果"""
        for tr in test_results:
            self.session.add(tr)
        await self.session.flush()
        return test_results
    
    async def delete(self, test_result: TestResult) -> None:
        """删除测试结果"""
        await self.session.delete(test_result)
        await self.session.flush()

