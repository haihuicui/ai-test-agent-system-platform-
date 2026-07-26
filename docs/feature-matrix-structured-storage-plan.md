# 跨 Phase 信息断裂优化方案：功能测试矩阵结构化存储

> **状态**：✅ 已实施（减法方案：1 工具 + prompt + middleware）
>
> **实际实施**与原方案的关键差异：删除了 `read_feature_matrix_tool`（deepagents 已有文件读取）和 `cross_check_coverage_tool`（关键词匹配不可靠），改为 prompt 驱动 LLM 读取矩阵 + middleware 兜底检查覆盖对照表。

> **问题根因**：Phase 1 → Phase 3 → Phase 4 之间，功能测试矩阵仅存在于对话历史文本中，LLM 在长对话中会遗忘，导致 Phase 4 误判"覆盖完整"，实际对照 Phase 1 原始矩阵发现遗漏。
>
> **核心思路**：将功能测试矩阵从"对话记忆"变为"磁盘文件"，Phase 1 写入 → Phase 3 对照 → Phase 4 确定性校验。

---

## 实际变更清单

| # | 文件 | 变更 | 说明 |
|---|------|------|------|
| 1 | `backend/app/agents/tools/testcase/feature_matrix_tools.py` | **新增** | `save_feature_matrix_tool`，含 schema 校验 |
| 2 | `backend/app/agents/tools/testcase/__init__.py` | 修改 | 注册新工具 |
| 3 | `backend/app/agents/testcase/agent.py` | 修改 | SYSTEM_PROMPT 增加 Phase 1/3/4 矩阵指令 |
| 4 | `.claude/skills/testcase/requirement-analysis/SKILL.md` | 修改 | 增加 Step 3.5 结构化持久化 |
| 5 | `.claude/skills/testcase/quality-review/SKILL.md` | 修改 | 增加维度一前置：结构化覆盖对照 |
| 6 | `.claude/skills/testcase/test-case-design/SKILL.md` | 修改 | 增加 Phase 3 矩阵对照 |
| 7 | `backend/app/agents/testcase/phase_review_middleware.py` | 修改 | 增加 `_has_coverage_mapping` + Phase 4 覆盖对照表兜底检查 |

---

### 1.1 当前数据流

```
Phase 1 (requirement-analysis)
  └─ 输出: Markdown 功能测试矩阵 + 风险清单
     └─ 存储位置: 仅对话历史 (LangGraph checkpoint)
        └─ 问题: LLM 上下文窗口有限，长对话后部信息被压缩/遗忘

Phase 3 (test-case-design)
  └─ 输出: 每模块 JSONL 用例文件 + 批量创建
     └─ 对照依据: 靠 LLM "回忆" Phase 1 的矩阵
        └─ 问题: 模块多了以后，早期功能点被遗忘

Phase 4 (quality-review)
  └─ 输出: 质量评审报告 (含"完整性检查")
     └─ 对照依据: 靠 LLM "回忆" Phase 1 的矩阵
        └─ 问题: 覆盖率评分基于模糊记忆，不可信
```

### 1.2 现有相关能力（可复用）

| 能力 | 位置 | 说明 |
|------|------|------|
| JSONL 文件读写 | `excel_tools.py:_parse_json_objects` | 强容错 JSON/JSONL 解析器 |
| 路径映射 | `excel_tools.py:_resolve_input_path` | 虚拟路径 → workspace_root 映射 |
| 模块自检 | `module_check_tools.py:_perform_module_self_check` | 用例质量校验逻辑 |
| 用例预览 | `testcase_tools.py:preview_test_cases` | 从 JSONL 抽样读取用例 |
| 文件系统后端 | `agent.py:composite_backend` | `/` 路由到 workspace_root |

### 1.3 关键差距

- ❌ **没有**将功能矩阵保存为结构化文件的工具
- ❌ **没有**读取功能矩阵做对照的工具
- ❌ **没有**"需求功能点 vs 已生成用例"的确定性覆盖映射
- ❌ Phase 1/3/4 的 prompt 没有强制要求结构化矩阵的写入/读取

---

## 二、方案设计

### 2.1 目标数据流

```
Phase 1 (requirement-analysis)
  ├─ 输出: Markdown 功能测试矩阵 (对话中展示)
  └─ 工具调用: save_feature_matrix_tool → feature_matrix.jsonl (落盘)
        │
Phase 3 (test-case-design)                    │
  ├─ 每模块开始前:                              │
  │    read_feature_matrix_tool ← 读取矩阵 ←───┘
  │    └─ 筛选当前模块的功能点，确保不漏
  ├─ 每模块完成后: 保存 JSONL 用例文件 (已有)
  └─ 全部完成后: 无需 LLM 凭记忆做完整性判断
        │
Phase 4 (quality-review)                      │
  ├─ 工具调用: cross_check_coverage_tool ─────┘
  │    ├─ 输入: feature_matrix.jsonl + 所有用例 JSONL 文件
  │    └─ 输出: 确定性覆盖映射报告
  └─ LLM 基于工具输出撰写评审报告 (而非凭记忆)
```

