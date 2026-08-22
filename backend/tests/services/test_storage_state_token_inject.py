"""token_inject 模式 token 提取的重试与诊断测试。

背景：2026-08-21 两次生成任务失败（a3803ef2 / 332cad62），错误只有
"JSONPath '$.data.token' 未匹配到任何值"，响应体未落日志，无法回溯；
且失败与成功在分钟内交替出现，疑似瞬时错误包络，重试一次可自愈。
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.services.storage_state_service import StorageStateService


class _FakeResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _QueueClient:
    """按队列依次返回响应的 httpx.AsyncClient 替身。"""

    queue: list = []

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def request(self, method, url, json=None, content=None):
        return _QueueClient.queue.pop(0)

    async def get(self, url, params=None):
        return _QueueClient.queue.pop(0)


def _make_service():
    service = StorageStateService(session=AsyncMock())
    return service


def _token_inject():
    return {
        "token_url": "https://x.example.com/api/auth/token/",
        "token_body": {"username": "u", "password": "p"},
        "token_path": "$.data.token",
        "target_domains": ["x.example.com"],
    }


class TestTokenInjectExtract:
    @pytest.mark.asyncio
    async def test_error_envelope_twice_raises_with_response_body(self, monkeypatch):
        """两次都返回错误包络 → RuntimeError 必须带响应体摘要（可回溯）。"""
        import httpx

        monkeypatch.setattr(httpx, "AsyncClient", _QueueClient)
        monkeypatch.setattr("asyncio.sleep", AsyncMock())  # 跳过重试等待
        _QueueClient.queue = [
            _FakeResp({"code": "4001", "message": "验证码错误", "data": None}),
            _FakeResp({"code": "4001", "message": "验证码错误", "data": None}),
        ]
        service = _make_service()

        with pytest.raises(RuntimeError) as exc_info:
            await service._generate_by_token_inject(
                job_id=uuid4(),
                token_inject=_token_inject(),
                output_path=Path("/tmp/ss-test/out.json"),
                headless=True,
            )
        msg = str(exc_info.value)
        assert "提取 token 失败" in msg
        assert "验证码错误" in msg  # 响应体摘要进入错误信息
        assert len(_QueueClient.queue) == 0  # 恰好重试一次

    @pytest.mark.asyncio
    async def test_retry_succeeds_after_transient_error_envelope(
        self, monkeypatch, tmp_path
    ):
        """第一次错误包络、第二次成功 → 正常走完提取并进入注入阶段。"""
        import httpx

        monkeypatch.setattr(httpx, "AsyncClient", _QueueClient)
        monkeypatch.setattr("asyncio.sleep", AsyncMock())
        _QueueClient.queue = [
            _FakeResp({"code": "4001", "message": "验证码错误", "data": None}),
            _FakeResp({"code": "2000", "data": {"token": "tok-abc"}}),
        ]
        monkeypatch.setattr(
            "app.services.storage_state_service.settings.web_mcp_root",
            str(tmp_path),
        )
        service = _make_service()
        # 跳过真实 Playwright 子进程
        service._run_playwright_subprocess = AsyncMock(return_value=("", "", 0))

        await service._generate_by_token_inject(
            job_id=uuid4(),
            token_inject=_token_inject(),
            output_path=tmp_path / "out.json",
            headless=True,
        )
        service._run_playwright_subprocess.assert_awaited_once()
        # 注入脚本包含提取到的 token
        spec_files = list(tmp_path.rglob("token-inject.spec.ts"))
        assert spec_files, "应生成注入脚本"
        assert "tok-abc" in spec_files[0].read_text(encoding="utf-8")
