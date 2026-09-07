"""工具调用 JSON 解析失败兜底中间件。

背景：模型（deepseek-v4-flash 实证）偶发生成畸形工具调用参数——2026-09-07
thread f26954df 实证：write_todos 的 args JSON key 被双重引号包裹
（`""content""`），langchain 解析失败后把调用降级为 invalid_tool_calls，
合法 tool_calls 为空。react 循环只认合法 tool_calls，判定"无工具要执行"，
图直接走到 END——run 以 success 静默结束，用户视角是 agent 说完
"我先建立任务清单"就永久假死。这是与输出截断同类的「静默成功」缺陷
（见 truncation_retry_middleware.py），但 finish_reason=tool_calls，
TruncationRetryMiddleware 按 length 判定时不会命中。

本中间件在每次模型调用后检查响应：若最后一条 AI 消息合法 tool_calls 为空
但 invalid_tool_calls 非空（模型明确想调工具、只是参数 JSON 畸形），则在
请求副本上追加一条提醒消息（request.override，不落 state）后重试一次；
重试仍失败时剥离 invalid_tool_calls、改写为可见诊断文本，让 run 以用户
可感知的信息结束而非无声消失。

只重试一次：参数畸形是偶发生成错误而非预算问题，单次重试大概率恢复，
多次重试只会放大成本。
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

logger = logging.getLogger(__name__)

# 参数畸形属偶发生成错误，单次重试足够；不无限放大模型调用成本
_MAX_RETRIES = 1

_NUDGE_TEMPLATE = (
    "[系统提示] 你的上一次回复中的工具调用（{tool_names}）参数 JSON 格式畸形"
    "（例如 key 被双重引号包裹），解析失败、未被执行。请立即重新发起同一个"
    "工具调用，并严格遵守：\n"
    "1. 参数必须是合法 JSON：key 与字符串值均使用单对双引号；\n"
    "2. 不要改变调用意图和参数内容，只修正格式；\n"
    "3. 不要在正文复述参数，直接发出工具调用。"
)

_DIAGNOSIS_TEMPLATE = (
    "⚠️ 本轮工具调用（{tool_names}）的参数 JSON 格式畸形，解析失败，"
    "系统自动重试 {retries} 次后仍未恢复，相关调用未执行、未写入任何内容。\n\n"
    "**建议操作：** 重新发送你的需求消息即可，我会从头开始执行。\n\n"
    "（诊断：finish_reason=tool_calls，invalid_tool_calls={invalid_count}，"
    "error={error}）"
)


def _invalid_tool_calls(msg: Any) -> list[dict[str, Any]]:
    """提取 invalid_tool_calls（实例属性优先，兼容 additional_kwargs fallback）。

    2026-09-07 thread f26954df 的 checkpoint 里畸形调用只出现在
    additional_kwargs['invalid_tool_calls']，两种载体都要认。
    """
    if isinstance(msg, dict):
        itc = msg.get("invalid_tool_calls") or []
        if not itc:
            itc = (msg.get("additional_kwargs") or {}).get("invalid_tool_calls") or []
        return itc
    itc = getattr(msg, "invalid_tool_calls", None) or []
    if not itc:
        itc = (getattr(msg, "additional_kwargs", None) or {}).get("invalid_tool_calls") or []
    return itc


def _classify_invalid_tool_call(response: ModelResponse) -> AIMessage | None:
    """识别「合法 tool_calls 为空但 invalid_tool_calls 非空」的末条 AI 消息。"""
    messages = getattr(response, "result", None) or []
    if not messages:
        return None
    msg = messages[-1]
    if getattr(msg, "type", None) != "ai":
        return None
    if getattr(msg, "tool_calls", None):
        return None
    if not _invalid_tool_calls(msg):
        return None
    return msg


def _tool_names(itc: list[dict[str, Any]]) -> str:
    names = [
        tc.get("name", "?") if isinstance(tc, dict) else getattr(tc, "name", "?")
        for tc in itc
    ]
    return "、".join(n or "?" for n in names) or "（未解析）"


def _first_error(itc: list[dict[str, Any]]) -> str:
    for tc in itc:
        err = tc.get("error") if isinstance(tc, dict) else getattr(tc, "error", None)
        if err:
            return str(err)[:200]
    return "args JSON 解析失败"


class InvalidToolCallRetryMiddleware(AgentMiddleware):
    """工具调用参数 JSON 畸形的单次自动重试与可见诊断（正常路径零介入）。"""

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        response = await handler(request)

        attempts = 0
        bad_msg = _classify_invalid_tool_call(response)
        while bad_msg is not None and attempts < _MAX_RETRIES:
            attempts += 1
            itc = _invalid_tool_calls(bad_msg)
            logger.warning(
                "invalid tool call detected (tools=%s, error=%s); "
                "retry %d/%d with nudge",
                _tool_names(itc), _first_error(itc), attempts, _MAX_RETRIES,
            )
            nudge = HumanMessage(
                content=_NUDGE_TEMPLATE.format(tool_names=_tool_names(itc))
            )
            # 请求副本注入提醒，不写 state
            retry_request = request.override(messages=[*(request.messages or []), nudge])
            response = await handler(retry_request)
            bad_msg = _classify_invalid_tool_call(response)

        if bad_msg is None:
            return response

        # 重试耗尽：剥离 invalid_tool_calls 改写为可见诊断，避免 run 静默结束。
        # 必须清掉 additional_kwargs 里的残留——部分 provider 转换器会透传
        # additional_kwargs，残留的畸形调用可能污染后续轮次的请求。
        itc = _invalid_tool_calls(bad_msg)
        logger.error(
            "invalid tool call persisted after %d retries (tools=%s); "
            "returning visible diagnosis",
            _MAX_RETRIES, _tool_names(itc),
        )
        stripped = bad_msg.model_copy()
        stripped.tool_calls = []
        stripped.invalid_tool_calls = []
        ak = dict(getattr(stripped, "additional_kwargs", {}) or {})
        ak.pop("tool_calls", None)
        ak.pop("invalid_tool_calls", None)
        stripped.additional_kwargs = ak
        diagnosis = stripped.model_copy(update={
            "content": _DIAGNOSIS_TEMPLATE.format(
                tool_names=_tool_names(itc),
                retries=_MAX_RETRIES,
                invalid_count=len(itc),
                error=_first_error(itc),
            )
        })
        return ModelResponse(result=[*response.result[:-1], diagnosis])
