"""意图感知路由中间件。

在 Agent 收到用户消息后，根据意图将请求路由到不同执行路径，
避免简单任务（如"导出为 Excel"）走完整 5-Phase 流程造成浪费。

意图分类：
  - "export":  直接进入 Phase 5（output-formatter）
  - "review":  直接激活 quality-review Skill
  - "design":  跳过 Phase 1/2，直接进入 test-case-design
  - "analysis": 仅执行需求分析阶段
  - "end_to_end": 完整 5-Phase 流程（默认）
"""

from __future__ import annotations

import re
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from deepagents.middleware._utils import append_to_system_message


# ── 意图 → 路由指令映射 ──

_INTENT_PATTERNS: dict[str, list[str]] = {
    "export": [
        r"导出.*(?:excel|csv|json|markdown|用例)",
        r"下载.*用例",
        r"生成.*(?:excel|csv|json|markdown).*文件",
    ],
    "review": [
        r"评审.*(用例|测试)",
        r"(用例|测试).*质量.*(检查|评审|评估)",
        r"审查.*测试",
    ],
    "design": [
        r"(设计|生成|补充|创建).*(用例|测试用例)",
        r"(写|新增|添加).*(用例|测试用例)",
    ],
    "strategy": [
        r"(制定|设计).*测试策略",
        r"测试方案",
        r"怎么测",
    ],
    "analysis": [
        r"(分析|解析).*(需求|PRD|文档|规格)",
        r"看看.*(?:PRD|需求|文档|规格)",
    ],
    "end_to_end": [
        r"全流程",
        r"从需求到用例",
        r"端到端.*生成",
    ],
}

_ROUTE_INSTRUCTIONS: dict[str, str] = {
    "export": (
        "\n\n[意图路由] 用户意图为「导出」。请跳过需求分析、策略设计、用例生成和评审阶段，"
        "直接进入 Phase 5（output-formatter），按用户指定格式生成交付物。"
        "用户已选定格式则直接执行；未指定则先输出 `## 输出格式化` 触发格式选择面板。"
    ),
    "review": (
        "\n\n[意图路由] 用户意图为「评审」。请跳过需求分析和用例设计阶段，"
        "直接激活 quality-review Skill，对已有用例进行质量评审。"
        "评审完成后输出 `## 📊 测试用例质量评审报告`。"
    ),
    "design": (
        "\n\n[意图路由] 用户意图为「用例设计」。请跳过 Phase 1（需求分析）和 Phase 2（测试策略），"
        "直接激活 test-case-design Skill 和 test-data-generator Skill，"
        "开始设计测试用例。不要先输出需求分析报告或测试策略报告。"
    ),
    "strategy": (
        "\n\n[意图路由] 用户意图为「测试策略」。请直接激活 test-strategy Skill，"
        "输出测试策略报告。无需执行需求分析或生成具体用例。"
    ),
    "analysis": (
        "\n\n[意图路由] 用户意图为「需求分析」。请仅激活 requirement-analysis Skill，"
        "输出需求解析报告。不要自动进入后续阶段。"
    ),
    "end_to_end": (
        "\n\n[意图路由] 用户意图为「端到端生成」。请按 Phase 1→2→3→4→5 完整流程执行。"
    ),
}

_DEFAULT_INTENT = "end_to_end"


def _extract_human_text(messages: list[Any]) -> str:
    """从最近一条 human 消息中提取纯文本内容。"""
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "human":
            content = getattr(msg, "content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for block in content:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                return "\n".join(parts)
            return str(content or "")
    return ""


def _detect_intent(messages: list[Any]) -> str:
    """从最近一条 human 消息中检测用户意图。"""
    text = _extract_human_text(messages)
    if not text:
        return _DEFAULT_INTENT

    for intent, patterns in _INTENT_PATTERNS.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            return intent

    return _DEFAULT_INTENT


class IntentRouterMiddleware(AgentMiddleware):
    """每次对话的首条 human 消息前，根据意图注入路由指令。

    仅在对话第一轮（human 消息数 == 1）时生效，后续多轮交互中
    不再重复注入，避免覆盖阶段评审反馈等后续指令。
    """

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler,
    ) -> ModelResponse:
        # 仅在首轮注入：只有一条 human 消息时
        human_count = sum(
            1 for m in (request.messages or [])
            if getattr(m, "type", None) == "human"
        )
        if human_count != 1:
            return await handler(request)

        intent = _detect_intent(request.messages or [])
        instruction = _ROUTE_INSTRUCTIONS.get(intent, _ROUTE_INSTRUCTIONS[_DEFAULT_INTENT])

        request = request.override(
            system_message=append_to_system_message(
                request.system_message, instruction
            )
        )
        return await handler(request)
