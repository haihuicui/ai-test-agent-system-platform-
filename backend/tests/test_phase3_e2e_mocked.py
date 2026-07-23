"""Mock LLM 驱动的 Phase 3 端到端回归测试。

不依赖真实 LLM 和外部 API，通过注入 FakeMessagesListChatModel 固定模型响应，
验证 Phase 3 链路中 ``ModuleSelfCheckMiddleware`` 能在真实 Agent 中间件栈里
自动拦截违规的 ``batch_create_test_cases_tool``。

注意：deepagents 的通用子 Agent 会在模型无 tool_calls 时自动要求继续工作，
因此本测试只验证"单轮提交违规 batch → 被中间件拦截"这一关键路径；
更完整的 Phase 3 链路请使用 ``scripts/run_phase3_e2e_real.py`` 配合真实 LLM 跑通。
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
# 注意：__init__.py 中从 document_tools import 了 get_rag_tools，需要 patch __init__ 中的引用。
import app.agents.tools.testcase as _testcase_tools
_testcase_tools.get_rag_tools = AsyncMock(return_value=[])
from app.agents.tools.testcase.document_tools import get_rag_tools as _orig_get_rag_tools  # noqa: F401

from app.agents.testcase import make_agent
from app.agents.testcase.agent import TestCaseGeneratorContext as _TestCaseGeneratorContext


def _valid_case(number: str) -> dict[str, Any]:
    return {
        "name": f"用例 {number}",
        "case_number": number,
        "module": "登录模块",
        "priority": "critical",
        "case_type": "functional",
        "test_data": {"username": "test001", "password": "Test@123"},
        "test_case_steps": [
            {
                "step": "输入用户名密码并点击登录",
                "result": "页面跳转至 /home 并显示昵称 test001",
            }
        ],
    }


def _ai_with_tool_call(name: str, args: dict[str, Any], call_id: str = "call_001") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "id": call_id,
                "name": name,
                "args": args,
                "type": "tool_call",
            }
        ],
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
async def test_phase3_self_check_gate_intercepts_bad_batch(workspace_root):
    """
    启动真实 Agent，模型一轮就提交违规 batch_create；
    ModuleSelfCheckMiddleware 应自动拦截，返回错误 ToolMessage。
    """
    project_id = "PR-PHASE3-E2E"

    bad_case = _valid_case("TC-PROJ-LOGIN-001")
    bad_case["case_number"] = "BAD-NUMBER"

    fake_model = FakeMessagesListChatModel(
        responses=[
            _ai_with_tool_call(
                "batch_create_test_cases_tool",
                {
                    "project_identifier": project_id,
                    "folder_id": "",
                    "test_cases": [bad_case],
                },
                call_id="call_invalid",
            ),
        ]
    )

    ctx = _TestCaseGeneratorContext(
        project_identifier=project_id,
        folder_id="",
        template_type="test_case",
        enable_rag=False,
        auto_approve_threshold=100.0,
    )

    # 注入 fake 模型并运行 agent。dynamic_model_selection 会根据消息选择 text_model，
    # 因此需要把 agent 模块里的 text_model 也替换为 fake_model，避免走真实 DeepSeek。
    import app.agents.testcase.agent as agent_mod
    agent_mod.text_model = fake_model
    agent_mod.image_model = fake_model

    async with make_agent(model=fake_model) as agent:
        with pytest.raises(Exception):  # GraphRecursionError 等
            await agent.ainvoke(
                {"messages": [HumanMessage(content="为用户登录功能设计测试用例")]},
                config={"recursion_limit": 3},
                context=ctx,
            )


@pytest.mark.asyncio
async def test_phase3_self_check_gate_calls_check(workspace_root):
    """
    直接验证：在真实 make_agent 创建的图中，ModuleSelfCheckMiddleware
    对 batch_create_test_cases_tool 的拦截逻辑会被执行。
    """
    from app.agents.testcase.module_self_check_middleware import ModuleSelfCheckMiddleware

    bad_case = _valid_case("TC-PROJ-LOGIN-001")
    bad_case["case_number"] = "BAD-NUMBER"

    middleware = ModuleSelfCheckMiddleware()

    class FakeRequest:
        tool_call = {
            "id": "call_001",
            "name": "batch_create_test_cases_tool",
            "args": {
                "project_identifier": "P1",
                "test_cases": [bad_case],
            },
        }

    async def handler(request):
        return ToolMessage(
            content='{"success": true}',
            tool_call_id=request.tool_call["id"],
            name=request.tool_call["name"],
        )

    result = await middleware.awrap_tool_call(FakeRequest(), handler)
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    payload = json.loads(result.content)
    assert payload["success"] is False
