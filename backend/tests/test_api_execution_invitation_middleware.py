"""APIExecutionInvitationMiddleware 单元测试。"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.api.execution_invitation_middleware import (
    APIExecutionInvitationMiddleware,
    _parse_execution_invitation,
)


def _build_payload(**overrides) -> dict:
    payload = {
        "type": "execution_invitation",
        "mode": "api",
        "endpoint_id": "ep-123",
        "script_name": "api-test-script.ts",
        "test_count": 5,
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
            "API 测试脚本已生成。"
            f"\n<EXECUTION_INVITATION>{json.dumps(payload, ensure_ascii=False)}</EXECUTION_INVITATION>"
        )
    return AIMessage(content=content)


class TestParseAPIExecutionInvitation:
    def test_returns_payload_when_marker_valid(self):
        payload = _build_payload()
        msg = _build_ai_message(payload)
        result = _parse_execution_invitation(str(msg.content))
        assert result == payload

    def test_returns_none_when_type_mismatch(self):
        payload = _build_payload(type="other_type")
        result = _parse_execution_invitation(str(_build_ai_message(payload).content))
        assert result is None

    def test_uses_default_alternatives_when_missing(self):
        payload = _build_payload()
        payload.pop("alternatives")
        result = _parse_execution_invitation(str(_build_ai_message(payload).content))
        assert result is not None
        assert result["alternatives"][0] == {"key": "execute", "label": "立即执行"}


class TestAPIExecutionInvitationMiddleware:
    @pytest.fixture
    def middleware(self):
        return APIExecutionInvitationMiddleware()

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
            "app.agents.api.execution_invitation_middleware.interrupt",
            return_value={"decision": decision},
        ) as mock_interrupt:
            result = middleware.after_model(state, runtime=None)

        mock_interrupt.assert_called_once_with(payload)
        assert result is not None
        assert result["jump_to"] == "model"
        human_msg = result["messages"][0]
        assert isinstance(human_msg, HumanMessage)
        assert expected_substring in str(human_msg.content)
        assert human_msg.additional_kwargs.get("_execution_invitation", {}).get("decision") == decision

    def test_execute_resume_refs_api_tools(self, middleware):
        payload = _build_payload()
        messages = [_build_ai_message(payload)]
        state = {"messages": messages}

        with patch(
            "app.agents.api.execution_invitation_middleware.interrupt",
            return_value={"decision": "execute", "comment": "使用测试环境"},
        ):
            result = middleware.after_model(state, runtime=None)

        human_msg = result["messages"][0]
        content = str(human_msg.content)
        assert "download_api_script" in content
        assert "execute_api_script" in content
        assert "execution_config" in content
        assert human_msg.additional_kwargs["_execution_invitation"]["endpoint_id"] == "ep-123"

    def test_no_interrupt_when_already_resumed(self, middleware):
        payload = _build_payload()
        ai_msg = _build_ai_message(payload)
        human_msg = HumanMessage(content="[执行邀约] 用户选择暂不执行测试")
        result = middleware.after_model({"messages": [ai_msg, human_msg]}, runtime=None)
        assert result is None

    def test_no_interrupt_with_tool_calls(self, middleware):
        payload = _build_payload()
        ai_msg = _build_ai_message(payload)
        ai_msg.tool_calls = [{"name": "save_test_script", "args": {}}]
        result = middleware.after_model({"messages": [ai_msg]}, runtime=None)
        assert result is None
