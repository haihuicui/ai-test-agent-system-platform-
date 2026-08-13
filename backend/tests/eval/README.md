# TestCase Agent 质量评估（DeepEval）

对 Agent 生成的测试用例做语义级质量门禁：**像写单元测试一样测 AI 输出**。

## 结构

```
tests/eval/
├── lint_cases.py             # 用例规范 lint（代码规则，零 token，可直接接 CI）
├── judge_model.py            # DeepSeek 裁判封装（DeepEvalBaseLLM 协议）
├── metrics.py                # 2 个 G-Eval 裁判定义（单一事实源，门禁与落盘共用）
├── test_testcase_quality.py  # pytest 参数化门禁
├── harvest_samples.py        # 从 workspace 历史产出采集回归样本（分层均衡 + 矩阵关联）
├── make_blind_labels.py      # 生成盲标工作表 + 标注骨架
├── collect_labels.py         # 回收工作表判定行 → 写回标注骨架
├── run_judges.py             # 裁判分数落盘（盲标完成后才准跑）
├── calibrate_report.py       # 一致率/Kappa/分歧清单
└── dataset/
    ├── regression_v1.jsonl   # 回归集 v1（actual_output only，45 条，只增不减）
    ├── regression_v2.jsonl   # 回归集 v2（带 feature_matrix，覆盖/忠实度裁判用）
    ├── human_labels_v1.jsonl # 人工盲标（0/1，校准基准）
    ├── judge_scores_v1.jsonl # 裁判分数落盘（重分析不重跑）
    └── blind_worksheet.md    # 盲标阅读材料（用例全文 + 判定行，无裁判分）
```

## 快速开始

```bash
# 0. 首次安装（backend/.venv，评估代码不进生产环境）
uv pip install --python backend/.venv/Scripts/python.exe "deepeval>=3.0"

# 用例规范 lint（零 token，推荐每次改 prompt 后先跑它）
cd backend
./.venv/Scripts/python.exe -m tests.eval.lint_cases          # 有 error 退出码 1

# 1. 采集真实样本（从 workspace 历史用例文件）
./.venv/Scripts/python.exe -m tests.eval.harvest_samples
# 带功能矩阵的 v2 采集（覆盖完整性/需求忠实度裁判的输入）
./.venv/Scripts/python.exe -m tests.eval.harvest_samples --strategy balanced --with-matrix --max-files 60

# 2. 跑评估
./.venv/Scripts/python.exe -m pytest tests/eval/ -v
```

> 想屏蔽 deepeval 的 PostHog 遥测上报（内网会超时告警，不影响功能）：
> `export DEEPEVAL_TELEMETRY_OPT_OUT=YES`

## lint 规则（lint_cases.py）

确定性代码检查，规则源自 workspace 全量 1828 条用例的真实违规画像：

| 级别 | 规则 | 查什么 |
|------|------|--------|
| error | E1 case_type 缺失 / E2 priority 缺失 / E3 无步骤 / E4 命名为空 | 结构性硬伤，直接阻断 |
| warning | W1 case_type 非法值 / W4 单步骤 / W5 步骤>10 / W6 无 REQ-/FP-/F- 追溯 / W7 命名不规范 | 单条用例规范 |
| warning | W8 priority 双体系混用 / W9 critical 占比>50% / W10 步骤非结构化(字符串) / W11 旧 schema | 文件级/结构级问题 |

首份基线（2026-08）：459 error / 826 warning，违规集中于 sorted_cases、dms_test_cases
等旧格式文件。新产出的准入标准：**error 必须为 0**，warning 只减不增。

## 样本格式（regression_v1.jsonl，每行一条）

```json
{
  "id": "ws-cases",
  "input": "需求原文（可为占位；裁判只看 actual_output 时不受影响）",
  "actual_output": "[{\"case_number\": \"TC-...\", ...}]",
  "source": "workspace/testcase/cases.jsonl",
  "case_count": 30,
  "group": "(root)"
}
```

