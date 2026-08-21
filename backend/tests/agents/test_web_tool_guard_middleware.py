"""WebToolGuardMiddleware 与 storageState 运行时探针单元测试。

覆盖（thread 681b9d01 实证场景）：
- probe_storage_state_liveness：401/403 判失效；2xx/404 放行；异常 fail-open
- WebToolGuardMiddleware.awrap_tool_call：browser_* 工具超时返回 ToolCallTimeout
  ToolMessage；非浏览器工具不介入；正常调用不受影响
- awrap_model_call：尾部连续 >=2 条 run_code_unsafe 错误时注入一次性纠偏消息
"""

import asyncio
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import SystemMessage, ToolMessage

from app.agents.web_mcp.tool_guard_middleware import (
    WebToolGuardMiddleware,
    _GUARD_NUDGE_PREFIX,
)
from app.config.settings import settings
from app.utils.web_mcp_storage_state import probe_storage_state_liveness


# ---------------------------------------------------------------------------
# probe_storage_state_liveness
# ---------------------------------------------------------------------------


def _write_storage_state(tmp_path, *, token="tok-123"):
    ss = {
        "cookies": [
            {"name": "Authorization", "value": token, "domain": "x.example.com"}
        ],
        "origins": [],
    }
    path = tmp_path / "ss.json"
    path.write_text(json.dumps(ss), encoding="utf-8")
    return str(path)


class _FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


class _FakeAsyncClient:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, headers=None):
        if self._exc:
            raise self._exc
        return self._response


class TestProbeStorageStateLiveness:
    @pytest.mark.asyncio
    async def test_401_marks_invalid(self, tmp_path, monkeypatch):
        import httpx

        monkeypatch.setattr(
            httpx, "AsyncClient",
            lambda **kw: _FakeAsyncClient(_FakeResponse(401)),
        )
        alive, reason = await probe_storage_state_liveness(
            _write_storage_state(tmp_path), "https://x.example.com"
        )
        assert alive is False
        assert "401" in reason

    @pytest.mark.asyncio
    async def test_200_and_404_pass(self, tmp_path, monkeypatch):
        import httpx

        for status in (200, 404):
            monkeypatch.setattr(
                httpx, "AsyncClient",
                lambda **kw: _FakeAsyncClient(_FakeResponse(status)),
            )
            alive, _ = await probe_storage_state_liveness(
                _write_storage_state(tmp_path), "https://x.example.com"
            )
            assert alive is True, f"status={status} 不应判失效"

    @pytest.mark.asyncio
    async def test_network_error_fails_open(self, tmp_path, monkeypatch):
        import httpx

        monkeypatch.setattr(
            httpx, "AsyncClient",
            lambda **kw: _FakeAsyncClient(exc=ConnectionError("down")),
        )
        alive, reason = await probe_storage_state_liveness(
            _write_storage_state(tmp_path), "https://x.example.com"
        )
        assert alive is True
        assert "放行" in reason

    @pytest.mark.asyncio
    async def test_no_token_skips(self, tmp_path):
        path = tmp_path / "ss.json"
        path.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")
        alive, reason = await probe_storage_state_liveness(
            str(path), "https://x.example.com"
        )
        assert alive is True
        assert "跳过" in reason


# ---------------------------------------------------------------------------
# WebToolGuardMiddleware
# ---------------------------------------------------------------------------


def _make_request(tool_name: str, messages=None):
    return SimpleNamespace(
        tool_call={"name": tool_name, "id": "call-1", "args": {}},
        messages=messages or [],
        override=lambda messages: SimpleNamespace(
            tool_call={"name": tool_name, "id": "call-1", "args": {}},
            messages=messages,
            override=None,
        ),
    )


class TestToolCallTimeout:
    @pytest.mark.asyncio
    async def test_browser_tool_timeout_returns_error_tool_message(self, monkeypatch):
        monkeypatch.setattr(settings, "web_mcp_tool_call_timeout_seconds", 1)
        mw = WebToolGuardMiddleware()

        async def slow_handler(request):
            await asyncio.sleep(30)
            return ToolMessage(content="ok", tool_call_id="call-1", name="browser_snapshot")

        result = await mw.awrap_tool_call(_make_request("browser_snapshot"), slow_handler)
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert result.tool_call_id == "call-1"
        payload = json.loads(result.content)
        assert payload["error_type"] == "ToolCallTimeout"
        assert "401" in payload["message"]  # 诊断指引指向认证失效场景

    @pytest.mark.asyncio
    async def test_normal_call_passthrough(self):
        mw = WebToolGuardMiddleware()

        async def handler(request):
            return ToolMessage(content="ok", tool_call_id="call-1", name="browser_click")

        result = await mw.awrap_tool_call(_make_request("browser_click"), handler)
        assert result.content == "ok"
        assert result.status != "error"

    @pytest.mark.asyncio
    async def test_non_browser_tool_not_guarded(self, monkeypatch):
        # 非 browser_/planner_ 前缀的工具即使很慢也不应被超时逻辑触碰
        monkeypatch.setattr(settings, "web_mcp_tool_call_timeout_seconds", 0)
        mw = WebToolGuardMiddleware()

        async def handler(request):
            return ToolMessage(content="ok", tool_call_id="call-1", name="write_todos")

        result = await mw.awrap_tool_call(_make_request("write_todos"), handler)
        assert result.content == "ok"


class TestRunCodeFailureGuard:
    def _error_msg(self):
        return ToolMessage(
            content='{"success": false}',
            tool_call_id="c1",
            name="browser_run_code_unsafe",
            status="error",
        )

    @pytest.mark.asyncio
    async def test_nudge_injected_after_two_consecutive_failures(self):
        mw = WebToolGuardMiddleware()
        messages = [self._error_msg(), self._error_msg()]
        captured = {}

        async def handler(request):
            captured["messages"] = request.messages
            return SimpleNamespace(result=[])

        await mw.awrap_model_call(_make_request("model", messages), handler)
        nudges = [
            m for m in captured["messages"]
            if isinstance(m, SystemMessage) and m.content.startswith(_GUARD_NUDGE_PREFIX)
        ]
        assert len(nudges) == 1
        assert "browser_snapshot" in nudges[0].content

    @pytest.mark.asyncio
    async def test_no_nudge_below_threshold_or_after_success(self):
        mw = WebToolGuardMiddleware()

        async def handler(request):
            return SimpleNamespace(result=[])

        # 单条失败不触发
        req = _make_request("model", [self._error_msg()])
        await mw.awrap_model_call(req, handler)  # 无异常即可

        # 失败被其他工具结果打断不触发
        ok_msg = ToolMessage(content="ok", tool_call_id="c9", name="browser_snapshot")
        messages = [self._error_msg(), self._error_msg(), ok_msg]
        assert mw._count_trailing_run_code_failures(messages) == 0

    @pytest.mark.asyncio
    async def test_ai_message_breaks_trailing_count(self):
        from langchain_core.messages import AIMessage

        mw = WebToolGuardMiddleware()
        # nudge 不落 state，模型响应（AIMessage）天然打断尾部连败计数，
        # 因此不会因同一批失败重复注入
        messages = [self._error_msg(), self._error_msg(), AIMessage(content="重试")]
        assert mw._count_trailing_run_code_failures(messages) == 0
