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
from app.utils.web_mcp_storage_state import (
    DEFAULT_PROBE_INVALID_PATTERN,
    judge_probe_response,
    probe_storage_state_liveness,
)


class TestJudgeProbeResponse:
    """业务层失效识别：xmetrix-sit 实证 token 过期返回 200+{"code":"4003"} 而非 401。"""

    def test_401_and_403_invalid(self):
        assert judge_probe_response(401, "")[0] is False
        assert judge_probe_response(403, "")[0] is False

    def test_200_with_expired_envelope_invalid(self):
        ok, reason = judge_probe_response(
            200, '{"code":"4003","message":"登陆已过期"}'
        )
        assert ok is False
        assert "失效特征" in reason

    def test_200_normal_body_valid(self):
        assert judge_probe_response(200, '{"code":"2000","data":[]}')[0] is True

    def test_404_and_500_not_invalid(self):
        # 404 可能只是探针路径不存在；5xx 是服务端问题，均不判失效
        assert judge_probe_response(404, "not found")[0] is True
        assert judge_probe_response(500, "server error")[0] is True

    def test_custom_pattern_override(self):
        import re

        pattern = re.compile(r'"code":\s*"9100"')
        assert judge_probe_response(200, '{"code":"9100"}', pattern)[0] is False
        # 自定义 pattern 不命中默认关键词时放行
        assert judge_probe_response(200, '{"code":"2000"}', pattern)[0] is True

    def test_default_pattern_no_false_positive_on_normal_text(self):
        assert DEFAULT_PROBE_INVALID_PATTERN.search('{"message":"success"}') is None


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

    async def request(self, method, url, headers=None, json=None):
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
    async def test_200_business_expired_envelope_marks_invalid(self, tmp_path, monkeypatch):
        """200 + {"code":"4003","message":"登陆已过期"} 必须判失效（xmetrix 实证形态）。"""
        import httpx

        monkeypatch.setattr(
            httpx, "AsyncClient",
            lambda **kw: _FakeAsyncClient(
                _FakeResponse(200, '{"code":"4003","message":"登陆已过期"}')
            ),
        )
        alive, reason = await probe_storage_state_liveness(
            _write_storage_state(tmp_path), "https://x.example.com"
        )
        assert alive is False
        assert "失效特征" in reason

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


class TestLoginStateRegen:
    @pytest.mark.asyncio
    async def test_timeout_triggers_regen_and_returns_recovery_steps(self, monkeypatch):
        """超时 + 重建成功 → ToolMessage 含 browser_close/planner_setup_page 恢复指引。"""
        monkeypatch.setattr(settings, "web_mcp_tool_call_timeout_seconds", 1)
        mw = WebToolGuardMiddleware()

        async def fake_regen():
            return True, "ok", 12.0

        monkeypatch.setattr(mw, "_try_regenerate_login_state", fake_regen)

        async def slow_handler(request):
            await asyncio.sleep(30)

        result = await mw.awrap_tool_call(_make_request("browser_snapshot"), slow_handler)
        payload = json.loads(result.content)
        assert payload["login_state_regenerated"] is True
        assert "browser_close" in payload["message"]
        assert "planner_setup_page" in payload["message"]

    @pytest.mark.asyncio
    async def test_regen_failure_falls_back_to_timeout_diagnosis(self, monkeypatch):
        """重建失败 → 仍返回原超时诊断文案并附失败原因。"""
        monkeypatch.setattr(settings, "web_mcp_tool_call_timeout_seconds", 1)
        mw = WebToolGuardMiddleware()

        async def fake_regen():
            return False, "环境未保存可用登录凭据（form_login/token_inject）", 0.1

        monkeypatch.setattr(mw, "_try_regenerate_login_state", fake_regen)

        async def slow_handler(request):
            await asyncio.sleep(30)

        result = await mw.awrap_tool_call(_make_request("browser_click"), slow_handler)
        payload = json.loads(result.content)
        assert payload["login_state_regenerated"] is False
        assert "401" in payload["message"]
        assert "未保存可用登录凭据" in payload["message"]

    @pytest.mark.asyncio
    async def test_regen_attempted_at_most_once_per_run(self):
        """每 run 限一次：旗标置位后直接短路，不触 DB/续期链路。"""
        mw = WebToolGuardMiddleware()
        mw._regen_attempted = True
        ok, note, _ = await mw._try_regenerate_login_state()
        assert ok is False
        assert "已尝试过" in note

    @pytest.mark.asyncio
    async def test_regen_skipped_without_project_identifier(self):
        """LangGraph 上下文外（无 project_identifier）直接判不可重建。"""
        mw = WebToolGuardMiddleware()
        ok, note, _ = await mw._try_regenerate_login_state()
        assert ok is False
        assert "project_identifier" in note


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


