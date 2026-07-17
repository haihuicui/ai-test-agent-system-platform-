"""
场景测试业务逻辑服务
"""

from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0doM09BPT06NDNmN2JhNDc=

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.test_scenario import (
    TestScenario,
    ScenarioStep,
    StepDataMapping,
    ScenarioRun,
    ScenarioStepResult,
)
from app.models.api_endpoint import APIEndpoint
from app.schemas.scenario import (
    ScenarioCreate,
    ScenarioUpdate,
    ScenarioStepCreate,
    ScenarioStepUpdate,
    DataMappingCreate,
)


class ScenarioService:
    """场景测试服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== 场景 CRUD ====================

    async def list_scenarios(
        self,
        project_id: UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """列出场景"""
        # 构建查询
        query = select(TestScenario).where(TestScenario.project_id == project_id)

        if status:
            query = query.where(TestScenario.status == status)

        # 查询总数
        count_query = select(func.count()).select_from(
            select(TestScenario).where(TestScenario.project_id == project_id)
        )
        if status:
            count_query = select(func.count()).select_from(
                select(TestScenario).where(
                    TestScenario.project_id == project_id,
                    TestScenario.status == status
                )
            )

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        # 分页查询
        query = query.order_by(TestScenario.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        scenarios = result.scalars().all()

        return {
            "total": total,
            "items": scenarios,
        }

    async def get_scenario(self, scenario_id: UUID) -> Optional[TestScenario]:
        """获取场景详情"""
        query = select(TestScenario).where(TestScenario.id == scenario_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_scenario_by_identifier(
        self,
        project_id: UUID,
        identifier: str
    ) -> Optional[TestScenario]:
        """通过标识符获取场景"""
        query = select(TestScenario).where(
            TestScenario.project_id == project_id,
            TestScenario.identifier == identifier
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_scenario(
        self,
        project_id: UUID,
        scenario_in: ScenarioCreate,
        created_by: UUID,
    ) -> TestScenario:
        """创建场景"""
        # 生成标识符：使用 MAX(identifier) + 1 而非 COUNT(*) + 1，
        # 避免因删除/间隙导致标识符冲突（如 TS-0004 已存在时 COUNT 无法感知）
        max_query = select(func.max(TestScenario.identifier)).where(
            TestScenario.project_id == project_id
        )
        max_result = await self.db.execute(max_query)
        max_identifier = max_result.scalar()
        if max_identifier and max_identifier.startswith("TS-"):
            try:
                max_number = int(max_identifier.split("-")[1])
            except (ValueError, IndexError):
                max_number = 0
        else:
            max_number = 0
        identifier = f"TS-{max_number + 1:04d}"

        scenario = TestScenario(
            id=uuid4(),
            project_id=project_id,
            folder_id=scenario_in.folder_id,
            identifier=identifier,
            name=scenario_in.name,
            description=scenario_in.description,
            global_variables=scenario_in.global_variables,
            retry_count=scenario_in.retry_count,
            timeout_seconds=scenario_in.timeout_seconds,
            parallel_execution=scenario_in.parallel_execution,
            status="draft",
            created_by=created_by,
        )
        self.db.add(scenario)
        await self.db.commit()
        await self.db.refresh(scenario)
        return scenario

    async def update_scenario(
        self,
        scenario_id: UUID,
        scenario_in: ScenarioUpdate,
    ) -> Optional[TestScenario]:
        """更新场景"""
        scenario = await self.get_scenario(scenario_id)
        if not scenario:
            return None

        update_data = scenario_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(scenario, field, value)

        await self.db.commit()
        await self.db.refresh(scenario)
        return scenario

    async def delete_scenario(self, scenario_id: UUID) -> bool:
        """删除场景"""
        scenario = await self.get_scenario(scenario_id)
        if not scenario:
            return False

        await self.db.delete(scenario)
        await self.db.commit()
        return True

    # ==================== 步骤管理 ====================

    async def list_steps(self, scenario_id: UUID) -> List[ScenarioStep]:
        """列出步骤"""
        query = select(ScenarioStep).where(
            ScenarioStep.scenario_id == scenario_id
        ).order_by(ScenarioStep.step_order).options(
            selectinload(ScenarioStep.data_mappings)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_step(self, step_id: UUID) -> Optional[ScenarioStep]:
        """获取单个步骤"""
        query = select(ScenarioStep).where(ScenarioStep.id == step_id).options(
            selectinload(ScenarioStep.data_mappings)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def add_step(
        self,
        scenario_id: UUID,
        step_in: ScenarioStepCreate,
    ) -> ScenarioStep:
        """添加步骤"""
        # 确定步骤顺序
        if step_in.step_order is None:
            existing_steps = await self.list_steps(scenario_id)
            step_order = len(existing_steps) + 1
        else:
            step_order = step_in.step_order
            # 如果指定了 step_order，也需要查询现有步骤数量用于更新 total_steps
            existing_steps = await self.list_steps(scenario_id)

        step = ScenarioStep(
            id=uuid4(),
            scenario_id=scenario_id,
            endpoint_id=step_in.endpoint_id,
            step_order=step_order,
            name=step_in.name,
            description=step_in.description,
            request_override=step_in.request_override,
            headers_override=step_in.headers_override,
            extractors=[e.model_dump() for e in step_in.extractors],
            assertions=[a.model_dump() for a in step_in.assertions],
            condition_expression=step_in.condition_expression,
            continue_on_failure=step_in.continue_on_failure,
            delay_ms=step_in.delay_ms,
            retry_count=step_in.retry_count,
        )
        self.db.add(step)

        # 更新场景的步骤总数（直接使用现有步骤数量+1，避免再次查询）
        scenario = await self.get_scenario(scenario_id)
        if scenario:
            scenario.total_steps = len(existing_steps) + 1
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0doM09BPT06NDNmN2JhNDc=

        await self.db.commit()
        await self.db.refresh(step, attribute_names=["data_mappings"])
        return step

    async def update_step(
        self,
        scenario_id: UUID,
        step_id: UUID,
        step_in: ScenarioStepUpdate,
    ) -> Optional[ScenarioStep]:
        """更新步骤"""
        query = select(ScenarioStep).where(
            ScenarioStep.id == step_id,
            ScenarioStep.scenario_id == scenario_id,
        ).options(
            selectinload(ScenarioStep.data_mappings)
        )
        result = await self.db.execute(query)
        step = result.scalar_one_or_none()
        if not step:
            return None

        update_data = step_in.model_dump(exclude_unset=True)

        # 处理 extractors 和 assertions
        if "extractors" in update_data:
            update_data["extractors"] = [e.model_dump() for e in step_in.extractors]
        if "assertions" in update_data:
            update_data["assertions"] = [a.model_dump() for a in step_in.assertions]

        for field, value in update_data.items():
            setattr(step, field, value)

        await self.db.commit()
        await self.db.refresh(step)
        return step

    async def delete_step(self, scenario_id: UUID, step_id: UUID) -> bool:
        """删除步骤"""
        from sqlalchemy import delete, update

        query = select(ScenarioStep).where(
            ScenarioStep.id == step_id,
            ScenarioStep.scenario_id == scenario_id,
        )
        result = await self.db.execute(query)
        step = result.scalar_one_or_none()
        if not step:
            return False

        # 先手动删除相关的步骤结果记录（避免 SQLAlchemy 尝试设置 NULL）
        await self.db.execute(
            delete(ScenarioStepResult).where(ScenarioStepResult.step_id == step_id)
        )
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0doM09BPT06NDNmN2JhNDc=

        # 删除步骤
        await self.db.delete(step)
        await self.db.commit()

        # 重新排序剩余步骤（使用两阶段更新避免唯一约束冲突）
        remaining_steps = await self.list_steps(scenario_id)

        if remaining_steps:
            # 第一步：将所有步骤设置为临时顺序（负数），避免唯一约束冲突
            temp_offset = 10000
            for idx, remaining_step in enumerate(remaining_steps):
                await self.db.execute(
                    update(ScenarioStep)
                    .where(ScenarioStep.id == remaining_step.id)
                    .values(step_order=temp_offset + idx)
                )
            await self.db.commit()

            # 第二步：更新为正确的顺序
            for idx, remaining_step in enumerate(remaining_steps, 1):
                await self.db.execute(
                    update(ScenarioStep)
                    .where(ScenarioStep.id == remaining_step.id)
                    .values(step_order=idx)
                )
            await self.db.commit()

        # 更新场景的步骤总数
        scenario = await self.get_scenario(scenario_id)
        if scenario:
            scenario.total_steps = len(remaining_steps)
            await self.db.commit()

        return True

    async def reorder_steps(
        self,
        scenario_id: UUID,
        step_orders: Dict[UUID, int],
    ):
        """重新排序步骤"""
        # 第一步：将所有受影响的步骤设置为临时顺序（负数），避免唯一约束冲突
        temp_offset = 10000
        for step_id in step_orders.keys():
            query = select(ScenarioStep).where(
                ScenarioStep.id == step_id,
                ScenarioStep.scenario_id == scenario_id,
            )
            result = await self.db.execute(query)
            step = result.scalar_one_or_none()
            if step:
                step.step_order = temp_offset
                temp_offset += 1

        await self.db.commit()

        # 第二步：更新为正确的顺序
        for step_id, new_order in step_orders.items():
            query = select(ScenarioStep).where(
                ScenarioStep.id == step_id,
                ScenarioStep.scenario_id == scenario_id,
            )
            result = await self.db.execute(query)
            step = result.scalar_one_or_none()
            if step:
                step.step_order = new_order

        await self.db.commit()

    # ==================== 数据映射 ====================

    async def add_data_mapping(
        self,
        step_id: UUID,
        mapping_in: DataMappingCreate,
    ) -> StepDataMapping:
        """添加数据映射"""
        mapping = StepDataMapping(
            id=uuid4(),
            step_id=step_id,
            source_type=mapping_in.source_type,
            source_step_id=mapping_in.source_step_id,
            source_path=mapping_in.source_path,
            target_path=mapping_in.target_path,
            transform_expression=mapping_in.transform_expression,
            description=mapping_in.description,
        )
        self.db.add(mapping)
        await self.db.commit()
        await self.db.refresh(mapping)
        return mapping

    async def delete_data_mapping(self, mapping_id: UUID):
        """删除数据映射"""
        query = select(StepDataMapping).where(StepDataMapping.id == mapping_id)
        result = await self.db.execute(query)
        mapping = result.scalar_one_or_none()
        if mapping:
            await self.db.delete(mapping)
            await self.db.commit()

    # ==================== 场景执行 ====================

    async def execute_scenario(
        self,
        scenario_id: UUID,
        variables: Dict[str, Any],
        base_url: str,
        executed_by: Optional[UUID],
        env_id: Optional[UUID] = None,
    ) -> ScenarioRun:
        """执行场景"""
        from app.services.scenario_execution_engine import ScenarioExecutionEngine

        # 提前加载场景以获取 project_id
        scenario = await self.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"场景 {scenario_id} 不存在")

        engine = ScenarioExecutionEngine(self.db)
        run = await engine.execute(
            scenario_id=scenario_id,
            variables=variables,
            base_url=base_url,
            project_id=scenario.project_id,
            env_id=env_id,
        )
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0doM09BPT06NDNmN2JhNDc=

        # 更新执行者
        run.executed_by = executed_by
        await self.db.commit()
        await self.db.refresh(run)

        return run

    async def execute_scenario_async(
        self,
        scenario_id: UUID,
        variables: Dict[str, Any],
        base_url: str,
        executed_by: Optional[UUID],
        env_id: Optional[UUID] = None,
    ) -> UUID:
        """异步执行场景（使用后台任务）"""
        # TODO: 集成 Celery 或 FastAPI BackgroundTasks
        # 暂时使用同步执行
        run = await self.execute_scenario(
            scenario_id=scenario_id,
            variables=variables,
            base_url=base_url,
            executed_by=executed_by,
            env_id=env_id,
        )
        return run.id

    # ==================== 执行记录查询 ====================

    async def list_runs(
        self,
        scenario_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> List[ScenarioRun]:
        """列出执行记录"""
        query = select(ScenarioRun).where(
            ScenarioRun.scenario_id == scenario_id
        ).order_by(ScenarioRun.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_run(self, run_id: UUID) -> Optional[ScenarioRun]:
        """获取执行记录"""
        query = select(ScenarioRun).where(ScenarioRun.id == run_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_step_results(self, run_id: UUID) -> List[ScenarioStepResult]:
        """获取步骤结果"""
        query = select(ScenarioStepResult).where(
            ScenarioStepResult.run_id == run_id
        ).order_by(ScenarioStepResult.step_order)
        result = await self.db.execute(query)
        return list(result.scalars().all())
