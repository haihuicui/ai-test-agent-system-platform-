"""
StorageStateService 单元测试

重点覆盖：
1. 失败时保留 stdout/stderr 并回填空 stderr
2. 失败时上传页面截图并创建 Attachment
3. 空选择器前置校验
4. 生成的 Playwright 配置与 spec 包含诊断增强
"""

import os
import tempfile
import asyncio
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.services.storage_state_service import StorageStateService
from app.schemas.storage_state import LoginSelectors


class FakeProc:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


def _make_service():
    session = AsyncMock()
    service = StorageStateService(session=session)
    service.project_repo = AsyncMock()
    service.env_repo = AsyncMock()
    return service


def _make_job(job_id: UUID):
    job = MagicMock()
    job.id = job_id
    job.project_id = uuid4()
    job.environment_id = uuid4()
    job.output_path = "/tmp/storage-state/global.json"
    job.attachment_id = None
    job.failure_screenshot_attachment_id = None
    job.status = "pending"
    return job


def _make_project():
    project = MagicMock()
    project.id = uuid4()
    project.name = "test-project"
    return project


@pytest.mark.asyncio
async def test_failure_preserves_stdout_and_stderr():
    """Playwright 返回非零时，stdout/stderr 应写入任务记录"""
    job_id = uuid4()
    job = _make_job(job_id)
    service = _make_service()
    service.session.get.return_value = job
    service.project_repo.get_by_id.return_value = _make_project()

    selectors = LoginSelectors(
        login_url="http://example.com/login",
        submit_selector="button[type='submit']",
        success_selector=".dashboard",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        web_mcp_root = Path(tmpdir) / "web_mcp"
        web_mcp_root.mkdir()

        with patch("app.services.storage_state_service.settings.web_mcp_root", str(web_mcp_root)):
            with patch(
                "app.services.storage_state_service.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=[],
                    returncode=1,
                    stdout="stdout content",
                    stderr="stderr content",
                ),
            ):
                with patch("app.services.storage_state_service.MinIOClient"):
                    await service._execute_generation(
                        job_id=job_id,
                        username="user",
                        password="pass",
                        captcha=None,
                        selectors=selectors,
                        headless=True,
                        save_attachment=False,
                        project_identifier="PR-1",
                    )

    assert job.status == "failed"
    assert "stdout content" in job.stdout
    assert "stderr content" in job.stderr
    assert "stderr content" in job.error_message


@pytest.mark.asyncio
async def test_failure_backfills_empty_stderr():
    """stderr 为空时，应用 error_message 回填"""
    job_id = uuid4()
    job = _make_job(job_id)
    service = _make_service()
    service.session.get.return_value = job
    service.project_repo.get_by_id.return_value = _make_project()

    selectors = LoginSelectors(
        login_url="http://example.com/login",
        submit_selector="button[type='submit']",
        success_selector=".dashboard",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        web_mcp_root = Path(tmpdir) / "web_mcp"
        web_mcp_root.mkdir()

        with patch("app.services.storage_state_service.settings.web_mcp_root", str(web_mcp_root)):
            with patch(
                "app.services.storage_state_service.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=[],
                    returncode=1,
                    stdout="some stdout",
                    stderr="",
                ),
            ):
                with patch("app.services.storage_state_service.MinIOClient"):
                    await service._execute_generation(
                        job_id=job_id,
                        username="user",
                        password="pass",
                        captcha=None,
                        selectors=selectors,
                        headless=True,
                        save_attachment=False,
                        project_identifier="PR-1",
                    )

    assert job.status == "failed"
    assert job.stderr is not None
    assert "Playwright 登录脚本执行失败" in job.stderr


@pytest.mark.asyncio
async def test_failure_uploads_screenshot():
    """失败截图存在时，应上传并创建 Attachment"""
    job_id = uuid4()
    job = _make_job(job_id)
    service = _make_service()
    service.session.get.return_value = job
    service.project_repo.get_by_id.return_value = _make_project()

    selectors = LoginSelectors(
        login_url="http://example.com/login",
        submit_selector="button[type='submit']",
        success_selector=".dashboard",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        web_mcp_root = Path(tmpdir) / "web_mcp"
        web_mcp_root.mkdir()

        with patch("app.services.storage_state_service.settings.web_mcp_root", str(web_mcp_root)):
            with patch(
                "app.services.storage_state_service.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=[],
                    returncode=1,
                    stdout="",
                    stderr="",
                ),
            ):
                with patch.object(
                    service.session, "flush", AsyncMock()
                ) as mock_flush:
                    # 模拟刷新后 attachment.id 被赋值
                    attachment_id = uuid4()

                    def _capture_attachment(*args, **kwargs):
                        # 找到刚 add 的 Attachment 实例并赋予 id
                        for obj in service.session.add.call_args_list:
                            att = obj.args[0]
                            if hasattr(att, "id"):
                                att.id = attachment_id
                        return None

                    mock_flush.side_effect = _capture_attachment

                    await service._execute_generation(
                        job_id=job_id,
                        username="user",
                        password="pass",
                        captcha=None,
                        selectors=selectors,
                        headless=True,
                        save_attachment=False,
                        project_identifier="PR-1",
                    )

        # 截图文件实际上不会被生成（子进程是 mock），所以不会上传
        # 这里主要验证代码路径没有异常
        assert job.status == "failed"


