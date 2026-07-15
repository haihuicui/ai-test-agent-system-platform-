"""Tests for PhaseReviewMiddleware 的评分提取与评审轮次计算。

覆盖 _extract_quality_score（从报告文本提取综合评分）与
_compute_review_round（基于历史消息中的评审元数据计算当前轮次）。
"""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.testcase.phase_review_middleware import (
    _compute_review_round,
    _extract_quality_score,
)


def _review_msg(phase: str, round_: int) -> HumanMessage:
    """构造一条带评审元数据的 HumanMessage。"""
    return HumanMessage(
        content=f"[阶段评审：{phase}] 用户反馈：请修改",
        additional_kwargs={"_review_round": {"phase": phase, "round": round_}},
    )


class TestExtractQualityScore:
    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ("综合评分：85 分", 85.0),
            ("综合评分:85分", 85.0),
            ("综合评分： 82.5 分", 82.5),
            ("评分：72 分", 72.0),
            ("质量得分 88", 88.0),
            ("质量得分：91", 91.0),
            ("综合评分：0 分", 0.0),
            ("综合评分：100 分", 100.0),
            ("报告综合评分：76 分，详见下表", 76.0),
        ],
    )
    def test_valid_scores(self, content, expected):
        assert _extract_quality_score(content) == expected

    @pytest.mark.parametrize(
        "content",
        [
            "",
            "本报告未给出评分",
            "综合评分：120 分",  # 超出 0-100 上限
            "综合评分：-5 分",   # 负号无法被 \d 匹配
            "评分：abc 分",
        ],
    )
    def test_no_valid_score(self, content):
        assert _extract_quality_score(content) is None


class TestComputeReviewRound:
    PHASE = "quality-review"

    def test_empty_history_is_first_round(self):
        assert _compute_review_round([], self.PHASE) == 1

    def test_messages_without_review_metadata(self):
        messages = [HumanMessage(content="请生成用例"), AIMessage(content="好的")]
        assert _compute_review_round(messages, self.PHASE) == 1

    def test_single_prior_review(self):
        messages = [_review_msg(self.PHASE, 1)]
        assert _compute_review_round(messages, self.PHASE) == 2

    def test_multiple_prior_reviews_take_max(self):
        messages = [_review_msg(self.PHASE, 1), _review_msg(self.PHASE, 2)]
        assert _compute_review_round(messages, self.PHASE) == 3

    def test_other_phase_ignored(self):
        messages = [_review_msg("requirement-analysis", 3)]
        assert _compute_review_round(messages, self.PHASE) == 1

    def test_mixed_phases_only_counts_target(self):
        messages = [_review_msg("requirement-analysis", 5), _review_msg(self.PHASE, 1)]
        assert _compute_review_round(messages, self.PHASE) == 2

    def test_malformed_metadata_ignored(self):
        messages = [
            # _review_round 不是 dict
            HumanMessage(content="x", additional_kwargs={"_review_round": "not-a-dict"}),
            # 缺 round 字段，按 0 处理
            HumanMessage(content="y", additional_kwargs={"_review_round": {"phase": self.PHASE}}),
        ]
        assert _compute_review_round(messages, self.PHASE) == 1

    def test_ai_message_metadata_ignored(self):
        messages = [
            AIMessage(
                content="x",
                additional_kwargs={"_review_round": {"phase": self.PHASE, "round": 5}},
            )
        ]
        assert _compute_review_round(messages, self.PHASE) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
