"""Tests for InvalidToolCallRetryMiddleware（工具调用参数 JSON 畸形兜底）。

复刻 2026-09-07 thread f26954df 形态：模型调用 write_todos 但 args JSON
key 被双重引号包裹，langchain 解析失败降级为 invalid_tool_calls，合法
tool_calls 为空，react 循环静默走到 END。

覆盖：检测分类（含 additional_kwargs fallback 载体）、单次重试成功、
重试耗尽剥离+可见诊断、正常响应零介入。
"""
from __future__ import annotations

import asyncio

from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.testcase.invalid_tool_call_retry_middleware import (
    InvalidToolCallRetryMiddleware,
    _classify_invalid_tool_call,
)


def _request() -> ModelRequest:
    return ModelRequest(
        model=FakeMessagesListChatModel(responses=[]),
        messages=[HumanMessage(content="hi")],
    )


_INVALID_TC = {
    "type": "invalid_tool_call",
    "id": "call_00_aiPSM2CQduFOPnKQWjKQ8366",
    "name": "write_todos",
    "args": '{"todos": [{""content"": ""Phase 1""}]}',  # 双重引号畸形（实证复刻）
    "error": "Expecting property name enclosed in double quotes",
}


def _invalid_response(via_additional_kwargs: bool = False) -> ModelResponse:
    """finish_reason=tool_calls 但合法 tool_calls 为空的畸形响应。"""
    kwargs = dict(
        content="我先建立全流程任务清单，然后检索背景知识。",
        response_metadata={"finish_reason": "tool_calls"},
    )
    if via_additional_kwargs:
        kwargs["additional_kwargs"] = {"invalid_tool_calls": [_INVALID_TC]}
    else:
        kwargs["invalid_tool_calls"] = [_INVALID_TC]
    return ModelResponse(result=[AIMessage(**kwargs)])


def _valid_tool_call_response() -> ModelResponse:
    msg = AIMessage(
        content="",
        tool_calls=[
            {"id": "call_1", "name": "write_todos", "args": {"todos": [{"content": "P1", "status": "in_progress"}]}}
        ],
        response_metadata={"finish_reason": "tool_calls"},
    )
    return ModelResponse(result=[msg])


def _plain_text_response() -> ModelResponse:
    return ModelResponse(result=[AIMessage(content="正常文本回复")])


class _StubHandler:
    """按脚本依次返回响应的 async handler，记录每次请求的 messages。"""

    def __init__(self, script: list[ModelResponse]):
        self._script = list(script)
        self.requests: list[ModelRequest] = []

    async def __call__(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return self._script.pop(0)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- classify


def test_classify_detects_invalid_only_message():
    msg = _classify_invalid_tool_call(_invalid_response())
    assert msg is not None


def test_classify_detects_additional_kwargs_carrier():
    """checkpoint 里畸形调用只落在 additional_kwargs 的载体也要认。"""
    msg = _classify_invalid_tool_call(_invalid_response(via_additional_kwargs=True))
    assert msg is not None


def test_classify_ignores_valid_tool_calls():
    assert _classify_invalid_tool_call(_valid_tool_call_response()) is None


def test_classify_ignores_plain_text():
    assert _classify_invalid_tool_call(_plain_text_response()) is None


# ---------------------------------------------------------------- wrap


def test_retry_once_recovers():
    """首次畸形 → 注入 nudge 重试 → 第二次返回合法调用，正常放行。"""
    mw = InvalidToolCallRetryMiddleware()
    handler = _StubHandler([_invalid_response(), _valid_tool_call_response()])
    resp = _run(mw.awrap_model_call(_request(), handler))

    assert len(handler.requests) == 2
    # nudge 注入在重试请求末尾，且不落原始请求
    retry_msgs = handler.requests[1].messages
    assert len(retry_msgs) == 2
    assert "参数 JSON 格式畸形" in retry_msgs[-1].content
    assert "write_todos" in retry_msgs[-1].content
    assert len(handler.requests[0].messages) == 1
    # 返回的是重试后的合法响应
    assert resp.result[-1].tool_calls[0]["name"] == "write_todos"


def test_retry_exhausted_returns_visible_diagnosis():
    """重试仍畸形 → 剥离 invalid_tool_calls，改写为可见诊断。"""
    mw = InvalidToolCallRetryMiddleware()
    handler = _StubHandler([_invalid_response(), _invalid_response()])
    resp = _run(mw.awrap_model_call(_request(), handler))

    assert len(handler.requests) == 2  # 只重试一次
    msg = resp.result[-1]
    assert "⚠️" in msg.content
    assert "write_todos" in msg.content
    assert "重新发送" in msg.content
    # 剥离干净：合法/非法 tool_calls 与 additional_kwargs 残留全清
    assert msg.tool_calls == []
    assert msg.invalid_tool_calls == []
    assert "invalid_tool_calls" not in msg.additional_kwargs
    assert "tool_calls" not in msg.additional_kwargs


def test_normal_response_untouched():
    """正常带合法 tool_calls 的响应零介入。"""
    mw = InvalidToolCallRetryMiddleware()
    handler = _StubHandler([_valid_tool_call_response()])
    resp = _run(mw.awrap_model_call(_request(), handler))

    assert len(handler.requests) == 1
    assert resp.result[-1].tool_calls[0]["name"] == "write_todos"


def test_plain_text_untouched():
    mw = InvalidToolCallRetryMiddleware()
    handler = _StubHandler([_plain_text_response()])
    resp = _run(mw.awrap_model_call(_request(), handler))

    assert len(handler.requests) == 1
    assert resp.result[-1].content == "正常文本回复"
