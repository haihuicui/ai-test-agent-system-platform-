"""主 Agent 输出截断兜底中间件。

背景：deepseek-v4 系列为推理模型，reasoning 与正文共享 max_tokens 配额。
主 Agent 在长上下文（数万 tokens 的 RAG 检索/文件读取结果）后进行深度规划时，
思考链可能耗尽全部输出配额，API 返回 finish_reason=length、正文 0 字符、无
tool_calls——react 循环把这条空消息视为"任务完成"，run 以 success 静默结束，
用户视角就是"agent 突然中断"（2026-08-06 thread e67525ea 实证：
input=67.9K，reasoning=8192/8192，content=0；同类问题此前已在子代理出现，
见 subagent_result_guard_middleware.py）。

本中间件在每次模型调用后检查响应：若为空截断响应，则在请求副本上追加一条
提醒消息（request.override，不落 state）后重新调用模型；重试仍撞顶时返回
带可见诊断说明的 AI 消息，让 run 以用户可感知的信息结束而非无声消失。
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

from app.config.settings import settings

logger = logging.getLogger(__name__)

# 空截断响应的最大自动重试次数（每次重试都是一轮完整模型调用，需克制）
_MAX_RETRIES = 2

_NUDGE_TEMPLATE = (
    "[系统提示] 你的上一次回复因输出 token 上限（max_tokens={max_tokens}）被思考链"
    "（reasoning）全部耗尽，正文未能产出任何内容（finish_reason=length），"
    "在用户视角等同于对话中断。请立即从断点处恢复工作，并严格遵守：\n"
    "1. 大幅压缩内部推理，禁止展开长篇规划——直接基于已有上下文产出下一步动作"
    "（工具调用或结论正文）；\n"
    "2. 需要长篇分析时，把分析过程用 write_file 写入工作区文件，正文只给摘要；\n"
    "3. 不要重复之前已成功执行的检索/读取类工具调用，直接利用已有结果继续。"
)

_DIAGNOSIS_TEMPLATE = (
    "⚠️ 本轮生成被模型输出上限打断：思考链（reasoning）耗尽了全部 {max_tokens} "
    "输出配额，未能产出正文（finish_reason=length）。系统已自动重试 {retries} 次仍未恢复。\n\n"
    "**建议操作：**\n"
    "- 直接回复「继续」，我会从断点处接着执行；\n"
    "- 或把本次需求拆小后重新发起。\n\n"
    "（诊断：input_tokens={input_tokens}，reasoning_tokens={reasoning}，content=0）"
)


def _content_is_empty(content: object) -> bool:
    """判定 AIMessage.content 是否为空白（str / content-block list / None）。"""
    if content is None:
        return True
    if isinstance(content, str):
        return not content.strip()
    if isinstance(content, list):
        return not any(
            isinstance(block, dict)
            and block.get("type") == "text"
            and str(block.get("text", "")).strip()
            for block in content
        )
    return True


def _is_empty_length_truncation(response: ModelResponse) -> bool:
    """识别「finish_reason=length 且正文为空且无工具调用」的截断响应。"""
    messages = getattr(response, "result", None) or []
    if not messages:
        return False
    msg = messages[-1]
    if getattr(msg, "type", None) != "ai":
        return False
    if getattr(msg, "tool_calls", None):
        return False
    if not _content_is_empty(getattr(msg, "content", None)):
        return False
    finish_reason = (getattr(msg, "response_metadata", None) or {}).get("finish_reason")
    return finish_reason == "length"


def _usage(msg: AIMessage) -> tuple[int | None, int | None]:
    usage = getattr(msg, "usage_metadata", None) or {}
    details = usage.get("output_token_details") or {}
    return usage.get("input_tokens"), details.get("reasoning")


class TruncationRetryMiddleware(AgentMiddleware):
    """主 Agent 空截断响应的自动重试与可见诊断（正常路径零介入）。"""

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        response = await handler(request)

        attempts = 0
        while _is_empty_length_truncation(response) and attempts < _MAX_RETRIES:
            attempts += 1
            msg = response.result[-1]
            input_tokens, reasoning = _usage(msg)
            logger.warning(
                "main agent empty truncation detected (finish_reason=length, "
                "input_tokens=%s, reasoning=%s); retry %d/%d with nudge",
                input_tokens, reasoning, attempts, _MAX_RETRIES,
            )
            nudge = HumanMessage(
                content=_NUDGE_TEMPLATE.format(max_tokens=settings.llm_max_tokens)
            )
            # 请求副本注入提醒，不写 state；每次都从原始请求派生，只带一条提醒
            retry_request = request.override(messages=[*(request.messages or []), nudge])
            response = await handler(retry_request)

        if not _is_empty_length_truncation(response):
            return response

        # 重试耗尽：把空消息改写为可见诊断，避免 run 静默结束
        msg = response.result[-1]
        input_tokens, reasoning = _usage(msg)
        logger.error(
            "main agent truncation persisted after %d retries "
            "(input_tokens=%s, reasoning=%s); returning visible diagnosis",
            _MAX_RETRIES, input_tokens, reasoning,
        )
        diagnosis = msg.model_copy(update={
            "content": _DIAGNOSIS_TEMPLATE.format(
                max_tokens=settings.llm_max_tokens,
                retries=_MAX_RETRIES,
                input_tokens=input_tokens,
                reasoning=reasoning,
            )
        })
        return ModelResponse(result=[*response.result[:-1], diagnosis])
