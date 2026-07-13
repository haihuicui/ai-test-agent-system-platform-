"""
ScenarioExecutor 执行日志格式化单元测试
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.enums import JobStatus
from app.services.execution.executors import ScenarioExecutor
from app.services.execution.log_utils import format_scenario_log


class DummySettings:
    """模拟配置对象"""

    api_test_sensitive_headers = [
        "authorization",
        "cookie",
        "x-api-key",
        "x-auth-token",
    ]
    api_test_sensitive_body_fields = [
        "password",
        "token",
        "secret",
        "apikey",
        "api_key",
        "accesstoken",
        "refreshtoken",
        "auth_token",
    ]
    api_test_body_truncate_threshold = 50_000
    api_test_body_preview_length = 2_000


def _make_run(**overrides):
    """构造模拟 ScenarioRun"""
    defaults = {
        "scenario_name": "测试场景",
        "identifier": "TSR-20260713-123456",
        "status": "completed",
        "duration_ms": 1234,
        "total_steps": 2,
        "passed_steps": 2,
        "failed_steps": 0,
        "skipped_steps": 0,
        "error_message": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_step_result(**overrides):
    """构造模拟 ScenarioStepResult"""
    defaults = {
        "step_name": "登录",
        "step_order": 1,
        "status": "passed",
        "duration_ms": 234,
        "full_url": "http://example.com/api/login",
        "request_data": {
            "method": "post",
            "headers": {"Content-Type": "application/json"},
            "body": {"username": "test", "password": "secret123"},
        },
        "response_data": {
            "status": 200,
            "headers": {"Content-Type": "application/json"},
            "body": {"token": "abc.def.ghi"},
        },
        "assertion_results": [
            {
                "assertion": {"type": "status", "expected": 200, "operator": "eq"},
                "passed": True,
                "actual": 200,
                "expected": 200,
                "message": "状态码等于 200",
            }
        ],
        "extracted_data": {"token": "abc.def.ghi"},
        "error_message": None,
        "error_stack": None,
        "step": SimpleNamespace(name="登录"),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestFormatScenarioLog:
    def test_successful_scenario_log(self):
        run = _make_run()
        step = _make_step_result()

        stdout, stderr = format_scenario_log(run, [step], DummySettings())

        assert "测试场景" in stdout
        assert "TSR-20260713-123456" in stdout
        assert "登录" in stdout
        assert "POST http://example.com/api/login" in stdout
        assert "状态码等于 200" in stdout
        assert stderr == ""

    def test_failed_scenario_log(self):
        run = _make_run(
            status="failed",
            passed_steps=0,
            failed_steps=1,
            error_message="步骤 1 失败: 断言失败",
        )
        step = _make_step_result(
            status="failed",
            assertion_results=[
                {
                    "assertion": {"type": "status", "expected": 201, "operator": "eq"},
                    "passed": False,
                    "actual": 200,
                    "expected": 201,
                    "message": "状态码等于 201",
                }
            ],
            error_message="断言失败",
            error_stack="Traceback: ...",
        )

        stdout, stderr = format_scenario_log(run, [step], DummySettings())

        assert "失败 1" in stdout
        assert "✗ 状态码等于 201" in stdout
        assert "实际值: 200" in stdout
        assert "期望值: 201" in stdout
        assert "场景执行失败: 步骤 1 失败: 断言失败" in stderr
        assert "断言失败" in stderr
        assert "Traceback: ..." in stderr

    def test_sensitive_headers_and_body_redacted(self):
        run = _make_run()
        step = _make_step_result(
            request_data={
                "method": "post",
                "headers": {
                    "Authorization": "Bearer secret-token",
                    "Cookie": "session=abc",
                    "Content-Type": "application/json",
                },
                "body": {"username": "test", "password": "secret123"},
            },
            response_data={
                "status": 200,
                "headers": {"X-Auth-Token": "token-value"},
                "body": {"token": "secret"},
            },
        )

        stdout, stderr = format_scenario_log(run, [step], DummySettings())

        assert "Authorization" in stdout
        assert "secret-token" not in stdout
        assert "session=abc" not in stdout
        assert "secret123" not in stdout
        assert '"Authorization": "***"' in stdout
        assert '"Cookie": "***"' in stdout
        assert '"password": "***"' in stdout

    def test_large_body_truncated(self):
        run = _make_run()
        large_body = {"data": "x" * 60_000}
        step = _make_step_result(
            response_data={
                "status": 200,
                "headers": {},
                "body": large_body,
            },
        )

        stdout, stderr = format_scenario_log(run, [step], DummySettings())

        assert "...[truncated]" in stdout
        assert len(stdout) < 80_000


class TestScenarioExecutorLogs:
    @pytest.mark.asyncio
    async def test_executor_fills_stdout_and_stderr(self):
        run_id = uuid4()
        scenario_id = uuid4()

        fake_run = _make_run(
            id=run_id,
            scenario_id=scenario_id,
            scenario_name="集成场景",
            status="completed",
        )
        fake_step = _make_step_result(
            step_name="获取用户信息",
            full_url="http://example.com/api/users/1",
        )

        fake_session = MagicMock()
        fake_session.commit = AsyncMock()
        fake_session.get = AsyncMock(return_value=MagicMock(name="集成场景"))

        fake_engine = MagicMock()
        fake_engine.execute = AsyncMock(return_value=fake_run)

        fake_step_result_query = MagicMock()
        fake_step_result_query.scalars.return_value.all.return_value = [fake_step]

        # session.execute 返回可等待对象；首次调用用于查询步骤结果
        async def execute_async(stmt):
            return fake_step_result_query

        fake_session.execute = execute_async

        session_factory = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=fake_session)
        cm.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = cm

        with patch(
            "app.services.execution.executors.async_session_factory", session_factory
        ):
            with patch(
                "app.services.scenario_execution_engine.ScenarioExecutionEngine",
                return_value=fake_engine,
            ):
                with patch(
                    "app.services.execution.executors.generate_scenario_report",
                    return_value="<html></html>",
                ):
                    with patch(
                        "app.services.execution.executors.MinIOClient.upload_bytes",
                    ):
                        executor = ScenarioExecutor()
                        result = await executor.execute(scenario_id, {})

        assert result.stdout != ""
        assert "集成场景" in result.stdout
        assert "获取用户信息" in result.stdout
        assert result.stderr == ""
        assert result.status == JobStatus.COMPLETED.value


class TestScenarioExecutorFailureClassification:
    """验证 ScenarioExecutor 对旧数据 NULL 计数的容错分类"""

    async def _execute_with_run(self, fake_run, fake_steps):
        fake_session = MagicMock()
        fake_session.commit = AsyncMock()
        fake_session.get = AsyncMock(return_value=MagicMock(name="场景"))

        fake_engine = MagicMock()
        fake_engine.execute = AsyncMock(return_value=fake_run)

        fake_step_result_query = MagicMock()
        fake_step_result_query.scalars.return_value.all.return_value = fake_steps

        async def execute_async(stmt):
            return fake_step_result_query

        fake_session.execute = execute_async

        session_factory = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=fake_session)
        cm.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = cm

        with patch(
            "app.services.execution.executors.async_session_factory", session_factory
        ):
            with patch(
                "app.services.scenario_execution_engine.ScenarioExecutionEngine",
                return_value=fake_engine,
            ):
                with patch(
                    "app.services.execution.executors.generate_scenario_report",
                    return_value="<html></html>",
                ):
                    with patch(
                        "app.services.execution.executors.MinIOClient.upload_bytes",
                    ):
                        executor = ScenarioExecutor()
                        return await executor.execute(uuid4(), {})

    @pytest.mark.asyncio
    async def test_null_failed_steps_with_failed_step_is_assertion(self):
        run = _make_run(
            id=uuid4(),
            scenario_id=uuid4(),
            status="failed",
            total_steps=None,
            passed_steps=None,
            failed_steps=None,
            skipped_steps=None,
            error_message=None,
        )
        step = _make_step_result(status="failed", error_message="断言失败")

        result = await self._execute_with_run(run, [step])

        assert result.failure_category == "assertion"
        assert result.has_missing_counts is True

    @pytest.mark.asyncio
    async def test_null_failed_steps_with_assertion_message_is_assertion(self):
        run = _make_run(
            id=uuid4(),
            scenario_id=uuid4(),
            status="failed",
            total_steps=None,
            passed_steps=None,
            failed_steps=None,
            skipped_steps=None,
            error_message="步骤 1 断言失败: expected 200 but got 404",
        )
        step = _make_step_result(status="passed")

        result = await self._execute_with_run(run, [step])

        assert result.failure_category == "assertion"
        assert result.has_missing_counts is True

    @pytest.mark.asyncio
    async def test_null_failed_steps_with_environment_message_is_environment(self):
        run = _make_run(
            id=uuid4(),
            scenario_id=uuid4(),
            status="failed",
            total_steps=None,
            passed_steps=None,
            failed_steps=None,
            skipped_steps=None,
            error_message="npx playwright not found",
        )
        step = _make_step_result(status="passed")

        result = await self._execute_with_run(run, [step])

        assert result.failure_category == "environment"
        assert result.has_missing_counts is True

    @pytest.mark.asyncio
    async def test_zero_failed_steps_with_no_signals_is_infra(self):
        run = _make_run(
            id=uuid4(),
            scenario_id=uuid4(),
            status="failed",
            total_steps=2,
            passed_steps=2,
            failed_steps=0,
            skipped_steps=0,
            error_message="",
        )
        step = _make_step_result(status="passed")

        result = await self._execute_with_run(run, [step])

        assert result.failure_category == "infra"
        assert result.has_missing_counts is False
