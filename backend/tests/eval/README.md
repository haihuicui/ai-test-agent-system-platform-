# TestCase Agent 质量评估（DeepEval）

对 Agent 生成的测试用例做语义级质量门禁：**像写单元测试一样测 AI 输出**。

## 结构

```
tests/eval/
├── judge_model.py            # DeepSeek 裁判封装（DeepEvalBaseLLM 协议）
├── test_testcase_quality.py  # 2 个 G-Eval 裁判 + pytest 参数化门禁
├── harvest_samples.py        # 从 workspace 历史产出采集回归样本
└── dataset/
    └── regression_v1.jsonl   # 回归集（每行一条样本）
```

## 快速开始

```bash
# 0. 首次安装（backend/.venv，评估代码不进生产环境）
uv pip install --python backend/.venv/Scripts/python.exe "deepeval>=3.0"

# 1. 采集真实样本（从 workspace 历史用例文件）
cd backend
../backend/.venv/Scripts/python.exe -m tests.eval.harvest_samples

# 2. 跑评估
../backend/.venv/Scripts/python.exe -m pytest tests/eval/ -v
```

> 想屏蔽 deepeval 的 PostHog 遥测上报（内网会超时告警，不影响功能）：
> `export DEEPEVAL_TELEMETRY_OPT_OUT=YES`

## 样本格式（regression_v1.jsonl，每行一条）

```json
{
  "id": "ws-cases",
  "input": "需求原文（可为占位；裁判只看 actual_output 时不受影响）",
  "actual_output": "[{\"case_number\": \"TC-...\", ...}]",
  "source": "workspace/testcase/cases.jsonl",
  "case_count": 30
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

裁判与被测 Agent 同源（都是 deepseek-v4-flash），存在自评偏好风险：

1. 跑一遍评估，导出各样本分数与裁判 `reason`
2. **人工复核 20-50 条**，记录你认可的分数
3. 算一致率：|裁判判 fail| 与 |人工判 fail| 的重合度
4. 一致率 < 80% → 改 `evaluation_steps` 措辞后重跑；≥ 80% 才允许：
   - 把 `threshold` 定为正式拦截线
   - 考虑接入 CI（`deepeval test run` / pytest 进 Jenkins）

## 红线

- **离线观测阶段**：评估结果只用于改进 Prompt，不接自动返工流程
- 裁判 prompt（evaluation_steps）的任何修改都要全量重跑回归集对比前后分数
- 回归集只增不减；翻车样本必须保留
