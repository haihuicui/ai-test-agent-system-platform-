"""陈旧大工具结果卸载中间件（read_file / grep）。

deepagents 的 FilesystemMiddleware 会把超阈值的工具结果自动卸载到磁盘、state 只留
指针，但 read_file / grep 被硬编码排除在自动卸载之外（TOOLS_EXCLUDED_FROM_EVICTION）。
它们单次结果虽被自截断到 ~80KB，但长会话里多次读取 / 检索会累积到数百 KB，随
checkpoint 一起膨胀，最终拖垮前端「加载历史对话」。

本中间件在每次模型调用前，把**已越过最近窗口**（KEEP_RECENT 条之前、Agent 已用完
不再需要的旧结果）中较大的 read_file / grep 结果，完整内容卸载到工作区
`/large_tool_results/` 下，state 里替换为「预览 + 文件路径」指针。最近的结果保持原样，
既不影响 Agent 当前推理，也不会诱发「刚读完就被折叠 → 重新读取」的回环。

安全性（严格规避本项目历史事故）：
- 只改写**已带稳定 id** 的 ToolMessage，且以 delta 形式
  `Command(update={"messages": [...]})` 回传，经 messages reducer 按 id 就地替换。
  **不用 Overwrite**：整通道重写会与同一轮里已启用的 summarization 中间件的 state
  更新相互覆盖；delta 走 reducer 则与其它中间件的更新按 id 各自合并，互不影响。
- 目标消息 id 稳定（非 None），不会触发 DeltaChannel 重放时的 id 重复
  （即曾导致 /history HTTP 400 的那类问题）。
- 保留 id / tool_call_id / name / status，维持 tool_call ↔ tool_result 配对。
- additional_kwargs["_stale_offloaded"] 幂等标记，保证每条结果只卸载一次。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from langchain.agents.middleware import (
    AgentMiddleware,
    ExtendedModelResponse,
    ModelRequest,
)
from langchain_core.messages import ToolMessage
from langgraph.types import Command

logger = logging.getLogger("app.stale_offload")

# deepagents 自动卸载排除名单里的两个「大户」，需要我们额外处理
_OFFLOAD_TOOLS = {"read_file", "grep"}
# 最近多少条消息保持原样（不折叠），避免影响 Agent 当前推理与重复读取回环
KEEP_RECENT = int(os.environ.get("STALE_OFFLOAD_KEEP_RECENT", "30"))
# 单条结果文本超过多少字符才折叠（针对旧结果，阈值可较激进）
OFFLOAD_THRESHOLD_CHARS = int(os.environ.get("STALE_OFFLOAD_THRESHOLD_CHARS", "6000"))
# 指针里保留的预览行数（头 / 尾）
_PREVIEW_HEAD_LINES = 6
_PREVIEW_TAIL_LINES = 4
_MAX_PREVIEW_LINE_CHARS = 500
_OFFLOAD_PREFIX = "/large_tool_results"
_TAG = "_stale_offloaded"


class StaleToolResultOffloadMiddleware(AgentMiddleware):
    """把越过最近窗口的大号 read_file / grep 结果卸载到磁盘，state 只留指针。"""

    def __init__(self, backend: Any) -> None:
        super().__init__()
        self._backend = backend

    @staticmethod
    def _extract_text(msg: ToolMessage) -> Optional[str]:
        """提取纯文本内容；含非文本块（如二进制 / 图片结果）时返回 None 表示不折叠。"""
        content = msg.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
                else:
                    return None
            return "\n".join(parts)
        return None

    def _preview(self, text: str, file_path: str) -> str:
        lines = text.splitlines()
        if len(lines) <= _PREVIEW_HEAD_LINES + _PREVIEW_TAIL_LINES:
            body = "\n".join(line[:_MAX_PREVIEW_LINE_CHARS] for line in lines)
        else:
            head = "\n".join(line[:_MAX_PREVIEW_LINE_CHARS] for line in lines[:_PREVIEW_HEAD_LINES])
            tail = "\n".join(line[:_MAX_PREVIEW_LINE_CHARS] for line in lines[-_PREVIEW_TAIL_LINES:])
            omitted = len(lines) - _PREVIEW_HEAD_LINES - _PREVIEW_TAIL_LINES
            body = f"{head}\n... [中间 {omitted} 行已折叠] ...\n{tail}"
        return (
            f"[旧工具结果已卸载至文件系统：{file_path}]\n"
            f"如需完整内容，请用 read_file 分段读取该路径（指定 offset / limit）。\n\n"
            f"{body}"
        )

    async def _offload(self, msg: ToolMessage) -> Optional[ToolMessage]:
        """把单条大结果写盘并返回指针版 ToolMessage；不满足条件或失败时返回 None。"""
        text = self._extract_text(msg)
        if text is None or len(text) <= OFFLOAD_THRESHOLD_CHARS:
            return None

        # 稳定且文件系统安全的路径：同一 tool_call_id 幂等，重复写覆盖同一文件
        raw_id = msg.tool_call_id or msg.id or "unknown"
        safe_id = "".join(c if (c.isalnum() or c in "-_") else "_" for c in raw_id)
        file_path = f"{_OFFLOAD_PREFIX}/stale-{safe_id}"
        try:
            result = await self._backend.awrite(file_path, text)
        except Exception:
            return None
        if getattr(result, "error", None):
            return None

        return ToolMessage(
            content=self._preview(text, file_path),
            id=msg.id,
            tool_call_id=msg.tool_call_id,
            name=msg.name,
            status=msg.status,
            additional_kwargs={**(msg.additional_kwargs or {}), _TAG: file_path},
            response_metadata=dict(getattr(msg, "response_metadata", {}) or {}),
        )

    async def awrap_model_call(self, request: ModelRequest, handler):  # type: ignore[override]
        messages = list(request.messages or [])
        cutoff = len(messages) - KEEP_RECENT
        if cutoff <= 0:
            return await handler(request)

        replacements: dict[int, ToolMessage] = {}
        for idx in range(cutoff):
            msg = messages[idx]
            if not isinstance(msg, ToolMessage):
                continue
            if msg.name not in _OFFLOAD_TOOLS:
                continue
            if (msg.additional_kwargs or {}).get(_TAG):
                continue
            new_msg = await self._offload(msg)
            if new_msg is not None:
                replacements[idx] = new_msg

        if not replacements:
            return await handler(request)

        logger.debug("stale-offload: 折叠 %d 条陈旧 read_file/grep 结果", len(replacements))

        # 请求侧：换上精简版，同步缩小本轮模型上下文
        for idx, new_msg in replacements.items():
            messages[idx] = new_msg
        if hasattr(request, "override"):
            request = request.override(messages=messages)
        else:
            request.messages = messages

        response = await handler(request)

        # 状态侧：只回传被改写的消息（delta），reducer 按 id 就地替换、与其它中间件互不覆盖
        command = Command(update={"messages": list(replacements.values())})
        return ExtendedModelResponse(model_response=response, command=command)
