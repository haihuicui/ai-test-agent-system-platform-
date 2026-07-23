---
name: output-formatter
description: 控制测试用例的最终输出格式与规范。确保所有生成的测试用例符合企业级测试管理工具（Jira Xray、TestRail、禅道、Tapd）的导入格式要求，同时提供Markdown、CSV/Excel、JSON等多种格式。当用户要求特定格式输出或导出测试用例时激活。
---

# 测试用例输出格式规范 Skill

## 激活场景
- 生成最终测试用例前，确定输出格式
- 用户要求导出特定格式（Excel/CSV/JSON/Markdown）
- 需要将测试用例导入测试管理工具
- 需要格式化已有的测试用例

---

## 用例编号命名规范

```
格式：TC-[项目代码]-[模块缩写]-[序号]

项目代码：2-4位大写字母（如 CRM / OMS / USER）
模块缩写：2-6位大写字母（常用缩写见下表）
序号：    3位数字，从001开始

示例：
TC-CRM-LOGIN-001   → CRM项目，登录模块，第1条
TC-OMS-ORDER-012   → OMS项目，订单模块，第12条
TC-USER-AUTH-001   → 用户系统，认证模块，第1条
```

**常用模块缩写对照表**：
| 业务模块 | 缩写 | 业务模块 | 缩写 |
|---------|------|---------|------|
| 用户登录 | LOGIN | 权限管理 | AUTH |
| 用户注册 | REG | 商品管理 | PROD |
| 个人信息 | PROFILE | 订单管理 | ORDER |
| 购物车 | CART | 支付结算 | PAY |
| 搜索功能 | SEARCH | 消息通知 | MSG |
| 文件上传 | UPLOAD | 数据导出 | EXPORT |
| 系统设置 | SYS | 报表统计 | REPORT |

---

## 输出格式一：标准Markdown格式（默认）

每个测试用例使用以下Markdown模板输出：

```markdown
---

### TC-[PROJECT]-[MODULE]-[NNN]：[用例标题]

> **模块**：[所属模块名] ｜ **优先级**：[P0/P1/P2/P3] ｜ **类型**：[用例类型] ｜ **方法**：[设计方法]

**前置条件**：
- [条件1，具体且可验证]
- [条件2]

**测试步骤**：

| 步骤 | 操作描述 | 操作对象 |
|------|---------|---------|
| 1 | [具体操作，使用主动动词：输入/点击/选择/上传] | [操作的UI元素或接口] |
| 2 | [具体操作] | [操作对象] |
| N | [具体操作] | [操作对象] |

**测试数据**：
```
[字段名]: [具体值]     # [说明]
[字段名]: [具体值]
```

**预期结果**：
1. ✅ [UI层：页面/组件的状态变化，精确描述]
2. ✅ [接口层：HTTP状态码、响应体中的关键字段]
3. ✅ [数据层：数据库/缓存中的状态变化]
4. ✅ [日志层：关键操作日志记录（如需）]

**备注**：关联需求 `REQ-[ID]` | 风险级别：[高/中/低]
```

---

## 输出格式二：表格汇总格式（全模块概览）

生成完所有用例后，提供汇总表格供快速审查：

```markdown
## 测试用例汇总表

| 用例编号 | 用例标题 | 模块 | 优先级 | 类型 | 设计方法 | 前置条件 | 预期结果摘要 |
|---------|---------|------|--------|------|---------|---------|------------|
| TC-XXX-LOGIN-001 | 正确账号密码登录 | 用户登录 | P0 | 功能 | 等价类 | 账号已注册 | 跳转首页，显示用户名 |
| TC-XXX-LOGIN-002 | 错误密码登录 | 用户登录 | P1 | 功能 | 错误推测 | 账号已注册 | 提示密码错误，不跳转 |

**统计摘要**：
| 维度 | 数量 |
|------|------|
| 总用例数 | N |
| P0用例数 | N |
| P1用例数 | N |
| P2用例数 | N |
| P3用例数 | N |
| 功能测试 | N |
| 接口测试 | N |
| 安全测试 | N |
```

