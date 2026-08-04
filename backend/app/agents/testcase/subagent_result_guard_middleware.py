"""task 子代理空结果兜底中间件。

背景：隔离评审子代理（adversarial-reviewer / general-purpose）在执行超长推理
任务时，可能因 max_tokens 被思考链（reasoning）耗尽而正常结束、最终消息正文
却为空（finish_reason=length，输出 token 全部消耗在 reasoning 上）。
deepagents 的 task 工具直接取子代理最后一条消息文本作为 ToolMessage 返回，
此时主 Agent 收到的是 status=success 的空内容，无法分辨"评审无发现"与
"输出被截断"，容易误判为"环境异常"后按原样盲目重试（同样输入会再次撞顶）。

本中间件在 task 工具返回时检查 ToolMessage 内容：若为空白，则替换为带诊断
与应对指引的文本，让主 Agent 能改用"读取结果文件 / 拆分模块分批评审"等策略。
"""
from __future__ import annotations

import dataclasses
import logging
from typing import Any, Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

logger = logging.getLogger(__name__)

_EMPTY_RESULT_GUIDANCE = (
    "[子代理未返回有效内容] task 子代理（{agent_type}）已正常结束，但最终消息为空。"
    "最常见原因：推理模型的 max_tokens 被思考链（reasoning）全部耗尽，正文未能输出"
    "（finish_reason=length）。**不要按原样重试**——同样的输入会再次撞顶。应对策略：\n"
    "1. 若任务中已约定子代理将结果写入文件（如 adversarial_review.md），"
    "直接用 read_file 读取该文件获取评审结果；\n"
    "2. 否则缩小任务范围后重试：按模块拆分为多次 task 调用（每次只审 1~2 个模块），"
    "并要求子代理逐模块把发现写入文件、最终消息只返回统计摘要。"
)


def _extract_text(content: Any) -> str:
    """从 ToolMessage.content（str / content-block list / None）提取纯文本。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


class SubagentResultGuardMiddleware(AgentMiddleware):
    """task 工具结果为空时，替换为可操作的诊断文本（不拦截正常结果）。"""

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        return self._guard(request, handler(request))

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        return self._guard(request, await handler(request))

    def _guard(
        self,
        request: ToolCallRequest,
        result: ToolMessage | Command,
    ) -> ToolMessage | Command:
        tool_call = request.tool_call or {}
        if tool_call.get("name") != "task":
            return result

        agent_type = (tool_call.get("args") or {}).get("subagent_type") or "unknown"
        guidance = _EMPTY_RESULT_GUIDANCE.format(agent_type=agent_type)

        if isinstance(result, ToolMessage):
            if _extract_text(result.content).strip():
                return result
            logger.warning(
                "task subagent '%s' returned empty content; injecting guidance",
                agent_type,
            )
            return result.model_copy(update={"content": guidance})

        # Command：task 工具经 Command(update={"messages": [ToolMessage]}) 返回
        update = getattr(result, "update", None)
        if not isinstance(update, dict):
            return result
        messages = update.get("messages")
        if not isinstance(messages, list) or not messages:
            return result
        changed = False
        new_messages: list[Any] = []
        for msg in messages:
            if isinstance(msg, ToolMessage) and not _extract_text(msg.content).strip():
                new_messages.append(msg.model_copy(update={"content": guidance}))
                changed = True
            else:
                new_messages.append(msg)
        if not changed:
            return result
        logger.warning(
            "task subagent '%s' returned empty content via Command; injecting guidance",
            agent_type,
        )
        return dataclasses.replace(result, update={**update, "messages": new_messages})
