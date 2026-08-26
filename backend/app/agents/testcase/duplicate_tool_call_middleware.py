"""重复工具调用拦截中间件（缺陷④治理）。

背景：推理模型（deepseek-v4 系列）在长推理后偶发"言行不一"——reasoning 中
已规划好下一步正文，最终输出却原样重复上一轮已执行过的整组工具调用
（2026-08-18 thread 6f08f7ab 实证：AI(read_file+write_todos) → Tool结果×2 →
AI(同名同参、tool_call id 全新、reasoning 360→10404 字符) → Tool结果×2，
21KB SKILL 重复读取、40K input tokens 浪费、UI 出现两条雷同过渡语）。
已逐一排除平台/中间件重放：这是同 run 内模型的二次生成，无法在上游预防，
只能在工具执行前拦截其后果。

策略（保守全等比对，正常路径零介入）：
- 仅当「上一回合带 tool_calls 的 AI 消息」与「当前 AI 消息」之间只隔着
  ToolMessage（即紧邻的下一个模型回合），且整组调用签名（name+args 规范化，
  忽略 tool_call id）有序全等时，判定为重复回合；
- 乱序、部分重复、args 微调、隔着 HumanMessage/SystemMessage 一律放行
  （read_file 重读已编辑文件等合法场景不受影响）；
- 命中后剥离重复 tool_calls（不执行），正文附加拦截注记，追加纠偏消息，
  jump_to "model" 让模型基于已有工具结果继续；
- 防循环：纠偏消息（HumanMessage）挡在中间，下一次扫描自然不命中；
  若模型在纠偏后仍第三次原样重发，剥离 tool_calls 改写为可见诊断并
  结束当前回合（对齐 TruncationRetryMiddleware 的兜底哲学）。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Overwrite

logger = logging.getLogger(__name__)

# 纠偏消息标记：防循环加固识别用（见 after_model 注释）
_INTERCEPT_MARK = "_duplicate_tool_call_intercept"

_INTERCEPT_NOTE = (
    "\n\n> ⚠️ 本条消息附带的工具调用与上一轮完全相同，已被系统拦截、未执行。"
)

_NUDGE_TEMPLATE = (
    "[系统提示] 检测到你刚才重复发起了与上一轮完全相同的工具调用"
    "（{tool_names}），与已执行调用同名同参，系统已拦截、未执行。"
    "这些工具的结果已在上文 ToolMessage 中，请直接基于已有结果继续下一步"
    "（如开始撰写报告正文），禁止原样重发相同调用。"
)

_DIAGNOSIS_TEMPLATE = (
    "⚠️ 系统连续检测到重复的工具调用（{tool_names}），已拦截未执行。"
    "这些调用的结果在上文 ToolMessage 中，但模型连续重发相同调用、无法自行恢复，"
    "本轮已终止以避免无效循环。请回复「继续」让我基于已有结果接着执行。"
)


def _call_signatures(tool_calls: list[Any]) -> tuple[str, ...]:
    """生成一组工具调用的有序签名（name + 规范化 args，忽略 tool_call id）。"""
    sigs: list[str] = []
    for tc in tool_calls:
        if isinstance(tc, dict):
            name = tc.get("name", "?")
            args = tc.get("args", {})
        else:
            name = getattr(tc, "name", "?")
            args = getattr(tc, "args", {})
        try:
            args_text = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            args_text = str(args)
        sigs.append(f"{name}:{args_text}")
    return tuple(sigs)


def _strip_tool_calls(ai_msg: AIMessage) -> AIMessage:
    """创建 AI 消息副本，移除 tool_calls 与 additional_kwargs 中的 tool_calls。

    与 phase_review_middleware._strip_tool_calls 同构：剥离后的调用不执行，
    ToolCallAdjacencyMiddleware 视其为纯文本消息，邻接关系合法。
    """
    new_msg = ai_msg.model_copy()
    new_msg.tool_calls = []
    new_msg.invalid_tool_calls = []
    ak = dict(getattr(new_msg, "additional_kwargs", {}) or {})
    ak.pop("tool_calls", None)
    new_msg.additional_kwargs = ak
    return new_msg


def _append_note(ai_msg: AIMessage, note: str) -> AIMessage:
    """在 AI 消息正文末尾追加注记（兼容 str 与 content-block list）。"""
    new_msg = ai_msg.model_copy()
    if isinstance(new_msg.content, list):
        new_msg.content = [*new_msg.content, {"type": "text", "text": note}]
    else:
        new_msg.content = f"{new_msg.content or ''}{note}"
    return new_msg


def _tool_names(tool_calls: list[Any]) -> str:
    names = [
        tc.get("name", "?") if isinstance(tc, dict) else getattr(tc, "name", "?")
        for tc in tool_calls
    ]
    return "、".join(names)


class DuplicateToolCallMiddleware(AgentMiddleware):
    """拦截与上一回合签名全等的重复工具调用（低频模型行为缺陷兜底）。"""

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: dict[str, Any], runtime: Any) -> dict[str, Any] | None:
        messages: list[Any] = state.get("messages") or []
        if not messages:
            return None
        last = messages[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return None

        # 逆向扫描：跳过 ToolMessage，定位上一个非 ToolMessage。
        # 只允许紧邻的上一个工具调用回合参与比对——中间隔着
        # HumanMessage/SystemMessage/纯文本 AI 时不适用（可能是用户反馈后的
        # 有意重试，保守放行）。
        prev: AIMessage | None = None
        boundary_idx: int | None = None  # 上一个非 ToolMessage 的下标
        for i in range(len(messages) - 2, -1, -1):
            m = messages[i]
            if isinstance(m, ToolMessage):
                continue
            boundary_idx = i
            if isinstance(m, AIMessage) and m.tool_calls:
                prev = m
            break

        last_sigs = _call_signatures(last.tool_calls)

        if prev is None:
            # 防循环加固：边界是带标记的纠偏消息，说明上一轮已被拦截过一次；
            # 模型仍原样重发 → 继续向前找到最近一次真实执行过的同签名回合，
            # 确认后剥离 + 诊断，不再 jump（避免无效循环）。
            boundary = messages[boundary_idx] if boundary_idx is not None else None
            if not (
                isinstance(boundary, HumanMessage)
                and (boundary.additional_kwargs or {}).get(_INTERCEPT_MARK)
            ):
                return None
            earlier: AIMessage | None = None
            for j in range(boundary_idx - 1, -1, -1):
                m = messages[j]
                if isinstance(m, ToolMessage):
                    continue
                if isinstance(m, AIMessage):
                    if m.tool_calls:
                        earlier = m
                        break
                    continue  # 跳过已被剥离 tool_calls 的拦截残留
                break  # 撞到其他类型消息（Human/System）则停止
            if earlier is None or _call_signatures(earlier.tool_calls) != last_sigs:
                return None
            names = _tool_names(last.tool_calls)
            logger.error(
                "duplicate tool-call loop persisted after intercept (%s); "
                "returning visible diagnosis",
                names,
            )
            diagnosis = _strip_tool_calls(last).model_copy(
                update={"content": _DIAGNOSIS_TEMPLATE.format(tool_names=names)}
            )
            return {"messages": Overwrite(value=[*messages[:-1], diagnosis])}

        if _call_signatures(prev.tool_calls) != last_sigs:
            return None

        # 命中：剥离重复 tool_calls（不执行），追加纠偏消息，让模型基于
        # 已有工具结果继续。被剥离的调用未执行必须如实告知，否则模型会
        # 残留「已读取/已保存」等虚假声明（同 phase_review 的教训）。
        names = _tool_names(last.tool_calls)
        logger.warning(
            "duplicate tool-call round intercepted (%s); stripping %d call(s)",
            names,
            len(last.tool_calls),
        )
        cleaned = _append_note(_strip_tool_calls(last), _INTERCEPT_NOTE)
        nudge = HumanMessage(
            content=_NUDGE_TEMPLATE.format(tool_names=names),
            additional_kwargs={_INTERCEPT_MARK: True},
        )
        return {
            "messages": Overwrite(value=[*messages[:-1], cleaned, nudge]),
            "jump_to": "model",
        }