---

## 输出格式三：CSV格式（Excel/测试管理工具导入）

```csv
用例编号,用例标题,所属模块,用例类型,优先级,前置条件,测试步骤,测试数据,预期结果,备注
TC-XXX-LOGIN-001,正确账号密码登录,用户登录,功能测试,P0,"账号已注册且状态正常","1.打开登录页；2.输入用户名；3.输入密码；4.点击登录","用户名:test001;密码:Test@123","1.跳转首页；2.显示用户名；3.生成登录日志",REQ-LOGIN-001
```

---

## 输出格式四：Excel格式（推荐导出）

当用户要求导出 Excel 文件时，使用 `export_test_cases_to_excel` 工具生成 `.xlsx` 文件。

### Excel 文件结构

| 列名 | 对应字段 | 说明 |
|------|---------|------|
| 用例编号 | `id` | TC-XXX-MODULE-NNN 格式 |
| 用例标题 | `title` | 简洁描述验证点 |
| 所属模块 | `module` | 功能模块名称 |
| 用例类型 | `type` | 功能/接口/安全/性能/兼容等 |
| 优先级 | `priority` | P0 / P1 / P2 / P3 |
| 前置条件 | `preconditions` | 支持列表或字符串，自动换行编号 |
| 测试步骤 | `steps` | 列表自动转换为 `序号. 操作 [对象]` 格式 |
| 测试数据 | `test_data` | 键值对自动换行，或直接文本 |
| 预期结果 | `expected_results` | 支持列表或字符串，自动换行编号 |
| 备注 | `remarks` | 需求编号、风险说明等 |

### 字段必填要求

为避免导出的 Excel 出现空列，每条用例必须显式提供以下字段：
- `id` / `case_number`：用例编号
- `title` / `name`：用例标题
- `module`：所属模块
- `type` / `case_type`：用例类型（推荐传英文枚举，如 `functional`、`security`、`performance`）
- `preconditions`：前置条件
- `steps` / `test_case_steps`：测试步骤
- `expected_results`：预期结果
- `test_data`：测试数据
- `remarks` / `description`：备注/关联需求

### 样式规范

- 首行为深蓝色（#366092）表头，白色粗体字体
- 所有单元格带有细边框
- 内容列自动换行，默认行高 60 磅、列宽自适应常见场景
- 文件保存路径由调用方指定，建议存放于 `./exports/测试用例_YYYYMMDD.xlsx`

### 调用示例（Python）

```python
from app.tools.excel_exporter import export_test_cases_to_excel

test_cases = [
    {
        "id": "TC-CRM-LOGIN-001",
        "title": "正确账号密码登录成功",
        "module": "用户登录",
        "type": "functional",
        "priority": "P0",
        "preconditions": ["账号已注册", "账号状态正常"],
        "steps": [
            {"seq": 1, "action": "打开登录页面", "target": "登录页URL"},
            {"seq": 2, "action": "输入用户名", "target": "用户名输入框", "data": "test001"},
            {"seq": 3, "action": "输入密码", "target": "密码输入框", "data": "Test@123"},
            {"seq": 4, "action": "点击登录按钮", "target": "登录按钮"},
        ],
        "test_data": {"username": "test001", "password": "Test@123"},
        "expected_results": [
            "HTTP响应码200，响应体包含 token 字段",
            "页面跳转至 /dashboard",
            "数据库 login_log 表新增一条记录"
        ],
        "remarks": "REQ-LOGIN-001 | 风险级别：低"
    }
]

export_test_cases_to_excel(test_cases=test_cases, output_path="./exports/CRM登录模块测试用例.xlsx")
```

