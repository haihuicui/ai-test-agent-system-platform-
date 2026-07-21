"""
WebTestService._run_playwright_test 单元测试

重点覆盖：Playwright 测试失败时，错误信息通常位于 JSON 报告的 case.error 中，
而非 stderr。需要确保 stderr/error 能从 JSON 报告中回填，避免前端日志弹窗为空。
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.web_test_service import WebTestService


class FakeProc:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


class TestRunPlaywrightTest:
    @pytest.mark.asyncio
    async def test_fills_stderr_and_error_from_json_report_when_empty(self):
        """Playwright 返回非零但 stderr 为空时，应从 JSON 报告提取失败用例错误"""
        service = WebTestService(session=MagicMock())

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "playwright.config.ts")
            results_path = os.path.join(tmpdir, "results.json")

            # 写一份包含失败用例的 JSON 报告
            report = {
                "config": {},
                "suites": [
                    {
                        "title": "checkout",
                        "file": "web-test.spec.ts",
                        "specs": [
                            {
                                "title": "完成结账",
                                "file": "web-test.spec.ts",
                                "tests": [
                                    {
                                        "status": "unexpected",
                                        "results": [
                                            {
                                                "status": "failed",
                                                "duration": 1200,
                                                "error": {
                                                    "message": "Error: expect(received).toBe(expected) // Object.is equality",
                                                    "stack": "...",
                                                },
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "stats": {
                    "expected": 0,
                    "unexpected": 1,
                    "flaky": 0,
                    "skipped": 0,
                    "duration": 2500,
                },
            }
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump(report, f)

            # 第一次 create_subprocess_exec 是 npx --version 检查
            # 第二次是 playwright test
            def fake_create_subprocess(*args, **kwargs):
                if "--version" in args:
                    return FakeProc(0, b"10.0.0", b"")
                # 真正的 playwright test：返回非零，stderr 为空
                return FakeProc(1, b"", b"")

            with patch(
                "app.services.web_test_service.asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess,
            ):
                with patch(
                    "app.services.web_test_service.asyncio.wait_for",
                    new=lambda coro, timeout: coro,
                ):
                    result = await service._run_playwright_test(
                        workspace_root=tmpdir,
                        config_path=config_path,
                        execution_config={},
                    )

        assert result["success"] is False
        assert result["failed"] == 1
        # stderr 原本为空，应被 JSON 报告中的错误信息回填
        assert "完成结账" in result["stderr"]
        assert "expect(received).toBe(expected)" in result["stderr"]
        # error 字段同步有值，最终进入 WebTestRun.error_message / ScriptJob.error_message
        assert result["error"] is not None
        assert "完成结账" in result["error"]

    @pytest.mark.asyncio
    async def test_keeps_original_stderr_when_not_empty(self):
        """stderr 不为空时，应优先保留原始 stderr，不做覆盖"""
        service = WebTestService(session=MagicMock())

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "playwright.config.ts")
            results_path = os.path.join(tmpdir, "results.json")

            report = {
                "config": {},
                "suites": [
                    {
                        "title": "checkout",
                        "file": "web-test.spec.ts",
                        "specs": [
                            {
                                "title": "完成结账",
                                "file": "web-test.spec.ts",
                                "tests": [
                                    {
                                        "status": "unexpected",
                                        "results": [
                                            {
                                                "status": "failed",
                                                "duration": 1200,
                                                "error": {
                                                    "message": "JSON error message",
                                                },
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "stats": {
                    "expected": 0,
                    "unexpected": 1,
                    "flaky": 0,
                    "skipped": 0,
                    "duration": 2500,
                },
            }
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump(report, f)

            def fake_create_subprocess(*args, **kwargs):
                if "--version" in args:
                    return FakeProc(0, b"10.0.0", b"")
                return FakeProc(1, b"", b"original stderr message")

            with patch(
                "app.services.web_test_service.asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess,
            ):
                with patch(
                    "app.services.web_test_service.asyncio.wait_for",
                    new=lambda coro, timeout: coro,
                ):
                    result = await service._run_playwright_test(
                        workspace_root=tmpdir,
                        config_path=config_path,
                        execution_config={},
                    )

        assert result["success"] is False
        assert result["stderr"] == "original stderr message"
        assert result["error"] == "original stderr message"

    @pytest.mark.asyncio
    async def test_success_does_not_fill_error(self):
        """成功时 error 应为 None，stderr 保持原样"""
        service = WebTestService(session=MagicMock())

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "playwright.config.ts")
            results_path = os.path.join(tmpdir, "results.json")

            report = {
                "config": {},
                "suites": [
                    {
                        "title": "checkout",
                        "file": "web-test.spec.ts",
                        "specs": [
                            {
                                "title": "完成结账",
                                "file": "web-test.spec.ts",
                                "tests": [
                                    {
                                        "status": "expected",
                                        "results": [
                                            {
                                                "status": "passed",
                                                "duration": 1200,
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "stats": {
                    "expected": 1,
                    "unexpected": 0,
                    "flaky": 0,
                    "skipped": 0,
                    "duration": 2500,
                },
            }
            with open(results_path, "w", encoding="utf-8") as f:
                json.dump(report, f)

            def fake_create_subprocess(*args, **kwargs):
                if "--version" in args:
                    return FakeProc(0, b"10.0.0", b"")
                return FakeProc(0, b"1 passed", b"")

            with patch(
                "app.services.web_test_service.asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess,
            ):
                with patch(
                    "app.services.web_test_service.asyncio.wait_for",
                    new=lambda coro, timeout: coro,
                ):
                    result = await service._run_playwright_test(
                        workspace_root=tmpdir,
                        config_path=config_path,
                        execution_config={},
                    )

        assert result["success"] is True
        assert result["error"] is None
        assert result["stderr"] == ""
        assert "1 passed" in result["stdout"]

    @pytest.mark.asyncio
    async def test_json_parse_failure_falls_back_to_stdout(self):
        """JSON 解析失败且 stderr 为空时，应用 stdout 兜底"""
        service = WebTestService(session=MagicMock())

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "playwright.config.ts")
            # 故意不写合法的 results.json，让 JSON 解析失败

            def fake_create_subprocess(*args, **kwargs):
                if "--version" in args:
                    return FakeProc(0, b"10.0.0", b"")
                return FakeProc(1, b"some stdout output", b"")

            with patch(
                "app.services.web_test_service.asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess,
            ):
                with patch(
                    "app.services.web_test_service.asyncio.wait_for",
                    new=lambda coro, timeout: coro,
                ):
                    result = await service._run_playwright_test(
                        workspace_root=tmpdir,
                        config_path=config_path,
                        execution_config={},
                    )

        assert result["success"] is False
        assert result["stderr"] == "some stdout output"
        assert result["error"] == "some stdout output"

    @pytest.mark.asyncio
    async def test_timeout_and_exception_fill_stderr(self):
        """超时与异常路径也应保证 stderr 不为空"""
        service = WebTestService(session=MagicMock())

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "playwright.config.ts")

            def fake_create_subprocess(*args, **kwargs):
                if "--version" in args:
                    return FakeProc(0, b"10.0.0", b"")
                raise RuntimeError("subprocess exploded")

            with patch(
                "app.services.web_test_service.asyncio.create_subprocess_exec",
                side_effect=fake_create_subprocess,
            ):
                with patch(
                    "app.services.web_test_service.asyncio.wait_for",
                    new=lambda coro, timeout: coro,
                ):
                    result = await service._run_playwright_test(
                        workspace_root=tmpdir,
                        config_path=config_path,
                        execution_config={},
                    )

        assert result["success"] is False
        assert "subprocess exploded" in result["error"]
        assert "subprocess exploded" in result["stderr"]
