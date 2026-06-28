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
from app.schemas.enums import JobStatus
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
    ) -> List[ExecutionResult]:
        """
        调度执行一组作业。

        Args:
            project_id: 项目 ID（用于并发控制）
            jobs: 作业列表（通常是 TestRunScriptJob 实例）
            run_job: 执行单个作业的协程函数
            max_concurrency: 最大并发数（仅并行模式使用）

        Returns:
            ExecutionResult 列表，顺序与 jobs 一致
        """
        ...


class SequentialScheduler(JobScheduler):
    """顺序调度器：逐个执行，支持 stop_on_failure 中断"""
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFZOWVdRPT06NTI4ZDEyYjM=

    async def schedule(
        self,
        project_id: UUID,
        jobs: List[Any],
        run_job: Callable[[Any], Coroutine[Any, Any, ExecutionResult]],
        max_concurrency: int = 5,
    ) -> List[ExecutionResult]:
        results: List[ExecutionResult] = []
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFZOWVdRPT06NTI4ZDEyYjM=

        for job in jobs:
            result = await run_job(job)
            results.append(result)

            # 如果执行失败且配置了 stop_on_failure，中断后续作业
            if (
                not result.success
                and job.execution_config
                and job.execution_config.get("stop_on_failure")
            ):
                logger.info(
                    "[SequentialScheduler] 作业 %s 失败且 stop_on_failure=True，"
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

        return results


class ParallelScheduler(JobScheduler):
    """并行调度器：基于信号量限制并发数"""

    async def schedule(
        self,
        project_id: UUID,
        jobs: List[Any],
        run_job: Callable[[Any], Coroutine[Any, Any, ExecutionResult]],
        max_concurrency: int = 5,
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

        return processed
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFZOWVdRPT06NTI4ZDEyYjM=
