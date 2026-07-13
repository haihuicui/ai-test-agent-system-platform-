"""
执行调度器单元测试

覆盖 SequentialScheduler / ParallelScheduler 的失败策略行为。
"""

from uuid import uuid4

import pytest

from app.schemas.enums import FailurePolicy, JobStatus
from app.services.execution.models import ExecutionResult
from app.services.execution.schedulers import ParallelScheduler, SequentialScheduler


class DummyJob:
    """模拟 TestRunScriptJob 的最小属性集"""

    def __init__(self, execution_config=None):
        self.id = uuid4()
        self.execution_config = execution_config


async def _make_run_job(results):
    """返回一个按调用顺序从 results 中取出结果的 run_job 协程"""
    index = 0

    async def run_job(job):
        nonlocal index
        result = results[index]
        index += 1
        return result

    return run_job


class TestSequentialScheduler:
    @pytest.mark.asyncio
    async def test_continue_policy_keeps_running_after_failure(self):
        scheduler = SequentialScheduler()
        jobs = [DummyJob(), DummyJob(), DummyJob()]
        results = [
            ExecutionResult(success=True, status=JobStatus.COMPLETED.value),
            ExecutionResult(success=False, status=JobStatus.FAILED.value, failure_category="assertion"),
            ExecutionResult(success=True, status=JobStatus.COMPLETED.value),
        ]
        run_job = await _make_run_job(results)

        got = await scheduler.schedule(
            project_id=uuid4(),
            jobs=jobs,
            run_job=run_job,
            failure_policy=FailurePolicy.CONTINUE,
        )

        assert len(got) == 3
        assert got[0].success is True
        assert got[1].success is False
        assert got[2].success is True

    @pytest.mark.asyncio
    async def test_stop_run_policy_skips_remaining_jobs(self):
        scheduler = SequentialScheduler()
        jobs = [DummyJob(), DummyJob(), DummyJob()]
        results = [
            ExecutionResult(success=True, status=JobStatus.COMPLETED.value),
            ExecutionResult(success=False, status=JobStatus.FAILED.value, failure_category="assertion"),
            ExecutionResult(success=True, status=JobStatus.COMPLETED.value),
        ]
        run_job = await _make_run_job(results)

        got = await scheduler.schedule(
            project_id=uuid4(),
            jobs=jobs,
            run_job=run_job,
            failure_policy=FailurePolicy.STOP_RUN,
        )

        assert len(got) == 3
        assert got[0].success is True
        assert got[1].success is False
        assert got[2].status == JobStatus.SKIPPED.value
        assert got[2].error_message == "前置作业失败，已跳过"

    @pytest.mark.asyncio
    async def test_mark_blocked_policy_blocks_remaining_jobs(self):
        scheduler = SequentialScheduler()
        jobs = [DummyJob(), DummyJob(), DummyJob()]
        results = [
            ExecutionResult(success=True, status=JobStatus.COMPLETED.value),
            ExecutionResult(success=False, status=JobStatus.FAILED.value, failure_category="assertion"),
            ExecutionResult(success=True, status=JobStatus.COMPLETED.value),
        ]
        run_job = await _make_run_job(results)

        got = await scheduler.schedule(
            project_id=uuid4(),
            jobs=jobs,
            run_job=run_job,
            failure_policy=FailurePolicy.MARK_BLOCKED,
        )

        assert len(got) == 3
        assert got[0].success is True
        assert got[1].success is False
        assert got[2].status == JobStatus.BLOCKED.value
        assert got[2].error_message == "前置作业失败，已阻塞"

    @pytest.mark.asyncio
    async def test_stop_job_policy_same_as_continue(self):
        scheduler = SequentialScheduler()
        jobs = [DummyJob(), DummyJob(), DummyJob()]
        results = [
            ExecutionResult(success=True, status=JobStatus.COMPLETED.value),
            ExecutionResult(success=False, status=JobStatus.FAILED.value, failure_category="assertion"),
            ExecutionResult(success=True, status=JobStatus.COMPLETED.value),
        ]
        run_job = await _make_run_job(results)

        got = await scheduler.schedule(
            project_id=uuid4(),
            jobs=jobs,
            run_job=run_job,
            failure_policy=FailurePolicy.STOP_JOB,
        )

        assert len(got) == 3
        assert got[0].success is True
        assert got[1].success is False
        assert got[2].success is True

    @pytest.mark.asyncio
    async def test_backward_compatible_stop_on_failure(self):
        scheduler = SequentialScheduler()
        jobs = [
            DummyJob(execution_config={"stop_on_failure": True}),
            DummyJob(),
        ]
        results = [
            ExecutionResult(success=False, status=JobStatus.FAILED.value, failure_category="assertion"),
            ExecutionResult(success=True, status=JobStatus.COMPLETED.value),
        ]
        run_job = await _make_run_job(results)

        got = await scheduler.schedule(
            project_id=uuid4(),
            jobs=jobs,
            run_job=run_job,
            failure_policy=FailurePolicy.CONTINUE,
        )

        assert len(got) == 2
        assert got[0].success is False
        assert got[1].status == JobStatus.SKIPPED.value


class TestParallelScheduler:
    @pytest.mark.asyncio
    async def test_continue_policy_runs_all_jobs(self):
        scheduler = ParallelScheduler()
        jobs = [DummyJob(), DummyJob(), DummyJob()]

        async def run_job(job):
            # 第二个 job 失败，其他成功
            if job == jobs[1]:
                return ExecutionResult(success=False, status=JobStatus.FAILED.value, failure_category="assertion")
            return ExecutionResult(success=True, status=JobStatus.COMPLETED.value)

        got = await scheduler.schedule(
            project_id=uuid4(),
            jobs=jobs,
            run_job=run_job,
            failure_policy=FailurePolicy.CONTINUE,
        )

        assert len(got) == 3
        assert got[0].success is True
        assert got[1].success is False
        assert got[2].success is True

    @pytest.mark.asyncio
    async def test_stop_run_policy_overrides_results_after_first_failure(self):
        scheduler = ParallelScheduler()
        jobs = [DummyJob(), DummyJob(), DummyJob()]

        async def run_job(job):
            if job == jobs[1]:
                return ExecutionResult(success=False, status=JobStatus.FAILED.value, failure_category="assertion")
            return ExecutionResult(success=True, status=JobStatus.COMPLETED.value)

        got = await scheduler.schedule(
            project_id=uuid4(),
            jobs=jobs,
            run_job=run_job,
            failure_policy=FailurePolicy.STOP_RUN,
        )

        assert len(got) == 3
        assert got[0].success is True
        assert got[1].success is False
        assert got[2].status == JobStatus.SKIPPED.value

    @pytest.mark.asyncio
    async def test_mark_blocked_policy_overrides_results_after_first_failure(self):
        scheduler = ParallelScheduler()
        jobs = [DummyJob(), DummyJob(), DummyJob()]

        async def run_job(job):
            if job == jobs[1]:
                return ExecutionResult(success=False, status=JobStatus.FAILED.value, failure_category="assertion")
            return ExecutionResult(success=True, status=JobStatus.COMPLETED.value)

        got = await scheduler.schedule(
            project_id=uuid4(),
            jobs=jobs,
            run_job=run_job,
            failure_policy=FailurePolicy.MARK_BLOCKED,
        )

        assert len(got) == 3
        assert got[0].success is True
        assert got[1].success is False
        assert got[2].status == JobStatus.BLOCKED.value