> ⚠️ **用例多时（约 ≥ 30 条）必须改用文件中转方式导出，否则会因模型单次输出 token 上限导致 JSON 被截断、用例丢失。**
>
> 推荐流程（分批写 JSONL，再读文件导出）：
> 1. 用文件写入工具，把用例**分批追加**写入一个 `.jsonl` 文件，**每行一个 JSON 对象**（一条用例一行），每批控制在 20~30 条以内：
>    ```
>    # exports/cases.jsonl（每行一条，示例两行）
>    {"id":"TC-001","title":"...","module":"...","priority":"P0","steps":[...],"expected_results":[...]}
>    {"id":"TC-002","title":"...","module":"...","priority":"P1","steps":[...],"expected_results":[...]}
>    ```
> 2. 全部写完后，一次性读取该文件导出 Excel：
>    ```python
>    export_test_cases_to_excel(input_file="./exports/cases.jsonl", output_path="./exports/CRM登录模块测试用例.xlsx")
>    ```
> 分批写入不受单次模型输出长度限制，可稳定导出成百上千条用例。`input_file` 也支持整文件 JSON 数组（`.json`）。

---

## 输出格式五：JSON格式（程序化处理）

```json
{
  "test_suite": {
    "project": "[项目名称]",
    "module": "[模块名称]",
    "generated_at": "2024-01-01T00:00:00Z",
    "total_count": 1,
    "test_cases": [
      {
        "id": "TC-XXX-LOGIN-001",
        "title": "正确账号密码登录成功",
        "module": "用户登录",
        "type": "functional",
        "priority": "P0",
        "design_method": "equivalence_partitioning",
        "preconditions": ["账号已注册", "账号状态正常"],
        "steps": [
          {"seq": 1, "action": "打开登录页面", "target": "登录页URL"},
          {"seq": 2, "action": "输入用户名", "target": "用户名输入框", "data": "test001"}
        ],
        "test_data": {"username": "test001", "password": "Test@123"},
        "expected_results": [
          "HTTP响应码200，包含token字段",
          "页面跳转至/dashboard",
          "数据库login_log表新增记录"
        ],
        "requirements": ["REQ-LOGIN-001"],
        "risk_level": "high"
      }
    ]
  }
}
```

---

## 格式选择建议

| 用途 | 推荐格式 |
|------|---------|
| 与用户对话/审查 | Markdown详细格式 |
| 快速全量概览 | Markdown表格汇总格式 |
| 导入禅道/Tapd/TestRail | CSV格式 / Excel格式 |
| 导入Jira Xray | JSON格式 |
| 自动化脚本生成 | JSON格式 |
| 需要精美排版、直接发给业务方审阅 | Excel格式 |

> 💡 **默认行为**：未指定格式时，优先输出「Markdown详细格式」，每个模块完成后附带「表格汇总格式」
> 💡 **导出行为**：当用户明确说"导出Excel"或"生成Excel"时，优先调用 `export_testcases_to_excel` 工具直接生成文件，而不是在对话中打印 CSV 文本。

---

## 版本控制规范

企业级测试资产必须进行版本管理，确保可追溯和可审计。

### 用例版本号规则

```
格式：V[主版本].[次版本].[修订号]

主版本（Major）：需求发生结构性变更时递增
  示例：V1.0.0 → V2.0.0（业务流程重构）

次版本（Minor）：新增功能模块或大规模补充用例时递增
  示例：V1.0.0 → V1.1.0（新增支付模块用例）

修订号（Patch）：用例修正、优化、数据更新时递增
  示例：V1.0.0 → V1.0.1（修复预期结果描述）
```

### 变更追踪规范

每条用例必须记录完整的变更历史：

```markdown
### 变更历史

| 版本 | 变更时间 | 变更人 | 变更类型 | 变更内容 |
|------|---------|--------|---------|---------|
| V1.0.0 | 2024-01-15 | AI Agent | 创建 | 初始版本 |
| V1.0.1 | 2024-01-20 | AI Agent | 修正 | 修正 TC-XXX-001 预期结果描述 |
| V1.1.0 | 2024-02-01 | AI Agent | 新增 | 新增忘记密码功能用例 3 条 |

变更类型：创建 / 修正 / 新增 / 删除 / 合并 / 拆分
```

