"""API 执行邀约人机交互中间件。

在 API Agent 完成测试脚本/场景生成后，将开放文字的反问改造为结构化 interrupt，
由前端渲染一键选择面板；用户选择后注入带决策的 HumanMessage 并继续工作流。

风险评估：根据执行上下文（模式、端点数、操作类型）评估风险等级（LOW/MEDIUM/HIGH），
附加到 interrupt payload 中供前端差异化展示。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import interrupt

from app.agents.api.execution_risk import evaluate_risk, extract_risk_context

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langgraph.types import Command

    from langchain.agents.middleware.types import ToolCallRequest

logger = logging.getLogger(__name__)


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

# 执行硬门禁管控的工具：必须存在用户「立即执行」邀约决策才允许调用。
# execute_api_script_by_artifact_id 不在此列——用户显式提供 Script ID 即授权。
_GATED_EXECUTION_TOOLS = {"execute_scenario", "execute_api_script"}


def _find_execute_decision(
    messages: list[Any],
    *,
    scenario_id: str = "",
    endpoint_id: str = "",
    tool_name: str = "",
) -> bool:
    """检查消息历史中是否存在匹配的「执行邀约 · 立即执行」决策。

    两级匹配：
    1. 精确：邀约 metadata 的 scenario_id/endpoint_id 与工具参数一致 → 放行；
    2. 兜底：存在同 mode 的 execute 决策（模型可能在邀约 JSON 中漏填 ID）
       → 放行但记 warning，避免误拦正常流程。
    """
    expected_mode = "scenario" if tool_name == "execute_scenario" else "api"
    fallback = False
    for m in reversed(messages):
        if not isinstance(m, HumanMessage):
            continue
        ak = m.additional_kwargs if isinstance(m.additional_kwargs, dict) else {}
        meta = ak.get("_execution_invitation")
        if not isinstance(meta, dict) or meta.get("decision") != "execute":
            continue
        if scenario_id and meta.get("scenario_id") == scenario_id:
            return True
        if endpoint_id and meta.get("endpoint_id") == endpoint_id:
            return True
        if meta.get("mode", "api") == expected_mode:
            fallback = True
    if fallback:
        logger.warning(
            "执行门禁兜底放行 %s：存在同模式邀约执行决策但 ID 未精确匹配",
            tool_name,
        )
    return fallback


def _build_gate_block_message(tool_call: dict[str, Any], tool_name: str) -> ToolMessage:
    """构造执行门禁拦截的 ToolMessage（模型当轮可见，可先补邀约再重试）。"""
    content = json.dumps({
        "success": False,
        "error": "执行门禁拦截：未检测到用户「立即执行」的邀约决策",
        "message": (
            "按流程必须先在回复末尾输出 <EXECUTION_INVITATION> 标记，"
            "等待用户选择「立即执行」后才能调用执行工具。"
            "请先输出邀约标记；若用户已在对话中明确同意执行，请补发邀约以完成确认闭环。"
        ),
    }, ensure_ascii=False)
    return ToolMessage(
        content=content,
        tool_call_id=tool_call["id"],
        name=tool_name,
        status="error",
    )


def _stable_invitation_id(payload: dict[str, Any], content: str) -> str:
    """从邀约内容推导稳定 ID。

    LangGraph 的 interrupt 恢复语义是「节点/hook 整体重新执行」而非从
    interrupt 点续跑：resume 到达后 after_model 会从头再跑一遍。若用随机
    UUID，重执行时 ID 必然变化，前端 resume 携带的旧 ID 永远不匹配，
    正常确认也会被误判为幽灵而反复重弹（E2E 实测确认）。
    内容 hash 保证同一邀约为同一 ID、不同邀约为不同 ID。
    """
    raw = "|".join([
        str(payload.get("mode", "")),
        str(payload.get("endpoint_id", "")),
        str(payload.get("scenario_id", "")),
        str(payload.get("script_name", "")),
        str(payload.get("test_count", "")),
        content,
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _interrupt_with_invitation_check(payload: dict[str, Any], max_reinterrupts: int = 3) -> Any:
    """触发邀约 interrupt，并校验 resume 是否属于本次邀约。

    背景与 testcase 的 _interrupt_with_phase_check 相同：前端 SDK 串行排队
    所有 submit，重复点击或过期卡片产生的 resume 会被排队的下一个
    pending interrupt 消费，造成"幽灵确认"。邀约 payload 携带
    invitation_id，前端 resume 时回传；不匹配则重新弹出当前卡片，
    最多重弹 max_reinterrupts 次后兜底接受（避免极端死循环）。
    未携带 invitation_id 的旧版前端 payload 直接放行（向后兼容）。
    """
    response = interrupt(payload)
    for _ in range(max_reinterrupts):
        if not isinstance(response, dict):
            return response
        response_id = response.get("invitation_id")
        if response_id is None or response_id == payload.get("invitation_id"):
            return response
        logger.warning(
            "邀约 resume 的 invitation_id 不匹配（期望 %s，实得 %s），重新弹出当前卡片",
            payload.get("invitation_id"),
            response_id,
        )
        response = interrupt(payload)
    return response


async def _derive_method_risk_flags(endpoint_id: str) -> tuple[bool, bool] | None:
    """从 endpoint 元数据静态推导 (has_write_ops, has_delete_ops)。

    邀约 payload 中的操作类型由模型自报，属于不受信输入——模型低报风险会
    导致 LOW 风险自动执行路径跳过人工确认。这里以数据库中的 HTTP method
    为准静态推导；任何失败（DB 抖动、endpoint 不存在、非法 UUID）返回
    None，调用方回退模型自报值（fail-open，不阻断邀约）。
    """
    try:
        from sqlalchemy import select

        from app.config.database import async_session_factory
        from app.models.api_endpoint import APIEndpoint

        async with async_session_factory() as session:
            result = await session.execute(
                select(APIEndpoint.method).where(APIEndpoint.id == endpoint_id)
            )
            method = (result.scalar_one_or_none() or "").upper()
        if not method:
            return None
        return method in {"POST", "PUT", "PATCH"}, method == "DELETE"
    except Exception as exc:
        logger.warning("静态推导 endpoint %s 的 method 失败，回退模型自报值: %s", endpoint_id, exc)
        return None


def _parse_execution_invitation(content: str) -> dict[str, Any] | None:
    """从 AI 消息中提取执行邀约标记。"""
    match = _EXECUTION_INVITATION_MARKER_RE.search(content)
    if not match:
        return None

    raw = match.group(1).strip()
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

    if not payload.get("alternatives"):
        payload["alternatives"] = _DEFAULT_ALTERNATIVES

    return payload


def _build_resume_human_message(
    decision: str, payload: dict[str, Any], comment: str = ""
) -> HumanMessage:
    """根据用户决策构造恢复后的 HumanMessage。"""
    mode = payload.get("mode", "api")
    script_name = payload.get("script_name", "")
    test_count = payload.get("test_count", 0)
    endpoint_id = payload.get("endpoint_id", "")
    scenario_id = payload.get("scenario_id", "")
    comment_text = comment.strip()
    comment_clause = f"补充说明：{comment_text}。" if comment_text else ""

    metadata = {
        "decision": decision,
        "comment": comment_text,
        "mode": mode,
    }
    if script_name:
        metadata["script_name"] = script_name
    if endpoint_id:
        metadata["endpoint_id"] = endpoint_id
    if scenario_id:
        metadata["scenario_id"] = scenario_id

    if decision == "execute":
        if mode == "scenario":
            # 场景模式走 execute_scenario，不是单端点的 download/execute_api_script 链路
            count_clause = f"（{test_count} 个步骤{f'，场景 {script_name}' if script_name else ''}）"
            scenario_clause = (
                f"请调用 execute_scenario 执行场景（scenario_id={scenario_id}，"
                if scenario_id
                else "请调用 execute_scenario 执行场景（"
            )
            feedback = (
                f"用户选择立即执行场景测试{count_clause}。"
                f"{comment_clause}"
                f"{scenario_clause}必须带 execution_config 中的 env_id），"
                "执行后按红线做反假阳性校验并保存报告。"
            )
        else:
            feedback = (
                f"用户选择立即执行测试"
                f"（{test_count} 个用例{f'，脚本 {script_name}' if script_name else ''}）。"
                f"{comment_clause}"
                "请调用 download_api_script 下载脚本，"
                "然后 execute_api_script 执行（必须带 execution_config 中的 env_id），"
                "执行后按红线做反假阳性校验并保存报告。"
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
            "请询问用户具体需要修改哪些内容（如用例、断言、请求数据、环境变量等），"
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


class APIExecutionInvitationMiddleware(AgentMiddleware):
    """API 测试执行邀约中间件。"""

    @hook_config(can_jump_to=["model", "end"])
    def after_model(
        self,
        state: dict[str, Any],
        runtime: Any,
        *,
        derived_flags: tuple[bool, bool] | None = None,
    ) -> dict[str, Any] | None:
        """检测执行邀约标记并触发结构化中断。

        derived_flags: aafter_model 异步路径从 endpoint 元数据静态推导的
        (has_write_ops, has_delete_ops)，用于覆盖模型自报的不受信值。
        """
        messages = state.get("messages", [])
        last_ai = next(
            (m for m in reversed(messages) if isinstance(m, AIMessage)),
            None,
        )
        if not last_ai:
            return None

        if last_ai.tool_calls:
            return None

        content = str(last_ai.content or "")
        payload = _parse_execution_invitation(content)
        if not payload:
            return None

        # 风险评估信源修正：api 单端点模式以 DB method 推导为准（模型自报不受信）；
        # scenario 模式恒 HIGH（evaluate_risk 内置），无需推导
        if derived_flags is not None and payload.get("mode", "api") == "api":
            payload["has_write_ops"], payload["has_delete_ops"] = derived_flags

        # 附加风险评估（LOW/MEDIUM/HIGH），供前端差异化展示
        risk_ctx = extract_risk_context(payload)
        risk_level, risk_reason = evaluate_risk(risk_ctx)
        payload["risk_level"] = risk_level.value
        payload["risk_reason"] = risk_reason
        # 幽灵确认防护：resume 必须回传匹配的 invitation_id（见
        # _interrupt_with_invitation_check 与 testcase 的 _phase 校验根因一致）。
        # ID 必须对 hook 重执行稳定——用内容 hash 而非随机 UUID。
        payload["invitation_id"] = _stable_invitation_id(payload, content)

        after_ai = messages[messages.index(last_ai) + 1 :]
        if any(
            isinstance(m, HumanMessage)
            and str(m.content).startswith("[执行邀约]")
            for m in after_ai
        ):
            return None

        response = _interrupt_with_invitation_check(payload)

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
        """异步版本：先做 endpoint method 静态推导，再复用同步逻辑。

        同步路径无法安全桥接异步 DB 查询（跨事件循环风险），回退模型自报值；
        生产 LangGraph server 走异步路径，静态推导在此生效。
        """
        derived: tuple[bool, bool] | None = None
        messages = state.get("messages", [])
        last_ai = next(
            (m for m in reversed(messages) if isinstance(m, AIMessage)),
            None,
        )
        if last_ai and not last_ai.tool_calls:
            payload = _parse_execution_invitation(str(last_ai.content or ""))
            if payload and payload.get("mode", "api") == "api" and payload.get("endpoint_id"):
                derived = await _derive_method_risk_flags(str(payload["endpoint_id"]))
        return self.after_model(state, runtime, derived_flags=derived)

    # ------------------------------------------------------------------
    # 执行硬门禁：未收到用户「立即执行」邀约决策前，拦截执行类工具调用。
    # 只读 state 做校验（纯同步逻辑），同步/异步路径行为一致。
    # ------------------------------------------------------------------

    def _check_execution_gate(
        self, request: "ToolCallRequest"
    ) -> ToolMessage | None:
        tool_call = request.tool_call
        tool_name = tool_call.get("name", "")
        if tool_name not in _GATED_EXECUTION_TOOLS:
            return None

        args = tool_call.get("args") or {}
        state = request.state if isinstance(request.state, dict) else {}
        messages = state.get("messages", []) or []

        if _find_execute_decision(
            messages,
            scenario_id=args.get("scenario_id") or "",
            endpoint_id=args.get("endpoint_id") or "",
            tool_name=tool_name,
        ):
            return None

        logger.warning("执行门禁拦截 %s：消息历史中无邀约执行决策", tool_name)
        return _build_gate_block_message(tool_call, tool_name)

    def wrap_tool_call(
        self,
        request: "ToolCallRequest",
        handler: "Callable[[ToolCallRequest], ToolMessage | Command[Any]]",
    ) -> "ToolMessage | Command[Any]":
        blocked = self._check_execution_gate(request)
        if blocked is not None:
            return blocked
        return handler(request)

    async def awrap_tool_call(
        self,
        request: "ToolCallRequest",
        handler: "Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]]",
    ) -> "ToolMessage | Command[Any]":
        blocked = self._check_execution_gate(request)
        if blocked is not None:
            return blocked
        return await handler(request)