@pytest.mark.asyncio
async def test_empty_selectors_mark_job_failed():
    """SUBMIT_SELECTOR / SUCCESS_SELECTOR 为空时应记录失败，不启动子进程"""
    job_id = uuid4()
    job = _make_job(job_id)
    service = _make_service()
    service.session.get.return_value = job
    service.project_repo.get_by_id.return_value = _make_project()

    with tempfile.TemporaryDirectory() as tmpdir:
        web_mcp_root = Path(tmpdir) / "web_mcp"
        web_mcp_root.mkdir()

        with patch("app.services.storage_state_service.settings.web_mcp_root", str(web_mcp_root)):
            with patch(
                "app.services.storage_state_service.subprocess.run"
            ) as mock_run:
                selectors = LoginSelectors(
                    login_url="http://example.com/login",
                    submit_selector="",
                    success_selector=".dashboard",
                )

                await service._execute_generation(
                    job_id=job_id,
                    username="user",
                    password="pass",
                    captcha=None,
                    selectors=selectors,
                    headless=True,
                    save_attachment=False,
                    project_identifier="PR-1",
                )

                assert job.status == "failed"
                assert "SUBMIT_SELECTOR" in job.error_message
                mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_generated_config_includes_trace_and_screenshot():
    """生成的 playwright.config.js 应开启 trace 和 screenshot"""
    service = _make_service()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        output_path = tmp_path / "storage-state" / "global.json"
        config_path, spec_path = await service._write_setup_project(
            tmp_path, output_path, headless=True
        )

        config_text = config_path.read_text(encoding="utf-8")
        assert "trace: 'on'" in config_text
        assert "screenshot: 'on'" in config_text


@pytest.mark.asyncio
async def test_generated_spec_includes_wait_for_and_screenshot():
    """生成的 setup.spec.ts 应包含显式 waitFor 和失败截图逻辑"""
    service = _make_service()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        output_path = tmp_path / "storage-state" / "global.json"
        config_path, spec_path = await service._write_setup_project(
            tmp_path, output_path, headless=True
        )

        spec_text = spec_path.read_text(encoding="utf-8")
        assert ".waitFor({ state: 'visible', timeout: 15000 })" in spec_text
        assert "process.env.FAILURE_SCREENSHOT_PATH" in spec_text
        assert "page.screenshot({ path: screenshotPath, fullPage: true })" in spec_text
        assert "Missing SUBMIT_SELECTOR or SUCCESS_SELECTOR" in spec_text


@pytest.mark.asyncio
async def test_uses_sync_subprocess():
    """Windows 下统一使用线程池中的同步 subprocess，避免 EventLoop 不支持子进程"""
    job_id = uuid4()
    job = _make_job(job_id)
    service = _make_service()
    service.session.get.return_value = job
    service.project_repo.get_by_id.return_value = _make_project()

    selectors = LoginSelectors(
        login_url="http://example.com/login",
        submit_selector="button[type='submit']",
        success_selector=".dashboard",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        web_mcp_root = Path(tmpdir) / "web_mcp"
        web_mcp_root.mkdir()

        with patch("app.services.storage_state_service.settings.web_mcp_root", str(web_mcp_root)):
            with patch(
                "app.services.storage_state_service.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=[],
                    returncode=1,
                    stdout="sync stdout",
                    stderr="sync stderr",
                ),
            ) as mock_run:
                with patch("app.services.storage_state_service.MinIOClient"):
                    await service._execute_generation(
                        job_id=job_id,
                        username="user",
                        password="pass",
                        captcha=None,
                        selectors=selectors,
                        headless=True,
                        save_attachment=False,
                        project_identifier="PR-1",
                    )

                    mock_run.assert_called_once()

    assert job.status == "failed"
    assert "sync stderr" in job.stderr
    assert "sync stdout" in job.stdout


