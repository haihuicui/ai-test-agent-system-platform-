"""Mock LLM 驱动的缺陷④图级回归测试。

不依赖真实 LLM：FakeMessagesListChatModel 按脚本依次返回
「AI1(save) → AI2(同签名 save) → AI3(结束语)」，验证在真实
make_agent 中间件栈中，DuplicateToolCallMiddleware 会拦截第二轮重复调用：
不产生第二个 ToolMessage，AI2 被剥离 tool_calls 并附加注记，模型继续。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel

# 在加载 testcase agent 之前 mock 掉 RAG MCP 工具加载，避免连接远程服务超时。
import app.agents.tools.testcase as _testcase_tools
_testcase_tools.get_rag_tools = AsyncMock(return_value=[])
from app.agents.tools.testcase.document_tools import get_rag_tools as _orig_get_rag_tools  # noqa: F401

from app.agents.testcase import make_agent
from app.agents.testcase.agent import TestCaseGeneratorContext as _TestCaseGeneratorContext
from app.agents.testcase.duplicate_tool_call_middleware import _INTERCEPT_MARK


class _ScriptedFakeChatModel(FakeMessagesListChatModel):
    """FakeMessagesListChatModel + bind_tools 支持（原版 bind_tools 直接
    raise NotImplementedError，无法进入真实 agent 图）。"""

    def bind_tools(self, tools, **kwargs):  # noqa: D102
        return self


def _valid_case(number: str) -> dict[str, Any]:
    return {
        "name": f"用例 {number}",
        "case_number": number,
        "module": "登录模块",
        "priority": "critical",
        "case_type": "functional",
        "test_data": {"username": "test001"},
        "test_case_steps": [{"step": "执行操作", "result": "页面显示字段=test001"}],
    }


_SAVE_ARGS = {
    "file_path": "test_cases_module_01.jsonl",
    "content": json.dumps(_valid_case("TC-PROJ-LOGIN-001"), ensure_ascii=False),
}


def _save_ai(call_id: str) -> AIMessage:
    return AIMessage(
        content="先保存 M1 用例。",
        tool_calls=[{"id": call_id, "name": "save_test_cases_file", "args": _SAVE_ARGS}],
    )


@pytest.fixture
def workspace_root(monkeypatch, tmp_path: Path):
    """把用例工具的工作目录指向临时目录，避免污染真实 workspace。"""
    from app.agents.tools.testcase import module_check_tools, excel_tools
    resolved = tmp_path.resolve()
    monkeypatch.setattr(excel_tools, "_WORKSPACE_ROOT", resolved)
    monkeypatch.setattr(module_check_tools, "_WORKSPACE_ROOT", resolved)
    return resolved


@pytest.mark.asyncio
async def test_duplicate_tool_call_intercepted_in_real_graph(workspace_root):
    """同签名整组重复调用在真实图中被拦截：只执行一次，无第二个 ToolMessage。"""
    fake_model = _ScriptedFakeChatModel(
        responses=[
            _save_ai("call_first"),
            _save_ai("call_second"),  # 与上一轮同名同参（id 全新）→ 应被拦截
            AIMessage(content="Mock 流程结束。"),
        ]
    )

    ctx = _TestCaseGeneratorContext(
        project_identifier="PR-DUP-E2E",
        folder_id="",
        template_type="test_case",
        enable_rag=False,
        auto_approve_threshold=100.0,
    )

    import importlib
    # 注意：不能写成 `import app.agents.testcase.agent as agent_mod`——
    # 包的 __init__.py 用 `from .agent import agent` 把包属性 agent 遮蔽成了
    # 函数，那样拿到的不是模块，替换 text_model 会静默失效、真实调用 LLM。
    agent_mod = importlib.import_module("app.agents.testcase.agent")
    agent_mod.text_model = fake_model
    agent_mod.image_model = fake_model

    async with make_agent(model=fake_model) as agent:
        state = await agent.ainvoke(
            {"messages": [HumanMessage(content="为登录功能设计测试用例")]},
            config={"recursion_limit": 25},
            context=ctx,
        )

    messages = state["messages"]

    # 1) save_test_cases_file 只执行了一次（重复调用被剥离，未进 tools 节点）
    tool_msgs = [m for m in messages if isinstance(m, ToolMessage) and m.name == "save_test_cases_file"]
    assert len(tool_msgs) == 1
    assert json.loads(tool_msgs[0].content)["success"] is True

    # 2) 第二轮 AI 被剥离 tool_calls 并附加拦截注记
    stripped_ai = next(
        m for m in messages
        if isinstance(m, AIMessage) and "已被系统拦截、未执行" in str(m.content)
    )
    assert stripped_ai.tool_calls == []

    # 3) 纠偏消息带防循环标记
    assert any(
        isinstance(m, HumanMessage) and (m.additional_kwargs or {}).get(_INTERCEPT_MARK)
        for m in messages
    )

    # 4) run 正常结束于结束语
    assert messages[-1].content == "Mock 流程结束。"

    # 5) 文件只写了第一轮的内容
    written = (workspace_root / "test_cases_module_01.jsonl").read_text(encoding="utf-8")
    assert len(written.strip().splitlines()) == 1
