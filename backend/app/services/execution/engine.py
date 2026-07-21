"""
统一脚本执行引擎

协调测试运行中所有脚本作业的执行，支持顺序/并行调度、
状态追踪、取消操作和结果汇总。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from app.config.database import async_session_factory
from app.models.test_run import TestRunScriptJob, TestRunExecutionSnapshot, TestRunExecutionSnapshotJob
from app.repositories.test_run_repo import (
    TestRunRepository,
    TestRunScriptJobRepository,
    TestRunExecutionSnapshotRepository,
)
from app.schemas.enums import ExecutionMode, JobStatus, TestRunState, FailurePolicy
from app.services.execution.executors import ExecutorRegistry
from app.services.execution.models import ExecutionResult
from app.services.execution.schedulers import (
    ParallelScheduler,
    SequentialScheduler,
)

logger = logging.getLogger(__name__)

# 模块级取消状态，保证跨实例共享（cancel_run 可能由不同 TestExecutionService 实例调用）
_cancelled_runs: Set[UUID] = set()
_active_executors: Dict[UUID, Any] = {}
# 模块级 run 计数锁，避免并发更新 TestRun 计数时互相覆盖
_run_count_locks: Dict[UUID, asyncio.Lock] = {}
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VG5aU1ZRPT06Njc4ZDgzY2U=


def decide_final_state(
    job_statuses: List[tuple],
) -> TestRunState:
    """根据全部作业的 (status, failure_category) 决定测试运行的最终状态（纯函数，便于测试）。

    规则：
    - 仍有 pending/running 作业 → IN_PROGRESS（防御，正常收尾不会出现）；
    - 无失败作业 → DONE；
    - 存在环境/基础设施类失败 → REJECTED；
    - 其余（断言/超时等业务失败）→ DONE_WITH_FAILURES。

    Args:
        job_statuses: 元素为 (JobStatus, Optional[str]) 的列表，
                      failure_category 可为 None。
    """
    infra_categories = {"environment", "infra"}
    failed = [c for s, c in job_statuses if s == JobStatus.FAILED]
    has_infra_error = any(c in infra_categories for c in failed)
    has_unfinished = any(
        s in (JobStatus.PENDING, JobStatus.RUNNING) for s, _ in job_statuses
    )

    if has_unfinished:
        return TestRunState.IN_PROGRESS
    if not failed:
        return TestRunState.DONE
    if has_infra_error:
        return TestRunState.REJECTED
    return TestRunState.DONE_WITH_FAILURES


class ScriptExecutionEngine:
    """统一脚本执行引擎"""

    def __init__(self, mongodb: Any = None):
        self.mongodb = mongodb

    def _get_run_count_lock(self, test_run_id: UUID) -> asyncio.Lock:
        """获取（必要时创建）指定测试运行的计数更新锁。"""
        if test_run_id not in _run_count_locks:
            _run_count_locks[test_run_id] = asyncio.Lock()
        return _run_count_locks[test_run_id]

    async def _update_run_counts(self, test_run_id: UUID) -> None:
        """根据当前 ScriptJob 状态刷新 TestRun 的整体进度计数。"""
        async with self._get_run_count_lock(test_run_id):
            try:
                async with async_session_factory() as session:
                    run_repo = TestRunRepository(session)
                    await run_repo.update_counts_from_jobs(test_run_id)
                    await session.commit()
            except Exception as e:
                logger.warning(
                    "[ScriptExecutionEngine] 更新测试运行 %s 计数失败: %s",
                    test_run_id,
                    e,
                )

    async def _create_execution_snapshot(
        self,
        test_run_id: UUID,
        jobs: List[TestRunScriptJob],
        *,
        triggered_by: str = "manual",
        started_at: Optional[datetime] = None,
    ) -> None:
        """为一次完整执行创建快照。

        捕获 TestRun 终态和每个 ScriptJob 的当前状态、结果、日志、报告路径。
        失败只记录日志，不影响主执行流程。
        """
        try:
            async with async_session_factory() as session:
                run_repo = TestRunRepository(session)
                snapshot_repo = TestRunExecutionSnapshotRepository(session)

                test_run = await run_repo.get_by_id(test_run_id)
                if not test_run:
                    return

                execution_number = await snapshot_repo.get_next_execution_number(
                    test_run_id
                )

                snapshot = TestRunExecutionSnapshot(
                    test_run_id=test_run_id,
                    execution_number=execution_number,
                    triggered_by=triggered_by,
                    run_state=str(test_run.run_state.value),
                    started_at=started_at,
                    completed_at=datetime.now(timezone.utc),
                    overall_progress={
                        "untested": test_run.untested_count or 0,
                        "passed": test_run.passed_count or 0,
                        "retest": test_run.retest_count or 0,
                        "failed": test_run.failed_count or 0,
                        "blocked": test_run.blocked_count or 0,
                        "skipped": test_run.skipped_count or 0,
                        "in_progress": test_run.in_progress_count or 0,
                    },
                )

                snapshot_jobs = [
                    TestRunExecutionSnapshotJob(
                        script_job_id=job.id,
                        test_run_id=test_run_id,
                        script_type=job.script_type,
                        script_id=job.script_id,
                        script_identifier=job.script_identifier,
                        script_name=job.script_name,
                        execution_order=job.execution_order,
                        execution_mode=job.execution_mode,
                        status=job.status,
                        started_at=job.started_at,
                        completed_at=job.completed_at,
                        duration_ms=job.duration_ms,
                        result_summary=job.result_summary,
                        error_message=job.error_message,
                        stdout=job.stdout,
                        stderr=job.stderr,
                        report_path=job.report_path,
                        retry_count=job.retry_count,
                        max_retries=job.max_retries,
                    )
                    for job in jobs
                ]

                await snapshot_repo.create(snapshot, snapshot_jobs)
                await session.commit()
                logger.info(
                    "[ScriptExecutionEngine] 已创建测试运行 %s 第 %s 次执行快照",
                    test_run_id,
                    execution_number,
                )
        except Exception as e:
            logger.warning(
                "[ScriptExecutionEngine] 创建测试运行 %s 执行快照失败: %s",
                test_run_id,
                e,
            )

    async def execute_run(
        self,
        test_run_id: UUID,
        trigger: str = "manual",
    ) -> Dict[str, Any]:
        """
        执行整个测试运行。

        工作流程：
        1. 加载 TestRun 和 ScriptJobs
        2. 更新 TestRun 状态为 IN_PROGRESS
        3. 按 execution_mode 执行所有 jobs
        4. 汇总结果并更新 TestRun 状态
        """
        # 1. 加载 TestRun 和 Jobs
        async with async_session_factory() as session:
            run_repo = TestRunRepository(session)
            job_repo = TestRunScriptJobRepository(session)

            test_run = await run_repo.get_by_id(test_run_id)
            if not test_run:
                raise ValueError(f"测试运行不存在: {test_run_id}")

            # 更新状态为进行中
            test_run.run_state = TestRunState.IN_PROGRESS
            await run_repo.update(test_run)
            await session.commit()
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VG5aU1ZRPT06Njc4ZDgzY2U=

            # 加载所有脚本作业
            jobs, _ = await job_repo.get_by_test_run(test_run_id)

            if not jobs:
                # 没有脚本作业，直接标记为完成并清零计数
                test_run.run_state = TestRunState.DONE
                await run_repo.update(test_run)
                await run_repo.update_counts_from_jobs(test_run_id)
                await session.commit()
                return {
                    "test_run_id": str(test_run_id),
                    "status": "done",
                    "message": "没有脚本作业需要执行",
                }

        # 提取执行配置（在 session 外访问标量属性是安全的，expire_on_commit=False）
        execution_mode = test_run.execution_mode or ExecutionMode.SEQUENTIAL
        max_concurrency = test_run.max_concurrency or 5
        failure_policy = test_run.failure_policy or FailurePolicy.CONTINUE
        project_id = test_run.project_id
        environment_id = test_run.environment_id
        started_at = datetime.now(timezone.utc)

        try:
            # 2. 执行作业
            try:
                if execution_mode == ExecutionMode.PARALLEL:
                    scheduler = ParallelScheduler()
                else:
                    scheduler = SequentialScheduler()

                results = await scheduler.schedule(
                    project_id=project_id,
                    jobs=jobs,
                    run_job=lambda job: self._run_job(
                        test_run_id, job, environment_id=environment_id
                    ),
                    max_concurrency=max_concurrency,
                    failure_policy=failure_policy,
                )

                # 清除取消标记
                _cancelled_runs.discard(test_run_id)

                # 3. 汇总结果并更新 TestRun 状态
                success_count = sum(1 for r in results if r.success)
                failed_count = len(results) - success_count

                # 根据失败分类推断最终状态
                infra_categories = {"environment", "infra"}
                has_infra_error = any(
                    r.failure_category in infra_categories and not r.has_missing_counts
                    for r in results
                )
                if failed_count == 0:
                    final_state = TestRunState.DONE
                elif has_infra_error:
                    final_state = TestRunState.REJECTED
                else:
                    final_state = TestRunState.DONE_WITH_FAILURES

                async with async_session_factory() as session:
                    run_repo = TestRunRepository(session)
                    job_repo = TestRunScriptJobRepository(session)
                    test_run = await run_repo.get_by_id(test_run_id)

                    test_run.run_state = final_state

                    await run_repo.update(test_run)
                    await run_repo.update_counts_from_jobs(test_run_id)
                    await session.commit()

                    # 重新加载 jobs 当前状态并创建快照
                    jobs, _ = await job_repo.get_by_test_run(test_run_id, limit=100000)
                    await self._create_execution_snapshot(
                        test_run_id,
                        jobs,
                        triggered_by=trigger,
                        started_at=started_at,
                    )

                logger.info(
                    "[ScriptExecutionEngine] 测试运行 %s 执行完成: "
                    "total=%s, passed=%s, failed=%s, state=%s",
                    test_run_id,
                    len(results),
                    success_count,
                    failed_count,
                    final_state.value,
                )

                return {
                    "test_run_id": str(test_run_id),
                    "status": final_state.value,
                    "total": len(results),
                    "passed": success_count,
                    "failed": failed_count,
                }

            except Exception as e:
                logger.exception("[ScriptExecutionEngine] 执行测试运行时异常")
                async with async_session_factory() as session:
                    run_repo = TestRunRepository(session)
                    job_repo = TestRunScriptJobRepository(session)
                    test_run = await run_repo.get_by_id(test_run_id)
                    test_run.run_state = TestRunState.REJECTED
                    await run_repo.update(test_run)
                    await run_repo.update_counts_from_jobs(test_run_id)
                    await session.commit()

                    # 异常情况下也保留当前状态快照
                    jobs, _ = await job_repo.get_by_test_run(test_run_id, limit=100000)
                    await self._create_execution_snapshot(
                        test_run_id,
                        jobs,
                        triggered_by=trigger,
                        started_at=started_at,
                    )

                return {
                    "test_run_id": str(test_run_id),
                    "status": "failed",
                    "error": str(e),
                }
        finally:
            _run_count_locks.pop(test_run_id, None)

    async def execute_jobs(
        self,
        test_run_id: UUID,
        job_ids: List[UUID],
    ) -> Dict[str, Any]:
        """仅执行指定的脚本作业（用于"重试"场景），随后基于全部作业重新定案。

        与 execute_run 的区别：
        - 只调度 job_ids 指定的作业，而非全部；
        - 最终状态由数据库中全部作业的当前状态决定（而非仅本次运行的结果），
          因此重试部分失败作业后能正确反映整体通过/失败情况。
        """
        # 1. 加载 TestRun 与指定作业
        async with async_session_factory() as session:
            run_repo = TestRunRepository(session)
            job_repo = TestRunScriptJobRepository(session)

            test_run = await run_repo.get_by_id(test_run_id)
            if not test_run:
                raise ValueError(f"测试运行不存在: {test_run_id}")

            # 兜底确保运行处于进行中（调用方一般已原子抢占执行权）
            test_run.run_state = TestRunState.IN_PROGRESS
            await run_repo.update(test_run)
            await session.commit()

            all_jobs, _ = await job_repo.get_by_test_run(test_run_id, limit=100000)
            wanted = set(job_ids)
            jobs = [j for j in all_jobs if j.id in wanted]

            if not jobs:
                final_state = await self._finalize_run_from_db(test_run_id)
                return {
                    "test_run_id": str(test_run_id),
                    "status": final_state.value,
                    "retried": 0,
                    "message": "没有需要重试的脚本作业",
                }

        # 提取执行配置（session 外访问标量属性安全，expire_on_commit=False）
        execution_mode = test_run.execution_mode or ExecutionMode.SEQUENTIAL
        max_concurrency = test_run.max_concurrency or 5
        failure_policy = test_run.failure_policy or FailurePolicy.CONTINUE
        project_id = test_run.project_id
        environment_id = test_run.environment_id
        started_at = datetime.now(timezone.utc)

        try:
            if execution_mode == ExecutionMode.PARALLEL:
                scheduler = ParallelScheduler()
            else:
                scheduler = SequentialScheduler()

            await scheduler.schedule(
                project_id=project_id,
                jobs=jobs,
                run_job=lambda job: self._run_job(
                    test_run_id, job, environment_id=environment_id
                ),
                max_concurrency=max_concurrency,
                failure_policy=failure_policy,
            )

            # 清除取消标记
            _cancelled_runs.discard(test_run_id)

            # 基于全部作业重新定案
            final_state = await self._finalize_run_from_db(test_run_id)

            # 重新加载全部 jobs 并创建快照
            async with async_session_factory() as session:
                job_repo = TestRunScriptJobRepository(session)
                all_jobs, _ = await job_repo.get_by_test_run(test_run_id, limit=100000)
            await self._create_execution_snapshot(
                test_run_id,
                all_jobs,
                triggered_by="retry",
                started_at=started_at,
            )

            logger.info(
                "[ScriptExecutionEngine] 测试运行 %s 重试执行完成: retried=%s, state=%s",
                test_run_id,
                len(jobs),
                final_state.value,
            )

            return {
                "test_run_id": str(test_run_id),
                "status": final_state.value,
                "retried": len(jobs),
            }

        except Exception as e:
            logger.exception("[ScriptExecutionEngine] 重试执行作业时异常")
            async with async_session_factory() as session:
                run_repo = TestRunRepository(session)
                job_repo = TestRunScriptJobRepository(session)
                test_run = await run_repo.get_by_id(test_run_id)
                test_run.run_state = TestRunState.REJECTED
                await run_repo.update(test_run)
                await run_repo.update_counts_from_jobs(test_run_id)
                await session.commit()

                # 异常情况下也保留当前状态快照
                all_jobs, _ = await job_repo.get_by_test_run(test_run_id, limit=100000)
                await self._create_execution_snapshot(
                    test_run_id,
                    all_jobs,
                    triggered_by="retry",
                    started_at=started_at,
                )

            return {
                "test_run_id": str(test_run_id),
                "status": "failed",
                "error": str(e),
            }
        finally:
            _run_count_locks.pop(test_run_id, None)

    async def _finalize_run_from_db(self, test_run_id: UUID) -> TestRunState:
        """基于数据库中全部脚本作业的当前状态，计算并写入测试运行的最终状态。

        定案规则见 decide_final_state。重试场景下调用，确保最终状态反映整体结果。
        """
        async with async_session_factory() as session:
            run_repo = TestRunRepository(session)
            job_repo = TestRunScriptJobRepository(session)

            test_run = await run_repo.get_by_id(test_run_id)
            jobs, _ = await job_repo.get_by_test_run(test_run_id, limit=100000)

            final_state = decide_final_state(
                [
                    (j.status, (j.result_summary or {}).get("failure_category"))
                    for j in jobs
                ]
            )

            test_run.run_state = final_state
            await run_repo.update(test_run)
            await run_repo.update_counts_from_jobs(test_run_id)
            await session.commit()
            return final_state

    async def _run_job(
        self,
        test_run_id: UUID,
        job: TestRunScriptJob,
        environment_id: Optional[UUID] = None,
    ) -> ExecutionResult:
        """执行单个作业并更新其状态"""
        start_time = datetime.now(timezone.utc)
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VG5aU1ZRPT06Njc4ZDgzY2U=

        # 检查是否已被取消
        if test_run_id in _cancelled_runs:
            return ExecutionResult(
                success=False,
                status=JobStatus.CANCELLED.value,
                error_message="测试运行已被取消",
            )

        # 更新作业状态为 RUNNING
        await self._update_job_status(
            job.id,
            JobStatus.RUNNING,
            started_at=start_time,
        )
        await self._update_run_counts(test_run_id)

        executor = None
        try:
            executor = ExecutorRegistry.get(job.script_type, self.mongodb)
            _active_executors[test_run_id] = executor
            config = job.execution_config or {}
            # 注入 TestRun 级别的环境 ID（job 级 execution_config 优先级更高）
            if environment_id and "env_id" not in config:
                config = {**config, "env_id": str(environment_id)}
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VG5aU1ZRPT06Njc4ZDgzY2U=

            result = await executor.execute(
                script_id=job.script_id,
                config=config,
            )

            completed_at = datetime.now(timezone.utc)
            duration_ms = result.duration_ms or int(
                (completed_at - start_time).total_seconds() * 1000
            )

            # 更新作业状态
            summary = dict(result.result_summary)
            summary["failure_category"] = result.failure_category
            summary["passed_count"] = result.passed_count
            summary["failed_count"] = result.failed_count
            summary["skipped_count"] = result.skipped_count
            summary["error_count"] = result.error_count

            await self._update_job_status(
                job.id,
                JobStatus(result.status),
                completed_at=completed_at,
                duration_ms=duration_ms,
                error_message=result.error_message,
                stdout=result.stdout,
                stderr=result.stderr,
                report_path=result.report_path,
                result_summary=summary,
            )
            await self._update_run_counts(test_run_id)

            return result

        except Exception as e:
            logger.exception("[ScriptExecutionEngine] 执行作业 %s 异常", job.id)
            completed_at = datetime.now(timezone.utc)
            duration_ms = int(
                (completed_at - start_time).total_seconds() * 1000
            )

            await self._update_job_status(
                job.id,
                JobStatus.FAILED,
                completed_at=completed_at,
                duration_ms=duration_ms,
                error_message=str(e),
                result_summary={"failure_category": "infra"},
            )
            await self._update_run_counts(test_run_id)

            return ExecutionResult(
                success=False,
                status=JobStatus.FAILED.value,
                failure_category="infra",
                duration_ms=duration_ms,
                error_message=str(e),
            )
        finally:
            _active_executors.pop(test_run_id, None)

    async def _update_job_status(
        self,
        job_id: UUID,
        status: JobStatus,
        **kwargs: Any,
    ) -> None:
        """更新作业状态"""
        try:
            async with async_session_factory() as session:
                job_repo = TestRunScriptJobRepository(session)
                await job_repo.update_status(job_id, status, **kwargs)
                await session.commit()
        except Exception as e:
            logger.warning("[ScriptExecutionEngine] 更新作业状态失败: %s", e)

    async def cancel_run(self, test_run_id: UUID) -> None:
        """取消测试运行"""
        _cancelled_runs.add(test_run_id)
        executor = _active_executors.get(test_run_id)
        if executor:
            try:
                await executor.cancel()
            except Exception as e:
                logger.warning("[ScriptExecutionEngine] 取消执行器失败: %s", e)
        logger.info("[ScriptExecutionEngine] 已标记取消测试运行 %s", test_run_id)
