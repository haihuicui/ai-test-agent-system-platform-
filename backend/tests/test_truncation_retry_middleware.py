"""Tests for TruncationRetryMiddleware 的「带 tool_calls 截断」扩展（缺陷⑤a）。

覆盖：tool_calls 截断自动重试、重试耗尽剥离+诊断、既有 empty 分支回归、
正常响应零介入。
"""
from __future__ import annotations

import asyncio

from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.testcase.truncation_retry_middleware import (
    TruncationRetryMiddleware,
    _classify_truncation,
)


def _request() -> ModelRequest:
    return ModelRequest(
        model=FakeMessagesListChatModel(responses=[]),
        messages=[HumanMessage(content="hi")],
    )


def _truncated_tool_call_response() -> ModelResponse:
    """finish_reason=length 且带 tool_calls 的截断响应（thread 6f08f7ab 复刻）。"""
    msg = AIMessage(
        content="先保存 M1 用例：",
        tool_calls=[
            {
                "id": "call_1",
                "name": "save_test_cases_file",
                "args": {"file_path": "m01.jsonl", "content": '{"case_number": "TC-1"'},
            }
        ],
        response_metadata={"finish_reason": "length"},
        usage_metadata={
            "input_tokens": 28568,
            "output_tokens": 16384,
            "total_tokens": 44952,
            "output_token_details": {"reasoning": 9312},
        },
    )
    return ModelResponse(result=[msg])


def _empty_truncated_response() -> ModelResponse:
    msg = AIMessage(
        content="",
        response_metadata={"finish_reason": "length"},
        usage_metadata={
            "input_tokens": 100,
            "output_tokens": 8192,
            "total_tokens": 8292,
            "output_token_details": {"reasoning": 8192},
        },
    )
    return ModelResponse(result=[msg])


def _normal_response() -> ModelResponse:
    msg = AIMessage(
        content="正常输出",
        tool_calls=[
            {"id": "call_9", "name": "save_test_cases_file", "args": {"file_path": "a.jsonl", "content": "[]"}}
        ],
        response_metadata={"finish_reason": "tool_calls"},
    )
    return ModelResponse(result=[msg])


class _StubHandler:
    """按脚本依次返回响应的 async handler，记录每次请求的 messages。"""

    def __init__(self, script: list[ModelResponse]):
        self._script = list(script)
        self.requests: list[ModelRequest] = []

    async def __call__(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return self._script.pop(0)


def _run(middleware: TruncationRetryMiddleware, handler: _StubHandler) -> ModelResponse:
    return asyncio.run(middleware.awrap_model_call(_request(), handler))


class TestToolCallTruncation:
    def test_retried_once_then_success(self):
        handler = _StubHandler([_truncated_tool_call_response(), _normal_response()])
        mw = TruncationRetryMiddleware()

        result = _run(mw, handler)

        assert len(handler.requests) == 2
        # 重试请求在副本上追加了 nudge（不落 state）
        retry_msgs = handler.requests[1].messages
        assert isinstance(retry_msgs[-1], HumanMessage)
        assert "10 条" in retry_msgs[-1].content
        assert "截断" in retry_msgs[-1].content
        # 最终返回正常响应
        assert result.result[-1].content == "正常输出"

    def test_retries_exhausted_strips_tool_calls(self):
        handler = _StubHandler([_truncated_tool_call_response() for _ in range(3)])
        mw = TruncationRetryMiddleware()

        result = _run(mw, handler)

        # 初次 + 2 次重试
        assert len(handler.requests) == 3
        final = result.result[-1]
        assert final.tool_calls == []
        assert final.invalid_tool_calls == []
        assert "tool_calls" not in final.additional_kwargs
        assert "未执行" in final.content
        assert "save_test_cases_file" in final.content  # 点名被拦截的工具

    def test_classifier_distinguishes_kinds(self):
        assert _classify_truncation(_truncated_tool_call_response()) == "tool_calls"
        assert _classify_truncation(_empty_truncated_response()) == "empty"
        assert _classify_truncation(_normal_response()) is None


class TestEmptyTruncationRegression:
    """既有 empty 分支行为保持不变（文案、重试次数、诊断结构）。"""

    def test_empty_truncation_still_retried_with_original_nudge(self):
        handler = _StubHandler([_empty_truncated_response(), _normal_response()])
        mw = TruncationRetryMiddleware()

        result = _run(mw, handler)

        assert len(handler.requests) == 2
        nudge = handler.requests[1].messages[-1]
        assert "思考链" in nudge.content  # 既有 nudge 文案特征
        assert result.result[-1].content == "正常输出"

    def test_empty_exhausted_returns_original_diagnosis(self):
        handler = _StubHandler([_empty_truncated_response() for _ in range(3)])
        mw = TruncationRetryMiddleware()

        result = _run(mw, handler)

        assert len(handler.requests) == 3
        final = result.result[-1]
        assert "输出上限打断" in final.content
        assert "reasoning_tokens=8192" in final.content


class TestNormalResponsePassthrough:
    def test_normal_response_untouched(self):
        handler = _StubHandler([_normal_response()])
        mw = TruncationRetryMiddleware()

        result = _run(mw, handler)

        assert len(handler.requests) == 1
        assert result.result[-1].tool_calls[0]["name"] == "save_test_cases_file"