# ============================================================================
# storage-state 目录访问拦截（凭证防泄漏）+ dynamic_bearer 就地刷新
# ============================================================================


def _make_fs_request(tool_name: str, args: dict):
    return SimpleNamespace(
        tool_call={"name": tool_name, "id": "call-fs", "args": args},
    )


class TestStorageStateAccessBlocked:
    """storage-state 目录含登录凭证，文件/shell 工具访问必须被拦截。"""

    @pytest.mark.asyncio
    async def test_read_file_blocked(self):
        mw = WebToolGuardMiddleware()

        async def handler(request):
            return ToolMessage(content="ok", tool_call_id="call-fs", name="read_file")

        req = _make_fs_request("read_file", {"file_path": "/storage-state/p/e/job.json"})
        result = await mw.awrap_tool_call(req, handler)
        assert result.status == "error"
        payload = json.loads(result.content)
        assert "禁止访问" in payload["error"]

    @pytest.mark.asyncio
    async def test_execute_command_blocked(self):
        mw = WebToolGuardMiddleware()

        async def handler(request):
            return ToolMessage(content="ok", tool_call_id="call-fs", name="execute")

        req = _make_fs_request("execute", {"command": "cat storage-state/global.json"})
        result = await mw.awrap_tool_call(req, handler)
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_normal_path_passthrough(self):
        mw = WebToolGuardMiddleware()

        async def handler(request):
            return ToolMessage(content="ok", tool_call_id="call-fs", name="read_file")

        req = _make_fs_request("read_file", {"file_path": "/skills/web_mcp/planner/SKILL.md"})
        result = await mw.awrap_tool_call(req, handler)
        assert result.content == "ok"
        assert result.status != "error"


class TestRefreshStorageStateToken:
    """dynamic_bearer 续期：就地替换 token，保留 userInfo 等其余数据。"""

    def _write_ss(self, tmp_path):
        ss = {
            "cookies": [{"name": "Authorization", "value": "old-token"}],
            "origins": [
                {
                    "origin": "https://x.example.com",
                    "localStorage": [
                        {"name": "token", "value": "old-token"},
                        {"name": "userInfo", "value": '{"username":"root"}'},
                    ],
                }
            ],
        }
        p = tmp_path / "ss.json"
        p.write_text(json.dumps(ss), encoding="utf-8")
        return p

    @pytest.mark.asyncio
    async def test_refresh_replaces_token_keeps_userinfo(self, tmp_path):
        from app.utils.web_mcp_storage_state import refresh_storage_state_token

        p = self._write_ss(tmp_path)
        ok, note = await refresh_storage_state_token(str(p), "new-token")
        assert ok is True

        data = json.loads(p.read_text(encoding="utf-8"))
        ls = data["origins"][0]["localStorage"]
        assert next(i for i in ls if i["name"] == "token")["value"] == "new-token"
        assert next(i for i in ls if i["name"] == "userInfo")["value"] == '{"username":"root"}'
        assert data["cookies"][0]["value"] == "new-token"

    @pytest.mark.asyncio
    async def test_refresh_no_token_fields_fails(self, tmp_path):
        from app.utils.web_mcp_storage_state import refresh_storage_state_token

        p = tmp_path / "ss.json"
        p.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")
        ok, note = await refresh_storage_state_token(str(p), "new-token")
        assert ok is False
        assert "未找到" in note
