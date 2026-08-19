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

# ── 裁判 3：需求覆盖完整性（FP 级，v2 带矩阵样本专用）────────────────
# 与 coverage_audit 分工：代码查「有没有用例声明覆盖这个 FP」，
# 本裁判查「相关用例的内容是否真语义覆盖了每个 test_point」——抓虚假声明。
# 评估单位为单个 FP（judge_coverage.py 负责按 FP 筛选相关用例组装 input），
# 避免「登录模块用例对编辑地点 FP 打低分」的冤案。
coverage_faithfulness_metric = GEval(
    name="需求覆盖完整性",
    evaluation_steps=[
        "input 是功能矩阵中的一个功能点（含 test_points 测试要点清单与 priority），actual_output 是与该功能点相关的测试用例集",
        "逐个 test_point 判定：用例集中是否存在至少一条用例，其测试步骤与预期结果在语义上真实验证了该要点",
        "仅名称/备注提到要点但步骤未实际验证的，不算覆盖（防虚假声明）",
        "每个未被覆盖的 test_point：P0 功能点扣 0.15 分，P1 扣 0.10 分，P2/P3 扣 0.05 分",
        "用例集与该功能点完全无关时，得分为 0",
        "reason 中必须明确列出每个未覆盖 test_point 的原文",
    ],
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.8,
    model=_judge,
    async_mode=False,
)

# ── 裁判 4：需求忠实度（幻觉用例，v2 带矩阵样本专用）────────────────
# 覆盖不完整只是漏，幻觉用例是错——用例验证的功能点在需求里根本不存在。
# 与裁判 3 互补：裁判 3 以 FP 为单位查「该有的有没有」，本裁判以文件为单位
# 查「不该有的有没有」。评估单位为单个产出文件（judge_faithfulness.py 组装）。
requirement_faithfulness_metric = GEval(
    name="需求忠实度",
    evaluation_steps=[
        "input 是需求功能矩阵（功能点清单：模块/名称/test_points 测试要点），actual_output 是为该需求生成的一份测试用例文件",
        "逐条判定用例的核心验证对象：其验证的功能能否归属于矩阵中某个功能点——对已有功能点的异常/边界/安全/负面变体属于合理衍生，不算幻觉",
        "幻觉用例 = 核心验证的功能在矩阵中完全不存在（AI 自由发挥编造的需求）；每条幻觉用例扣 0.2 分",
        "前置条件/测试数据中提及但未在步骤中实际验证的功能不算幻觉，只有被步骤实际验证的对象才参与判定",
        "reason 中必须列出每条幻觉用例的 case_number、其验证的功能，以及它与矩阵中最近功能点的差异",
    ],
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.8,
    model=_judge,
    async_mode=False,
)

# (维度 key, metric) —— run_judges 落盘与 calibrate_report 对比共用此 key
JUDGES = (
    ("assertability", assertability_metric),
    ("coverage", exception_coverage_metric),
)