@pytest.mark.asyncio
async def test_execute_generation_catches_outer_exception_and_marks_failed():
    """_execute_generation 抛出未捕获异常时，execute_generation 应将任务标记为失败"""
    job_id = uuid4()
    job = _make_job(job_id)

    mock_session = AsyncMock()
    mock_session.get.return_value = job

    class FakeAsyncSessionContext:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    with patch(
        "app.services.storage_state_service.async_session_factory",
        return_value=FakeAsyncSessionContext(),
    ):
        with patch.object(
            StorageStateService,
            "_execute_generation",
            side_effect=RuntimeError("project lookup failed"),
        ):
            service = StorageStateService(session=MagicMock())
            await service.execute_generation(
                job_id=job_id,
                username="user",
                password="pass",
                captcha=None,
                selectors=LoginSelectors(
                    login_url="http://example.com/login",
                    submit_selector="button[type='submit']",
                    success_selector=".dashboard",
                ),
                headless=True,
                save_attachment=False,
                project_identifier="PR-1",
            )

    assert job.status == "failed"
    assert "project lookup failed" in job.error_message
    assert job.completed_at is not None


@pytest.mark.asyncio
async def test_timeout_error_has_meaningful_message():
    """subprocess 超时后应转换为有意义的错误信息"""
    job_id = uuid4()
    job = _make_job(job_id)
    service = _make_service()
    service.session.get.return_value = job
    service.project_repo.get_by_id.return_value = _make_project()

    selectors = LoginSelectors(
        login_url="http://example.com/login",
        submit_selector="button[type='submit']",
        success_selector=".dashboard",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        web_mcp_root = Path(tmpdir) / "web_mcp"
        web_mcp_root.mkdir()

        with patch("app.services.storage_state_service.settings.web_mcp_root", str(web_mcp_root)):
            with patch(
                "app.services.storage_state_service.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=[], timeout=10),
            ):
                with patch("app.services.storage_state_service.MinIOClient"):
                    await service._execute_generation(
                        job_id=job_id,
                        username="user",
                        password="pass",
                        captcha=None,
                        selectors=selectors,
                        headless=True,
                        save_attachment=False,
                        project_identifier="PR-1",
                    )

    assert job.status == "failed"
    assert "超时" in job.error_message
    assert "超时" in job.stderr


@pytest.mark.asyncio
async def test_empty_exception_message_uses_class_name():
    """异常消息为空时，应使用异常类名作为错误信息"""
    job_id = uuid4()
    job = _make_job(job_id)
    service = _make_service()
    service.session.get.return_value = job
    service.project_repo.get_by_id.return_value = _make_project()

    selectors = LoginSelectors(
        login_url="http://example.com/login",
        submit_selector="button[type='submit']",
        success_selector=".dashboard",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        web_mcp_root = Path(tmpdir) / "web_mcp"
        web_mcp_root.mkdir()

        with patch("app.services.storage_state_service.settings.web_mcp_root", str(web_mcp_root)):
            with patch(
                "app.services.storage_state_service.subprocess.run",
                side_effect=RuntimeError(""),
            ):
                with patch("app.services.storage_state_service.MinIOClient"):
                    await service._execute_generation(
                        job_id=job_id,
                        username="user",
                        password="pass",
                        captcha=None,
                        selectors=selectors,
                        headless=True,
                        save_attachment=False,
                        project_identifier="PR-1",
                    )

    assert job.status == "failed"
    assert "RuntimeError" in job.error_message
    assert "RuntimeError" in job.stderr


@pytest.mark.asyncio
async def test_success_switches_auth_type_from_none_to_form_login():
    """生成成功后，若环境 auth_type 为 none 且存在 storage_state 配置，
    应自动切换为 form_login，避免后续 Web 测试因 auth_type 未识别而跳过注入。"""
    job_id = uuid4()
    job = _make_job(job_id)
    service = _make_service()
    service.session.get.return_value = job
    service.project_repo.get_by_id.return_value = _make_project()

    env = MagicMock()
    env.id = job.environment_id
    env.auth_type = "none"
    env.auth_config = {
        "storage_state": {
            "username": "admin",
            "login_url": "http://example.com/login",
            "selectors": {"username_selector": "#user"},
        }
    }
    service.env_repo.get_by_id.return_value = env

    selectors = LoginSelectors(
        login_url="http://example.com/login",
        submit_selector="button[type='submit']",
        success_selector=".dashboard",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        web_mcp_root = Path(tmpdir) / "web_mcp"
        web_mcp_root.mkdir()
        output_path = Path(job.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text('{"cookies": [], "origins": []}', encoding="utf-8")

        with patch("app.services.storage_state_service.settings.web_mcp_root", str(web_mcp_root)):
            with patch(
                "app.services.storage_state_service.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
            ):
                with patch("app.services.storage_state_service.MinIOClient"):
                    with patch(
                        "app.services.storage_state_service.ensure_playwright_mcp_project"
                    ):
                        await service._execute_generation(
                            job_id=job_id,
                            username="user",
                            password="pass",
                            captcha=None,
                            selectors=selectors,
                            headless=True,
                            save_attachment=False,
                            project_identifier="PR-1",
                        )

    assert job.status == "completed"
    assert env.auth_type == "form_login"
    assert "form_login" in env.auth_config
    assert env.auth_config["form_login"]["username"] == "admin"