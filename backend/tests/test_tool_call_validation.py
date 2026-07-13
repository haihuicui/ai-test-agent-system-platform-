"""Tests for ToolCallAdjacencyMiddleware repair logic."""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai.chat_models.base import _convert_message_to_dict

from app.agents.testcase.tool_call_validation_middleware import (
    _ensure_tool_call_adjacency,
    _tool_calls,
    _validate_adjacency,
)


def _ai(tool_call_ids: list[str], content: str = "") -> AIMessage:
    return AIMessage(
        content=content,
        tool_calls=[
            {"id": tc_id, "name": f"tool_{tc_id}", "args": {}} for tc_id in tool_call_ids
        ],
    )


def _tool(tc_id: str, content: str = "result") -> ToolMessage:
    return ToolMessage(content=content, tool_call_id=tc_id, name=f"tool_{tc_id}")


def _to_openai_dicts(messages: list) -> list[dict]:
    """Convert messages to OpenAI API dicts; raises if invalid for OpenAI."""
    return [_convert_message_to_dict(m) for m in messages]


class TestToolCallAdjacency:
    def test_already_valid(self):
        messages = [
            _ai(["call_1", "call_2"]),
            _tool("call_1"),
            _tool("call_2"),
            HumanMessage(content="next"),
        ]
        result = _ensure_tool_call_adjacency(messages)
        assert _validate_adjacency(result) is None
        _to_openai_dicts(result)

    def test_missing_tool_message_backfilled(self):
        messages = [
            _ai(["call_1", "call_2"]),
            _tool("call_1"),
            HumanMessage(content="next"),
        ]
        result = _ensure_tool_call_adjacency(messages)
        assert _validate_adjacency(result) is None
        assert sum(1 for m in result if isinstance(m, ToolMessage)) == 2
        _to_openai_dicts(result)

    def test_tool_message_after_human_moved(self):
        messages = [
            _ai(["call_1"]),
            HumanMessage(content="feedback"),
            _tool("call_1"),
        ]
        result = _ensure_tool_call_adjacency(messages)
        assert _validate_adjacency(result) is None
        assert isinstance(result[1], ToolMessage)
        assert isinstance(result[2], HumanMessage)
        _to_openai_dicts(result)

    def test_multiple_assistants(self):
        messages = [
            _ai(["call_1"]),
            _tool("call_1"),
            HumanMessage(content="ok"),
            _ai(["call_2"]),
            _tool("call_2"),
        ]
        result = _ensure_tool_call_adjacency(messages)
        assert _validate_adjacency(result) is None
        _to_openai_dicts(result)

    def test_orphan_tool_message_dropped(self):
        messages = [
            _ai(["call_1"]),
            _tool("call_1"),
            _tool("orphan"),
            HumanMessage(content="next"),
        ]
        result = _ensure_tool_call_adjacency(messages)
        assert _validate_adjacency(result) is None
        assert "orphan" not in [
            getattr(m, "tool_call_id", None) for m in result
        ]
        _to_openai_dicts(result)

    def test_duplicate_tool_message(self):
        messages = [
            _ai(["call_1"]),
            _tool("call_1", "first"),
            _tool("call_1", "second"),
        ]
        result = _ensure_tool_call_adjacency(messages)
        assert _validate_adjacency(result) is None
        tool_msgs = [m for m in result if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].content == "second"
        _to_openai_dicts(result)

    def test_tool_message_before_assistant(self):
        messages = [
            _tool("call_1"),
            _ai(["call_1"]),
            HumanMessage(content="next"),
        ]
        result = _ensure_tool_call_adjacency(messages)
        assert _validate_adjacency(result) is None
        assert isinstance(result[0], AIMessage)
        assert isinstance(result[1], ToolMessage)
        _to_openai_dicts(result)

    def test_openai_dict_missing_tool_message_backfilled(self):
        """OpenAI-format dicts should be repaired and produce dict dummy tool messages."""
        messages = [
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "foo", "arguments": "{}"}}
            ]},
            {"role": "user", "content": "next"},
        ]
        result = _ensure_tool_call_adjacency(messages)
        assert _validate_adjacency(result) is None
        assert all(isinstance(m, dict) for m in result)
        assert result[1]["role"] == "tool"
        assert result[1]["tool_call_id"] == "call_1"
        assert result[1]["name"] == "foo"

    def test_tool_calls_in_additional_kwargs_are_detected(self):
        """Tool calls stored in additional_kwargs (OpenAI format) must be detected."""
        messages = [
            AIMessage(
                content="",
                additional_kwargs={
                    "tool_calls": [
                        {"id": "call_ak", "type": "function", "function": {"name": "bar", "arguments": "{}"}}
                    ]
                },
            ),
            HumanMessage(content="next"),
        ]
        result = _ensure_tool_call_adjacency(messages)
        assert _validate_adjacency(result) is None
        tool_msgs = [m for m in result if isinstance(m, ToolMessage)]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_call_id == "call_ak"

    def test_deep_copy_prevents_external_mutation(self):
        """Repair should return independent copies, not share references with input."""
        ai = AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "foo", "args": {}}],
        )
        tool = ToolMessage(content="ok", tool_call_id="call_1", name="foo")
        messages = [ai, tool]
        result = _ensure_tool_call_adjacency(messages)
        # Result should be a new list with copied messages
        assert result is not messages
        assert result[0] is not ai
        assert result[1] is not tool
        # Mutating original should not affect result
        ai.tool_calls = []
        assert _tool_calls(result[0])  # still has tool_calls


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
