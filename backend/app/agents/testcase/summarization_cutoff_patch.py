"""summarization 空裁切推进补丁。

问题（E2E 实证，thread 7eb0415b，2026-08-14）：
deepagents SummarizationMiddleware 在「保留最近 N 条」的 keep 策略下，若上次摘要后
新增消息不足 N 条而 token 仍超阈值（典型场景：最近消息里有巨型 ToolMessage），
`_determine_cutoff_index` 给出的裁切点会落在「只裁掉旧 summary 消息」的位置——
裁切范围经 `_filter_summary_messages` 过滤后为空，形成空裁切：

- `_offload_to_backend` 无条件写入 `## Summarized at <ts>` 空 section
  （conversation_history 文件垃圾，实测连续 5 个空 section）；
- `_create_summary` 对空内容白调一次 LLM（每次数十秒，纯浪费）；
- state cutoff 不推进、token 不下降 → 下一轮 wrap_model_call 再次触发，
  8 分钟内连续 5 次空摘要（间隔 48s/47s/350s/23s），期间 SKILL 格式契约等
  上下文细节被反复压缩丢失（实证：.md 评审契约被遗忘漂移为 .jsonl）。

修复：patch `_determine_cutoff_index`——空裁切时向后推进 cutoff 到第一个
「裁切范围内含真实消息且切点安全（不拆 AI/Tool 消息对）」的位置，保证每次
摘要事件至少裁掉一条真实消息（生产性裁切）：token 逐轮下降、循环必然收敛，
且每次 offload 都有真实内容落盘。

与 context_overflow_patch 同款 monkey-patch 模式：模块级一次性 patch 类方法，
幂等；deepagents 双 venv 版本漂移时防御性跳过（仅告警，不影响启动）。
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("app.summarization_cutoff_patch")

_PATCHED = False
_original_determine: Any = None


def _find_productive_cutoff(middleware: Any, messages: list, base_cutoff: int) -> int:
    """空裁切时向后推进 cutoff：找到第一个裁入真实消息的安全位置。

    复用 langchain helper 的 `_find_safe_cutoff_point`（只向前回退，保证不拆
    AIMessage(tool_calls)/ToolMessage 对）；candidate 必须越过 base_cutoff、
    不超过 len(messages)-1（至少保留一条消息给模型）。
    """
    find_safe = middleware._lc_helper._find_safe_cutoff_point
    upper = len(messages) - 1
    target = base_cutoff
    while target < upper:
        target += 1
        candidate = min(find_safe(messages, target), upper)
        if candidate <= base_cutoff:
            # 切点落在 ToolMessage 区被安全回退、仍未越过原 cutoff——继续向后推进
            continue
        if middleware._filter_summary_messages(messages[:candidate]):
            return candidate
    return base_cutoff  # 保底：找不到生产性位置则维持原裁切（行为与未 patch 一致）


def _patched_determine_cutoff_index(self: Any, messages: list) -> int:
    cutoff = _original_determine(self, messages)
    if cutoff <= 0 or cutoff >= len(messages):
        return cutoff
    if self._filter_summary_messages(messages[:cutoff]):
        return cutoff  # 生产性裁切，无需修正
    productive = _find_productive_cutoff(self, messages, cutoff)
    if productive != cutoff:
        logger.warning(
            "summarization 空裁切修正：cutoff %d → %d（原裁切范围仅含旧摘要，"
            "推进至至少裁入一条真实消息，避免空 section 与无效 LLM 摘要调用）",
            cutoff,
            productive,
        )
    return productive


def patch_summarization_cutoff() -> None:
    """对 deepagents SummarizationMiddleware 挂载空裁切推进 patch（幂等）。"""
    global _PATCHED, _original_determine
    if _PATCHED:
        return
    try:
        from deepagents.middleware.summarization import SummarizationMiddleware
    except ImportError:
        logger.warning("deepagents 未安装，summarization 空裁切 patch 跳过")
        return
    # _lc_helper 是实例属性（__init__ 赋值），类级检查只覆盖类方法
    for attr in ("_determine_cutoff_index", "_filter_summary_messages"):
        if not hasattr(SummarizationMiddleware, attr):
            logger.warning(
                "deepagents 版本漂移：SummarizationMiddleware.%s 不存在，空裁切 patch 未挂载",
                attr,
            )
            return
    _original_determine = SummarizationMiddleware._determine_cutoff_index
    SummarizationMiddleware._determine_cutoff_index = _patched_determine_cutoff_index
    _PATCHED = True
    logger.info("SummarizationMiddleware 空裁切推进 patch 已挂载")
