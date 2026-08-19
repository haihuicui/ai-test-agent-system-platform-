# TestCase Agent 质量评估（DeepEval）

对 Agent 生成的测试用例做语义级质量门禁：**像写单元测试一样测 AI 输出**。

> 评估维度的完整规划（三层体系：代码 lint / LLM 语义裁判 / 过程质量）
> 与各层实施状态见 [DIMENSIONS.md](DIMENSIONS.md)。

## 结构

```
tests/eval/
├── DIMENSIONS.md             # 评估维度三层地图（规划 + 实施状态追踪）
├── lint_cases.py             # 用例规范 lint（代码规则，零 token，可直接接 CI）
├── coverage_audit.py         # 覆盖漏测审计（复用运行时 compute_coverage，项目级全景）
├── judge_coverage.py         # 需求覆盖语义裁判（FP 级 G-Eval，抓虚假声明/真漏测）
├── defense_stats.py          # 防线有效性统计（拦截率/评审发现/信任度，零 token）
├── compare_runs.py           # 模型 A/B 对比（同需求两版产出三维对比，裁判 3 次采样取中位）
├── judge_model.py            # DeepSeek 裁判封装（DeepEvalBaseLLM 协议）
├── metrics.py                # G-Eval 裁判定义（单一事实源，门禁与落盘共用）
├── test_testcase_quality.py  # pytest 参数化门禁
├── harvest_samples.py        # 从 workspace 历史产出采集回归样本（分层均衡 + 矩阵关联）
├── make_blind_labels.py      # 生成盲标工作表 + 标注骨架
├── collect_labels.py         # 回收工作表判定行 → 写回标注骨架
├── run_judges.py             # 裁判分数落盘（盲标完成后才准跑）
├── calibrate_report.py       # 一致率/Kappa/分歧清单
└── dataset/
    ├── regression_v1.jsonl   # 回归集 v1（actual_output only，45 条，只增不减）
    ├── regression_v2.jsonl   # 回归集 v2（带 feature_matrix，覆盖/忠实度裁判用）
    ├── lint_baseline.json    # lint 存量违规冻结基线（1615 条 @2026-08-19，只拦新增）
    ├── judge_coverage_v1.jsonl # 覆盖裁判首份基线（25 FP = 23 过 / 2 真漏测）
    ├── judge_coverage_ab.jsonl      # A/B 实战：两模型各自目录 × 各自矩阵
    ├── judge_coverage_ab_cross.jsonl # A/B 交叉：跨目录 × 跨矩阵对照
    ├── human_labels_v1.jsonl # 人工盲标骨架（未标注，校准轨道已冻结——见「校准」）
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
# baseline 模式：存量 1615 条已冻结为基线（历史不修），日常只报新增
./.venv/Scripts/python.exe -m tests.eval.lint_cases --baseline

# 本地门禁已上线：git push 自动跑 lint --baseline + coverage_audit
# （新增 error 或 P0 未覆盖即阻断，--no-verify 可跳过）。
# 为什么不在云端 CI：workspace 用例数据是 .gitignore 的本地资产，
# GitHub Actions 没有数据可扫。换机克隆后需执行一次：
#   git config core.hooksPath .githooks

# 覆盖漏测审计（项目级全景：FP 漏测清单/薄弱覆盖/无追溯文件；P0 未覆盖退出码 1；
# REQ 需求级对齐防 FP 编号撞车虚高——跨需求显式声明不计入覆盖）
./.venv/Scripts/python.exe -m tests.eval.coverage_audit

# 需求覆盖语义裁判（FP 级 G-Eval：相关用例是否真语义覆盖每个 test_point；
# REQ 主题需求级对齐防 FP 编号撞车；断点续跑。首跑：25 FP = 23 过 / 2 真漏测）
./.venv/Scripts/python.exe -m tests.eval.judge_coverage --project PR-1
# 会话目录级 / 跨矩阵评估（模型 A/B 对比用）：
./.venv/Scripts/python.exe -m tests.eval.judge_coverage \
    --cases-dir workspace/testcase/PR-1/<thread_id> --source-tag qwen

# 防线有效性统计（中间件拦截率、对抗评审发现、信任度分布——过程质量量化）
./.venv/Scripts/python.exe -m tests.eval.defense_stats

# 模型 A/B 对比（同需求两版产出三维对比：lint / 语义裁判 / 覆盖裁判；
# 裁判 3 次采样取中位数抗摆动——实测同一裁判同一样本评分摆动 0.00↔0.90）
./.venv/Scripts/python.exe -m tests.eval.compare_runs \
    --a-name "deepseek-v4-flash" --a-path workspace/testcase/PR-1 \
    --b-name "qwen"             --b-path workspace/testcase/PR-1/<thread_id> \
    --matrix workspace/testcase/PR-1/feature_matrix.jsonl
# 加 --skip-judges 只跑零 token 的 lint 对比（快速预览）

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

首份基线（2026-08-13）：459 error / 826 warning，违规集中于 sorted_cases、dms_test_cases
等旧格式文件。新产出的准入标准：**error 必须为 0**，warning 只减不增。

扫描口径（2026-08-19）：`adversarial_review*` 文件不再扫描——评审报告逐字引用
缺陷用例作证据，lint 这些"被展示的反面教材"是纯假阳性（排除后新增违规 540→330）。
基线同日推进 1285→1615（吸收 A/B 实验与 E2E 线程产出）。

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

| 裁判 | 评什么 | 状态 |
|------|--------|------|
| 预期结果可断言性 | 模糊词扣分、因果断裂扣分（质量红线第 2 条） | 初始阈值 0.8，未校准（校准轨道冻结，见下） |
| 异常与安全覆盖 | 异常流密度、安全用例、边界值（红线第 4/6/7 条） | 初始阈值 0.7，未校准；A/B 对比中作相对分用 |
| 需求覆盖完整性 | FP 级：相关用例是否真语义覆盖每个 test_point | ✅ 实战主力，judge_coverage.py 专用 |

## A/B 实战首份结论（2026-08-17，compare_runs + judge_coverage）

DeepSeek vs Qwen 同需求生成对比：lint 打平、可断言性打平 0.70、
异常覆盖 DS 0.90 > QW 0.70、矩阵拆分 QW 23FP > DS 11FP（粒度差异非遗漏）、
效率 DS 快 2.3×。经验：**裁判单次分数不可作对比依据**（推理路径非确定，
同一样本两次评分摆动 0.00↔0.90），compare_runs 一律 3 次采样取中位数。

## 校准（轨道已冻结，重启 LLM 裁判门禁时才走）

> **2026-08-13 决策：放弃 v1 双裁判（可断言性/异常覆盖）的盲标校准**，
> 转向确定性 lint + 覆盖类专用裁判优先。`human_labels_v1.jsonl` 45 条骨架
> 未标注，以下工具链保留可用。本 SOP 仅在重启 LLM 裁判作正式门禁时恢复执行。

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
