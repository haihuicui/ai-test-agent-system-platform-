"""
测试运行仓储

提供测试运行数据访问层
参考: https://www.browserstack.com/docs/test-management/api-reference/test-runs
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, or_, update, delete, cast, Date
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_run import TestRun, TestRunTestCase, TestRunScriptJob, TestRunSchedule
from app.models.test_case import TestCase
from app.models.test_plan import TestPlan
from app.schemas.enums import TestRunState, TestRunActiveState, TestResultStatus, ScriptType, JobStatus, ScheduleTriggerType


class TestRunRepository:
    """测试运行数据仓储"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, test_run_id: UUID) -> Optional[TestRun]:
        """根据 ID 获取测试运行"""
        stmt = select(TestRun).where(TestRun.id == test_run_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_identifier(self, identifier: str) -> Optional[TestRun]:
        """根据标识符获取测试运行"""
        stmt = select(TestRun).where(TestRun.identifier == identifier)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_relations(self, test_run_id: UUID) -> Optional[TestRun]:
        """获取测试运行并预加载关联（test_plan, sub_test_plan）"""
        stmt = (
            select(TestRun)
            .options(
                joinedload(TestRun.test_plan),
                joinedload(TestRun.sub_test_plan),
            )
            .where(TestRun.id == test_run_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_list(
        self,
        project_id: UUID,
        *,
        run_states: Optional[list[TestRunState]] = None,
        assignees: Optional[list[str]] = None,
        test_plan_id: Optional[UUID] = None,
        include_closed: bool = False,
        closed_before: Optional[date] = None,
        closed_after: Optional[date] = None,
        created_before: Optional[date] = None,
        created_after: Optional[date] = None,
        search: Optional[str] = None,
        # 旧字段，保持兼容
        active_state: Optional[TestRunActiveState] = None,
        run_state: Optional[TestRunState] = None,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[TestRun], int]:
        """
        获取测试运行列表（BS 规范）

        - run_states/assignees 是多值 OR，参数间是 AND
        - include_closed=False 时强制 active_state=ACTIVE；True 不限制
        - closed_before/after 对 closed_at 做日期比较
        - created_before/after 对 created_at 做日期比较
        """
        stmt = select(TestRun).where(TestRun.project_id == project_id)
        count_stmt = (
            select(func.count())
            .select_from(TestRun)
            .where(TestRun.project_id == project_id)
        )

        def _add(filter_clause):
            nonlocal stmt, count_stmt
            stmt = stmt.where(filter_clause)
            count_stmt = count_stmt.where(filter_clause)

        # 活跃状态
        if include_closed is False and active_state is None:
            _add(TestRun.active_state == TestRunActiveState.ACTIVE)
        elif active_state is not None:
            _add(TestRun.active_state == active_state)

        # 运行状态（多值优先；老参数 run_state 用作兜底）
        if run_states:
            _add(TestRun.run_state.in_(run_states))
        elif run_state:
            _add(TestRun.run_state == run_state)

        if assignees:
            _add(TestRun.assignee.in_(assignees))

        if test_plan_id:
            _add(
                or_(
                    TestRun.test_plan_id == test_plan_id,
                    TestRun.sub_test_plan_id == test_plan_id,
                )
            )
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkVOellnPT06ZWRjMDdkNDQ=

        if closed_before:
            _add(cast(TestRun.closed_at, Date) <= closed_before)
        if closed_after:
            _add(cast(TestRun.closed_at, Date) >= closed_after)
        if created_before:
            _add(cast(TestRun.created_at, Date) <= created_before)
        if created_after:
            _add(cast(TestRun.created_at, Date) >= created_after)

        if search:
            _add(
                or_(
                    TestRun.name.ilike(f"%{search}%"),
                    TestRun.identifier.ilike(f"%{search}%"),
                )
            )

        stmt = stmt.order_by(TestRun.created_at.desc()).offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        count_result = await self.session.execute(count_stmt)

        return list(result.scalars().all()), count_result.scalar() or 0

    async def create(self, test_run: TestRun) -> TestRun:
        """创建测试运行"""
        self.session.add(test_run)
        await self.session.flush()
        return test_run

    async def update(self, test_run: TestRun) -> TestRun:
        """更新测试运行"""
        await self.session.flush()
        await self.session.refresh(test_run)
        return test_run

    async def delete(self, test_run: TestRun) -> None:
        """删除测试运行"""
        await self.session.delete(test_run)
        await self.session.flush()

    async def generate_identifier(self, project_id: UUID) -> str:
        """生成测试运行标识符"""
        stmt = (
            select(func.count())
            .select_from(TestRun)
            .where(TestRun.project_id == project_id)
        )
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return f"TR-{count + 1}"

    async def update_counts(self, test_run_id: UUID) -> None:
        """更新测试运行的统计数据，覆盖 BS 的 7 个状态"""
        status_counts: dict[TestResultStatus, int] = {}
        for status in TestResultStatus:
            stmt = (
                select(func.count())
                .select_from(TestRunTestCase)
                .where(
                    and_(
                        TestRunTestCase.test_run_id == test_run_id,
                        TestRunTestCase.latest_status == status,
                    )
                )
            )
            result = await self.session.execute(stmt)
            status_counts[status] = result.scalar() or 0

        # NOT_EXECUTED 与 UNTESTED 合并到 untested_count
        untested = status_counts.get(
            TestResultStatus.UNTESTED, 0
        ) + status_counts.get(TestResultStatus.NOT_EXECUTED, 0)

        total = sum(status_counts.values())

        update_stmt = (
            update(TestRun)
            .where(TestRun.id == test_run_id)
            .values(
                test_cases_count=total,
                untested_count=untested,
                passed_count=status_counts.get(TestResultStatus.PASSED, 0),
                retest_count=status_counts.get(TestResultStatus.RETEST, 0),
                failed_count=status_counts.get(TestResultStatus.FAILED, 0),
                blocked_count=status_counts.get(TestResultStatus.BLOCKED, 0),
                skipped_count=status_counts.get(TestResultStatus.SKIPPED, 0),
                in_progress_count=status_counts.get(
                    TestResultStatus.IN_PROGRESS, 0
                ),
                # not_executed_count 保留同步，便于过渡期对账
                not_executed_count=status_counts.get(
                    TestResultStatus.NOT_EXECUTED, 0
                ),
            )
        )
        await self.session.execute(update_stmt)
        await self.session.flush()

    async def update_counts_from_jobs(self, test_run_id: UUID) -> None:
        """基于 ScriptJob 结果更新 TestRun 统计（script_jobs 模式）"""
        from sqlalchemy import select as sa_select

        stmt = sa_select(TestRunScriptJob).where(
            TestRunScriptJob.test_run_id == test_run_id
        )
        result = await self.session.execute(stmt)
        jobs = list(result.scalars().all())
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkVOellnPT06ZWRjMDdkNDQ=

        total = len(jobs)
        untested = 0
        passed = 0
        failed = 0
        skipped = 0
        blocked = 0
        in_progress = 0
        retest = 0

        for job in jobs:
            status = job.status
            summary = job.result_summary or {}
            has_explicit_results = bool(job.result_summary)  # True if result_summary is a non-None, non-empty dict
            if status == JobStatus.PENDING:
                untested += 1
            elif status == JobStatus.RUNNING:
                in_progress += 1
            elif status == JobStatus.COMPLETED:
                if has_explicit_results:
                    passed += summary.get("passed", 0)
                    failed += summary.get("failed", 0)
                    skipped += summary.get("skipped", 0)
                else:
                    passed += 1
            elif status == JobStatus.FAILED:
                if has_explicit_results:
                    passed += summary.get("passed", 0)
                    failed += summary.get("failed", 0)
                    skipped += summary.get("skipped", 0)
                else:
                    failed += 1
            elif status == JobStatus.SKIPPED:
                skipped += 1
            elif status == JobStatus.CANCELLED:
                blocked += 1

        update_stmt = (
            update(TestRun)
            .where(TestRun.id == test_run_id)
            .values(
                test_cases_count=total,
                untested_count=untested,
                passed_count=passed,
                retest_count=retest,
                failed_count=failed,
                blocked_count=blocked,
                skipped_count=skipped,
                in_progress_count=in_progress,
            )
        )
        await self.session.execute(update_stmt)
        await self.session.flush()

    async def get_by_test_plan_id(
        self,
        test_plan_id: UUID,
        offset: int = 0,
        limit: int = 30,
    ) -> list[TestRun]:
        """根据测试计划 ID 获取测试运行列表"""
        stmt = (
            select(TestRun)
            .where(
                or_(
                    TestRun.test_plan_id == test_plan_id,
                    TestRun.sub_test_plan_id == test_plan_id,
                )
            )
            .order_by(TestRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_test_plan_id(self, test_plan_id: UUID) -> int:
        """获取测试计划下测试运行总数"""
        stmt = (
            select(func.count())
            .select_from(TestRun)
            .where(
                or_(
                    TestRun.test_plan_id == test_plan_id,
                    TestRun.sub_test_plan_id == test_plan_id,
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0


class TestRunTestCaseRepository:
    """测试运行测试用例仓储"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: UUID) -> Optional[TestRunTestCase]:
        """根据 ID 获取关联"""
        stmt = select(TestRunTestCase).where(TestRunTestCase.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_test_run_and_case(
        self,
        test_run_id: UUID,
        test_case_id: UUID,
        configuration_id: Optional[int] = None,
    ) -> Optional[TestRunTestCase]:
        """获取特定测试运行中的测试用例"""
        conditions = [
            TestRunTestCase.test_run_id == test_run_id,
            TestRunTestCase.test_case_id == test_case_id,
        ]
        if configuration_id is not None:
            conditions.append(TestRunTestCase.configuration_id == configuration_id)
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkVOellnPT06ZWRjMDdkNDQ=

        stmt = select(TestRunTestCase).where(and_(*conditions))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_list(
        self,
        test_run_id: UUID,
        *,
        status: Optional[TestResultStatus] = None,
        assignee: Optional[str] = None,
        search: Optional[str] = None,
        with_steps: bool = False,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[TestRunTestCase], int]:
        """获取测试运行中的测试用例列表"""
        load_test_case = joinedload(TestRunTestCase.test_case)
        if with_steps:
            load_test_case = load_test_case.selectinload(TestCase.steps)

        stmt = (
            select(TestRunTestCase)
            .options(load_test_case)
            .where(TestRunTestCase.test_run_id == test_run_id)
        )
        count_stmt = (
            select(func.count())
            .select_from(TestRunTestCase)
            .where(TestRunTestCase.test_run_id == test_run_id)
        )

        if status:
            stmt = stmt.where(TestRunTestCase.latest_status == status)
            count_stmt = count_stmt.where(TestRunTestCase.latest_status == status)

        if assignee:
            stmt = stmt.where(TestRunTestCase.assignee == assignee)
            count_stmt = count_stmt.where(TestRunTestCase.assignee == assignee)

        if search:
            stmt = stmt.join(TestCase).where(
                or_(
                    TestCase.name.ilike(f"%{search}%"),
                    TestCase.identifier.ilike(f"%{search}%"),
                )
            )
            count_stmt = count_stmt.join(TestCase).where(
                or_(
                    TestCase.name.ilike(f"%{search}%"),
                    TestCase.identifier.ilike(f"%{search}%"),
                )
            )

        stmt = (
            stmt.order_by(TestRunTestCase.created_at.asc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        count_result = await self.session.execute(count_stmt)

        return (
            list(result.scalars().unique().all()),
            count_result.scalar() or 0,
        )
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkVOellnPT06ZWRjMDdkNDQ=

    async def get_all_for_run(
        self, test_run_id: UUID, *, with_steps: bool = False
    ) -> list[TestRunTestCase]:
        """获取测试运行下所有关联（用于详情内联与全量替换）"""
        load_test_case = joinedload(TestRunTestCase.test_case)
        if with_steps:
            load_test_case = load_test_case.selectinload(TestCase.steps)

        stmt = (
            select(TestRunTestCase)
            .options(load_test_case)
            .where(TestRunTestCase.test_run_id == test_run_id)
            .order_by(TestRunTestCase.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def add_test_cases(
        self,
        test_run_id: UUID,
        test_cases: list[TestRunTestCase],
    ) -> list[TestRunTestCase]:
        """批量添加测试用例到测试运行"""
        for tc in test_cases:
            self.session.add(tc)
        await self.session.flush()
        return test_cases

    async def remove_test_cases(
        self,
        test_run_id: UUID,
        test_case_ids: list[UUID],
        configuration_ids: Optional[list[int]] = None,
    ) -> int:
        """批量移除测试用例"""
        conditions = [
            TestRunTestCase.test_run_id == test_run_id,
            TestRunTestCase.test_case_id.in_(test_case_ids),
        ]
        if configuration_ids:
            conditions.append(
                TestRunTestCase.configuration_id.in_(configuration_ids)
            )

        stmt = delete(TestRunTestCase).where(and_(*conditions))
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def remove_all_for_run(self, test_run_id: UUID) -> int:
        """清空测试运行的所有关联（用于全量替换）"""
        stmt = delete(TestRunTestCase).where(
            TestRunTestCase.test_run_id == test_run_id
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def update_assignees(
        self,
        test_run_id: UUID,
        assignments: list[dict],
    ) -> int:
        """批量更新负责人"""
        count = 0
        for assignment in assignments:
            conditions = [
                TestRunTestCase.test_run_id == test_run_id,
                TestRunTestCase.test_case_id == assignment["test_case_id"],
            ]
            if assignment.get("configuration_id") is not None:
                conditions.append(
                    TestRunTestCase.configuration_id
                    == assignment["configuration_id"]
                )

            stmt = (
                update(TestRunTestCase)
                .where(and_(*conditions))
                .values(assignee=assignment["assignee"])
            )
            result = await self.session.execute(stmt)
            count += result.rowcount

        await self.session.flush()
        return count

    async def update_status(
        self,
        id: UUID,
        status: TestResultStatus,
        result_id: Optional[UUID] = None,
    ) -> TestRunTestCase:
        """更新测试用例状态"""
        stmt = (
            update(TestRunTestCase)
            .where(TestRunTestCase.id == id)
            .values(latest_status=status, latest_result_id=result_id)
            .returning(TestRunTestCase)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one()


class TestRunScriptJobRepository:
    """测试运行脚本作业仓储"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, job_id: UUID) -> Optional[TestRunScriptJob]:
        stmt = select(TestRunScriptJob).where(TestRunScriptJob.id == job_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_test_run(
        self,
        test_run_id: UUID,
        script_type: Optional[ScriptType] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[TestRunScriptJob], int]:
        stmt = select(TestRunScriptJob).where(
            TestRunScriptJob.test_run_id == test_run_id
        )
        count_stmt = (
            select(func.count())
            .select_from(TestRunScriptJob)
            .where(TestRunScriptJob.test_run_id == test_run_id)
        )

        if script_type:
            stmt = stmt.where(TestRunScriptJob.script_type == script_type)
            count_stmt = count_stmt.where(
                TestRunScriptJob.script_type == script_type
            )

        stmt = (
            stmt.order_by(TestRunScriptJob.execution_order.asc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        count_result = await self.session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    async def create(self, job: TestRunScriptJob) -> TestRunScriptJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def create_many(
        self, jobs: list[TestRunScriptJob]
    ) -> list[TestRunScriptJob]:
        for job in jobs:
            self.session.add(job)
        await self.session.flush()
        return jobs

    async def update(self, job: TestRunScriptJob) -> TestRunScriptJob:
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def update_status(
        self,
        job_id: UUID,
        status: JobStatus,
        **kwargs,
    ) -> Optional[TestRunScriptJob]:
        values = {"status": status, **kwargs}
        stmt = (
            update(TestRunScriptJob)
            .where(TestRunScriptJob.id == job_id)
            .values(**values)
            .returning(TestRunScriptJob)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def delete(self, job: TestRunScriptJob) -> None:
        await self.session.delete(job)
        await self.session.flush()

    async def delete_by_test_run(self, test_run_id: UUID) -> int:
        stmt = delete(TestRunScriptJob).where(
            TestRunScriptJob.test_run_id == test_run_id
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def get_history_by_script(
        self,
        script_type: ScriptType,
        script_id: UUID,
        limit: int = 30,
    ) -> list[TestRunScriptJob]:
        """获取同一脚本的历史执行记录（用于趋势分析和性能基准）"""
        stmt = (
            select(TestRunScriptJob)
            .where(
                TestRunScriptJob.script_type == script_type,
                TestRunScriptJob.script_id == script_id,
            )
            .order_by(TestRunScriptJob.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class TestRunScheduleRepository:
    """测试运行定时调度仓储"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, schedule_id: UUID) -> Optional[TestRunSchedule]:
        stmt = select(TestRunSchedule).where(TestRunSchedule.id == schedule_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_project(
        self,
        project_id: UUID,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[TestRunSchedule], int]:
        stmt = (
            select(TestRunSchedule)
            .where(TestRunSchedule.project_id == project_id)
            .order_by(TestRunSchedule.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = (
            select(func.count())
            .select_from(TestRunSchedule)
            .where(TestRunSchedule.project_id == project_id)
        )
        result = await self.session.execute(stmt)
        count_result = await self.session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    async def create(self, schedule: TestRunSchedule) -> TestRunSchedule:
        self.session.add(schedule)
        await self.session.flush()
        return schedule

    async def update(self, schedule: TestRunSchedule) -> TestRunSchedule:
        await self.session.flush()
        await self.session.refresh(schedule)
        return schedule

    async def delete(self, schedule: TestRunSchedule) -> None:
        await self.session.delete(schedule)
        await self.session.flush()
