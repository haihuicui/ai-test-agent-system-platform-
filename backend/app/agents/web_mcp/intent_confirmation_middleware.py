"""Web 意图确认人机交互中间件。

在 Web Agent 检测到已有匹配功能时，将开放文字反问改造为结构化 interrupt，
由前端渲染一键选择面板；用户选择后注入带决策的 HumanMessage 并继续工作流。
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import interrupt


_INTENT_MARKER_RE = re.compile(
    r"<INTENT_CONFIRMATION>\s*(.*?)\s*</INTENT_CONFIRMATION>",
    re.DOTALL | re.IGNORECASE,
)


def _extract_text(content: Any) -> str:
    """提取 AI 消息的纯文本内容。

    content 为 str 时直接返回；为 content blocks（list）时拼接其中的 text 块——
    直接 str(list) 会得到 repr，导致标记正则失效。
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content or "")


def _parse_intent_confirmation(content: str) -> dict[str, Any] | None:
    """从 AI 消息中提取意图确认标记。

    Returns:
        解析后的 payload；若未找到标记、JSON 非法或类型不匹配则返回 None。
    """
    match = _INTENT_MARKER_RE.search(content)
    if not match:
        return None

    raw = match.group(1).strip()
    # 兼容模型在标记内包裹 markdown 代码块的情况
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
    if raw.endswith("```"):
        raw = raw.rsplit("\n", 1)[0]
    raw = raw.strip()

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("type") != "web_intent_confirmation":
        return None

    existing = payload.get("existing_function") or {}
    candidates = payload.get("candidates") or []
    has_existing = bool(existing.get("id") and existing.get("identifier"))
    has_candidates = bool(
        isinstance(candidates, list)
        and len(candidates) > 0
        and all(
            isinstance(c, dict) and c.get("id") and c.get("identifier")
            for c in candidates
        )
    )

    if not has_existing and not has_candidates:
        return None

    # 校验 candidates 列表，过滤无效条目
    if isinstance(candidates, list) and len(candidates) > 0:
        payload["candidates"] = [
            c for c in candidates
            if isinstance(c, dict) and c.get("id") and c.get("identifier")
        ]

    return payload


def _build_resume_human_message(
    decision: str, payload: dict[str, Any], comment: str = ""
) -> HumanMessage:
    """根据用户决策构造恢复后的 HumanMessage。"""
    existing = payload.get("existing_function") or {}
    candidates = payload.get("candidates") or []
    comment_text = comment.strip()
    comment_clause = f"补充说明：{comment_text}。" if comment_text else ""

    # 解析被选中的功能信息
    def _resolve_function_info(target_identifier: str = "") -> dict[str, str]:
        """从 existing_function 或 candidates 中解析功能信息。"""
        if existing.get("identifier") == target_identifier or not target_identifier:
            return {
                "function_id": existing.get("id", ""),
                "identifier": existing.get("identifier", ""),
                "display_name": existing.get("display_name", ""),
            }
        for c in candidates:
            if c.get("id") == target_identifier or c.get("identifier") == target_identifier:
                return {
                    "function_id": c.get("id", ""),
                    "identifier": c.get("identifier", ""),
                    "display_name": c.get("display_name", ""),
                }
        return {
            "function_id": existing.get("id", ""),
            "identifier": existing.get("identifier", ""),
            "display_name": existing.get("display_name", ""),
        }

    info = _resolve_function_info()
    function_id = info["function_id"]
    identifier = info["identifier"]
    display_name = info["display_name"]

    if decision.startswith("candidate:"):
        # 用户从多个候选中选择了某个功能
        selected_id = decision.split(":", 1)[1].strip()
        info_sel = _resolve_function_info(selected_id)
        function_id = info_sel["function_id"]
        identifier = info_sel["identifier"]
        display_name = info_sel["display_name"]
        feedback = (
            f"用户从 {len(candidates)} 个候选功能中选择了 {identifier}（{display_name}）。"
            f"{comment_clause}"
            "请基于该功能及其子功能，按生成测试流程（planner → case-designer → generator）"
            "生成/完善测试计划、用例与脚本，并执行执行邀约。"
        )
    elif decision == "expand":
        feedback = (
            f"用户选择扩展已有功能 {identifier}（{display_name}）。"
            f"{comment_clause}"
            "请基于该功能及其子功能，按生成测试流程（planner → case-designer → generator）"
            "生成/完善测试计划、用例与脚本，并执行执行邀约。"
        )
    elif decision == "new":
        feedback = (
            f"用户选择新建功能。{comment_clause}"
            "请忽略上述匹配建议，按创建功能流程新建 Web 功能。"
        )
    elif decision == "view_details":
        feedback = (
            f"用户希望先查看功能 {identifier}（{display_name}）的详情。"
            f"{comment_clause}"
            "请调用 get_function_details 展示信息，并在展示完信息后再次输出意图确认标记，"
            "供用户最终选择。"
        )
    elif decision == "execute":
        feedback = (
            f"用户选择立即执行 {identifier}（{display_name}）的测试。"
            f"{comment_clause}"
            "请调用 get_function_details 获取子功能列表，"
            "然后 get_web_sub_function_artifacts → download_web_script → "
            "execute_web_script → save_web_test_report 完成执行并保存报告。"
        )
    else:
        feedback = f"收到选择：{decision}。{comment_clause}请按用户意图继续。"

    return HumanMessage(
        content=f"[Web意图确认] {feedback}",
        additional_kwargs={
            "_web_intent_confirmation": {
                "decision": decision,
                "comment": comment_text,
                "function_id": function_id,
                "identifier": identifier,
                "display_name": display_name,
            }
        },
    )


