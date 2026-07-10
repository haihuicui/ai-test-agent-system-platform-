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
from app.models.test_run import TestRunScriptJob
from app.repositories.test_run_repo import (
    TestRunRepository,
    TestRunScriptJobRepository,
)
from app.schemas.enums import ExecutionMode, JobStatus, TestRunState
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
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VG5aU1ZRPT06Njc4ZDgzY2U=


class ScriptExecutionEngine:
    """统一脚本执行引擎"""

    def __init__(self, mongodb: Any = None):
        self.mongodb = mongodb

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
                # 没有脚本作业，直接标记为完成
                test_run.run_state = TestRunState.DONE
                await run_repo.update(test_run)
                await session.commit()
                return {
                    "test_run_id": str(test_run_id),
                    "status": "done",
                    "message": "没有脚本作业需要执行",
                }

        # 提取执行配置（在 session 外访问标量属性是安全的，expire_on_commit=False）
        execution_mode = test_run.execution_mode or ExecutionMode.SEQUENTIAL
        max_concurrency = test_run.max_concurrency or 5
        project_id = test_run.project_id
        environment_id = test_run.environment_id

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
            )

            # 清除取消标记
            _cancelled_runs.discard(test_run_id)

            # 3. 汇总结果并更新 TestRun 状态
            success_count = sum(1 for r in results if r.success)
            failed_count = len(results) - success_count

            async with async_session_factory() as session:
                run_repo = TestRunRepository(session)
                test_run = await run_repo.get_by_id(test_run_id)

                if failed_count > 0:
                    test_run.run_state = TestRunState.REJECTED
                else:
                    test_run.run_state = TestRunState.DONE

                await run_repo.update(test_run)
                await run_repo.update_counts_from_jobs(test_run_id)
                await session.commit()

            logger.info(
                "[ScriptExecutionEngine] 测试运行 %s 执行完成: "
                "total=%s, passed=%s, failed=%s",
                test_run_id,
                len(results),
                success_count,
                failed_count,
            )

            return {
                "test_run_id": str(test_run_id),
                "status": "done" if failed_count == 0 else "rejected",
                "total": len(results),
                "passed": success_count,
                "failed": failed_count,
            }

        except Exception as e:
            logger.exception("[ScriptExecutionEngine] 执行测试运行时异常")
            async with async_session_factory() as session:
                run_repo = TestRunRepository(session)
                test_run = await run_repo.get_by_id(test_run_id)
                test_run.run_state = TestRunState.REJECTED
                await run_repo.update(test_run)
                await run_repo.update_counts_from_jobs(test_run_id)
                await session.commit()

            return {
                "test_run_id": str(test_run_id),
                "status": "failed",
                "error": str(e),
            }

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
            await self._update_job_status(
                job.id,
                JobStatus(result.status),
                completed_at=completed_at,
                duration_ms=duration_ms,
                error_message=result.error_message,
                stdout=result.stdout,
                stderr=result.stderr,
                report_path=result.report_path,
                result_summary=result.result_summary,
            )

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
            )

            return ExecutionResult(
                success=False,
                status=JobStatus.FAILED.value,
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