### 2.2 新增工具

#### 工具 1: `save_feature_matrix_tool`

**用途**: Phase 1 完成后，将功能测试矩阵持久化为结构化 JSONL 文件。

```python
@tool
async def save_feature_matrix_tool(
    features: list[dict[str, Any]],
    output_file: str = "feature_matrix.jsonl",
    project_identifier: str = "",
) -> dict[str, Any]:
    """
    将功能测试矩阵保存为结构化 JSONL 文件。

    在 Phase 1 需求分析完成后必须调用，将功能点清单持久化，
    供 Phase 3 用例设计和 Phase 4 质量评审做确定性覆盖对照。

    Args:
        features: 功能点列表，每个元素包含：
            - id: 功能点编号 (如 "FP-001")
            - module: 所属模块
            - feature: 功能点名称
            - test_points: 测试要点列表
            - priority: 优先级 (P0/P1/P2/P3)
            - risk_level: 风险等级 (高/中/低)
            - test_type: 测试类型列表 (如 ["功能", "安全"])
            - source: 来源标注 (如 "需求原文 §2.1")
        output_file: 输出文件路径，默认 feature_matrix.jsonl
        project_identifier: 项目标识符

    Returns:
        {"success": bool, "file": str, "count": int, "modules": [...]}
    """
```

**JSONL 每行 schema**:
```json
{
  "id": "FP-001",
  "module": "用户认证",
  "feature": "手机号登录",
  "test_points": ["验证码有效期5min", "验证码发送频率限制", "错误次数锁定"],
  "priority": "P0",
  "risk_level": "高",
  "test_type": ["功能", "安全"],
  "source": "需求原文 §2.1"
}
```

---

#### 工具 2: `read_feature_matrix_tool`

**用途**: Phase 3/4 读取功能矩阵做对照，可选按模块过滤。

```python
@tool
async def read_feature_matrix_tool(
    input_file: str = "feature_matrix.jsonl",
    module: str | None = None,
    priority: str | None = None,
) -> dict[str, Any]:
    """
    读取结构化功能测试矩阵，供 Phase 3/4 对照使用。

    Phase 3 每模块开始前应调用本工具，用 module 过滤获取当前模块的功能点。
    Phase 4 质量评审时应读取全量矩阵做覆盖对照。

    Args:
        input_file: 功能矩阵文件路径
        module: 按模块名过滤 (可选)
        priority: 按优先级过滤 (可选)

    Returns:
        {
          "success": bool,
          "total": int,
          "modules": ["模块1", "模块2", ...],
          "features": [...],
          "summary": "共 N 个功能点，涉及 M 个模块"
        }
    """
```

---

#### 工具 3: `cross_check_coverage_tool` ⭐ 核心工具

**用途**: Phase 4 质量评审时，确定性计算"需求功能点 vs 已生成用例"覆盖映射。**不依赖 LLM 记忆**。

```python
@tool
async def cross_check_coverage_tool(
    feature_matrix_file: str = "feature_matrix.jsonl",
    test_case_files: list[str] | None = None,
    match_mode: str = "keyword_fuzzy",
) -> dict[str, Any]:
    """
    确定性覆盖映射：功能矩阵 vs 已生成用例。

    Phase 4 质量评审时必须首先调用本工具。工具会：
    1. 读取功能矩阵中的全部功能点
    2. 扫描所有用例 JSONL 文件
    3. 对每个功能点，按关键词/模块名匹配找到对应的用例
    4. 输出覆盖状态：covered / partial / uncovered

    Args:
        feature_matrix_file: 功能矩阵 JSONL 文件路径
        test_case_files: 用例文件列表 (可选，不传则自动扫描 workspace_root 下所有 .jsonl)
        match_mode: 匹配模式
            - "keyword_fuzzy": 按功能点关键词 + 模块名做模糊匹配 (默认)
            - "module_only": 仅按模块名匹配 (宽松)
            - "strict": 关键词严格包含匹配

    Returns:
        {
          "success": bool,
          "total_features": int,
          "covered_features": int,
          "partial_features": int,
          "uncovered_features": int,
          "coverage_rate": float,
          "details": [
            {
              "feature_id": "FP-001",
              "module": "用户认证",
              "feature": "手机号登录",
              "priority": "P0",
              "risk_level": "高",
              "status": "covered",
              "matched_case_count": 5,
              "matched_cases": ["TC-AUTH-001", "TC-AUTH-002", ...],
              "match_confidence": "high"
            },
            {
              "feature_id": "FP-012",
              "module": "支付模块",
              "feature": "退款流程-部分退款",
              "priority": "P0",
              "risk_level": "高",
              "status": "uncovered",
              "matched_case_count": 0,
              "matched_cases": [],
              "suggestion": "建议为支付模块新增退款流程-部分退款的测试用例"
            }
          ],
          "uncovered_p0": [...],  # P0 未覆盖项 (重点关注)
          "summary": "覆盖率 88% (22/25)，3 个功能点未覆盖，其中 1 个为 P0"
        }
    """
```

