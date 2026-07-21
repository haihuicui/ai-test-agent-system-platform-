"""WebExecutionInvitationMiddleware 单元测试。"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.web_mcp.execution_invitation_middleware import (
    WebExecutionInvitationMiddleware,
    _parse_execution_invitation,
)


def _build_payload(**overrides) -> dict:
    payload = {
        "type": "execution_invitation",
        "mode": "web",
        "sub_function_id": "sub-123",
        "script_name": "test-script.ts",
        "test_count": 3,
        "description": "测试计划、测试用例、测试脚本已保存；尚未执行。",
        "alternatives": [
            {"key": "execute", "label": "立即执行"},
            {"key": "skip", "label": "暂不执行"},
            {"key": "edit", "label": "修改脚本"},
            {"key": "other", "label": "其他"},
        ],
    }
    payload.update(overrides)
    return payload


def _build_ai_message(payload: dict | None = None) -> AIMessage:
    if payload is None:
        content = " plain message without marker "
    else:
        content = (
            "测试脚本已生成。"
            f"\n<EXECUTION_INVITATION>{json.dumps(payload, ensure_ascii=False)}</EXECUTION_INVITATION>"
        )
    return AIMessage(content=content)


class TestParseExecutionInvitation:
    def test_returns_payload_when_marker_valid(self):
        payload = _build_payload()
        msg = _build_ai_message(payload)
        result = _parse_execution_invitation(str(msg.content))
        assert result == payload

    def test_returns_payload_when_wrapped_in_code_fence(self):
        payload = _build_payload()
        content = (
            "脚本已生成。\n"
            "<EXECUTION_INVITATION>\n"
            "```json\n"
            f"{json.dumps(payload, ensure_ascii=False)}\n"
            "```\n"
            "</EXECUTION_INVITATION>"
        )
        result = _parse_execution_invitation(content)
        assert result == payload

    def test_returns_none_when_no_marker(self):
        result = _parse_execution_invitation("no marker here")
        assert result is None

    def test_returns_none_when_invalid_json(self):
        result = _parse_execution_invitation(
            "<EXECUTION_INVITATION>not json</EXECUTION_INVITATION>"
        )
        assert result is None

    def test_returns_none_when_type_mismatch(self):
        payload = _build_payload(type="other_type")
        result = _parse_execution_invitation(str(_build_ai_message(payload).content))
        assert result is None

    def test_uses_default_alternatives_when_missing(self):
        payload = _build_payload()
        payload.pop("alternatives")
        result = _parse_execution_invitation(str(_build_ai_message(payload).content))
        assert result is not None
        assert result["alternatives"] == [
            {"key": "execute", "label": "立即执行"},
            {"key": "skip", "label": "暂不执行"},
            {"key": "edit", "label": "修改脚本"},
            {"key": "other", "label": "其他"},
        ]


class TestWebExecutionInvitationMiddleware:
    @pytest.fixture
    def middleware(self):
        return WebExecutionInvitationMiddleware()

    @pytest.mark.parametrize(
        "decision,expected_substring",
        [
            ("execute", "用户选择立即执行测试"),
            ("skip", "用户选择暂不执行测试"),
            ("edit", "用户希望先修改脚本"),
            ("other", "用户选择其他操作"),
        ],
    )
    def test_interrupt_and_resume(self, middleware, decision, expected_substring):
        payload = _build_payload()
        messages = [_build_ai_message(payload)]
        state = {"messages": messages}

        with patch(
            "app.agents.web_mcp.execution_invitation_middleware.interrupt",
            return_value={"decision": decision},
        ) as mock_interrupt:
            result = middleware.after_model(state, runtime=None)

        mock_interrupt.assert_called_once_with(payload)
        assert result is not None
        assert result["jump_to"] == "model"
        assert len(result["messages"]) == 1
        human_msg = result["messages"][0]
        assert isinstance(human_msg, HumanMessage)
        assert expected_substring in str(human_msg.content)
        assert human_msg.additional_kwargs.get("_execution_invitation", {}).get("decision") == decision
        assert human_msg.additional_kwargs.get("_execution_invitation", {}).get("comment") == ""

    def test_interrupt_and_resume_with_comment(self, middleware):
        payload = _build_payload()
        messages = [_build_ai_message(payload)]
        state = {"messages": messages}
        comment = "先使用 headless 模式执行"

        with patch(
            "app.agents.web_mcp.execution_invitation_middleware.interrupt",
            return_value={"decision": "execute", "comment": comment},
        ) as mock_interrupt:
            result = middleware.after_model(state, runtime=None)

        mock_interrupt.assert_called_once_with(payload)
        assert result is not None
        human_msg = result["messages"][0]
        assert isinstance(human_msg, HumanMessage)
        assert "用户选择立即执行测试" in str(human_msg.content)
        assert f"补充说明：{comment}" in str(human_msg.content)
        invitation = human_msg.additional_kwargs.get("_execution_invitation", {})
        assert invitation.get("decision") == "execute"
        assert invitation.get("comment") == comment
        assert invitation.get("sub_function_id") == "sub-123"

    def test_no_interrupt_without_ai_message(self, middleware):
        result = middleware.after_model({"messages": []}, runtime=None)
        assert result is None

    def test_no_interrupt_with_tool_calls(self, middleware):
        payload = _build_payload()
        ai_msg = _build_ai_message(payload)
        ai_msg.tool_calls = [{"name": "save_web_test_script", "args": {}}]
        result = middleware.after_model({"messages": [ai_msg]}, runtime=None)
        assert result is None

    def test_no_interrupt_when_already_resumed(self, middleware):
        payload = _build_payload()
        ai_msg = _build_ai_message(payload)
        human_msg = HumanMessage(content="[执行邀约] 用户选择立即执行测试")
        result = middleware.after_model({"messages": [ai_msg, human_msg]}, runtime=None)
        assert result is None

    def test_defaults_to_execute_when_interrupt_response_empty(self, middleware):
        payload = _build_payload()
        messages = [_build_ai_message(payload)]
        state = {"messages": messages}

        with patch(
            "app.agents.web_mcp.execution_invitation_middleware.interrupt",
            return_value=None,
        ) as mock_interrupt:
            result = middleware.after_model(state, runtime=None)

        mock_interrupt.assert_called_once_with(payload)
        human_msg = result["messages"][0]
        assert "用户选择立即执行测试" in str(human_msg.content)
        assert human_msg.additional_kwargs["_execution_invitation"]["decision"] == "execute"
