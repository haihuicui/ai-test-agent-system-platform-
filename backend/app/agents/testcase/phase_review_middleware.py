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
from langgraph.types import Overwrite, interrupt


_PHASE_PATTERNS: dict[str, list[str]] = {
    "requirement-analysis": [
        # Markdown heading 格式 (## 开头)
        r"##\s*需求解析报告",
        r"##\s*需求解析摘要",
        r"##\s*功能测试矩阵",
        # Emoji 格式 (兼容 SKILL.md 输出规范中的 📊/📋 前缀)
        r"📊\s*需求解析报告",
        r"📊\s*需求解析摘要",
        r"📋\s*功能测试矩阵",
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


def _has_case_preview(content: str) -> bool:
    """检测 Phase 3 报告中是否展示了具体用例内容。

    宽松匹配：只要报告中同时出现用例编号标识和测试步骤/测试数据标识，
    即认为展示了具体用例，可通过人工评审。

    支持中英文及常见同义词，避免 LLM 用"操作步骤"/"输入数据"等变体时被误判。
    同时兼容符合规范的 `TC-XXX` 用例编号格式，避免未写"用例编号/case_number"
    字样时被误判为仅汇总信息。
    """
    case_number_markers = ["case_number", "用例编号", "用例 ID", "用例ID", "编号"]
    has_explicit_case_number = any(marker in content for marker in case_number_markers)

    # 兼容 LLM 直接展示 TC-[项目]-[模块]-[序号] 编号的场景
    tc_number_pattern = re.compile(
        r"TC-[A-Za-z0-9一-鿿]+(?:-[A-Za-z0-9一-鿿]+)*-\d{2,}"
    )
    has_tc_number = bool(tc_number_pattern.search(content))
    has_case_number = has_explicit_case_number or has_tc_number

    steps_markers = [
        "test_case_steps", "测试步骤", "操作步骤", "用例步骤", "执行步骤",
        "步骤", "测试流程", "操作流程",
    ]
    has_steps = any(marker in content for marker in steps_markers)

    data_markers = [
        "test_data", "测试数据", "输入数据", "用例数据", "测试输入",
        "数据", "输入值",
    ]
    has_test_data = any(marker in content for marker in data_markers)

    return has_case_number and (has_steps or has_test_data)


def _has_coverage_mapping(content: str) -> bool:
    """检测 Phase 4 质量评审报告中是否包含了覆盖对照信息。

    满足以下任一条件即为通过：
    1. 报告中提到了 feature_matrix（说明 LLM 读取了结构化矩阵）
    2. 包含逐功能点的覆盖对照表（同时出现 FP- 和 TC- 编号）
    3. 标注了 [无结构化矩阵] 降级说明（Phase 1 被跳过时的合法降级）
    """
    # 条件 1：提到了结构化矩阵文件
    if "feature_matrix" in content:
        return True

    # 条件 2：包含功能点-用例覆盖对照（FP- + TC- 或 "功能点" + "用例编号" 配对）
    has_fp = bool(re.search(r"FP-\d+", content)) or "功能点" in content
    has_tc = bool(re.search(r"TC-\w+", content)) or "用例编号" in content
    has_coverage = "覆盖率" in content or "覆盖" in content
    if has_fp and has_tc and has_coverage:
        return True

    # 条件 3：标注了结构化矩阵缺失
    if "无结构化矩阵" in content:
        return True

    return False


def _detect_phase3_coverage_gap(content: str) -> list[str]:
    """检测 Phase 3 报告中标注为 0% 覆盖的模块。

    从报告的覆盖对照表中提取覆盖率列显示为 0% 或标明"无用例"的模块名。
    若报告不含覆盖对照表，返回空列表（由 _has_case_preview 负责兜底）。

    Returns:
        未覆盖的模块名列表。空列表 = 所有可见模块至少有一条用例。
    """
    uncovered: list[str] = []

    # 模式1：Markdown 表格行 "| 设备管理 | 4 | 0 | 0% ❌ | ..."
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        # 同时检测 "0%" 覆盖标记和配套的否定信号
        has_zero_pct = "0%" in stripped
        has_negative = any(
            kw in stripped for kw in ("❌", "未覆盖", "0 条", "0条", "无用例", "无任何")
        )
        if not (has_zero_pct and has_negative):
            continue

        cells = [c.strip() for c in stripped.split("|")]
        # 至少需要 2 列：模块名 + 覆盖数据
        meaningful = [c for c in cells if c and c not in ("", "---", "------")]
        if len(meaningful) < 2:
            continue

        module_name = meaningful[0]
        # 排除表头行和汇总行
        if module_name.lower() in ("模块", "---", "汇总", "合计", "总计", "module"):
            continue

        uncovered.append(module_name)

    # 模式2：中文段落描述 "设备管理（FP-017~FP-020）完全无用例"
    desc_pattern = re.compile(
        r"(FP-\d+(?:~FP-\d+)?)\s*[（(]?\s*(\S+?)\s*[）)]?\s*(?:完全)?无(?:任何)?(?:测试)?用例",
    )
    for match in desc_pattern.finditer(content):
        detail = match.group(2).strip() if match.group(2) else match.group(1)
        if detail and detail not in uncovered:
            uncovered.append(detail)

    # 去重，保留顺序
    return list(dict.fromkeys(uncovered))


def _detect_uncovered_p0(content: str) -> list[str]:
    """检测 Phase 4 质量评审报告中标注为未覆盖的 P0 功能点。

    从评审报告的覆盖对照表中提取优先级为 P0 且标记为未覆盖的功能点 ID。
    若报告不含覆盖对照表，返回空列表。

    Returns:
        未覆盖的 P0 功能点 ID 列表。空列表 = 所有 P0 均有覆盖或无法解析。
    """
    uncovered_p0: list[str] = []

    # 模式1：表格行 "| FP-016 | ... | P0 | ... | 🔴 未覆盖/未覆盖 |"
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.split("|")]
        # 至少需要 4 列：FP-ID | ... | 优先级 | 覆盖状态
        meaningful = [c for c in cells if c and c not in ("", "---", "------")]
        if len(meaningful) < 3:
            continue

        # 检查是否为 P0 行
        has_p0 = any("P0" in c for c in meaningful)
        if not has_p0:
            continue

        # 检查是否标记为未覆盖
        has_uncovered = any(
            kw in stripped
            for kw in ("🔴", "❌", "未覆盖", "0%", "0 条", "0条", "无用例", "无任何")
        )
        if not has_uncovered:
            continue

        # 提取 FP 编号（第一个匹配的 FP-\d+）
        fp_match = re.search(r"FP-\d+", stripped)
        if fp_match:
            fp_id = fp_match.group(0)
            if fp_id not in uncovered_p0:
                uncovered_p0.append(fp_id)

    # 模式2：段落描述 "FP-016、FP-020 完全未覆盖（P0）"
    # 注意：[^。\n] 限制在同一行内匹配，防止跨行误匹配表格中的其他 FP 编号。
    desc_pattern = re.compile(
        r"((?:FP-\d+(?:[,、]\s*)?)+)\s*[^。\n]*(?:完全)?未覆盖[^。\n]*P0",
    )
    for match in desc_pattern.finditer(content):
        fp_ids = re.findall(r"FP-\d+", match.group(0))
        for fp_id in fp_ids:
            if fp_id not in uncovered_p0:
                uncovered_p0.append(fp_id)

    return uncovered_p0


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
    # Markdown 表格加粗格式：| **综合评分** | — | **[58.1]** | [58.1%] |
    re.compile(r"\*\*综合评分\*\*\s*\|[^|]*\|\s*\*{0,2}\[?(\d+(?:\.\d+)?)\]?\*{0,2}"),
    # Markdown 表格无加粗格式：| 综合评分 | — | 58.1 | 58.1% |
    re.compile(r"综合评分\s*\|[^|]*\|\s*\[?(\d+(?:\.\d+)?)\]?"),
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


def _get_completed_phases(messages: list[Any]) -> set[str]:
    """扫描消息历史，返回已完成评审（approved/skipped）的阶段集合。

    从 HumanMessage 的 _review_round 元数据中提取 decision 为 approve
    或 skip 的阶段。用于检测跨阶段跳步（如 Phase 4 报告出现但 Phase 3
    从未完成评审）。
    """
    completed: set[str] = set()
    for msg in messages:
        if not isinstance(msg, HumanMessage):
            continue
        review_round = (getattr(msg, "additional_kwargs", None) or {}).get("_review_round")
        if not isinstance(review_round, dict):
            continue
        decision = review_round.get("decision", "")
        if decision in ("approve", "skip"):
            completed.add(review_round.get("phase", ""))
    return completed


# Phase 3→4 跨阶段跳步检测的生效条件：
# 仅当对话中至少存在 1 条 AI 消息（说明不是在 Phase 1 初始阶段），
# 且功能点数 >= 该阈值时才拦截。小型项目（≤10 FP）走 3 阶段模式，
# Phase 3/4 合并，跳步检测不适用。
_MIN_FP_FOR_PHASE3_REVIEW = 11


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


def _strip_tool_calls(ai_msg: AIMessage) -> AIMessage:
    """创建 AI 消息副本，移除 tool_calls 与 additional_kwargs 中的 tool_calls。

    用于阶段报告与工具调用混在单条消息时的兜底拆分：只保留文本内容，
    让 PhaseReviewMiddleware 能正常检测到阶段标题并弹出评审卡片。
    """
    new_msg = ai_msg.model_copy()
    new_msg.tool_calls = []
    ak = dict(getattr(new_msg, "additional_kwargs", {}) or {})
    ak.pop("tool_calls", None)
    new_msg.additional_kwargs = ak
    return new_msg


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

        content = str(last_ai.content or "")
        phase = _detect_phase(content)

        # 兜底：阶段报告与工具调用混在单条 AI 消息中。
        # 模型有时会未遵守 prompt，在输出阶段标题后继续附带工具调用，
        # 导致本中间件因 tool_calls 存在而跳过评审。这里拆分出纯文本阶段报告，
        # 并提示模型分步输出；下次 model call 时即可正常触发人工评审卡片。
        if phase and last_ai.tool_calls:
            cleaned_ai = _strip_tool_calls(last_ai)
            phase_name = _PHASE_DISPLAY_NAMES[phase]
            return {
                "messages": Overwrite(value=[
                    *messages[: messages.index(last_ai)],
                    cleaned_ai,
                    HumanMessage(
                        content=(
                            f"检测到 {phase_name} 阶段报告与工具调用混在一起，"
                            "人工评审卡片无法弹出。请仅输出阶段报告文本（不要附带任何工具调用），"
                            "等待系统弹出人工评审卡片并收到用户决策后，再执行后续工具调用。"
                        )
                    ),
                ]),
                "jump_to": "model",
            }

        # 如果当前 AI 消息有工具调用但不含阶段报告，先交给 HumanInTheLoopMiddleware 处理
        if last_ai.tool_calls:
            return None

        if not phase:
            return None

        # Phase 3 可审性兜底：仅输出汇总表、没有展示具体用例时，要求补充
        if phase == "test-case-generation" and not _has_case_preview(content):
            current_round = _compute_review_round(messages, phase)
            return {
                "messages": [
                    _build_review_human_message(
                        phase=phase,
                        round=current_round,
                        feedback=(
                            "当前 Phase 3 报告仅包含汇总信息，系统未检测到具体用例内容，无法进入人工评审卡片。"
                            "请在报告中补充每个模块的关键用例详情，满足以下任一方式即可：\n"
                            "1. 若用例已写入 JSONL 文件：调用 `preview_test_cases(source='文件名.jsonl', limit=3)` 读取并展示关键用例；\n"
                            "2. 直接在报告中 inline 展示：每个模块至少 1 条 P0 用例和 1 条边界/异常/安全用例，包含完整字段："
                            "用例名称、case_number、module、priority、case_type、test_data、preconditions、test_case_steps、expected_result（预期结果）。\n"
                            "补充完成后，重新输出 `## 测试用例生成完成` 触发人工评审。"
                            "注意：若你已经在报告中展示了具体用例但仍收到本条反馈，请检查是否同时包含 '用例编号/case_number' 和 '测试步骤/操作步骤/test_case_steps' 或 '测试数据/test_data' 字样。"
                        ),
                        decision_type="request_changes",
                        comment="报告缺少具体用例内容",
                        checklist={item["key"]: False for item in _REVIEW_CHECKLIST},
                    )
                ],
                "jump_to": "model",
            }

        # Phase 3 完成覆盖率门禁：检测报告中是否有模块标注为 0% 覆盖。
        # 若报告表格中有 "0% ❌" 或 "无用例" 等标记，说明部分模块未完成设计，
        # 自动退回要求继续设计，不弹出人工评审卡片（最大 _MAX_AUTO_REJECT_ROUNDS 轮）。
        if phase == "test-case-generation":
            uncovered_modules = _detect_phase3_coverage_gap(content)
            if uncovered_modules:
                current_round = _compute_review_round(messages, phase)
                if current_round <= _MAX_AUTO_REJECT_ROUNDS:
                    module_list = "、".join(uncovered_modules[:8])
                    suffix = "…" if len(uncovered_modules) > 8 else ""
                    return {
                        "messages": [
                            _build_review_human_message(
                                phase=phase,
                                round=current_round,
                                feedback=(
                                    f"当前 Phase 3 报告显示以下 {len(uncovered_modules)} 个模块"
                                    f" 无任何测试用例覆盖：{module_list}{suffix}。\n\n"
                                    f"Phase 3 的完成标准是**所有功能点至少有一条用例**。"
                                    f"请继续设计未完成模块的用例，全部完成后再输出"
                                    f" `## 测试用例生成完成` 触发人工评审。\n\n"
                                    f"（第 {current_round} 轮自动退回，"
                                    f"最多 {_MAX_AUTO_REJECT_ROUNDS} 轮）"
                                ),
                                decision_type="auto_reject",
                                comment=(
                                    f"覆盖率不完整：{len(uncovered_modules)} 个模块无用例"
                                ),
                                checklist={item["key"]: False for item in _REVIEW_CHECKLIST},
                            )
                        ],
                        "jump_to": "model",
                    }

        # 防御性检查：如果该 AI 消息后已存在同阶段的评审反馈，避免重复中断
        after_ai = messages[messages.index(last_ai) + 1 :]
        if any(
            isinstance(m, HumanMessage)
            and f"[阶段评审：{phase}]" in str(m.content)
            for m in after_ai
        ):
            return None

        # Phase 4 覆盖对照兜底：评审报告缺少逐功能点覆盖对照时，拦截要求补充。
        # 与 Phase 3 的 _has_case_preview 同理 —— 不依赖 prompt 质量，
        # 由代码确定性检查报告是否包含覆盖映射信息。
        if phase == "quality-review" and not _has_coverage_mapping(content):
            current_round = _compute_review_round(messages, phase)
            return {
                "messages": [
                    _build_review_human_message(
                        phase=phase,
                        round=current_round,
                        feedback=(
                            "当前 Phase 4 质量评审报告缺少功能覆盖对照信息，"
                            "无法确认覆盖率评分是否基于 Phase 1 的功能矩阵。\n\n"
                            "请执行以下操作后重新输出 `## 📊 测试用例质量评审报告`：\n"
                            "1. 使用文件读取工具读取 `feature_matrix.jsonl`，获取全部功能点清单\n"
                            "2. 逐功能点对照已生成的用例，以表格形式列出覆盖状态：\n"
                            "   | 功能点 ID | 模块 | 功能点 | 优先级 | 是否已覆盖 | 对应用例编号 |\n"
                            "   |----------|------|--------|--------|----------|------------|\n"
                            "3. 未覆盖的功能点（尤其是 P0）必须标记为 🔴 严重问题\n\n"
                            "若 feature_matrix.jsonl 不存在（Phase 1 未保存），"
                            "请在报告中标注 '[无结构化矩阵] 覆盖度基于对话历史判断，可能存在遗漏'。"
                        ),
                        decision_type="request_changes",
                        comment="报告缺少覆盖对照信息",
                        checklist={item["key"]: False for item in _REVIEW_CHECKLIST},
                    )
                ],
                "jump_to": "model",
            }

        phase_name = _PHASE_DISPLAY_NAMES[phase]

        # 基于评分的自动决策仅对 quality-review 阶段生效：
        # 评分模式较宽泛（如"评分：80"），Phase 1/2 报告中出现类似文字时
        # 不应触发自动通过/退回。
        if phase == "quality-review":
            score = _extract_quality_score(content)

            # 自动退回：评分低于质量红线，直接注入返工反馈。
            # 此项检查优先级最高 —— 即使 Phase 3 被跳过，低分报告也应先退回。
            if score is not None:
                current_round = _compute_review_round(messages, phase)
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
                                    f"\n\n⚠️ 若确认跳过返工、以当前不完整状态继续，"
                                    f"请回复「确认跳过返工」。"
                                    f"跳过返工意味着交付残缺用例集，可能导致线上缺陷遗漏。"
                                ),
                                decision_type="auto_reject",
                                comment=auto_comment,
                                checklist={item["key"]: False for item in _REVIEW_CHECKLIST},
                            )
                        ],
                        "jump_to": "model",
                    }

            # Phase 3→4 跨阶段跳步检测：Phase 4 报告出现但 Phase 3 未评审。
            # 在自动退回之后检查 —— 低分报告直接退回，不需要额外提示跳步。
            completed = _get_completed_phases(messages)
            if "test-case-generation" not in completed:
                has_case_context = any(
                    "TC-" in str(getattr(m, "content", ""))
                    or "batch_create_test_cases" in str(getattr(m, "tool_calls", ""))
                    for m in messages
                    if isinstance(m, AIMessage)
                )
                if has_case_context:
                    current_round = _compute_review_round(messages, phase)
                    return {
                        "messages": [
                            _build_review_human_message(
                                phase=phase,
                                round=current_round,
                                feedback=(
                                    "⚠️ 检测到 Phase 3（测试用例生成）尚未经过人工评审，"
                                    "但当前已输出 Phase 4 质量评审报告。\n\n"
                                    "正确的流程顺序为：\n"
                                    "1. 完成所有模块用例设计后，输出 `## 测试用例生成完成`"
                                    " 触发 Phase 3 人工评审卡片\n"
                                    "2. 用户确认用例后，再进入 Phase 4 质量评审\n\n"
                                    "请按以下步骤补救：\n"
                                    "1. 输出 Phase 3 完成报告（含每个模块的关键用例抽样展示，"
                                    "至少 1 条 P0 + 1 条边界/异常用例的完整字段）\n"
                                    "2. 标题使用 `## 测试用例生成完成` 触发人工评审卡片\n"
                                    "3. 待用户审批通过后，再重新进入 Phase 4 质量评审\n\n"
                                    "（跨阶段跳步拦截 —— 确保用户有机会在评审前审阅具体用例）"
                                ),
                                decision_type="request_changes",
                                comment="Phase 3 人工评审被跳过，需回退补完",
                                checklist={item["key"]: False for item in _REVIEW_CHECKLIST},
                            )
                        ],
                        "jump_to": "model",
                    }

            # 自动审批：当报告质量评分达到阈值时，跳过人工评审卡片
            if score is not None:
                current_round = _compute_review_round(messages, phase)
                threshold = _get_auto_approve_threshold(runtime, messages)
                if threshold < 100.0 and score >= threshold:
                    # ⚠️ 未覆盖 P0 门禁：即使评分达标，若报告中存在
                    # 未覆盖的 P0 功能点，阻止自动审批，强制弹出人工评审卡片。
                    uncovered_p0 = _detect_uncovered_p0(content)
                    if uncovered_p0:
                        fp_list = "、".join(uncovered_p0)
                        # 构造带 P0 未覆盖警告的人工评审卡片
                        hitl_request = HITLRequest(
                            action_requests=[
                                ActionRequest(
                                    name=f"{phase}_review",
                                    args={
                                        "phase": phase,
                                        "phase_name": phase_name,
                                        "preview": _extract_preview(content, phase),
                                        "checklist": _REVIEW_CHECKLIST,
                                    },
                                    description=(
                                        f"⚠️ 已完成 {phase_name}（评分 {score:.0f}），"
                                        f"但检测到 {len(uncovered_p0)} 个 P0 功能点未覆盖"
                                        f"（{fp_list}）。"
                                        f"系统已阻止自动审批，请人工审阅并决定是否继续。"
                                    ),
                                )
                            ],
                            review_configs=[
                                ReviewConfig(
                                    action_name=f"{phase}_review",
                                    allowed_decisions=["approve", "reject"],
                                )
                            ],
                        )
                        response = interrupt(hitl_request)
                        # 解析用户决策
                        decision_type = "approve"
                        comment = ""
                        checklist: dict[str, bool] = {}
                        if isinstance(response, dict):
                            decision_type = response.get("decision") or "approve"
                            comment = (response.get("message") or "").strip()
                            checklist = response.get("checklist") or {}
                        elif isinstance(response, list) and response:
                            old_decision = response[0]
                            if isinstance(old_decision, dict):
                                decision_type = old_decision.get("type") or "approve"
                                if decision_type == "reject":
                                    decision_type = "request_changes"
                                comment = (old_decision.get("message") or "").strip()
                        current_round = _compute_review_round(messages, phase)
                        if decision_type == "approve":
                            fb = (
                                f"报告已确认（⚠️ 用户已知悉 {len(uncovered_p0)} 个 P0"
                                f" 功能点未覆盖：{fp_list}）。"
                                " 请先调用 write_todos 更新任务状态后再进入 Phase 5。"
                            )
                            if comment:
                                fb += f" 评审意见：{comment}"
                        elif decision_type == "request_changes":
                            fb = (
                                f"报告需要修改。请根据未覆盖 P0（{fp_list}）"
                                f" 和以下意见补充用例：{comment}" if comment
                                else f"报告需要修改。请补充 {fp_list} 的用例覆盖。"
                            )
                        else:
                            fb = f"收到反馈（{decision_type}）：{comment}" if comment else "收到反馈，请按指示继续。"
                        return {
                            "messages": [
                                _build_review_human_message(
                                    phase=phase,
                                    round=current_round,
                                    feedback=fb,
                                    decision_type=decision_type,
                                    comment=comment,
                                    checklist=checklist,
                                )
                            ],
                            "jump_to": "model",
                        }
                    else:
                        auto_comment = (
                            f"报告综合评分 {score:.0f} 分，达到自动审批阈值 {threshold:.0f} 分，系统自动通过。"
                        )
                        return {
                            "messages": [
                                _build_review_human_message(
                                    phase=phase,
                                    round=current_round,
                                    feedback=(
                                        f"报告已确认。{auto_comment}"
                                        " 请先调用 write_todos 将 Phase 4 标记为 completed"
                                        " 后再进入 Phase 5。"
                                    ),
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

            # 追加任务状态同步提示（避免 AI 跳过 write_todos 直接干活）
            feedback += (
                " 请先调用 write_todos 更新任务状态（当前阶段→completed，下一阶段→in_progress）后再继续。"
            )

            # test-strategy 阶段通过后提示读取功能矩阵（避免 AI 跳过矩阵直接设计用例）
            if phase == "test-strategy":
                feedback += (
                    " 进入 Phase 3 前，必须使用文件读取工具读取 feature_matrix.jsonl"
                    " 获取当前模块的功能点清单，确保用例设计基于结构化矩阵。"
                )
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