**匹配逻辑** (确定性，非 LLM):
1. 提取功能点的 `module` + `feature` + `test_points` 关键词
2. 扫描所有用例的 `module` + `name` + `case_number` + `test_case_steps` 文本
3. 三层匹配策略:
   - **High confidence**: 用例的 module 匹配 AND 用例 name/steps 包含功能点关键词
   - **Medium confidence**: 仅 module 匹配 (同模块但无法确定是否覆盖该具体功能点)
   - **No match**: 任何用例都未匹配到

---

### 2.3 Prompt 修改

#### Agent 系统提示词 (`agent.py` SYSTEM_PROMPT)

在 Phase 1/3/4 的说明中增加强制工具调用要求：

```markdown
### Phase 1 特别说明（结构化矩阵持久化 - 强制）

完成需求分析报告（Markdown）后，**必须立即调用 `save_feature_matrix_tool`** 
将功能测试矩阵保存为结构化 JSONL 文件。这是跨 Phase 信息传递的唯一可靠方式。

要求：
1. 每个功能点必须有唯一 id (FP-001, FP-002, ...)
2. 每个功能点必须标注 module、priority、risk_level、test_type
3. test_points 列表必须具体，每个测试要点一行
4. 保存完成后在报告中注明文件路径和功能点总数

**禁止**仅输出 Markdown 矩阵就进入人工评审。系统不会拦截，但后续 Phase 3/4 将无法做确定性覆盖对照。
```

```markdown
### Phase 3 特别说明（矩阵对照 - 强制）

每开始一个模块的用例设计前，**必须调用 `read_feature_matrix_tool`** 
读取功能矩阵中该模块的功能点，确保用例设计覆盖所有功能点。

要求：
1. 设计前: 调用 read_feature_matrix_tool(module="当前模块名") 
2. 设计中: 每个功能点至少 1 条用例
3. 完成后: 在 `batch_create_test_cases_tool` 成功后标注已覆盖的功能点

**禁止**仅凭记忆设计用例。工具读取的结果是权威的功能点清单。
```

```markdown
### Phase 4 特别说明（覆盖映射 - 强制）

质量评审的**第一步必须调用 `cross_check_coverage_tool`**，
获取确定性的"功能点 vs 用例"覆盖映射报告。

要求：
1. 调用 cross_check_coverage_tool() 获取覆盖报告
2. 报告中"完整性检查"维度的评分必须基于工具返回的覆盖率数据
3. uncovered 的功能点必须在报告的"补充建议"中列出
4. uncovered P0 功能点必须标记为 🔴 严重问题

**禁止**在未调用 cross_check_coverage_tool 的情况下撰写完整性评分。
**禁止**仅凭对话历史中的记忆判断覆盖率。
```

#### Skill 文件修改

**`.claude/skills/testcase/requirement-analysis/SKILL.md`**:

在 Step 3（功能矩阵建立）之后插入 `Step 3.5`：

```markdown
### Step 3.5：结构化矩阵持久化（强制）

完成功能矩阵表格后，**必须调用 `save_feature_matrix_tool`** 将矩阵保存为 JSONL 文件。

调用示例：
```python
save_feature_matrix_tool(
    features=[
        {
            "id": "FP-001",
            "module": "用户认证",
            "feature": "手机号登录",
            "test_points": ["验证码有效期5min", "验证码发送频率限制", ...],
            "priority": "P0",
            "risk_level": "高",
            "test_type": ["功能", "安全"],
            "source": "需求原文 §2.1"
        },
        ...
    ],
    output_file="feature_matrix.jsonl",
    project_identifier=project_identifier
)
```

> ⚡ **强制要求**：不调用此工具的 Phase 1 是不完整的，后续 Phase 将失去确定性覆盖对照的能力。
```

**`.claude/skills/testcase/quality-review/SKILL.md`**:

在"维度一：完整性检查"的最前面插入：

```markdown
### 维度一前置：确定性覆盖映射（强制）

在评估完整性之前，**必须先调用 `cross_check_coverage_tool`** 获取确定性的覆盖映射报告：

```python
cross_check_coverage_tool(
    feature_matrix_file="feature_matrix.jsonl"
)
```

工具返回的 `coverage_rate`、`uncovered_features`、`uncovered_p0` 是本维度评分的唯一数据源。不要凭记忆判断覆盖完整性。
```

