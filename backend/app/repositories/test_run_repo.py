"""
测试运行仓储

提供测试运行数据访问层
参考: https://www.browserstack.com/docs/test-management/api-reference/test-runs
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, or_, update, delete, cast, Date, Integer
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_run import TestRun, TestRunTestCase, TestRunScriptJob, TestRunSchedule, TestRunExecutionSnapshot, TestRunExecutionSnapshotJob
from app.models.test_case import TestCase
from app.models.test_plan import TestPlan
from app.schemas.enums import TestRunState, TestRunActiveState, TestResultStatus, ScriptType, JobStatus, ScheduleTriggerType


def _aggregate_progress_from_jobs(jobs: list[TestRunScriptJob]) -> dict[str, int]:
    """根据 ScriptJob 列表聚合 TestRun 进度统计（纯函数，便于测试）。

    返回的计数字典保证 total == passed + failed + skipped + blocked
    + in_progress + untested + retest。
    """
    total = 0
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

        # 兼容 result_summary 中可能使用的不同 key（passed / passed_count）
        passed_in_summary = summary.get("passed", summary.get("passed_count", 0)) or 0
        failed_in_summary = summary.get("failed", summary.get("failed_count", 0)) or 0
        skipped_in_summary = summary.get("skipped", summary.get("skipped_count", 0)) or 0
        total_in_summary = summary.get("total")

        # 显式结果：summary 里至少包含一个计数字段。
        # 仅有 failure_category 等元数据时按状态兜底分配，避免 total=1 但分项全 0。
        has_explicit_results = any(
            summary.get(k) is not None
            for k in ("total", "passed", "failed", "skipped")
        )

        if has_explicit_results and status in (JobStatus.COMPLETED, JobStatus.FAILED):
            # 有显式计数：按 summary 分配，并保证 total == passed+failed+skipped。
            if total_in_summary is not None:
                job_total = total_in_summary
            else:
                job_total = passed_in_summary + failed_in_summary + skipped_in_summary
            if job_total < 1:
                job_total = 1

            job_passed = passed_in_summary
            job_failed = failed_in_summary
            job_skipped = skipped_in_summary
            accounted = job_passed + job_failed + job_skipped

            if accounted < job_total:
                # 分项之和小于 total（如部分用例未执行/中断），差额按状态补齐。
                # - 已完成作业：未计入的默认为通过
                # - 失败作业且分项全为 0（如基础设施错误导致完全未执行）：
                #   差额计入 failed（保守，整单失败）
                # - 失败作业但已有部分执行结果（如场景步骤因前置失败被跳过）：
                #   差额计入 skipped，避免前端展示"失败数虚高"
                if status == JobStatus.COMPLETED:
                    job_passed += job_total - accounted
                elif accounted == 0:
                    job_failed += job_total - accounted
                else:
                    job_skipped += job_total - accounted
            elif accounted > job_total:
                # 分项之和超过 total（如 total 为 0 但 failed>0），以分项为准扩大 total
                job_total = accounted
        elif status == JobStatus.COMPLETED:
            # 无显式计数但已完成：按 1 个用例全部计入通过
            job_total = 1
            job_passed = 1
            job_failed = 0
            job_skipped = 0
        elif status == JobStatus.FAILED:
            # 无显式计数但失败：按 1 个用例全部计入失败
            job_total = 1
            job_passed = 0
            job_failed = 1
            job_skipped = 0
        else:
            # 其他状态：按 1 个用例计，待状态分配
            job_total = 1
            job_passed = 0
            job_failed = 0
            job_skipped = 0

        total += job_total

        if status == JobStatus.PENDING:
            untested += job_total
        elif status == JobStatus.RUNNING:
            in_progress += job_total
        elif status == JobStatus.COMPLETED:
            passed += job_passed
            failed += job_failed
            skipped += job_skipped
        elif status == JobStatus.FAILED:
            passed += job_passed
            failed += job_failed
            skipped += job_skipped
        elif status == JobStatus.SKIPPED:
            skipped += job_total
        elif status == JobStatus.BLOCKED:
            blocked += job_total
        elif status == JobStatus.CANCELLED:
            blocked += job_total

    return {
        "test_cases_count": total,
        "untested_count": untested,
        "passed_count": passed,
        "retest_count": retest,
        "failed_count": failed,
        "blocked_count": blocked,
        "skipped_count": skipped,
        "in_progress_count": in_progress,
    }


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
        trigger_types: Optional[list] = None,
        scheduled_by: Optional[UUID] = None,
        script_ids: Optional[list[UUID]] = None,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[TestRun], int]:
        """
        获取测试运行列表（BS 规范）

        - run_states/assignees 是多值 OR，参数间是 AND
        - include_closed=False 时强制 active_state=ACTIVE；True 不限制
        - closed_before/after 对 closed_at 做日期比较
        - created_before/after 对 created_at 做日期比较
        - trigger_types 按触发方式过滤
        - scheduled_by 按来源调度过滤
        - search 支持按调度名称搜索（通过 join TestRunSchedule）
        """
        # 如果需要按调度名称搜索，需要 join TestRunSchedule
        need_schedule_join = search is not None

        stmt = select(TestRun).where(TestRun.project_id == project_id)
        count_stmt = (
            select(func.count())
            .select_from(TestRun)
            .where(TestRun.project_id == project_id)
        )

        if need_schedule_join:
            stmt = stmt.outerjoin(
                TestRunSchedule, TestRun.scheduled_by == TestRunSchedule.id
            )
            count_stmt = count_stmt.outerjoin(
                TestRunSchedule, TestRun.scheduled_by == TestRunSchedule.id
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

        # 触发方式过滤
        if trigger_types:
            _add(TestRun.trigger_type.in_(trigger_types))

        # 来源调度过滤
        if scheduled_by:
            _add(TestRun.scheduled_by == scheduled_by)

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
                    TestRunSchedule.name.ilike(f"%{search}%"),
                )
            )

        if script_ids:
            matched_run_ids = (
                select(
                    TestRunScriptJob.test_run_id,
                    func.count(func.distinct(TestRunScriptJob.script_id)).label(
                        "match_count"
                    ),
                )
                .where(TestRunScriptJob.script_id.in_(script_ids))
                .group_by(TestRunScriptJob.test_run_id)
                .having(func.count(func.distinct(TestRunScriptJob.script_id)) > 0)
            ).subquery()
            stmt = stmt.join(matched_run_ids, TestRun.id == matched_run_ids.c.test_run_id)
            count_stmt = count_stmt.join(matched_run_ids, TestRun.id == matched_run_ids.c.test_run_id)
            # 按匹配脚本数降序，再按创建时间降序，保证相关历史优先出现
            stmt = stmt.order_by(
                matched_run_ids.c.match_count.desc(), TestRun.created_at.desc()
            )
        else:
            stmt = stmt.order_by(TestRun.created_at.desc())

        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        count_result = await self.session.execute(count_stmt)

        return list(result.scalars().all()), count_result.scalar() or 0

    async def create(self, test_run: TestRun) -> TestRun:
        """创建测试运行"""
        self.session.add(test_run)
        await self.session.flush()
        return test_run

    async def get_recent_by_schedule(
        self,
        schedule_id: UUID,
        seconds: int = 60,
    ) -> Optional[TestRun]:
        """获取某调度在最近 N 秒内创建的测试运行（用于幂等）"""
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        stmt = (
            select(TestRun)
            .where(
                TestRun.scheduled_by == schedule_id,
                TestRun.created_at >= cutoff,
            )
            .order_by(TestRun.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_in_progress_by_schedule(
        self,
        schedule_id: UUID,
    ) -> Optional[TestRun]:
        """获取某调度当前正在执行的测试运行（用于跳过并发触发）"""
        from app.schemas.enums import TestRunState
        stmt = (
            select(TestRun)
            .where(
                TestRun.scheduled_by == schedule_id,
                TestRun.run_state == TestRunState.IN_PROGRESS,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, test_run: TestRun) -> TestRun:
        """更新测试运行"""
        await self.session.flush()
        await self.session.refresh(test_run)
        return test_run

    async def try_mark_in_progress(self, test_run_id: UUID) -> bool:
        """原子地将测试运行置为进行中（防止并发重复执行）。

        使用单条带条件的 UPDATE 作为"抢占锁"：仅当运行当前不在进行中且处于活跃状态时
        才会更新成功。返回是否抢到执行权（rowcount > 0）。

        附带语义：已关闭（active_state=closed）的运行无法被置为进行中。
        """
        stmt = (
            update(TestRun)
            .where(
                TestRun.id == test_run_id,
                TestRun.run_state != TestRunState.IN_PROGRESS,
                TestRun.active_state == TestRunActiveState.ACTIVE,
            )
            .values(run_state=TestRunState.IN_PROGRESS)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def delete(self, test_run: TestRun) -> None:
        """删除测试运行"""
        await self.session.delete(test_run)
        await self.session.flush()

    async def generate_identifier(self) -> str:
        """生成测试运行标识符（全局自增，避免删除/并发导致重复）"""
        # 从现有 TR-% 标识符中提取最大数字，生成 TR-{max+1}
        numeric_part = cast(
            func.regexp_replace(TestRun.identifier, "[^0-9]", "", "g"),
            Integer,
        )
        stmt = (
            select(func.max(numeric_part))
            .select_from(TestRun)
            .where(TestRun.identifier.like("TR-%"))
        )
        result = await self.session.execute(stmt)
        max_num = result.scalar() or 0
        return f"TR-{max_num + 1}"

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

        counts = _aggregate_progress_from_jobs(jobs)
        update_stmt = update(TestRun).where(TestRun.id == test_run_id).values(**counts)
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

    async def get_by_ids(self, schedule_ids: list[UUID]) -> list[TestRunSchedule]:
        """根据 ID 列表批量获取调度"""
        if not schedule_ids:
            return []
        stmt = (
            select(TestRunSchedule)
            .where(TestRunSchedule.id.in_(schedule_ids))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

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


class TestRunExecutionSnapshotRepository:
    """测试运行执行快照仓储"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_next_execution_number(self, test_run_id: UUID) -> int:
        """获取该 TestRun 的下一个执行序号"""
        stmt = (
            select(func.coalesce(func.max(TestRunExecutionSnapshot.execution_number), 0) + 1)
            .where(TestRunExecutionSnapshot.test_run_id == test_run_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 1

    async def create(
        self,
        snapshot: TestRunExecutionSnapshot,
        snapshot_jobs: list[TestRunExecutionSnapshotJob],
    ) -> TestRunExecutionSnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        for job in snapshot_jobs:
            job.snapshot_id = snapshot.id
            self.session.add(job)
        await self.session.flush()
        return snapshot

    async def get_by_id(self, snapshot_id: UUID) -> Optional[TestRunExecutionSnapshot]:
        stmt = (
            select(TestRunExecutionSnapshot)
            .options(selectinload(TestRunExecutionSnapshot.snapshot_jobs))
            .where(TestRunExecutionSnapshot.id == snapshot_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_test_run(
        self,
        test_run_id: UUID,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[TestRunExecutionSnapshot], int]:
        stmt = (
            select(TestRunExecutionSnapshot)
            .where(TestRunExecutionSnapshot.test_run_id == test_run_id)
            .order_by(TestRunExecutionSnapshot.execution_number.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = (
            select(func.count())
            .select_from(TestRunExecutionSnapshot)
            .where(TestRunExecutionSnapshot.test_run_id == test_run_id)
        )
        result = await self.session.execute(stmt)
        count_result = await self.session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    async def get_latest_by_test_run(
        self, test_run_id: UUID
    ) -> Optional[TestRunExecutionSnapshot]:
        stmt = (
            select(TestRunExecutionSnapshot)
            .where(TestRunExecutionSnapshot.test_run_id == test_run_id)
            .order_by(TestRunExecutionSnapshot.execution_number.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
