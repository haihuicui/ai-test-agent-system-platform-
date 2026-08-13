"""RAG 工具会话级 space_id 注入测试。

覆盖 _wrap_rag_tools_with_session_space 的三条规则：
缺省注入会话项目 / 显式冲突以会话项目为准 / 非会话上下文透传。
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.agents.tools.testcase.document_tools import _wrap_rag_tools_with_session_space
from app.utils.session_scope import session_project_ctx


class _FakeRagTool:
    """模拟 langchain-mcp-adapters 的 rag_* 工具（记录收到的 kwargs）。"""

    def __init__(self, name: str = "rag_query"):
        self.name = name
        self.calls: list[dict] = []

    async def _arun(self, *args, **kwargs):
        self.calls.append(kwargs)
        return "ok"


@pytest.fixture(autouse=True)
def _clean_ctx():
    token = session_project_ctx.set(None)
    yield
    session_project_ctx.reset(token)


class TestSessionSpaceInjection:
    @pytest.mark.asyncio
    async def test_injects_session_project_when_absent(self):
        tool = _FakeRagTool()
        _wrap_rag_tools_with_session_space([tool])
        token = session_project_ctx.set("proj-alpha")
        try:
            with patch(
                "app.agents.tools.testcase.document_tools.get_session_project",
                return_value="proj-alpha",
            ):
                await tool._arun(query="登录接口怎么测")
        finally:
            session_project_ctx.reset(token)
        assert tool.calls[0]["space_id"] == "proj-alpha"

    @pytest.mark.asyncio
    async def test_conflicting_space_id_overridden(self):
        tool = _FakeRagTool()
        _wrap_rag_tools_with_session_space([tool])
        with patch(
            "app.agents.tools.testcase.document_tools.get_session_project",
            return_value="proj-alpha",
        ):
            await tool._arun(query="x", space_id="proj-beta")
        assert tool.calls[0]["space_id"] == "proj-alpha"

    @pytest.mark.asyncio
    async def test_passthrough_without_session(self):
        """非会话上下文（get_session_project 返回 None）尊重调用方传参。"""
        tool = _FakeRagTool()
        _wrap_rag_tools_with_session_space([tool])
        with patch(
            "app.agents.tools.testcase.document_tools.get_session_project",
            return_value=None,
        ):
            await tool._arun(query="x", space_id="proj-beta")
            await tool._arun(query="y")
        assert tool.calls[0]["space_id"] == "proj-beta"
        assert "space_id" not in tool.calls[1]

    @pytest.mark.asyncio
    async def test_non_rag_tools_untouched(self):
        tool = _FakeRagTool(name="parse_document")
        _wrap_rag_tools_with_session_space([tool])
        with patch(
            "app.agents.tools.testcase.document_tools.get_session_project",
            return_value="proj-alpha",
        ):
            await tool._arun(url="http://x")
        assert "space_id" not in tool.calls[0]