---

### 2.4 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/agents/tools/testcase/feature_matrix_tools.py` | **新增** | 三个新工具的完整实现 |
| `backend/app/agents/tools/testcase/__init__.py` | 修改 | 注册新工具到 TOOL 列表 |
| `backend/app/agents/testcase/agent.py` | 修改 | SYSTEM_PROMPT 增加结构化矩阵指令 |
| `.claude/skills/testcase/requirement-analysis/SKILL.md` | 修改 | 增加 Step 3.5 结构化持久化 |
| `.claude/skills/testcase/quality-review/SKILL.md` | 修改 | 维度一前置：确定性覆盖映射 |
| `.claude/skills/testcase/test-case-design/SKILL.md` | 修改 | 增加 Phase 3 矩阵对照说明 |

---

## 三、实现要点

### 3.1 匹配算法（cross_check_coverage_tool 核心）

`match_mode="keyword_fuzzy"` 的匹配策略（确定性，无 LLM 参与）：

```
输入: 功能点 FP = {module: "用户认证", feature: "手机号登录", test_points: ["验证码有效期", ...]}
      用例列表 cases = [{module: "用户认证", name: "...", case_number: "TC-AUTH-001", ...}, ...]

Step 1: 模块筛选 → 只保留 module == "用户认证" 的用例
Step 2: 关键词提取 → 从 feature + test_points 提取特征词:
          ["手机号", "登录", "验证码", "有效期", "发送频率", "错误次数"]
Step 3: 文本匹配 → 对每条筛选后的用例，拼接 name + case_number + test_case_steps 文本，
         计算命中的特征词比例
Step 4: 置信度标注:
          - high: 命中 ≥ 50% 特征词
          - medium: 命中 ≥ 1 个特征词 且 module 匹配
          - none: 0 命中
Step 5: 覆盖判定:
          - covered: ≥ 1 条 high 或 ≥ 3 条 medium
          - partial: ≥ 1 条 medium (但不足 covered 标准)
          - uncovered: 0 条命中
```

### 3.2 与现有系统的集成点

- **文件路径映射**：复用 `excel_tools.py` 的 `_resolve_input_path`，统一落到 `workspace_root`
- **JSONL 解析**：复用 `excel_tools.py` 的 `_parse_json_objects`，强容错
- **workspace 清理**：`StaleToolResultOffloadMiddleware` 不会卸载小文件（JSONL 只有几 KB），无需特殊处理
- **工具生命周期**：新工具为纯本地工具，无需异步初始化，直接加入 `ALL_LOCAL_TOOLS`

### 3.3 向后兼容

- 新工具全部为 opt-in：Phase 1 如果 LLM 不调用 `save_feature_matrix_tool`，Phase 3/4 的工具会返回文件不存在的友好提示，不会崩溃
- 现有 prompt 中的 Phase 3 JSONL 保存逻辑不受影响
- 现有 `preview_test_cases`、`module_self_check_tool` 不受影响
- 旧对话（已生成但没有 feature_matrix.jsonl）重新进入 Phase 4 时，`cross_check_coverage_tool` 返回 `{"success": False, "error": "功能矩阵文件不存在，请先完成 Phase 1"}`——友好的降级

---

## 四、效果预期

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| 覆盖判断方式 | LLM 凭对话记忆估计 | 工具确定性计算 |
| Phase 4 覆盖率偏差 | 常见 ±15%（遗漏 P0 功能点） | ≤ 5%（匹配算法误差） |
| 长对话稳定性 | 超过 50 轮后明显遗忘 | 不受对话长度影响 |
| 人工校验成本 | 需人工逐项对照 Phase 1 矩阵 | 工具直接输出 gap 清单 |
| 跨 Phase 信息丢失风险 | 高（依赖 LLM 上下文窗口） | 零（文件在磁盘上） |

---

## 五、实施步骤

| 步骤 | 内容 | 预估工作量 |
|------|------|-----------|
| 1 | 实现 `feature_matrix_tools.py`（3 个工具） | 核心 |
| 2 | 在 `__init__.py` 注册新工具 | 小 |
| 3 | 修改 `agent.py` SYSTEM_PROMPT 增加结构化矩阵指令 | 中 |
| 4 | 修改 `requirement-analysis/SKILL.md` | 小 |
| 5 | 修改 `quality-review/SKILL.md` | 小 |
| 6 | 修改 `test-case-design/SKILL.md` | 小 |
| 7 | 端到端测试：需求 → 矩阵保存 → 用例生成 → 覆盖校验 | 验证 |
