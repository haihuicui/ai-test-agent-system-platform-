"""web_mcp agent 辅助逻辑单元测试：工具白名单解析 + 登录态解析缓存。

覆盖：
- parse_mcp_tool_whitelist：默认核心集 / full 关闭过滤 / 自定义列表
- 核心集完整性：主流程必需工具在内，重型/冷僻工具被裁掉
- _resolve_project_login_state：缓存命中跳过 DB；DB 异常返回默认值且不缓存
"""

import pytest

from app.agents.web_mcp import agent as agent_module
from app.agents.web_mcp.agent import (
    CORE_MCP_TOOLS,
    _login_state_cache,
    _resolve_project_login_state,
    parse_mcp_tool_whitelist,
)


class TestParseMcpToolWhitelist:
    def test_default_returns_core_set(self):
        assert parse_mcp_tool_whitelist("") is CORE_MCP_TOOLS
        assert parse_mcp_tool_whitelist(None) is CORE_MCP_TOOLS
        assert parse_mcp_tool_whitelist("   ") is CORE_MCP_TOOLS

    @pytest.mark.parametrize("raw", ["full", "FULL", "all", "ALL", "*"])
    def test_full_keywords_disable_filtering(self, raw):
        assert parse_mcp_tool_whitelist(raw) is None

    def test_custom_list(self):
        result = parse_mcp_tool_whitelist("browser_navigate, browser_click ,,")
        assert result == frozenset({"browser_navigate", "browser_click"})

    def test_core_set_covers_main_flow(self):
        required = {
            "planner_setup_page",  # browser_* 前置铁律
            "browser_navigate", "browser_click", "browser_type",
            "browser_fill_form", "browser_select_option",  # 结账表单
            "browser_snapshot", "browser_wait_for",
            "test_run", "generator_write_test",
        }
        assert required <= CORE_MCP_TOOLS

    def test_core_set_trims_heavy_tools(self):
        excluded = {
            "browser_pdf_save", "browser_start_video", "browser_stop_video",
            "browser_mouse_move_xy", "browser_mouse_down", "browser_mouse_up",
            "browser_start_tracing", "browser_route", "browser_annotate",
            "planner_save_plan", "planner_submit_plan",  # 另有 excluded 集合兜底
        }
        assert excluded.isdisjoint(CORE_MCP_TOOLS)


class TestBuildWebAgentModel:
    def test_thinking_disabled_by_default(self, monkeypatch):
        monkeypatch.setattr(agent_module.settings, "web_agent_disable_thinking", True)
        m = agent_module.build_web_agent_model()
        assert m.extra_body == {"thinking": {"type": "disabled"}}
        # 独立于共享单例，不影响其他 agent 的推理能力
        assert m is not agent_module.model

    def test_thinking_enabled_returns_shared_singleton(self, monkeypatch):
        monkeypatch.setattr(agent_module.settings, "web_agent_disable_thinking", False)
        assert agent_module.build_web_agent_model() is agent_module.model


class TestResolveProjectLoginStateCache:
    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        _login_state_cache.clear()
        yield
        _login_state_cache.clear()

    @pytest.mark.asyncio
    async def test_cache_hit_skips_db(self, monkeypatch):
        import asyncio

        now = asyncio.get_running_loop().time()
        _login_state_cache["PR-1"] = (now, True, "/tmp/ss.json")

        def _boom():
            raise AssertionError("缓存命中时不应触碰 DB")

        monkeypatch.setattr(agent_module, "async_session_factory", _boom)
        has_login, ss = await _resolve_project_login_state("PR-1")
        assert (has_login, ss) == (True, "/tmp/ss.json")

    @pytest.mark.asyncio
    async def test_db_error_returns_default_and_not_cached(self, monkeypatch):
        def _boom():
            raise RuntimeError("db down")

        monkeypatch.setattr(agent_module, "async_session_factory", _boom)
        has_login, ss = await _resolve_project_login_state("PR-9")
        assert (has_login, ss) == (False, None)
        assert "PR-9" not in _login_state_cache