**样本三来源**（优先级从高到低）：
1. 生产翻车 case——Langfuse 里筛失败/低分 trace，回填真实 `input`
2. harvest 采集的历史产出（`input` 为占位，裁判仅评 `actual_output`）
3. 手工构造的边界样本（如全 Happy Path 的用例集，验证裁判会给低分）

## 当前裁判（阈值待定，见「校准」）

| 裁判 | 评什么 | 初始阈值 |
|------|--------|---------|
| 预期结果可断言性 | 模糊词扣分、因果断裂扣分（质量红线第 2 条） | 0.8 |
| 异常与安全覆盖 | 异常流密度、安全用例、边界值（红线第 4/6/7 条） | 0.7 |

## 校准（启用真门禁前必做）

裁判与被测 Agent 同源（都是 deepseek-v4-flash），存在自评偏好风险。
校准 = 证明「裁判的 pass/fail 与人的判断足够一致」，不一致就调裁判，而不是信裁判。

**SOP（顺序即纪律，乱序校准失效）：**

```bash
cd backend

# 1. 扩采校准集：分层均衡策略防单项目霸榜（PR-2 占 workspace 近半文件）
./.venv/Scripts/python.exe -m tests.eval.harvest_samples --strategy balanced --max-files 60

# 2. 生成盲标材料：worksheet 含用例全文、无任何裁判分；行序固定 seed 打乱
./.venv/Scripts/python.exe -m tests.eval.make_blind_labels

# 3. 人工盲标：对照 dataset/blind_worksheet.md 判定 45 条样本
#    （判定规则写在 worksheet 头部，与两个裁判一一对应）。
#    两种填法可混用：
#    a) 一体式：在 worksheet 每条样本末尾的「> 判定」行把 _ 改成 0/1，标完回收：
./.venv/Scripts/python.exe -m tests.eval.collect_labels
#    b) 答题卡：直接填 human_labels_v1.jsonl 的 null。
#    【此步完成前禁止跑 run_judges——提前看裁判分会污染人工判断】
#    ⚠️ worksheet 里已填判定后，重跑 make_blind_labels 前必须先 collect 回收

# 4. 裁判落盘：逐条跑分写 judge_scores_v1.jsonl，断点续跑，Ctrl+C 可中断
./.venv/Scripts/python.exe -m tests.eval.run_judges
#    分批试跑（如先标 15 条验证管线）：jsonl 只保留已标行（null 行移走），
#    用 --only-labeled 只跑已标样本省 API；报告带样本量闸，n<20 仅出警告结论
./.venv/Scripts/python.exe -m tests.eval.run_judges --only-labeled

# 5. 出校准报告：一致率/Kappa/混淆矩阵/分层一致率 + 分歧清单
./.venv/Scripts/python.exe -m tests.eval.calibrate_report
```

**启用决策线**：两维均满足 一致率 ≥ 80% 且 Cohen's Kappa ≥ 0.6，才允许：

- 把 `metrics.py` 的 `threshold` 定为正式拦截线（strict_mode）
- 考虑接入 CI（`deepeval test run` / pytest 进 Jenkins）

未过线 → 逐条过 `dataset/disagreements.md` 判分歧主因（rubric 措辞 / 阈值 /
同源自评偏好），改 `metrics.py` 后**全量重跑** run_judges（删 judge_scores 文件
或改文件名）再出报告。若同源自评偏好是主因，引入异源第二裁判复核分歧样本。

## 红线

- **离线观测阶段**：评估结果只用于改进 Prompt，不接自动返工流程
- 裁判 prompt（`metrics.py` 的 evaluation_steps）的任何修改都要全量重跑回归集
  对比前后分数（删 judge_scores_v1.jsonl 后重跑 run_judges）
- 回归集只增不减；翻车样本必须保留
