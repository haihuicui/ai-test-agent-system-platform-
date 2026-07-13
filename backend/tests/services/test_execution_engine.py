"""
统一脚本执行引擎单元测试

覆盖 ScriptExecutionEngine 的最终状态推断逻辑。
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.enums import FailurePolicy, JobStatus, TestRunState
from app.services.execution.engine import ScriptExecutionEngine
from app.services.execution.models import ExecutionResult


class DummyTestRun:
    """模拟 TestRun ORM 对象"""

    def __init__(self, run_id, failure_policy=FailurePolicy.CONTINUE):
        self.id = run_id
        self.project_id = uuid4()
        self.execution_mode = "sequential"
        self.max_concurrency = 5
        self.failure_policy = failure_policy
        self.environment_id = None
        self.run_state = TestRunState.IN_PROGRESS


class DummyJob:
    """模拟 TestRunScriptJob"""

    def __init__(self):
        self.id = uuid4()
        self.script_id = uuid4()
        self.script_type = "api_test"
        self.execution_config = None
        self.execution_order = 0


def _make_session_factory(return_value):
    """返回一个同步 callable，调用后得到 async with 可用的异步上下文管理器"""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=return_value)
    cm.__aexit__ = AsyncMock(return_value=False)

    def factory():
        return cm

    return factory


class TestScriptExecutionEngineFinalState:
    @pytest.mark.asyncio
    async def test_all_success_results_in_done(self):
        run_id = uuid4()
        test_run = DummyTestRun(run_id)

        fake_session = MagicMock()
        fake_session.commit = AsyncMock()

        fake_run_repo = MagicMock()
        fake_run_repo.get_by_id = AsyncMock(return_value=test_run)
        fake_run_repo.update = AsyncMock(return_value=test_run)
        fake_run_repo.update_counts_from_jobs = AsyncMock()

        fake_job_repo = MagicMock()
        fake_job_repo.get_by_test_run = AsyncMock(return_value=([DummyJob()], 1))

        session_factory = _make_session_factory(fake_session)

        # 构造一个 engine，直接让 _run_job 返回成功结果
        engine = ScriptExecutionEngine()
        engine._run_job = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                status=JobStatus.COMPLETED.value,
            )
        )

        with patch(
            "app.services.execution.engine.async_session_factory", session_factory
        ):
            with patch(
                "app.services.execution.engine.TestRunRepository",
                return_value=fake_run_repo,
            ):
                with patch(
                    "app.services.execution.engine.TestRunScriptJobRepository",
                    return_value=fake_job_repo,
                ):
                    result = await engine.execute_run(run_id)

        assert test_run.run_state == TestRunState.DONE
        assert result["status"] == TestRunState.DONE.value

    @pytest.mark.asyncio
    async def test_assertion_failure_results_in_done_with_failures(self):
        run_id = uuid4()
        test_run = DummyTestRun(run_id, failure_policy=FailurePolicy.CONTINUE)

        fake_session = MagicMock()
        fake_session.commit = AsyncMock()

        fake_run_repo = MagicMock()
        fake_run_repo.get_by_id = AsyncMock(return_value=test_run)
        fake_run_repo.update = AsyncMock(return_value=test_run)
        fake_run_repo.update_counts_from_jobs = AsyncMock()

        fake_job_repo = MagicMock()
        fake_job_repo.get_by_test_run = AsyncMock(return_value=([DummyJob()], 1))

        session_factory = _make_session_factory(fake_session)

        engine = ScriptExecutionEngine()
        engine._run_job = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                status=JobStatus.FAILED.value,
                failure_category="assertion",
            )
        )

        with patch(
            "app.services.execution.engine.async_session_factory", session_factory
        ):
            with patch(
                "app.services.execution.engine.TestRunRepository",
                return_value=fake_run_repo,
            ):
                with patch(
                    "app.services.execution.engine.TestRunScriptJobRepository",
                    return_value=fake_job_repo,
                ):
                    result = await engine.execute_run(run_id)

        assert test_run.run_state == TestRunState.DONE_WITH_FAILURES
        assert result["status"] == TestRunState.DONE_WITH_FAILURES.value

    @pytest.mark.asyncio
    async def test_environment_error_results_in_rejected(self):
        run_id = uuid4()
        test_run = DummyTestRun(run_id, failure_policy=FailurePolicy.CONTINUE)

        fake_session = MagicMock()
        fake_session.commit = AsyncMock()

        fake_run_repo = MagicMock()
        fake_run_repo.get_by_id = AsyncMock(return_value=test_run)
        fake_run_repo.update = AsyncMock(return_value=test_run)
        fake_run_repo.update_counts_from_jobs = AsyncMock()

        fake_job_repo = MagicMock()
        fake_job_repo.get_by_test_run = AsyncMock(return_value=([DummyJob()], 1))

        session_factory = _make_session_factory(fake_session)

        engine = ScriptExecutionEngine()
        engine._run_job = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                status=JobStatus.FAILED.value,
                failure_category="environment",
            )
        )

        with patch(
            "app.services.execution.engine.async_session_factory", session_factory
        ):
            with patch(
                "app.services.execution.engine.TestRunRepository",
                return_value=fake_run_repo,
            ):
                with patch(
                    "app.services.execution.engine.TestRunScriptJobRepository",
                    return_value=fake_job_repo,
                ):
                    result = await engine.execute_run(run_id)

        assert test_run.run_state == TestRunState.REJECTED
        assert result["status"] == TestRunState.REJECTED.value

    @pytest.mark.asyncio
    async def test_mixed_assertion_and_environment_results_in_rejected(self):
        run_id = uuid4()
        test_run = DummyTestRun(run_id, failure_policy=FailurePolicy.CONTINUE)

        fake_session = MagicMock()
        fake_session.commit = AsyncMock()

        fake_run_repo = MagicMock()
        fake_run_repo.get_by_id = AsyncMock(return_value=test_run)
        fake_run_repo.update = AsyncMock(return_value=test_run)
        fake_run_repo.update_counts_from_jobs = AsyncMock()

        fake_job_repo = MagicMock()
        fake_job_repo.get_by_test_run = AsyncMock(
            return_value=([DummyJob(), DummyJob()], 2)
        )

        session_factory = _make_session_factory(fake_session)

        engine = ScriptExecutionEngine()
        engine._run_job = AsyncMock(side_effect=[
            ExecutionResult(
                success=False,
                status=JobStatus.FAILED.value,
                failure_category="assertion",
            ),
            ExecutionResult(
                success=False,
                status=JobStatus.FAILED.value,
                failure_category="environment",
            ),
        ])

        with patch(
            "app.services.execution.engine.async_session_factory", session_factory
        ):
            with patch(
                "app.services.execution.engine.TestRunRepository",
                return_value=fake_run_repo,
            ):
                with patch(
                    "app.services.execution.engine.TestRunScriptJobRepository",
                    return_value=fake_job_repo,
                ):
                    result = await engine.execute_run(run_id)

        assert test_run.run_state == TestRunState.REJECTED
        assert result["status"] == TestRunState.REJECTED.value

    @pytest.mark.asyncio
    async def test_empty_jobs_results_in_done(self):
        run_id = uuid4()
        test_run = DummyTestRun(run_id)

        fake_session = MagicMock()
        fake_session.commit = AsyncMock()

        fake_run_repo = MagicMock()
        fake_run_repo.get_by_id = AsyncMock(return_value=test_run)
        fake_run_repo.update = AsyncMock(return_value=test_run)
        fake_run_repo.update_counts_from_jobs = AsyncMock()

        fake_job_repo = MagicMock()
        fake_job_repo.get_by_test_run = AsyncMock(return_value=([], 0))

        session_factory = _make_session_factory(fake_session)

        engine = ScriptExecutionEngine()

        with patch(
            "app.services.execution.engine.async_session_factory", session_factory
        ):
            with patch(
                "app.services.execution.engine.TestRunRepository",
                return_value=fake_run_repo,
            ):
                with patch(
                    "app.services.execution.engine.TestRunScriptJobRepository",
                    return_value=fake_job_repo,
                ):
                    result = await engine.execute_run(run_id)

        assert test_run.run_state == TestRunState.DONE
        assert result["status"] == "done"

    @pytest.mark.asyncio
    async def test_failure_category_none_results_in_done_with_failures(self):
        """执行器未设置 failure_category 时，失败也不应进入 REJECTED"""
        run_id = uuid4()
        test_run = DummyTestRun(run_id, failure_policy=FailurePolicy.CONTINUE)

        fake_session = MagicMock()
        fake_session.commit = AsyncMock()

        fake_run_repo = MagicMock()
        fake_run_repo.get_by_id = AsyncMock(return_value=test_run)
        fake_run_repo.update = AsyncMock(return_value=test_run)
        fake_run_repo.update_counts_from_jobs = AsyncMock()

        fake_job_repo = MagicMock()
        fake_job_repo.get_by_test_run = AsyncMock(return_value=([DummyJob()], 1))

        session_factory = _make_session_factory(fake_session)

        engine = ScriptExecutionEngine()
        engine._run_job = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                status=JobStatus.FAILED.value,
                failure_category=None,  # 模拟旧执行器未分类
            )
        )

        with patch(
            "app.services.execution.engine.async_session_factory", session_factory
        ):
            with patch(
                "app.services.execution.engine.TestRunRepository",
                return_value=fake_run_repo,
            ):
                with patch(
                    "app.services.execution.engine.TestRunScriptJobRepository",
                    return_value=fake_job_repo,
                ):
                    result = await engine.execute_run(run_id)

        assert test_run.run_state == TestRunState.DONE_WITH_FAILURES
        assert result["status"] == TestRunState.DONE_WITH_FAILURES.value

    @pytest.mark.asyncio
    async def test_missing_count_infra_does_not_reject(self):
        """计数缺失时返回的 infra 不应把 TestRun 推成 REJECTED"""
        run_id = uuid4()
        test_run = DummyTestRun(run_id, failure_policy=FailurePolicy.CONTINUE)

        fake_session = MagicMock()
        fake_session.commit = AsyncMock()

        fake_run_repo = MagicMock()
        fake_run_repo.get_by_id = AsyncMock(return_value=test_run)
        fake_run_repo.update = AsyncMock(return_value=test_run)
        fake_run_repo.update_counts_from_jobs = AsyncMock()

        fake_job_repo = MagicMock()
        fake_job_repo.get_by_test_run = AsyncMock(return_value=([DummyJob()], 1))

        session_factory = _make_session_factory(fake_session)

        engine = ScriptExecutionEngine()
        engine._run_job = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                status=JobStatus.FAILED.value,
                failure_category="infra",
                has_missing_counts=True,
            )
        )

        with patch(
            "app.services.execution.engine.async_session_factory", session_factory
        ):
            with patch(
                "app.services.execution.engine.TestRunRepository",
                return_value=fake_run_repo,
            ):
                with patch(
                    "app.services.execution.engine.TestRunScriptJobRepository",
                    return_value=fake_job_repo,
                ):
                    result = await engine.execute_run(run_id)

        assert test_run.run_state == TestRunState.DONE_WITH_FAILURES
        assert result["status"] == TestRunState.DONE_WITH_FAILURES.value

    @pytest.mark.asyncio
    async def test_environment_error_still_rejects(self):
        """非缺失计数产生的 environment 错误仍应导致 REJECTED"""
        run_id = uuid4()
        test_run = DummyTestRun(run_id, failure_policy=FailurePolicy.CONTINUE)

        fake_session = MagicMock()
        fake_session.commit = AsyncMock()

        fake_run_repo = MagicMock()
        fake_run_repo.get_by_id = AsyncMock(return_value=test_run)
        fake_run_repo.update = AsyncMock(return_value=test_run)
        fake_run_repo.update_counts_from_jobs = AsyncMock()

        fake_job_repo = MagicMock()
        fake_job_repo.get_by_test_run = AsyncMock(return_value=([DummyJob()], 1))

        session_factory = _make_session_factory(fake_session)

        engine = ScriptExecutionEngine()
        engine._run_job = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                status=JobStatus.FAILED.value,
                failure_category="environment",
                has_missing_counts=False,
            )
        )

        with patch(
            "app.services.execution.engine.async_session_factory", session_factory
        ):
            with patch(
                "app.services.execution.engine.TestRunRepository",
                return_value=fake_run_repo,
            ):
                with patch(
                    "app.services.execution.engine.TestRunScriptJobRepository",
                    return_value=fake_job_repo,
                ):
                    result = await engine.execute_run(run_id)

        assert test_run.run_state == TestRunState.REJECTED
        assert result["status"] == TestRunState.REJECTED.value
