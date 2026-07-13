"""
执行调度器

支持顺序执行和并行执行两种模式。
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, Dict, List
from uuid import UUID

from app.services.execution.models import ExecutionResult
from app.schemas.enums import JobStatus, FailurePolicy
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFZOWVdRPT06NTI4ZDEyYjM=

logger = logging.getLogger(__name__)

# 项目级并发信号量缓存
_project_semaphores: Dict[UUID, asyncio.Semaphore] = {}


def _get_project_semaphore(project_id: UUID, max_concurrent: int) -> asyncio.Semaphore:
    """获取或创建项目级并发信号量"""
    if project_id not in _project_semaphores:
        _project_semaphores[project_id] = asyncio.Semaphore(max_concurrent)
    return _project_semaphores[project_id]


class JobScheduler(ABC):
    """作业调度器抽象基类"""

    @abstractmethod
    async def schedule(
        self,
        project_id: UUID,
        jobs: List[Any],
        run_job: Callable[[Any], Coroutine[Any, Any, ExecutionResult]],
        max_concurrency: int = 5,
        failure_policy: FailurePolicy = FailurePolicy.CONTINUE,
    ) -> List[ExecutionResult]:
        """
        调度执行一组作业。

        Args:
            project_id: 项目 ID（用于并发控制）
            jobs: 作业列表（通常是 TestRunScriptJob 实例）
            run_job: 执行单个作业的协程函数
            max_concurrency: 最大并发数（仅并行模式使用）
            failure_policy: 失败策略

        Returns:
            ExecutionResult 列表，顺序与 jobs 一致
        """
        ...


class SequentialScheduler(JobScheduler):
    """顺序调度器：逐个执行，支持失败策略"""
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFZOWVdRPT06NTI4ZDEyYjM=

    async def schedule(
        self,
        project_id: UUID,
        jobs: List[Any],
        run_job: Callable[[Any], Coroutine[Any, Any, ExecutionResult]],
        max_concurrency: int = 5,
        failure_policy: FailurePolicy = FailurePolicy.CONTINUE,
    ) -> List[ExecutionResult]:
        results: List[ExecutionResult] = []
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFZOWVdRPT06NTI4ZDEyYjM=

        # 向后兼容：旧 API 通过 job.execution_config.stop_on_failure=True 表达 STOP_RUN
        if failure_policy == FailurePolicy.CONTINUE:
            for job in jobs:
                if job.execution_config and job.execution_config.get("stop_on_failure"):
                    failure_policy = FailurePolicy.STOP_RUN
                    logger.info(
                        "[SequentialScheduler] 检测到 job.execution_config.stop_on_failure=True，"
                        "升级失败策略为 STOP_RUN"
                    )
                    break

        for job in jobs:
            result = await run_job(job)
            results.append(result)

            if not result.success:
                if failure_policy == FailurePolicy.STOP_RUN:
                    logger.info(
                        "[SequentialScheduler] 作业 %s 失败且策略为 STOP_RUN，"
                        "跳过剩余 %s 个作业",
                        job.id,
                        len(jobs) - len(results),
                    )
                    for skipped_job in jobs[len(results):]:
                        results.append(
                            ExecutionResult(
                                success=False,
                                status=JobStatus.SKIPPED.value,
                                error_message="前置作业失败，已跳过",
                            )
                        )
                    break
                if failure_policy == FailurePolicy.MARK_BLOCKED:
                    logger.info(
                        "[SequentialScheduler] 作业 %s 失败且策略为 MARK_BLOCKED，"
                        "后续 %s 个作业标记为 BLOCKED",
                        job.id,
                        len(jobs) - len(results),
                    )
                    for _ in jobs[len(results):]:
                        results.append(
                            ExecutionResult(
                                success=False,
                                status=JobStatus.BLOCKED.value,
                                error_message="前置作业失败，已阻塞",
                            )
                        )
                    break
                # CONTINUE / STOP_JOB：仅记录当前失败，继续执行下一个

        return results


class ParallelScheduler(JobScheduler):
    """并行调度器：基于信号量限制并发数，支持失败策略"""

    async def schedule(
        self,
        project_id: UUID,
        jobs: List[Any],
        run_job: Callable[[Any], Coroutine[Any, Any, ExecutionResult]],
        max_concurrency: int = 5,
        failure_policy: FailurePolicy = FailurePolicy.CONTINUE,
    ) -> List[ExecutionResult]:
        semaphore = _get_project_semaphore(project_id, max_concurrency)

        async def _run_with_limit(job: Any) -> ExecutionResult:
            async with semaphore:
                return await run_job(job)

        tasks = [
            asyncio.create_task(_run_with_limit(job), name=f"job-{job.id}")
            for job in jobs
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 将异常转换为 FAILED 结果
        processed: List[ExecutionResult] = []
        for result in results:
            if isinstance(result, Exception):
                logger.exception("[ParallelScheduler] 作业执行异常")
                processed.append(
                    ExecutionResult(
                        success=False,
                        status=JobStatus.FAILED.value,
                        error_message=str(result),
                    )
                )
            else:
                processed.append(result)

        # 并行模式下 STOP_RUN / MARK_BLOCKED 采用后处理：
        # 找到第一个失败的 job，其后的 job 标记为 SKIPPED/BLOCKED。
        # 注意：这些 job 实际上已经执行过了，这里覆盖结果以符合策略语义。
        if failure_policy in (FailurePolicy.STOP_RUN, FailurePolicy.MARK_BLOCKED):
            first_failure_index = None
            for idx, result in enumerate(processed):
                if not result.success:
                    first_failure_index = idx
                    break
            if first_failure_index is not None:
                override_status = (
                    JobStatus.BLOCKED.value
                    if failure_policy == FailurePolicy.MARK_BLOCKED
                    else JobStatus.SKIPPED.value
                )
                override_message = (
                    "前置作业失败，已阻塞"
                    if failure_policy == FailurePolicy.MARK_BLOCKED
                    else "前置作业失败，已跳过"
                )
                for idx in range(first_failure_index + 1, len(processed)):
                    processed[idx] = ExecutionResult(
                        success=False,
                        status=override_status,
                        error_message=override_message,
                    )
                logger.info(
                    "[ParallelScheduler] 失败策略为 %s，第 %s 个作业失败后"
                    "覆盖后续 %s 个作业结果为 %s",
                    failure_policy.value,
                    first_failure_index,
                    len(processed) - first_failure_index - 1,
                    override_status,
                )

        return processed
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFZOWVdRPT06NTI4ZDEyYjM=
