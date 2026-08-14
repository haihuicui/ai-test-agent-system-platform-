"""Tests for summarization_cutoff_patch 空裁切推进补丁。

覆盖：
- 生产性裁切不改动（原 cutoff 范围内含真实消息）
- 空裁切推进（仅含旧 summary → 推进到裁入真实消息）
- 推进时不拆 AIMessage(tool_calls)/ToolMessage 对
- 找不到生产性位置时保底维持原裁切
- patch 挂载幂等

E2E 背景（thread 7eb0415b）：空裁切导致 8 分钟内连续 5 次空摘要事件——
空 section 写入历史文件、每次白调一次 LLM 摘要、state cutoff 不推进。
"""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.testcase import summarization_cutoff_patch as patch_mod


def _summary_msg() -> HumanMessage:
    return HumanMessage(content="【旧摘要】此前对话已压缩", additional_kwargs={"lc_source": "summarization"})


def _ai_with_tool_call(call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "rag_query_data", "args": {"query": "x"}, "id": call_id, "type": "tool_call"}],
    )


class _StubMiddleware:
    """最小 stub：复用真实的 _filter_summary_messages / _find_safe_cutoff_point 逻辑。"""

    def __init__(self):
        from deepagents.middleware.summarization import SummarizationMiddleware
        from langchain.agents.middleware.summarization import (
            SummarizationMiddleware as LCSummarizationMiddleware,
        )

        self._filter_summary_messages = lambda msgs: SummarizationMiddleware._filter_summary_messages(self, msgs)
        self._is_summary_message = lambda msg: SummarizationMiddleware._is_summary_message(self, msg)

        class _Helper:
            _find_safe_cutoff_point = staticmethod(LCSummarizationMiddleware._find_safe_cutoff_point)

        self._lc_helper = _Helper()


class TestFindProductiveCutoff:
    def test_advances_past_bare_summary(self):
        """空裁切（[旧summary]）推进到裁入第一条真实消息。"""
        mw = _StubMiddleware()
        messages = [_summary_msg(), HumanMessage(content="用户问题1"), AIMessage(content="回复1")]
        # base_cutoff=1：裁切范围 [summary] 过滤后为空
        result = patch_mod._find_productive_cutoff(mw, messages, base_cutoff=1)
        assert result == 2  # 裁入 HumanMessage("用户问题1")
        assert mw._filter_summary_messages(messages[:result])

    def test_does_not_split_ai_tool_pair(self):
        """推进路径遇 ToolMessage 切点时安全回退，最终整对裁入。"""
        mw = _StubMiddleware()
        messages = [
            _summary_msg(),                      # 0
            _ai_with_tool_call("call_1"),        # 1
            ToolMessage(content="巨型结果", tool_call_id="call_1"),  # 2
            HumanMessage(content="用户问题2"),    # 3
        ]
        result = patch_mod._find_productive_cutoff(mw, messages, base_cutoff=1)
        # target=2 落在 ToolMessage 上被回退到 1（未越过），继续推进到 3：
        # 裁切范围 [summary, AI(tool_calls), ToolMessage] —— AI/Tool 对完整裁入
        assert result == 3
        cut = messages[:result]
        assert isinstance(cut[-1], ToolMessage)

    def test_fallback_when_no_productive_position(self):
        """全部是 summary 消息时保底维持原裁切。"""
        mw = _StubMiddleware()
        messages = [_summary_msg(), _summary_msg(), _summary_msg()]
        result = patch_mod._find_productive_cutoff(mw, messages, base_cutoff=1)
        assert result == 1

    def test_never_cuts_everything(self):
        """推进上界 len-1：至少保留一条消息给模型。"""
        mw = _StubMiddleware()
        messages = [_summary_msg(), HumanMessage(content="q"), HumanMessage(content="p")]
        result = patch_mod._find_productive_cutoff(mw, messages, base_cutoff=1)
        assert result <= len(messages) - 1


class TestPatchedDetermineCutoffIndex:
    def test_productive_cutoff_unchanged(self, monkeypatch):
        """原裁切已含真实消息时不做修正。"""
        monkeypatch.setattr(patch_mod, "_original_determine", lambda self, msgs: 3)
        mw = _StubMiddleware()
        messages = [HumanMessage(content="q1"), AIMessage(content="a1"), HumanMessage(content="q2"), HumanMessage(content="q3")]
        assert patch_mod._patched_determine_cutoff_index(mw, messages) == 3

    def test_bare_summary_cutoff_advanced(self, monkeypatch):
        """空裁切被推进（E2E 事故场景复现）。"""
        monkeypatch.setattr(patch_mod, "_original_determine", lambda self, msgs: 1)
        mw = _StubMiddleware()
        messages = [_summary_msg(), HumanMessage(content="q"), AIMessage(content="a"), HumanMessage(content="p")]
        assert patch_mod._patched_determine_cutoff_index(mw, messages) == 2

    def test_zero_cutoff_passthrough(self, monkeypatch):
        """cutoff<=0（无法裁切）直接透传。"""
        monkeypatch.setattr(patch_mod, "_original_determine", lambda self, msgs: 0)
        mw = _StubMiddleware()
        assert patch_mod._patched_determine_cutoff_index(mw, [HumanMessage(content="q")]) == 0


class TestPatchMount:
    def test_mount_is_idempotent(self):
        patch_mod.patch_summarization_cutoff()
        first = patch_mod._original_determine
        patch_mod.patch_summarization_cutoff()
        assert patch_mod._original_determine is first

        from deepagents.middleware.summarization import SummarizationMiddleware

        assert SummarizationMiddleware._determine_cutoff_index is patch_mod._patched_determine_cutoff_index


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