### 变更影响标记

当用例发生变更时，标注影响范围：

```
[无影响]：仅文字描述优化，不影响执行逻辑
[低风险]：预期结果微调，测试数据不变
[中风险]：测试步骤或数据变更，需重新验证
[高风险]：前置条件或核心步骤变更，需重新执行全量验证
```

---

## 测试管理工具字段映射详表

### 禅道（Zentao）导入字段映射

| 禅道字段 | 本系统字段 | 映射规则 | 必填 |
|---------|-----------|---------|------|
| 用例编号 | `id` | 直接映射 | 是 |
| 用例标题 | `title` | 直接映射 | 是 |
| 所属模块 | `module` | 直接映射 | 是 |
| 用例类型 | `type` | 功能→功能测试，接口→接口测试 | 是 |
| 优先级 | `priority` | P0→1, P1→2, P2→3, P3→4 | 是 |
| 前置条件 | `preconditions` | 列表用换行符连接 | 否 |
| 步骤 | `steps` | 格式化为 `步骤N: 操作 [对象]` | 是 |
| 预期 | `expected_results` | 列表用换行符连接 | 是 |
| 关键词 | `design_method` | 映射为关键词标签 | 否 |
| 需求ID | `requirements` | 直接映射 | 否 |

### TestRail 导入字段映射

| TestRail字段 | 本系统字段 | 映射规则 | 必填 |
|-------------|-----------|---------|------|
| Title | `title` | 直接映射 | 是 |
| Section | `module` | 映射为 Section | 是 |
| Template | - | 固定为 "Test Case (Text)" | - |
| Type | `type` | 直接映射 | 否 |
| Priority | `priority` | P0→Critical, P1→High, P2→Medium, P3→Low | 是 |
| Preconditions | `preconditions` | 直接映射 | 否 |
| Steps | `steps` | 每条步骤单独一行，格式为 `Step N: action` | 是 |
| Expected Result | `expected_results` | 直接映射 | 是 |
| References | `requirements` | 直接映射 | 否 |

### Jira Xray 导入字段映射（JSON格式）

```json
{
  "tests": [
    {
      "testKey": "",
      "testType": "Manual",
      "fields": {
        "summary": "{title}",
        "description": "{preconditions}",
        "priority": {
          "name": "{priority映射值}"
        },
        "labels": ["{module}", "{design_method}"]
      },
      "steps": [
        {
          "action": "{step.action}",
          "data": "{step.data}",
          "result": "{expected_result}"
        }
      ]
    }
  ]
}
```

---

## 多语言输出规范

当测试团队需要中英双语用例时，遵循以下规范：

### 双语用例模板

```markdown
### TC-[PROJECT]-[MODULE]-[NNN]：[中文标题] / [English Title]

| 字段 | 中文 | English |
|------|------|---------|
| **用例编号** | TC-XXX | TC-XXX |
| **用例标题** | [中文标题] | [English Title] |
| **所属模块** | [中文模块名] | [English Module Name] |
| **优先级** | P0 / P1 / P2 / P3 | P0 / P1 / P2 / P3 |

**前置条件 / Preconditions**：
- [中文前置条件]
- [English preconditions]

**测试步骤 / Test Steps**：

| 步骤 | 操作描述 (CN) | Operation (EN) | 操作对象 |
|------|-------------|---------------|---------|
| 1 | [中文操作] | [English action] | [对象] |

**预期结果 / Expected Results**：
1. [中文预期结果] / [English expected result]
2. [中文预期结果] / [English expected result]
```

### 语言输出策略

| 场景 | 输出语言 | 说明 |
|------|---------|------|
| 国内团队内部使用 | 纯中文 | 默认策略 |
| 有海外团队参与 | 中英双语 | 用户明确指定时 |
| 外资企业/海外项目 | 纯英文 | 用户明确指定时 |
| 与海外供应商对接 | 中英双语 | 接口测试用例优先双语 |

