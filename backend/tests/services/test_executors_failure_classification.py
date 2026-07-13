"""
Playwright / Web 测试执行器失败分类单元测试

覆盖旧数据 NULL 计数或仅有错误消息时的分类行为。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.enums import JobStatus
from app.services.execution.executors import PlaywrightExecutor, WebTestExecutor


def _make_session_factory(fake_session):
    """构造异步 session 工厂 mock"""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=fake_session)
    cm.__aexit__ = AsyncMock(return_value=False)

    def factory():
        return cm

    return factory


class TestPlaywrightExecutorFailureClassification:
    async def _execute_with_run(self, run):
        fake_session = MagicMock()
        fake_session.commit = AsyncMock()

        fake_run_repo = MagicMock()
        fake_run_repo.get_by_id = AsyncMock(return_value=run)

        session_factory = _make_session_factory(fake_session)

        with patch(
            "app.services.execution.executors.async_session_factory", session_factory
        ):
            with patch(
                "app.services.api_test_executor.APITestExecutor.execute_test",
                new_callable=AsyncMock,
                return_value=str(uuid4()),
            ):
                with patch(
                    "app.repositories.api_test_repo.APITestRunRepository",
                    return_value=fake_run_repo,
                ):
                    executor = PlaywrightExecutor()
                    return await executor.execute(uuid4(), {})

    def _make_run(
        self,
        status="failed",
        total_tests=None,
        passed_tests=None,
        failed_tests=None,
        skipped_tests=None,
        error_message=None,
    ):
        return SimpleNamespace(
            id=uuid4(),
            status=status,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            error_message=error_message,
            report_path=None,
            stdout=None,
            stderr=None,
        )

    @pytest.mark.asyncio
    async def test_null_failed_tests_with_assertion_message_is_assertion(self):
        run = self._make_run(
            total_tests=None,
            passed_tests=None,
            failed_tests=None,
            skipped_tests=None,
            error_message="expected 200 but got 404",
        )

        result = await self._execute_with_run(run)

        assert result.failure_category == "assertion"
        assert result.has_missing_counts is True

    @pytest.mark.asyncio
    async def test_null_failed_tests_with_environment_message_is_environment(self):
        run = self._make_run(
            total_tests=None,
            passed_tests=None,
            failed_tests=None,
            skipped_tests=None,
            error_message="npx playwright not found",
        )

        result = await self._execute_with_run(run)

        assert result.failure_category == "environment"
        assert result.has_missing_counts is True

    @pytest.mark.asyncio
    async def test_null_failed_tests_with_no_signals_is_infra(self):
        run = self._make_run(
            total_tests=None,
            passed_tests=None,
            failed_tests=None,
            skipped_tests=None,
            error_message="",
        )

        result = await self._execute_with_run(run)

        assert result.failure_category == "infra"
        assert result.has_missing_counts is True

    @pytest.mark.asyncio
    async def test_failed_count_greater_than_zero_is_assertion(self):
        run = self._make_run(
            total_tests=2,
            passed_tests=1,
            failed_tests=1,
            skipped_tests=0,
            error_message="",
        )

        result = await self._execute_with_run(run)

        assert result.failure_category == "assertion"
        assert result.has_missing_counts is False


class TestWebTestExecutorFailureClassification:
    async def _execute_with_run(self, web_test, project, run):
        fake_session = MagicMock()
        fake_session.commit = AsyncMock()

        fake_web_test_repo = MagicMock()
        fake_web_test_repo.get_by_id = AsyncMock(return_value=web_test)

        fake_project_repo = MagicMock()
        fake_project_repo.get_by_id = AsyncMock(return_value=project)

        fake_run_repo = MagicMock()
        fake_run_repo.get_by_id = AsyncMock(return_value=run)

        fake_service = MagicMock()
        fake_service.run_web_test = AsyncMock(
            return_value={"run_id": str(run.id), "status": "started"}
        )

        session_factory = _make_session_factory(fake_session)

        with patch(
            "app.services.execution.executors.async_session_factory", session_factory
        ):
            with patch(
                "app.repositories.web_test_repo.WebTestRepository",
                return_value=fake_web_test_repo,
            ):
                with patch(
                    "app.repositories.project_repo.ProjectRepository",
                    return_value=fake_project_repo,
                ):
                    with patch(
                        "app.repositories.web_test_repo.WebTestRunRepository",
                        return_value=fake_run_repo,
                    ):
                        with patch(
                            "app.services.web_test_service.WebTestService",
                            return_value=fake_service,
                        ):
                            executor = WebTestExecutor()
                            return await executor.execute(web_test.id, {})

    def _make_web_test(self):
        return SimpleNamespace(id=uuid4(), project_id=uuid4())

    def _make_project(self):
        return SimpleNamespace(identifier="test-project")

    def _make_run(
        self,
        status="failed",
        total_tests=2,
        passed_tests=1,
        failed_tests=1,
        skipped_tests=0,
        error_message=None,
    ):
        return SimpleNamespace(
            id=uuid4(),
            status=status,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            error_message=error_message,
            report_path=None,
            stdout=None,
            stderr=None,
        )

    @pytest.mark.asyncio
    async def test_assertion_message_is_assertion(self):
        web_test = self._make_web_test()
        project = self._make_project()
        run = self._make_run(error_message="AssertionError: expected visible")

        result = await self._execute_with_run(web_test, project, run)

        assert result.failure_category == "assertion"

    @pytest.mark.asyncio
    async def test_environment_message_is_environment(self):
        web_test = self._make_web_test()
        project = self._make_project()
        run = self._make_run(error_message="browser driver not found")

        result = await self._execute_with_run(web_test, project, run)

        assert result.failure_category == "environment"

    @pytest.mark.asyncio
    async def test_timeout_message_is_timeout(self):
        web_test = self._make_web_test()
        project = self._make_project()
        run = self._make_run(error_message="test timed out after 30s")

        result = await self._execute_with_run(web_test, project, run)

        assert result.failure_category == "timeout"
