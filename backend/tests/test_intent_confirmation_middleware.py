"""WebIntentConfirmationMiddleware 单元测试。"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.web_mcp.intent_confirmation_middleware import (
    WebIntentConfirmationMiddleware,
    _parse_intent_confirmation,
)


def _build_payload(**overrides) -> dict:
    payload = {
        "type": "web_intent_confirmation",
        "recommendation": "expand",
        "reason": "检测到功能 WF-1008 与目标站点匹配度 100%，建议扩展",
        "description": "请选择后续操作",
        "existing_function": {
            "id": "func-123",
            "identifier": "WF-1008",
            "display_name": "SauceDemo 登录与购物",
            "base_url": "https://www.saucedemo.com",
        },
        "alternatives": [
            {"key": "expand", "label": "扩展已有功能"},
            {"key": "new", "label": "新建功能"},
            {"key": "view_details", "label": "先查看详情"},
        ],
    }
    payload.update(overrides)
    return payload


def _build_ai_message(payload: dict | None = None) -> AIMessage:
    if payload is None:
        content = " plain message without marker "
    else:
        content = (
            "检测到已有匹配功能。"
            f"\n<INTENT_CONFIRMATION>{json.dumps(payload, ensure_ascii=False)}</INTENT_CONFIRMATION>"
        )
    return AIMessage(content=content)


class TestParseIntentConfirmation:
    def test_returns_payload_when_marker_valid(self):
        payload = _build_payload()
        msg = _build_ai_message(payload)
        result = _parse_intent_confirmation(str(msg.content))
        assert result == payload

    def test_returns_payload_when_wrapped_in_code_fence(self):
        payload = _build_payload()
        content = (
            "推荐：\n"
            "<INTENT_CONFIRMATION>\n"
            "```json\n"
            f"{json.dumps(payload, ensure_ascii=False)}\n"
            "```\n"
            "</INTENT_CONFIRMATION>"
        )
        result = _parse_intent_confirmation(content)
        assert result == payload

    def test_returns_none_when_no_marker(self):
        result = _parse_intent_confirmation("no marker here")
        assert result is None

    def test_returns_none_when_invalid_json(self):
        result = _parse_intent_confirmation("<INTENT_CONFIRMATION>not json</INTENT_CONFIRMATION>")
        assert result is None

    def test_returns_none_when_type_mismatch(self):
        payload = _build_payload(type="other_type")
        result = _parse_intent_confirmation(str(_build_ai_message(payload).content))
        assert result is None

    def test_returns_none_when_missing_function_id(self):
        payload = _build_payload()
        payload["existing_function"].pop("id")
        result = _parse_intent_confirmation(str(_build_ai_message(payload).content))
        assert result is None

    def test_returns_none_when_missing_function_identifier(self):
        payload = _build_payload()
        payload["existing_function"].pop("identifier")
        result = _parse_intent_confirmation(str(_build_ai_message(payload).content))
        assert result is None


class TestWebIntentConfirmationMiddleware:
    @pytest.fixture
    def middleware(self):
        return WebIntentConfirmationMiddleware()

    @pytest.mark.parametrize(
        "decision,expected_substring",
        [
            ("expand", "用户选择扩展已有功能 WF-1008"),
            ("new", "用户选择新建功能"),
            ("view_details", "用户希望先查看功能 WF-1008"),
        ],
    )
    def test_interrupt_and_resume(self, middleware, decision, expected_substring):
        payload = _build_payload()
        messages = [_build_ai_message(payload)]
        state = {"messages": messages}

        with patch(
            "app.agents.web_mcp.intent_confirmation_middleware.interrupt",
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
        assert human_msg.additional_kwargs.get("_web_intent_confirmation", {}).get("decision") == decision

    def test_no_interrupt_without_ai_message(self, middleware):
        result = middleware.after_model({"messages": []}, runtime=None)
        assert result is None

    def test_no_interrupt_with_tool_calls(self, middleware):
        payload = _build_payload()
        ai_msg = _build_ai_message(payload)
        ai_msg.tool_calls = [{"name": "list_web_functions", "args": {}}]
        result = middleware.after_model({"messages": [ai_msg]}, runtime=None)
        assert result is None

    def test_no_interrupt_when_already_resumed(self, middleware):
        payload = _build_payload()
        ai_msg = _build_ai_message(payload)
        human_msg = HumanMessage(content="[Web意图确认] 用户选择扩展已有功能 WF-1008")
        result = middleware.after_model({"messages": [ai_msg, human_msg]}, runtime=None)
        assert result is None
