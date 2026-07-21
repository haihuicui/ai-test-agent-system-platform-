"""Web 执行邀约人机交互中间件。

在 Web Agent 完成测试脚本生成后，将开放文字的反问改造为结构化 interrupt，
由前端渲染一键选择面板；用户选择后注入带决策的 HumanMessage 并继续工作流。
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import interrupt


_EXECUTION_INVITATION_MARKER_RE = re.compile(
    r"<EXECUTION_INVITATION>\s*(.*?)\s*</EXECUTION_INVITATION>",
    re.DOTALL | re.IGNORECASE,
)


_DEFAULT_ALTERNATIVES = [
    {"key": "execute", "label": "立即执行"},
    {"key": "skip", "label": "暂不执行"},
    {"key": "edit", "label": "修改脚本"},
    {"key": "other", "label": "其他"},
]


def _parse_execution_invitation(content: str) -> dict[str, Any] | None:
    """从 AI 消息中提取执行邀约标记。

    Returns:
        解析后的 payload；若未找到标记、JSON 非法或类型不匹配则返回 None。
    """
    match = _EXECUTION_INVITATION_MARKER_RE.search(content)
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
    if payload.get("type") != "execution_invitation":
        return None

    # 允许 model 不填 alternatives，使用默认值
    if not payload.get("alternatives"):
        payload["alternatives"] = _DEFAULT_ALTERNATIVES

    return payload


def _build_resume_human_message(
    decision: str, payload: dict[str, Any], comment: str = ""
) -> HumanMessage:
    """根据用户决策构造恢复后的 HumanMessage。"""
    mode = payload.get("mode", "web")
    script_name = payload.get("script_name", "")
    test_count = payload.get("test_count", 0)
    sub_function_id = payload.get("sub_function_id", "")
    comment_text = comment.strip()
    comment_clause = f"补充说明：{comment_text}。" if comment_text else ""

    metadata = {
        "decision": decision,
        "comment": comment_text,
        "mode": mode,
    }
    if script_name:
        metadata["script_name"] = script_name
    if sub_function_id:
        metadata["sub_function_id"] = sub_function_id

    if decision == "execute":
        feedback = (
            f"用户选择立即执行测试"
            f"（{test_count} 个用例{f'，脚本 {script_name}' if script_name else ''}）。"
            f"{comment_clause}"
            "请调用 get_web_sub_function_artifacts 确认成果物，"
            "然后 download_web_script → execute_web_script → save_web_test_report 完成执行并保存报告。"
        )
    elif decision == "skip":
        feedback = (
            f"用户选择暂不执行测试"
            f"{f'（{script_name}）' if script_name else ''}。"
            f"{comment_clause}"
            "请停止执行流程，礼貌等待用户后续指令，不要主动调用任何执行类工具。"
        )
    elif decision == "edit":
        feedback = (
            f"用户希望先修改脚本"
            f"{f'（{script_name}）' if script_name else ''}。"
            f"{comment_clause}"
            "请询问用户具体需要修改哪些内容（如用例、定位器、断言、数据等），"
            "收到明确需求后再修改脚本；修改完成后再输出执行邀约标记。"
        )
    elif decision == "other":
        feedback = (
            f"用户选择其他操作"
            f"{f'（{script_name}）' if script_name else ''}。"
            f"{comment_clause}"
            "请按用户说明继续处理，不要主动调用执行类工具，除非用户明确要求执行。"
        )
    else:
        feedback = f"收到选择：{decision}。{comment_clause}请按用户意图继续。"

    return HumanMessage(
        content=f"[执行邀约] {feedback}",
        additional_kwargs={"_execution_invitation": metadata},
    )


class WebExecutionInvitationMiddleware(AgentMiddleware):
    """Web 测试执行邀约中间件。

    与 HumanInTheLoopMiddleware / PhaseReviewMiddleware / WebIntentConfirmationMiddleware 协作：
    - 若当前 AI 消息包含待审批的工具调用，先让路给工具审批机制。
    - 若当前 AI 消息是执行邀约（无工具调用），触发结构化中断。
    """

    @hook_config(can_jump_to=["model", "end"])
    def after_model(self, state: dict[str, Any], runtime: Any) -> dict[str, Any] | None:
        """检测执行邀约标记并触发结构化中断。"""
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
        payload = _parse_execution_invitation(content)
        if not payload:
            return None

        # 防止同一条 AI 消息重复触发
        after_ai = messages[messages.index(last_ai) + 1 :]
        if any(
            isinstance(m, HumanMessage)
            and str(m.content).startswith("[执行邀约]")
            for m in after_ai
        ):
            return None

        response = interrupt(payload)

        decision = "execute"
        comment = ""
        if isinstance(response, dict):
            decision = response.get("decision") or "execute"
            comment = response.get("comment") or ""
        elif isinstance(response, list) and response:
            first = response[0]
            if isinstance(first, dict):
                decision = first.get("decision") or "execute"
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
