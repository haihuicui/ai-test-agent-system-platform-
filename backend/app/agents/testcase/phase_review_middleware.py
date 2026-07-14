"""阶段报告人工评审中间件。

在 testcase agent 完成需求分析报告、测试策略报告、质量评审报告后，
自动触发 LangGraph interrupt，等待用户确认或给出修改意见后再继续下一阶段。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain.agents.middleware.human_in_the_loop import (
    ActionRequest,
    HITLRequest,
    ReviewConfig,
)
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import interrupt


_PHASE_PATTERNS: dict[str, list[str]] = {
    "requirement-analysis": [
        r"##\s*需求解析报告",
        r"##\s*需求解析摘要",
        r"##\s*功能测试矩阵",
    ],
    "test-strategy": [
        r"##\s*测试策略报告",
    ],
    "test-case-generation": [
        r"##\s*测试用例生成完成",
        r"##\s*用例生成汇总",
        r"##\s*测试用例汇总",
    ],
    "quality-review": [
        r"##\s*📊\s*测试用例质量评审报告",
        r"##\s*测试用例质量评审报告",
    ],
    "output-format-selection": [
        r"##\s*输出格式化",
        r"##\s*交付物格式选择",
    ],
}

_PHASE_DISPLAY_NAMES: dict[str, str] = {
    "requirement-analysis": "需求分析报告",
    "test-strategy": "测试策略报告",
    "test-case-generation": "测试用例生成",
    "quality-review": "质量评审报告",
    "output-format-selection": "输出格式化",
}

_OUTPUT_FORMATS: list[dict[str, str]] = [
    {"key": "markdown", "label": "Markdown 详细格式"},
    {"key": "excel", "label": "Excel 文件（.xlsx）"},
    {"key": "json", "label": "JSON 格式"},
    {"key": "csv", "label": "CSV 格式"},
]

# 阶段评审维度清单（默认全部勾选，用户可取消未通过项）
_REVIEW_CHECKLIST: list[dict[str, str]] = [
    {"key": "coverage", "label": "功能覆盖完整"},
    {"key": "boundary", "label": "边界值场景充分"},
    {"key": "security", "label": "包含安全/异常场景"},
    {"key": "priority", "label": "优先级分配合理"},
]


def _detect_phase(content: str) -> str | None:
    """根据 Markdown 标题检测当前完成的阶段。"""
    for phase, patterns in _PHASE_PATTERNS.items():
        if any(re.search(pattern, content) for pattern in patterns):
            return phase
    return None


def _extract_preview(content: str, phase: str) -> str:
    """提取报告预览，用于展示给用户的摘要。"""
    return content.strip()


def _build_checklist_feedback(
    checklist: dict[str, bool], comment: str, phase_name: str
) -> str:
    """根据 checklist 未勾选项和评论生成反馈文本。"""
    unchecked = [
        item["label"]
        for item in _REVIEW_CHECKLIST
        if not checklist.get(item["key"], True)
    ]

    parts: list[str] = []
    if unchecked:
        parts.append(f"以下维度需要补充或调整：{', '.join(unchecked)}。")
    if comment:
        parts.append(f"具体意见：{comment}")

    if not parts:
        return ""

    return f"{phase_name}需要改进。" + " ".join(parts)


_QUALITY_SCORE_PATTERNS: list[re.Pattern[str]] = [
    # 综合评分：85 分 / 综合评分: 85
    re.compile(r"综合评分[：:]\s*(\d+(?:\.\d+)?)\s*分?"),
    # 评分：85 分
    re.compile(r"评分[：:]\s*(\d+(?:\.\d+)?)\s*分?"),
    # 质量得分 85
    re.compile(r"质量得分[：:]?\s*(\d+(?:\.\d+)?)"),
]

# 质量红线：综合评分低于该分数时自动退回返工（对齐 SYSTEM_PROMPT 中"综合评分 < 75 分需回退修改"）
_AUTO_REJECT_SCORE = 75.0
# 自动退回最大轮次：超限后降级为人工评审，避免模型反复返工仍不达标时死循环
_MAX_AUTO_REJECT_ROUNDS = 2


def _extract_quality_score(content: str) -> float | None:
    """从阶段报告中提取质量综合评分（0-100）。"""
    for pattern in _QUALITY_SCORE_PATTERNS:
        match = pattern.search(content)
        if match:
            try:
                score = float(match.group(1))
                if 0 <= score <= 100:
                    return score
            except (ValueError, TypeError):
                continue
    return None


def _get_auto_approve_threshold(runtime: Any, messages: list[Any]) -> float:
    """读取自动审批阈值，优先从最近一条 human 消息 additional_kwargs 读取。

    注意：after_model 触发时最后一条消息是刚生成的 AIMessage，
    必须沿历史倒序找最近一条 human 消息，否则消息级阈值永远不生效。
    """
    threshold: float | None = None
    for msg in reversed(messages or []):
        if isinstance(msg, HumanMessage):
            ak = getattr(msg, "additional_kwargs", None) or {}
            if isinstance(ak, dict):
                raw = ak.get("auto_approve_threshold")
                if raw is not None:
                    try:
                        threshold = float(raw)
                    except (ValueError, TypeError):
                        threshold = None
            break  # 只看最近一条 human 消息

    if threshold is None:
        ctx = getattr(runtime, "context", None) if runtime else None
        threshold = getattr(ctx, "auto_approve_threshold", 100.0) if ctx else 100.0

    return max(0.0, min(100.0, threshold or 100.0))


def _compute_review_round(messages: list[Any], phase: str) -> int:
    """扫描消息历史，计算当前阶段是第几轮评审（从 1 开始）。"""
    max_round = 0
    for msg in messages:
        if isinstance(msg, HumanMessage):
            review_round = (getattr(msg, "additional_kwargs", None) or {}).get("_review_round")
            if isinstance(review_round, dict) and review_round.get("phase") == phase:
                max_round = max(max_round, int(review_round.get("round", 0)))
    return max_round + 1


def _build_review_human_message(
    phase: str,
    round: int,
    feedback: str,
    decision_type: str,
    comment: str,
    checklist: dict[str, bool],
) -> HumanMessage:
    """构造带评审元数据的 HumanMessage。"""
    return HumanMessage(
        content=f"[阶段评审：{phase}] 用户反馈：{feedback}",
        additional_kwargs={
            "_review_round": {
                "phase": phase,
                "round": round,
                "decision": decision_type,
                "comment": comment,
                "checklist": checklist,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        },
    )


class PhaseReviewMiddleware(AgentMiddleware):
    """
    阶段报告人工评审中间件。

    与 ``HumanInTheLoopMiddleware`` 协作：
    - 若当前 AI 消息包含待审批的工具调用，HumanInTheLoopMiddleware 会先中断，
      本中间件本轮不会触发。
    - 若当前 AI 消息是阶段报告（无工具调用），本中间件触发中断。
    """

    @hook_config(can_jump_to=["model", "end"])
    def after_model(self, state: dict[str, Any], runtime: Any) -> dict[str, Any] | None:
        """检测阶段报告并在完成后触发人工评审。"""
        messages = state.get("messages", [])
        last_ai = next(
            (m for m in reversed(messages) if isinstance(m, AIMessage)),
            None,
        )
        if not last_ai:
            return None

        # 如果当前 AI 消息还有待审批的工具调用，先交给 HumanInTheLoopMiddleware 处理
        if last_ai.tool_calls:
            return None

        content = str(last_ai.content or "")
        phase = _detect_phase(content)
        if not phase:
            return None

        # 防御性检查：如果该 AI 消息后已存在同阶段的评审反馈，避免重复中断
        after_ai = messages[messages.index(last_ai) + 1 :]
        if any(
            isinstance(m, HumanMessage)
            and f"[阶段评审：{phase}]" in str(m.content)
            for m in after_ai
        ):
            return None

        phase_name = _PHASE_DISPLAY_NAMES[phase]

        # 基于评分的自动决策仅对 quality-review 阶段生效：
        # 评分模式较宽泛（如"评分：80"），Phase 1/2 报告中出现类似文字时
        # 不应触发自动通过/退回。
        if phase == "quality-review":
            score = _extract_quality_score(content)
            if score is not None:
                current_round = _compute_review_round(messages, phase)

                # 自动退回：评分低于质量红线，直接注入返工反馈（确定性执行，
                # 不依赖模型自觉遵守 prompt 中的"评分 < 75 需回退"规则）。
                # 超过 _MAX_AUTO_REJECT_ROUNDS 轮后降级为人工评审，避免死循环。
                if score < _AUTO_REJECT_SCORE and current_round <= _MAX_AUTO_REJECT_ROUNDS:
                    auto_comment = (
                        f"报告综合评分 {score:.0f} 分，低于质量红线 {_AUTO_REJECT_SCORE:.0f} 分，"
                        f"系统自动退回（第 {current_round} 轮自动返工）。"
                    )
                    return {
                        "messages": [
                            _build_review_human_message(
                                phase=phase,
                                round=current_round,
                                feedback=(
                                    f"{auto_comment} 请根据质量评审报告中指出的问题补充、"
                                    f"修改测试用例，完成后重新输出质量评审报告。"
                                ),
                                decision_type="auto_reject",
                                comment=auto_comment,
                                checklist={item["key"]: False for item in _REVIEW_CHECKLIST},
                            )
                        ],
                        "jump_to": "model",
                    }

                # 自动审批：当报告质量评分达到阈值时，跳过人工评审卡片
                threshold = _get_auto_approve_threshold(runtime, messages)
                if threshold < 100.0 and score >= threshold:
                    auto_comment = (
                        f"报告综合评分 {score:.0f} 分，达到自动审批阈值 {threshold:.0f} 分，系统自动通过。"
                    )
                    return {
                        "messages": [
                            _build_review_human_message(
                                phase=phase,
                                round=current_round,
                                feedback=f"报告已确认。{auto_comment} 请继续执行下一阶段。",
                                decision_type="approve",
                                comment=auto_comment,
                                checklist={item["key"]: True for item in _REVIEW_CHECKLIST},
                            )
                        ],
                        "jump_to": "model",
                    }

        action_name = f"{phase}_review"

        if phase == "output-format-selection":
            # 输出格式选择：使用自定义 payload，前端渲染专用 UI
            response = interrupt({
                "type": "format_selection",
                "formats": _OUTPUT_FORMATS,
                "description": "请选择最终交付物格式",
            })

            selected_format = "markdown"
            if isinstance(response, dict):
                selected_format = response.get("format") or "markdown"
            elif isinstance(response, list) and response:
                # 兼容可能的数组格式
                first = response[0]
                if isinstance(first, dict):
                    selected_format = first.get("format") or "markdown"

            return {
                "messages": [
                    HumanMessage(
                        content=f"[阶段评审：{phase}] 用户选择输出格式：{selected_format}。请按该格式输出最终交付物。"
                    )
                ],
                "jump_to": "model",
            }

        phase_name = _PHASE_DISPLAY_NAMES[phase]
        hitl_request = HITLRequest(
            action_requests=[
                ActionRequest(
                    name=action_name,
                    args={
                        "phase": phase,
                        "phase_name": phase_name,
                        "preview": _extract_preview(content, phase),
                        "checklist": _REVIEW_CHECKLIST,
                    },
                    description=f"已完成 {phase_name}，请审阅并决定是否继续下一阶段。",
                )
            ],
            review_configs=[
                ReviewConfig(
                    action_name=action_name,
                    allowed_decisions=["approve", "reject"],
                )
            ],
        )

        # 触发 LangGraph 中断；恢复时返回用户决策对象
        # 前端 PhaseReviewInterrupt 发送：
        # { "decision": "approve|request_changes|regenerate|skip|narrow_scope",
        #   "message": "...", "checklist": {"coverage": true, ...} }
        response = interrupt(hitl_request)

        decision_type = "approve"
        comment = ""
        checklist: dict[str, bool] = {}

        if isinstance(response, dict):
            decision_type = response.get("decision") or "approve"
            comment = (response.get("message") or "").strip()
            checklist = response.get("checklist") or {}
        elif isinstance(response, list) and response:
            # 兼容旧版 InterruptActions 发送的数组格式
            old_decision = response[0]
            if isinstance(old_decision, dict):
                decision_type = old_decision.get("type") or "approve"
                if decision_type == "reject":
                    decision_type = "request_changes"
                comment = (old_decision.get("message") or "").strip()

        current_round = _compute_review_round(messages, phase)

        # 快捷操作映射
        if decision_type == "regenerate":
            feedback = comment or "请重新生成本阶段报告，优化不足之处。"
        elif decision_type == "skip":
            return {
                "messages": [
                    _build_review_human_message(
                        phase=phase,
                        round=current_round,
                        feedback=f"用户选择跳过 {phase_name}，请继续执行下一阶段。",
                        decision_type=decision_type,
                        comment=comment,
                        checklist=checklist,
                    )
                ],
                "jump_to": "model",
            }
        elif decision_type == "narrow_scope":
            feedback = (
                f"请缩小 {phase_name} 范围。{comment}"
                if comment
                else f"请缩小 {phase_name} 范围，聚焦核心内容。"
            )
        elif decision_type == "approve":
            checklist_feedback = _build_checklist_feedback(checklist, comment, phase_name)
            if checklist_feedback:
                feedback = f"报告整体通过。{checklist_feedback} 请在后续阶段注意以上意见。"
            elif comment:
                feedback = f"报告已确认。评审意见：{comment} 请在后续阶段注意以上意见，并继续执行下一阶段。"
            else:
                feedback = "报告已确认，请继续执行下一阶段。"
        elif decision_type == "request_changes":
            checklist_feedback = _build_checklist_feedback(checklist, comment, phase_name)
            if checklist_feedback:
                feedback = checklist_feedback
            else:
                feedback = comment or "报告需要调整，请根据反馈修改后重新输出。"
        else:
            feedback = f"收到反馈（{decision_type}）：{comment}" if comment else "收到反馈，请按指示继续。"

        return {
            "messages": [
                _build_review_human_message(
                    phase=phase,
                    round=current_round,
                    feedback=feedback,
                    decision_type=decision_type,
                    comment=comment,
                    checklist=checklist,
                )
            ],
            "jump_to": "model",
        }

    async def aafter_model(
        self, state: dict[str, Any], runtime: Any
    ) -> dict[str, Any] | None:
        """异步版本的 after_model（本中间件逻辑为同步计算，直接复用）。"""
        return self.after_model(state, runtime)
