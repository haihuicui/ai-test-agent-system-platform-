"""
测试计划服务

处理测试计划相关的业务逻辑
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTJsMVNBPT06YzEyYzYwZjk=

from app.models.test_plan import TestPlan
from app.repositories.test_plan_repo import TestPlanRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.test_plan import (
    TestPlanCreate,
    TestPlanUpdate,
    TestPlanInfo,
    TestPlanListInfo,
    TestPlanLinks,
    TestRunBrief,
    TestRunsCount,
)
from app.schemas.enums import TestPlanStatus, TestPlanActiveState
from app.utils.exceptions import NotFoundException
from app.utils.identifier import generate_test_plan_identifier
from app.config.settings import settings


class TestPlanService:
    """
    测试计划服务类
    
    处理测试计划相关的业务逻辑
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TestPlanRepository(session)
        self.project_repo = ProjectRepository(session)
    
    async def get_test_plans(
        self,
        project_identifier: str,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[TestPlanListInfo], int]:
        """
        获取测试计划列表
        
        Args:
            project_identifier: 项目标识符
            offset: 偏移量
            limit: 限制数量
            
        Returns:
            tuple: (测试计划列表, 总数)
        """
        project = await self.project_repo.get_by_identifier(project_identifier)
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=project_identifier)
        
        test_plans = await self.repo.get_by_project_id(project.id, offset, limit)
        total = await self.repo.count_by_project_id(project.id)
        
        result = []
        for tp in test_plans:
            counts = await self.repo.get_test_runs_count(tp.id)
            info = TestPlanListInfo(
                id=tp.id,
                identifier=tp.identifier,
                name=tp.name,
                plan_status=TestPlanStatus(tp.plan_status.value),
                active_state=TestPlanActiveState(tp.active_state.value),
                test_runs_count=TestRunsCount(active=counts["active"], closed=counts["closed"]),
                start_date=tp.start_date,
                end_date=tp.end_date,
                created_at=tp.created_at,
            )
            result.append(info)
        
        return result, total
    
    async def get_test_plan(
        self,
        project_identifier: str,
        test_plan_identifier: str,
    ) -> TestPlanInfo:
        """
        获取测试计划详情
        
        Args:
            project_identifier: 项目标识符
            test_plan_identifier: 测试计划标识符
            
        Returns:
            TestPlanInfo: 测试计划信息
        """
        project = await self.project_repo.get_by_identifier(project_identifier)
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=project_identifier)
        
        test_plan = await self.repo.get_by_identifier(test_plan_identifier)
        if not test_plan or test_plan.project_id != project.id:
            raise NotFoundException(resource_type="测试计划", resource_id=test_plan_identifier)
        
        return await self._build_test_plan_info(test_plan, project_identifier)
    
    async def _build_test_plan_info(
        self,
        test_plan: TestPlan,
        project_identifier: str,
    ) -> TestPlanInfo:
        """构建测试计划完整信息"""
        counts = await self.repo.get_test_runs_count(test_plan.id)
        
        # 构建测试运行简要信息
        test_runs_brief = []
        if test_plan.test_runs:
            for tr in test_plan.test_runs:
                test_runs_brief.append(TestRunBrief(
                    identifier=tr.identifier,
                    name=tr.name,
                ))
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTJsMVNBPT06YzEyYzYwZjk=
        
        base_url = f"{settings.api_prefix}/projects/{project_identifier}/test-plans/{test_plan.identifier}"
        
        return TestPlanInfo(
            id=test_plan.id,
            identifier=test_plan.identifier,
            name=test_plan.name,
            description=test_plan.description,
            plan_status=TestPlanStatus(test_plan.plan_status.value),
            active_state=TestPlanActiveState(test_plan.active_state.value),
            project_id=project_identifier,
            start_date=test_plan.start_date,
            end_date=test_plan.end_date,
            owner=test_plan.owner,
            test_runs_count=TestRunsCount(active=counts["active"], closed=counts["closed"]),
            tags=test_plan.tags,
            custom_fields=test_plan.custom_fields,
            test_runs=test_runs_brief if test_runs_brief else None,
            created_at=test_plan.created_at,
            updated_at=test_plan.updated_at,
            links=TestPlanLinks(
                self_link=base_url,
                test_runs=f"{base_url}/test-runs",
            ),
        )

    async def create_test_plan(
        self,
        project_identifier: str,
        data: TestPlanCreate,
    ) -> TestPlanInfo:
        """
        创建测试计划

        Args:
            project_identifier: 项目标识符
            data: 创建数据

        Returns:
            TestPlanInfo: 创建的测试计划信息
        """
        project = await self.project_repo.get_by_identifier(project_identifier)
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=project_identifier)

        # 生成标识符
        sequence = await self.repo.get_next_sequence()
        identifier = generate_test_plan_identifier(sequence)

        # 确保标识符唯一
        while await self.repo.identifier_exists(identifier):
            sequence += 1
            identifier = generate_test_plan_identifier(sequence)

        # 创建测试计划
        test_plan = await self.repo.create(
            project_id=project.id,
            identifier=identifier,
            name=data.name,
            description=data.description,
            plan_status=data.plan_status,
            active_state=TestPlanActiveState.ACTIVE,
            start_date=data.start_date,
            end_date=data.end_date,
            owner=data.owner,
            tags=data.tags,
            custom_fields=data.custom_fields,
        )

        return await self._build_test_plan_info(test_plan, project_identifier)

    async def update_test_plan(
        self,
        project_identifier: str,
        test_plan_identifier: str,
        data: TestPlanUpdate,
    ) -> TestPlanInfo:
        """
        更新测试计划

        Args:
            project_identifier: 项目标识符
            test_plan_identifier: 测试计划标识符
            data: 更新数据

        Returns:
            TestPlanInfo: 更新后的测试计划信息
        """
        project = await self.project_repo.get_by_identifier(project_identifier)
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=project_identifier)

        test_plan = await self.repo.get_by_identifier(test_plan_identifier)
        if not test_plan or test_plan.project_id != project.id:
            raise NotFoundException(resource_type="测试计划", resource_id=test_plan_identifier)

        # 更新字段
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(test_plan, field) and value is not None:
                setattr(test_plan, field, value)

        await self.session.flush()
        await self.session.refresh(test_plan)

        return await self._build_test_plan_info(test_plan, project_identifier)
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTJsMVNBPT06YzEyYzYwZjk=

    async def get_test_runs_for_plan(
        self,
        project_identifier: str,
        test_plan_identifier: str,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[TestRunBrief], int]:
        """
        获取测试计划关联的测试运行列表

        Args:
            project_identifier: 项目标识符
            test_plan_identifier: 测试计划标识符
            offset: 偏移量
            limit: 限制数量

        Returns:
            tuple: (测试运行列表, 总数)
        """
        from app.repositories.test_run_repo import TestRunRepository

        project = await self.project_repo.get_by_identifier(project_identifier)
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=project_identifier)

        test_plan = await self.repo.get_by_identifier(test_plan_identifier)
        if not test_plan or test_plan.project_id != project.id:
            raise NotFoundException(resource_type="测试计划", resource_id=test_plan_identifier)

        test_run_repo = TestRunRepository(self.session)
        test_runs = await test_run_repo.get_by_test_plan_id(test_plan.id, offset, limit)
        total = await test_run_repo.count_by_test_plan_id(test_plan.id)

        result = [
            TestRunBrief(identifier=tr.identifier, name=tr.name)
            for tr in test_runs
        ]

        return result, total

    async def get_test_runs(
        self,
        project_identifier: str,
        test_plan_identifier: str,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[TestRunBrief], int]:
        """
        获取测试计划关联的测试运行列表（别名方法）
        """
        return await self.get_test_runs_for_plan(
            project_identifier, test_plan_identifier, offset, limit
        )

    async def close_test_plan(
        self,
        project_identifier: str,
        test_plan_identifier: str,
    ) -> TestPlanInfo:
        """
        关闭测试计划

        Args:
            project_identifier: 项目标识符
            test_plan_identifier: 测试计划标识符

        Returns:
            TestPlanInfo: 更新后的测试计划信息
        """
        project = await self.project_repo.get_by_identifier(project_identifier)
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=project_identifier)

        test_plan = await self.repo.get_by_identifier(test_plan_identifier)
        if not test_plan or test_plan.project_id != project.id:
            raise NotFoundException(resource_type="测试计划", resource_id=test_plan_identifier)

        # 更新活跃状态为关闭
        test_plan.active_state = TestPlanActiveState.CLOSED
        await self.session.flush()

        return await self._build_test_plan_info(test_plan, project_identifier)
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTJsMVNBPT06YzEyYzYwZjk=

    async def delete_test_plan(
        self,
        project_identifier: str,
        test_plan_identifier: str,
    ) -> None:
        """
        删除测试计划

        Args:
            project_identifier: 项目标识符
            test_plan_identifier: 测试计划标识符
        """
        project = await self.project_repo.get_by_identifier(project_identifier)
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=project_identifier)

        test_plan = await self.repo.get_by_identifier(test_plan_identifier)
        if not test_plan or test_plan.project_id != project.id:
            raise NotFoundException(resource_type="测试计划", resource_id=test_plan_identifier)

        await self.repo.delete(test_plan)
