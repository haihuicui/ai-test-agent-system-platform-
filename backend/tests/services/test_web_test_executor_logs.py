"""
WebTestExecutor 执行日志单元测试
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.enums import JobStatus
from app.services.execution.executors import WebTestExecutor


class TestWebTestExecutorLogs:
    @pytest.mark.asyncio
    async def test_executor_fills_stdout_and_stderr(self):
        """WebTestExecutor 应轮询等待并返回 WebTestRun 的 stdout/stderr"""
        run_id = uuid4()
        script_id = uuid4()
        project_id = uuid4()

        fake_web_test = SimpleNamespace(
            id=script_id,
            project_id=project_id,
            name="登录流程",
        )
        fake_project = SimpleNamespace(
            id=project_id,
            identifier="PROJ-001",
        )
        fake_run = SimpleNamespace(
            id=run_id,
            status="completed",
            total_tests=2,
            passed_tests=2,
            failed_tests=0,
            skipped_tests=0,
            duration_ms=1500,
            error_message=None,
            report_path="web-reports/.../report.zip",
            stdout="Running 2 tests...\n2 passed",
            stderr="",
        )

        fake_session = MagicMock()
        fake_session.commit = AsyncMock()

        # session.get 用于查询 WebTest / Project
        async def fake_get(model, _id):
            if model.__name__ == "WebTest":
                return fake_web_test
            if model.__name__ == "Project":
                return fake_project
            return None

        fake_session.get = AsyncMock(side_effect=fake_get)

        fake_run_repo = MagicMock()
        fake_run_repo.get_by_id = AsyncMock(return_value=fake_run)

        fake_service = MagicMock()
        fake_service.run_web_test = AsyncMock(
            return_value={
                "run_id": str(run_id),
                "identifier": "WTR-20260713-001",
                "status": "pending",
            }
        )

        session_factory = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=fake_session)
        cm.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = cm

        with patch(
            "app.services.execution.executors.async_session_factory", session_factory
        ):
            with patch(
                "app.services.web_test_service.WebTestService",
                return_value=fake_service,
            ):
                with patch(
                    "app.repositories.web_test_repo.WebTestRepository",
                ) as mock_web_test_repo_cls:
                    mock_web_test_repo_cls.return_value = MagicMock(
                        get_by_id=AsyncMock(return_value=fake_web_test)
                    )
                    with patch(
                        "app.repositories.project_repo.ProjectRepository",
                    ) as mock_project_repo_cls:
                        mock_project_repo_cls.return_value = MagicMock(
                            get_by_id=AsyncMock(return_value=fake_project)
                        )
                        with patch(
                            "app.repositories.web_test_repo.WebTestRunRepository",
                        ) as mock_run_repo_cls:
                            mock_run_repo_cls.return_value = fake_run_repo
                            with patch(
                                "app.services.execution.executors.asyncio.sleep",
                                new=AsyncMock(),
                            ):
                                executor = WebTestExecutor()
                                result = await executor.execute(script_id, {})

        assert result.status == JobStatus.COMPLETED.value
        assert result.success is True
        assert "Running 2 tests" in result.stdout
        assert result.stderr == ""
        assert result.detail_run_id == str(run_id)
        assert result.report_path == fake_run.report_path

    @pytest.mark.asyncio
    async def test_executor_returns_stderr_on_failure(self):
        """失败时 stderr 应包含 Playwright 错误输出"""
        run_id = uuid4()
        script_id = uuid4()
        project_id = uuid4()

        fake_web_test = SimpleNamespace(
            id=script_id,
            project_id=project_id,
            name="登录流程",
        )
        fake_project = SimpleNamespace(
            id=project_id,
            identifier="PROJ-001",
        )
        fake_run = SimpleNamespace(
            id=run_id,
            status="failed",
            total_tests=1,
            passed_tests=0,
            failed_tests=1,
            skipped_tests=0,
            duration_ms=800,
            error_message="Test timeout of 5000ms exceeded",
            report_path=None,
            stdout="Running 1 test...",
            stderr="Error: page.waitForSelector: Test timeout of 5000ms exceeded",
        )

        fake_session = MagicMock()
        fake_session.commit = AsyncMock()

        async def fake_get(model, _id):
            if model.__name__ == "WebTest":
                return fake_web_test
            if model.__name__ == "Project":
                return fake_project
            return None

        fake_session.get = AsyncMock(side_effect=fake_get)

        fake_run_repo = MagicMock()
        fake_run_repo.get_by_id = AsyncMock(return_value=fake_run)

        fake_service = MagicMock()
        fake_service.run_web_test = AsyncMock(
            return_value={
                "run_id": str(run_id),
                "identifier": "WTR-20260713-002",
                "status": "pending",
            }
        )

        session_factory = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=fake_session)
        cm.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = cm

        with patch(
            "app.services.execution.executors.async_session_factory", session_factory
        ):
            with patch(
                "app.services.web_test_service.WebTestService",
                return_value=fake_service,
            ):
                with patch(
                    "app.repositories.web_test_repo.WebTestRepository",
                ) as mock_web_test_repo_cls:
                    mock_web_test_repo_cls.return_value = MagicMock(
                        get_by_id=AsyncMock(return_value=fake_web_test)
                    )
                    with patch(
                        "app.repositories.project_repo.ProjectRepository",
                    ) as mock_project_repo_cls:
                        mock_project_repo_cls.return_value = MagicMock(
                            get_by_id=AsyncMock(return_value=fake_project)
                        )
                        with patch(
                            "app.repositories.web_test_repo.WebTestRunRepository",
                        ) as mock_run_repo_cls:
                            mock_run_repo_cls.return_value = fake_run_repo
                            with patch(
                                "app.services.execution.executors.asyncio.sleep",
                                new=AsyncMock(),
                            ):
                                executor = WebTestExecutor()
                                result = await executor.execute(script_id, {})

        assert result.status == JobStatus.FAILED.value
        assert result.success is False
        assert result.failure_category == "timeout"
        assert "Running 1 test" in result.stdout
        assert "Test timeout" in result.stderr

    @pytest.mark.asyncio
    async def test_executor_timeout_when_run_does_not_finish(self):
        """后台任务一直未完成时，应返回 timeout 失败"""
        run_id = uuid4()
        script_id = uuid4()
        project_id = uuid4()

        fake_web_test = SimpleNamespace(
            id=script_id,
            project_id=project_id,
            name="登录流程",
        )
        fake_project = SimpleNamespace(
            id=project_id,
            identifier="PROJ-001",
        )
        # 一直处于 running 状态
        fake_run = SimpleNamespace(
            id=run_id,
            status="running",
        )

        fake_session = MagicMock()
        fake_session.commit = AsyncMock()

        async def fake_get(model, _id):
            if model.__name__ == "WebTest":
                return fake_web_test
            if model.__name__ == "Project":
                return fake_project
            return None

        fake_session.get = AsyncMock(side_effect=fake_get)

        fake_run_repo = MagicMock()
        fake_run_repo.get_by_id = AsyncMock(return_value=fake_run)

        fake_service = MagicMock()
        fake_service.run_web_test = AsyncMock(
            return_value={
                "run_id": str(run_id),
                "identifier": "WTR-20260713-003",
                "status": "pending",
            }
        )

        session_factory = MagicMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=fake_session)
        cm.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = cm

        with patch(
            "app.services.execution.executors.async_session_factory", session_factory
        ):
            with patch(
                "app.services.web_test_service.WebTestService",
                return_value=fake_service,
            ):
                with patch(
                    "app.repositories.web_test_repo.WebTestRepository",
                ) as mock_web_test_repo_cls:
                    mock_web_test_repo_cls.return_value = MagicMock(
                        get_by_id=AsyncMock(return_value=fake_web_test)
                    )
                    with patch(
                        "app.repositories.project_repo.ProjectRepository",
                    ) as mock_project_repo_cls:
                        mock_project_repo_cls.return_value = MagicMock(
                            get_by_id=AsyncMock(return_value=fake_project)
                        )
                        with patch(
                            "app.repositories.web_test_repo.WebTestRunRepository",
                        ) as mock_run_repo_cls:
                            mock_run_repo_cls.return_value = fake_run_repo
                            with patch(
                                "app.services.execution.executors.asyncio.sleep",
                                new=AsyncMock(),
                            ):
                                executor = WebTestExecutor()
                                result = await executor.execute(
                                    script_id, {"timeout": 4}
                                )

        assert result.status == JobStatus.FAILED.value
        assert result.failure_category == "timeout"
        assert "超过 4 秒" in result.error_message