class WebIntentConfirmationMiddleware(AgentMiddleware):
    """Web 测试意图确认中间件。

    与 HumanInTheLoopMiddleware / PhaseReviewMiddleware 协作：
    - 若当前 AI 消息包含待审批的工具调用，先让路给工具审批机制。
    - 若当前 AI 消息是意图推荐（无工具调用），触发结构化中断。
    """

    @hook_config(can_jump_to=["model", "end"])
    def after_model(self, state: dict[str, Any], runtime: Any) -> dict[str, Any] | None:
        """检测意图确认标记并触发结构化中断。"""
        messages = state.get("messages", [])
        last_ai = next(
            (m for m in reversed(messages) if isinstance(m, AIMessage)),
            None,
        )
        if not last_ai:
            return None

        # 工具调用先交给 ToolApproval / HumanInTheLoop 处理
        if last_ai.tool_calls:
            return None

        content = _extract_text(last_ai.content)
        payload = _parse_intent_confirmation(content)
        if not payload:
            return None

        # ── 全局去重：若历史中已有 [Web意图确认] HumanMessage（非 view_details），
        #     说明意图确认流程已完成，后续 AI 消息再输出 <INTENT_CONFIRMATION> 标记
        #     属于模型行为错误，应拦截而非重复弹窗。
        #     例外：view_details 决策会要求模型"展示完信息后再次输出意图确认标记"，
        #     此时应允许再次触发。
        existing_intent_msgs = [
            m for m in messages
            if isinstance(m, HumanMessage)
            and str(m.content).startswith("[Web意图确认]")
        ]
        if existing_intent_msgs:
            last_intent_msg = existing_intent_msgs[-1]
            ak = (last_intent_msg.additional_kwargs or {})
            ic = ak.get("_web_intent_confirmation", {})
            last_decision = ic.get("decision", "")
            if last_decision and last_decision != "view_details":
                return None

        # ── 自动跳过确认：唯一功能 + 全部 pass + auto_skip 标记 ──
        candidates = payload.get("candidates") or []
        existing = payload.get("existing_function") or {}
        auto_skip = payload.get("auto_skip", False)

        has_single_existing = bool(existing.get("id")) and len(candidates) == 0
        has_single_candidate = len(candidates) == 1 and not existing.get("id")

        if auto_skip and (has_single_existing or has_single_candidate):
            # 唯一精确匹配 → 自动选择 expand，不触发中断
            return {
                "messages": [_build_resume_human_message("expand", payload)],
                "jump_to": "model",
            }

        response = interrupt(payload)

        decision = "expand"
        comment = ""
        if isinstance(response, dict):
            decision = response.get("decision") or "expand"
            comment = response.get("comment") or ""
        elif isinstance(response, list) and response:
            first = response[0]
            if isinstance(first, dict):
                decision = first.get("decision") or "expand"
                comment = first.get("comment") or ""

        return {
            "messages": [_build_resume_human_message(decision, payload, comment)],
            "jump_to": "model",
        }

    async def aafter_model(
        self, state: dict[str, Any], runtime: Any
    ) -> dict[str, Any] | None:
        """异步版本直接复用同步逻辑。"""
        return self.after_model(state, runtime)
