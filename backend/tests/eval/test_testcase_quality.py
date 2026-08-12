"""TestCase Agent 输出质量门禁（G-Eval 裁判）。

跑法：
    cd backend && ../backend/.venv/Scripts/python.exe -m pytest tests/eval/ -v
    # 仓库根目录（pyproject 已配 pythonpath=["backend"]）：
    backend/.venv/Scripts/python.exe -m pytest backend/tests/eval/ -v

设计原则（落地顺序约定）：
1. 本阶段为【离线观测模式】——只看分数分布与裁判理由，不接任何自动流程；
2. 抽 20-50 条人工复核裁判理由，一致率 ≥80% 后才允许把 threshold 调成
   真正的拦截线（strict_mode）；
3. 翻车样本人工标注后加入 dataset/，回归集只增不减。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from tests.eval.metrics import assertability_metric, exception_coverage_metric

DATASET_PATH = Path(__file__).parent / "dataset" / "regression_v1.jsonl"


def load_dataset() -> list[dict]:
    if not DATASET_PATH.exists():
        pytest.skip(f"回归集不存在：{DATASET_PATH}（先跑 harvest_samples 采集样本）")
    samples = [
        json.loads(line)
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not samples:
        pytest.skip(f"回归集为空：{DATASET_PATH}")
    return samples


@pytest.mark.parametrize(
    "sample",
    load_dataset(),
    ids=lambda s: s.get("id", "unknown"),
)
def test_testcase_output_quality(sample: dict) -> None:
    """每条回归样本过两个 G-Eval 裁判。

    离线观测阶段：失败意味着「该历史产出的质量低于阈值」，
    是改进 Prompt 的线索，不代表平台功能损坏。
    """
    test_case = LLMTestCase(
        input=sample["input"],
        actual_output=sample["actual_output"],
    )
    assert_test(test_case, [assertability_metric, exception_coverage_metric])
