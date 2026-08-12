"""G-Eval 裁判定义（单一事实源）。

test_testcase_quality.py（pytest 门禁）与 run_judges.py（分数落盘）共用，
避免两处 evaluation_steps 漂移——裁判措辞的任何修改都必须全量重跑回归集
对比前后分数（见 README「红线」）。
"""
from __future__ import annotations

from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams

from tests.eval.judge_model import DeepSeekJudge

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

# (维度 key, metric) —— run_judges 落盘与 calibrate_report 对比共用此 key
JUDGES = (
    ("assertability", assertability_metric),
    ("coverage", exception_coverage_metric),
)
