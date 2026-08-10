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
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from tests.eval.judge_model import DeepSeekJudge

DATASET_PATH = Path(__file__).parent / "dataset" / "regression_v1.jsonl"

_judge = DeepSeekJudge()

# ── 裁判 1：预期结果可断言性 ─────────────────────────────────────────────
# 对应「用例质量红线」第 2 条：预期结果禁止模糊词，必须可客观判定 Pass/Fail
assertability_metric = GEval(
    name="预期结果可断言性",
    evaluation_steps=[
        "逐条检查测试用例的预期结果（expected_result 或 test_case_steps 中的 result 字段）",
        "判定每条预期结果是否可客观断言：包含具体数值、状态码、确切文案、明确的页面元素或状态变化",
        "出现「正确」「成功」「正常」「合理」「显示无误」「符合预期」等无法客观判定的模糊词，每处扣 0.15 分",
        "预期结果与测试步骤存在因果断裂（步骤未操作却断言结果）的，每处扣 0.2 分",
    ],
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.8,
    model=_judge,
    async_mode=False,  # DeepSeek 网关限流敏感，串行更稳
)

# ── 裁判 2：异常流与安全覆盖 ─────────────────────────────────────────────
# 对应「用例质量红线」第 4/6/7 条：异常输入、安全用例、边界值
exception_coverage_metric = GEval(
    name="异常与安全覆盖",
    evaluation_steps=[
        "统计用例集中的异常流用例：空值/非法格式/超长输入/Unicode/emoji 等维度",
        "异常流用例不足 2 条时，得分不得高于 0.5",
        "检查是否包含安全测试用例（SQL 注入/XSS/越权/未授权访问），涉及用户输入的功能完全缺失安全用例时扣 0.3 分",
        "检查有取值范围的字段是否覆盖边界值（min-1/min/min+1/max-1/max/max+1 中的至少 3 个）",
        "全部为 Happy Path（无任何异常/边界/安全用例）时，得分为 0",
    ],
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.7,
    model=_judge,
    async_mode=False,
)


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
