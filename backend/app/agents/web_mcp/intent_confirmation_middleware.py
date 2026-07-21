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
    if not existing.get("id") or not existing.get("identifier"):
        return None

    return payload


def _build_resume_human_message(
    decision: str, payload: dict[str, Any], comment: str = ""
) -> HumanMessage:
    """根据用户决策构造恢复后的 HumanMessage。"""
    existing = payload.get("existing_function", {})
    function_id = existing.get("id", "")
    identifier = existing.get("identifier", "")
    display_name = existing.get("display_name", "")
    comment_text = comment.strip()
    comment_clause = f"补充说明：{comment_text}。" if comment_text else ""

    if decision == "expand":
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

        content = str(last_ai.content or "")
        payload = _parse_intent_confirmation(content)
        if not payload:
            return None

        # 防止同一条 AI 消息重复触发
        after_ai = messages[messages.index(last_ai) + 1 :]
        if any(
            isinstance(m, HumanMessage)
            and str(m.content).startswith("[Web意图确认]")
            for m in after_ai
        ):
            return None

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
