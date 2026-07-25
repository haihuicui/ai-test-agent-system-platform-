# API测试 AI助手 优化设计方案

> 版本: v1.0 | 日期: 2026-07-25 | 作者: AI测试团队
>
> 关联文档:
> - [api_agent 实现](../../backend/app/agents/api/agent.py)
> - [执行邀约中间件](../../backend/app/agents/api/execution_invitation_middleware.py)
> - [场景质量中间件](../../backend/app/agents/api/scenario_quality_middleware.py)
> - [断言分析器](../../backend/app/agents/tools/api/assertion_analyzer.py)
> - [成果物工具](../../backend/app/agents/tools/api/artifacts_tools.py)

---

## 1. 背景与问题诊断

### 1.1 当前架构回顾

```
用户输入 → LangGraph api_agent
              ├─ System Prompt (100+ 行, 20 条红线)
              ├─ Skills Middleware (6 个 skill, 按需加载)
              ├─ Context Middleware (注入 project_id 等)
              ├─ Quality Gate Middleware (场景预检)
              ├─ Execution Invitation Middleware (执行中断)
              └─ 30+ Tools (按域分类)
```

整体方向正确，核心设计理念（确定性骨架 + AI 填充、断言门禁、执行邀约）是合理的。

### 1.2 三个结构性问题

| 问题 | 症状 | 根因 |
|------|------|------|
| **Token 膨胀** | System prompt 100+ 行，20 条规则平铺，每条请求都发送 | 代码已强制执行的规则和 prompt-only 规则混在一起 |
| **流程刚性** | 所有端点走相同 10 步管道，简单 GET 也要走全流程 | 缺乏前置评估和路径分支 |
| **缺少反馈闭环** | 每次生成从零开始，不利用历史执行数据 | 无项目级 API 行为特征归纳机制 |

### 1.3 规则安全等级分析

对当前 20 条红线按「是否有代码兜底」逐条分类：

| 等级 | 数量 | 含义 | 示例 |
|------|------|------|------|
| 🟢 **代码强制** | 6 条 | 工具/中间件硬拦截，违反即被拒 | 断言门禁、执行邀约、场景质量、修复即更新 |
| 🟡 **部分强制** | 2 条 | 部分代码兜底，需保留关键提示 | 成果必存、假阳性检测 |
| 🔴 **纯 Prompt** | 12 条 | 无代码兜底，prompt 是唯一防线 | 禁硬编码、禁 fallback token、必须用骨架、最多重试 3 次 |

关键发现：**代码强制的 6 条规则占了 ~25 行，可以安全缩减**。但 🔴 级规则中的 4 条高危（禁硬编码、禁 fallback token、必须用骨架、修复不降断言）必须保留且表述更突出。

---

## 2. 设计目标与原则

### 2.1 目标

| 目标 | 衡量标准 |
|------|---------|
| 核心 prompt 缩减 60%+ | 从 ~100 行 → ~35 行 |
| 不必要的中断减少 80%+ | 纯 GET 查询自动执行 |
| 单次对话重复查询归零 | 端点信息缓存命中率 100% |
| **零功能退化** | 所有现有测试用例通过，生成质量不降 |

### 2.2 设计原则

1. **代码兜底优先** — 能用代码强制的不靠 prompt，代码是最可靠的约束
2. **按安全等级分层** — 高危规则必须保留，已强制规则可缩减，参考规范按需加载
3. **渐进式交付** — Phase 1 先做无风险的（prompt 重构、缓存），Phase 2 做流程变更
4. **可回滚** — 每一步改动独立可回滚，不影响其他模块

---

## 3. 方案一：Prompt 三层瘦身模型

### 3.1 架构

```
用户请求
    │
    ▼
┌──────────────────────────────────────────┐
│ Layer 0: 代码强制（不占 prompt 篇幅）      │
│                                          │
│ ┌──────────────────────────────────────┐ │
│ │ 规则 4: 断言门禁                      │ │
│ │   → save_test_script 硬拦            │ │
│ │   → audit_script_assertions 预检     │ │
│ │ 规则 7: 修复即更新                    │ │
│ │   → save_test_script 按 ID 匹配      │ │
│ │ 规则 12: 执行邀约                     │ │
│ │   → ExecutionInvitationMiddleware   │ │
│ │ 规则 16-18: 场景质量                  │ │
│ │   → ScenarioQualityGateMiddleware    │ │
│ └──────────────────────────────────────┘ │
│ prompt 缩减为: "工具内置门禁会自动拦截"    │
└──────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────┐
│ Layer 1: 核心 Prompt（始终加载, ~35 行）   │
│                                          │
│ - 角色定义 + 核心能力                     │
│ - 工作流骨架（3 条路径）                   │
│ - 🔴 5 条高危红线                         │
│   · 禁硬编码 URL/token/业务值              │
│   · 禁 fallback token (AUTH_TOKEN||'xx')  │
│   · 必须用 derive_test_skeleton           │
│   · 修复不降断言（400/401 不得改 200）     │
│   · 同一操作最多重试 3 次                  │
│ - 通用约束（环境选择/上下文参数）           │
└──────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────┐
│ Layer 2: 阶段规则（Middleware 按 mode 注入）│
│                                          │
│ template_type="api_test" 时注入:          │
│   - 单端点工作流细节                       │
│   - 假阳性检测流程（规则 15）              │
│   - 批量操作须知                          │
│                                          │
│ template_type="scenario_test" 时注入:      │
│   - 场景工作流细节                        │
│   - 一步一场景（规则 11）                  │
│   - 场景模板变量规范（规则 20）            │
└──────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────┐
│ Layer 3: Skills 参考规范（按需加载）       │
│                                          │
│ /skills/api/generator/SKILL.md           │
│   - 代码模板、断言规范、禁止模式           │
│ /skills/api/healer/SKILL.md              │
│   - 失败诊断流程、修复策略                 │
│ /skills/api/scenario/SKILL.md            │
│   - 场景编排最佳实践                      │
│ /skills/api/planner/SKILL.md             │
│   - 测试策略模板                          │
│ /skills/api/executor/SKILL.md            │
│   - 执行策略、结果分析                    │
│ /skills/api/reporter/SKILL.md            │
│   - 报告生成规范                          │
└──────────────────────────────────────────┘
```

### 3.2 改动点: `agent.py`

#### 3.2.1 瘦身后的 SYSTEM_PROMPT

```python
SYSTEM_PROMPT = """# API 自动化测试专家

你是资深 API 自动化测试专家，负责 REST API 测试的全生命周期管理。优先选择合适的 Skills 完成任务。

## 🔄 工作流主干

**快速判断路径（收到请求后第一步）：**
- 用户提供了 Script ID → 直接 `execute_api_script_by_artifact_id`，不重新生成
- 新端点 → 完整生成路径（获取信息 → 骨架 → 计划 → 用例 → 脚本 → 邀约 → 执行）
- 修复失败 → 参考 healer skill → `save_test_script` 更新 → `run_tests` 复验

**单端点标准流程：**
1. `get_endpoint_details` 获取接口完整信息（method/path/parameters/request_body/responses）
2. `get_project_environments` 获取环境（按 `environment_id` 或默认环境）
3. `derive_test_skeleton` → 生成计划 → `save_test_plan`
4. 填充用例 → `save_test_cases`
5. `get_response_schema` → 生成脚本 → `audit_script_assertions` → `save_test_script`
6. ⚠️ 输出执行邀约标记（系统将弹出确认面板，收到用户决策后方可执行）

**场景测试完整流程：**
1. `create_test_scenario` → 逐步骤添加（每个步骤调 `get_endpoint_details` 读取 schema）
2. 配置路径参数闭环映射（extractor → `{{variable}}` 引用）
3. 创建类步骤提取资源 ID → 配 teardown
4. `validate_scenario_design` 预检 → 输出执行邀约 → `execute_scenario`
5. 自动修复，最多 3 次；仍失败则报告原因

## ⛔ 核心红线（必须遵守）

1. **禁硬编码**：脚本禁止出现域名/URL/token/业务唯一值（customerName/phone/email/orderNo），一律 `process.env.API_BASE_URL` / `process.env.AUTH_TOKEN`，动态值用 `Date.now()` / `uuid` / `faker` 或 `{{$uuid}}` / `{{$timestamp}}`
2. **禁 fallback token**：`process.env.AUTH_TOKEN || 'test'` **严格禁止**，必须 `process.env.AUTH_TOKEN!`
3. **必须用骨架**：生成用例前必须调用 `derive_test_skeleton`，不得纯自由发挥
4. **修复不降断言**：缺必填参数返回 200、无效 token 返回 200 属 API/安全缺陷，保留 400/401/403 预期，不得改成 `toBe(200)`；token 失效是环境问题，检查 `token_url`/`token_body` 配置而非改脚本
5. **重试上限**：同一操作失败 ≥3 次必须切换策略或向用户报告，禁止无限重试
6. **必传 execution_config**：`execute_api_script` 必须传 `env_id`（后端自动解析 base_url 并注入 AUTH_TOKEN），`reporter` 用 `html`
7. **假阳性必检**：执行后检查 `trace_entries` 中的 `responseBody.code`/`responseBody.success`——HTTP 200 + 业务失败码 = 假阳性，必须向用户报告为失败

## 📖 工具门禁（系统自动执行，违反会被拒绝）

以下规则由工具代码强制执行，你只需按流程调用即可：
- `save_test_script` 内置断言质量门禁（FAIL/WEAK 硬拒），保存前先 `audit_script_assertions` 预检
- 执行邀约由系统中间件自动触发，你只需在保存脚本/场景后输出 `<EXECUTION_INVITATION>` 标记
- 场景质量由 `ScenarioQualityGateMiddleware` 在 `execute_scenario` 前自动预检
- `save_test_script` 按 `endpoint_id` 自动更新已有记录，不会重复创建

## 🌐 环境与上下文

- `project_identifier`、`folder_id`、`environment_id` 已由系统注入（见下方运行时上下文），不要询问用户
- 未提供 `environment_id` 时，调用 `get_project_environments` 选 `is_default=true` 的默认环境
- 项目无环境时脚本用环境变量占位，执行时会明确报错提示配置环境

## 📖 Skills 知识库（按需加载）

| Skill | 触发场景 |
|-------|---------|
| planner | 生成测试计划 |
| generator | 生成代码、编写断言 |
| scenario | 场景设计、数据依赖 |
| executor | 执行脚本、分析结果 |
| healer | 诊断失败、修复脚本 |
| reporter | 生成测试报告 |

**记住**：获取信息先用工具；成果必存；执行邀约是必经步骤；代码门禁是你的安全网。
"""
```

#### 3.2.2 阶段规则注入

在 `APIContextInjectionMiddleware` 中增加按 `template_type` 注入阶段规则的逻辑：

```python
# backend/app/agents/api/agent.py — 修改 APIContextInjectionMiddleware.awrap_model_call

_STAGE_RULES = {
    "api_test": """
## 🔧 单端点模式补充规则

**执行后必做：** `execute_api_script` 返回的 `trace_entries` 中检查每个正向用例的 `responseBody.code` 或 `responseBody.success`：
- 成功值（0/"0"/200/"success"/true）→ ✅ 真实通过
- 错误值（"4001"/"4009"/"5000" 等非成功值）→ ❌ 假阳性
严禁在业务失败时报告"全部通过"。

**批量操作：** `batch_generate_tests` 搭配 `batch_run_tests`；确认前说明端点数与预估影响。
""",
    "scenario_test": """
## 🔧 场景模式补充规则

**一次对话一个场景：** 同对话再次 `create_test_scenario` 自动覆盖旧场景，除非用户明确要求。

**模板变量规范：** 统一使用 `{{$timestamp}}` / `{{$uuid}}` / `{{$faker.name}}` / `{{variableName}}`，括号与变量名之间不加空格。

**步骤质量要求：**
- 每个步骤至少 1 个 status 断言 + 1 个 jsonpath/header 业务断言
- URL 中 `{xxx}` 必须在前序步骤用 `add_step_extractor` 提取，用 `{{xxx}}` 引用
- 创建类步骤必须提取资源 ID + 配置 teardown
- 分页/列表步骤必须断言 records/list 非空、total 为数字
""",
}


class APIContextInjectionMiddleware(AgentMiddleware):

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        project_identifier = request.runtime.context.project_identifier
        folder_id = request.runtime.context.folder_id
        environment_id = request.runtime.context.environment_id
        template_type = request.runtime.context.template_type  # 新增: 读取模式

        # ... 原有的 conversation_id 逻辑 ...

        context_info = f"""

---
## 🎯 运行时上下文

- `project_identifier`: `{project_identifier}`
- `folder_id`: `{folder_id}`
- `environment_id`: `{environment_id}`
- `conversation_id`: `{conversation_id}`

环境选择：`environment_id` 已提供则优先使用；否则选默认环境；无环境则脚本用占位变量。
会话去重：同 conversation_id 内同一端点只保留一份最终报告。
---
"""
        # 注入阶段规则
        stage_rule = _STAGE_RULES.get(template_type, "")
        if stage_rule:
            context_info += stage_rule

        if isinstance(request.system_message.content, list):
            request.system_message.content = request.system_message.content + [
                {"type": "text", "text": context_info}
            ]
        else:
            request.system_message.content = request.system_message.content + context_info

        return await handler(request)
```

### 3.3 改动点: Skills 文件

当前 6 个 skill 文件在 `.claude/skills/api/` 下，agent 通过 SkillsMiddleware 按需加载。需要将 prompt 中原有的详细规范迁移到对应 skill。

#### generator/SKILL.md 优化

将 prompt 中的断言规范、代码模板、禁止模式迁移至此：

```markdown
# API 测试脚本生成规范

## 断言规则

### 硬性要求
- 每个用例 ≥1 个状态码断言 + ≥2 个有效业务断言
- 禁止纯状态码断言（会被 save_test_script 门禁拒绝）
- 以下断言不计入有效数：
  - `toBeTruthy()` / `toBeFalsy()` — 过于宽泛
  - `toBeDefined()` / `toBeUndefined()` 对裸变量使用 — 无实际意义
  - `toBeInstanceOf(Object)` 无参数 — 几乎永远通过
  - `if (x !== undefined) expect(x)` 条件断言 — 字段缺失时会跳过

### 推荐断言模式
1. **字段存在性**: `expect(body.data).toHaveProperty('id')`
2. **类型断言**: `expect(typeof body.data.id).toBe('number')`
3. **枚举断言**: `expect(['pending','paid']).toContain(body.data.status)`
4. **契约校验**: `validateSchema(body, SCHEMA)` — 一次覆盖所有字段/类型/必填/枚举
5. **错误断言**: `expect(body.message).toContain('参数')`

### 字段名来源
必须从 `get_endpoint_details` 和 `get_response_schema` 返回的 schema 中提取，禁止臆测。

## 代码模板

### 环境变量
```typescript
const API_BASE_URL = process.env.API_BASE_URL!;
const AUTH_TOKEN = process.env.AUTH_TOKEN!;  // 禁止 || 'fallback'
```

### 动态值
```typescript
const uniqueName = `test_${Date.now()}`;
const uniqueId = crypto.randomUUID();
```

## 禁止模式
- ❌ 硬编码 URL: `https://api.example.com/v1/users`
- ❌ 硬编码 token: `Bearer eyJhbGciOi...`
- ❌ fallback token: `process.env.AUTH_TOKEN || 'test-token'`
- ❌ 条件断言: `if (x !== undefined) { expect(x).toBe(...) }`
- ❌ 臆测字段名: 无 schema 依据直接写 `expect(body.data.userName)`
```

#### healer/SKILL.md 优化

```markdown
# API 测试修复规范

## 诊断流程
1. 读取 `parse_test_results` 输出，定位失败用例
2. 分类失败类型：
   - 连接/超时: 检查 base_url / 网络
   - 认证失败 (401/403): 检查 token 配置，NOT 脚本
   - 业务断言失败: 检查预期值与实际响应
   - 数据冲突: 唯一字段重复 → 改用动态值

## 修复红线（绝对不改）
- ❌ 把 400/401/403 预期改成 200
- ❌ 放宽/删除核心业务断言
- ❌ 在脚本中硬编码 token
- ❌ 把必填参数去掉来"绕过"校验错误

## 修复策略
1. 数据冲突 → `Date.now()` / `uuid` / `faker`
2. 断言预期值错误 → 对齐实际响应格式
3. 环境配置问题 → 提示用户检查环境，不改脚本
4. 超时 → 增加 `timeout` 配置
```

---

## 4. 方案二：执行邀约分级

### 4.1 当前问题

[execution_invitation_middleware.py](backend/app/agents/api/execution_invitation_middleware.py) 对所有场景一刀切——单端点 2 个 GET 用例也中断，批量 50 个 POST 也中断。没有区分风险等级。

### 4.2 设计

```python
# 新增: backend/app/agents/api/execution_risk.py

from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"        # 自动执行，事后通知
    MEDIUM = "medium"  # 软提示，可一键跳过
    HIGH = "high"      # 强制中断确认（当前行为）


@dataclass
class ExecutionContext:
    mode: str           # "api" | "scenario" | "batch"
    endpoint_count: int
    test_count: int
    has_write_ops: bool  # 是否包含 POST/PUT/PATCH/DELETE
    has_delete_ops: bool # 是否包含 DELETE（更高风险）


def evaluate_risk(ctx: ExecutionContext) -> tuple[RiskLevel, str]:
    """评估执行风险等级。"""

    if ctx.mode == "scenario":
        return RiskLevel.HIGH, "场景测试涉及多步骤数据依赖和副作用"

    if ctx.mode == "batch":
        if ctx.endpoint_count > 10:
            return RiskLevel.HIGH, f"批量执行 {ctx.endpoint_count} 个端点，影响面较大"
        if ctx.has_write_ops and ctx.endpoint_count > 3:
            return RiskLevel.HIGH, f"批量执行包含 {ctx.endpoint_count} 个写操作端点"
        if ctx.has_write_ops:
            return RiskLevel.MEDIUM, f"批量执行包含写操作"
        if ctx.endpoint_count <= 10:
            return RiskLevel.LOW, f"批量执行 {ctx.endpoint_count} 个只读端点"

    if ctx.mode == "api":
        if ctx.has_delete_ops:
            return RiskLevel.HIGH, "包含 DELETE 操作，可能造成数据丢失"
        if ctx.has_write_ops:
            if ctx.test_count > 5:
                return RiskLevel.MEDIUM, f"包含写操作的 {ctx.test_count} 个用例"
            return RiskLevel.MEDIUM, "包含写操作"
        # 纯 GET/HEAD 只读
        if ctx.test_count <= 5:
            return RiskLevel.LOW, "纯查询操作，低风险"
        return RiskLevel.MEDIUM, f"{ctx.test_count} 个只读用例"

    return RiskLevel.HIGH, "默认需确认"


def is_auto_executable(ctx: ExecutionContext) -> bool:
    """判断是否可以自动执行。"""
    level, _ = evaluate_risk(ctx)
    return level == RiskLevel.LOW
```

### 4.3 风险信息提取

在执行邀约中间件中，解析 `<EXECUTION_INVITATION>` 标记的 payload 时提取风险上下文：

```python
# execution_invitation_middleware.py 修改

def _extract_risk_context(payload: dict) -> ExecutionContext:
    """从邀约 payload 中提取风险评估所需信息。"""
    return ExecutionContext(
        mode=payload.get("mode", "api"),
        endpoint_count=payload.get("endpoint_count", 1),
        test_count=payload.get("test_count", 0),
        has_write_ops=payload.get("has_write_ops", False),
        has_delete_ops=payload.get("has_delete_ops", False),
    )
```

### 4.4 前端配合

在 [ChatInterface.tsx](ui/components/langgraph/ChatInterface.tsx) 的 `ExecutionInvitationInterrupt` 组件中，根据风险等级调整 UI：

- `LOW`：不弹窗，静默自动执行，在消息流中展示一条 "自动执行中..." 通知
- `MEDIUM`：弹出简化面板（仅 [立即执行] [暂不执行]），3 秒后可一键关闭
- `HIGH`：完整面板（当前行为）

同时在 ChatInterface 底部增加 **"自动执行"** 开关，与已有的 `autoApproveEnabled` 同一位置：

```tsx
// 在 ChatInterface.tsx 中新增
const [autoExecuteEnabled, setAutoExecuteEnabled] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem("chat_auto_execute_enabled") === "true";
});

// 开关 UI（紧邻 autoApprove 开关）
<Label htmlFor="auto-execute-switch">自动执行</Label>
<Switch
    id="auto-execute-switch"
    checked={autoExecuteEnabled}
    onCheckedChange={setAutoExecuteEnabled}
    disabled={isLoading}
/>
```

> **注意**：`autoExecuteEnabled` 只影响 LOW 和 MEDIUM 风险场景。HIGH 风险场景（场景测试、批量 >10 端点、DELETE 操作）始终强制确认，不受此开关影响。

### 4.5 Agent prompt 中的变更

在 system prompt 的执行邀约标记示例中增加风险字段：

```
<EXECUTION_INVITATION>
{"type":"execution_invitation","mode":"api","endpoint_id":"<ID>",
 "script_name":"<文件名>","test_count":<N>,
 "has_write_ops":true,"has_delete_ops":false,"endpoint_count":1,
 "description":"...","alternatives":[...]}
</EXECUTION_INVITATION>
```

---

## 5. 方案三：对话内端点缓存

### 5.1 设计

利用已有的 `conversation_id_ctx`（contextvar），在工具调用层加一个会话级缓存：

```python
# 新增: backend/app/agents/tools/api/_cache.py

import time
import logging
from typing import Any, Callable, Awaitable

from app.agents.api.runtime_context import get_conversation_id

logger = logging.getLogger(__name__)

# 会话级缓存: key → (expires_at, value)
_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 300  # 5 分钟


def _cache_key(conversation_id: str, tool_name: str, *args, **kwargs) -> str:
    """生成缓存 key。只对确定性读操作缓存。"""
    return f"{conversation_id}:{tool_name}:{args}:{sorted(kwargs.items())}"


def cached_read(tool_name: str):
    """装饰器：对读操作做会话级缓存。

    只用于无副作用的读工具：get_endpoint_details, get_response_schema,
    get_project_environments, get_environment_details 等。
    """

    def decorator(func: Callable[..., Awaitable[Any]]):
        async def wrapper(*args, **kwargs):
            conv_id = get_conversation_id()
            if not conv_id:
                # 无 conversation_id 时不做缓存（如批量接口调用）
                return await func(*args, **kwargs)

            key = _cache_key(conv_id, tool_name, *args, **kwargs)
            now = time.time()

            if key in _cache:
                expires, val = _cache[key]
                if now < expires:
                    logger.debug("Cache hit: %s", tool_name)
                    return val
                del _cache[key]

            result = await func(*args, **kwargs)
            _cache[key] = (now + _CACHE_TTL, result)
            logger.debug("Cache set: %s (size=%d)", tool_name, len(_cache))
            return result

        return wrapper

    return decorator


def clear_conversation_cache(conversation_id: str) -> int:
    """清除指定会话的所有缓存（对话结束时调用）。"""
    prefix = f"{conversation_id}:"
    keys = [k for k in _cache if k.startswith(prefix)]
    for k in keys:
        del _cache[k]
    return len(keys)
```

### 5.2 适用范围

只为**确定性读操作**加缓存。写操作（save_*、execute_*、delete_*）不做缓存。

| 工具 | 缓存 | 理由 |
|------|------|------|
| `get_endpoint_details` | ✅ | 端点信息在对话内不变 |
| `get_multiple_endpoints_details` | ✅ | 同上 |
| `get_response_schema` | ✅ | 同上 |
| `get_project_environments` | ✅ | 环境配置在对话内不变 |
| `get_environment_details` | ✅ | 同上 |
| `get_endpoint_artifacts` | ⚠️ | TTL 缩短为 60s（可能刚保存了成果物） |
| `save_test_plan` / `save_test_cases` / `save_test_script` | ❌ | 写操作，每次执行 |
| `execute_api_script` | ❌ | 写操作，每次执行 |
| `derive_test_skeleton` | ✅ | 确定性的，输入相同输出相同 |

### 5.3 集成方式

在工具定义处加装饰器：

```python
# backend/app/agents/tools/api/openapi_tools.py

from app.agents.tools.api._cache import cached_read

@tool
@cached_read("get_endpoint_details")  # 新增
async def get_endpoint_details(endpoint_id: str) -> str:
    ...
```

### 5.4 缓存清理

- 对话结束时清理（在 agent 生命周期钩子中调用 `clear_conversation_cache`）
- TTL 自动过期（300s，够覆盖一次完整对话）
- 写操作（save_*）不清缓存—因为端点信息在对话内确实不变

---

## 6. 方案四：智能路由（Phase 2，可选）

### 6.1 设计

在 system prompt 中增加「前置评估」步骤，让 agent 在开始生成前先检查已有成果物：

```
## 前置评估（收到请求后第一步）

1. 若有 endpoint_id：
   - 调用 get_endpoint_artifacts(endpoint_id) 查看已有成果物
   - 有计划+用例+脚本 → 询问用户：执行 / 修复 / 重新生成？
   - 只有部分成果物 → 从缺失步骤继续
   - 无成果物 → 走完整生成路径

2. 若为纯 GET + 无参数 + 无 requestBody：
   - 快速路径：get_endpoint_details → get_response_schema → 生成脚本 → 保存 → 邀约
   - 跳过骨架（不需要复杂用例），生成 2-3 个精简用例

3. 告知用户选择的原因和路径
```

### 6.2 效果

| 场景 | 当前步骤数 | 优化后步骤数 | 节省 |
|------|-----------|-------------|------|
| 全新 POST 端点 | 10 | 10 | 0% |
| 已有成果物的端点（执行） | 10 | 1 | **90%** |
| 纯 GET 无参数端点 | 10 | 5 | **50%** |

---

## 7. 代码改动清单

### 7.1 Phase 1（必做）

| 文件 | 改动 | 行数 | 风险 |
|------|------|------|------|
| `backend/app/agents/api/agent.py` | 替换 SYSTEM_PROMPT + APIContextInjectionMiddleware 注入阶段规则 | ~80 行改 ~45 行 | 低 |
| `backend/app/agents/api/execution_risk.py` | **新增**: 风险评估模块 | ~60 行 | 无（新文件） |
| `backend/app/agents/api/execution_invitation_middleware.py` | 集成风险评估，修改 `_parse_execution_invitation` 提取上下文 | ~20 行改 | 低 |
| `backend/app/agents/tools/api/_cache.py` | **新增**: 会话缓存模块 | ~55 行 | 无（新文件） |
| `backend/app/agents/tools/api/openapi_tools.py` | 给读操作加 `@cached_read` | ~5 行 | 极低 |
| `backend/app/agents/tools/api/schema_tools.py` | 给 `get_response_schema` 加 `@cached_read` | ~2 行 | 极低 |
| `backend/app/agents/tools/api/environment_tools.py` | 给读操作加 `@cached_read` | ~3 行 | 极低 |
| `ui/components/langgraph/ChatInterface.tsx` | 增加「自动执行」开关 | ~20 行 | 低 |
| `ui/components/langgraph/ExecutionInvitationInterrupt.tsx` | 按风险等级差异化 UI | ~30 行 | 中 |
| `.claude/skills/api/generator/SKILL.md` | 迁移代码规范、断言规范、禁止模式 | ~80 行改 | 低 |
| `.claude/skills/api/healer/SKILL.md` | 迁移修复红线 | ~40 行改 | 低 |

### 7.2 Phase 2（可选）

| 文件 | 改动 | 行数 |
|------|------|------|
| `backend/app/agents/api/agent.py` | SYSTEM_PROMPT 增加「前置评估」步骤 | ~15 行 |
| `backend/app/agents/tools/api/artifacts_tools.py` | `save_test_script` 渐进式门禁（Stage 1 软门禁） | ~30 行 |
| `ui/lib/langgraph/config.ts` | 新增 `autoExecuteEnabled` 配置持久化 | ~10 行 |

---

## 8. 测试策略

### 8.1 回归测试

| 测试项 | 方法 | 预期 |
|--------|------|------|
| 瘦身 prompt 后单端点生成 | 对 5 个不同复杂度的端点触发完整生成流程 | 生成质量不低于当前，断言门禁通过率相同 |
| 瘦身 prompt 后场景生成 | 触发 3 个场景测试（CRUD/分页/审批） | 场景能正常编排并执行 |
| 断言门禁仍有效 | 故意生成纯状态码断言脚本 → `save_test_script` | 被拒绝，返回 FAIL/WEAK |
| 执行邀约仍触发 | 脚本保存后检查是否输出 `<EXECUTION_INVITATION>` | 正常触发 |
| 风险分级 | 分别模拟 LOW/MEDIUM/HIGH 场景 | 分级正确 |

### 8.2 性能测试

| 指标 | 方法 | 目标 |
|------|------|------|
| Prompt token 数 | 对比瘦身前后的 system prompt 字符数 | 减少 50%+ |
| 对话内重复查询 | 同对话中两次调用 `get_endpoint_details` 同一端点 | 第二次命中缓存，无 DB 查询 |
| 生成延迟 | 完整单端点生成耗时（端到端） | 不劣于当前（缓存补偿 prompt 缩减） |

### 8.3 手工验收

使用项目中的 [test_api_agent_prompt_quality.py](../../backend/tests/test_api_agent_prompt_quality.py) 测试套件。

---

## 9. 风险与回滚

### 9.1 风险矩阵

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 瘦身 prompt 后 LLM 忘记关键规则 | 低 | 高 | 5 条高危规则保留在核心 prompt 中；代码强制的规则有兜底 |
| 缓存返回过期数据 | 低 | 中 | TTL=300s，对话结束时清理 |
| 自动执行误操作（删除类） | 极低 | 严重 | DELETE 操作始终 HIGH 风险，强制确认 |
| 风险评估不准确 | 中 | 低 | 默认偏向安全（不确定 → HIGH） |

### 9.2 回滚方案

每项改动独立可回滚：

- **Prompt 瘦身**：还原 `agent.py` 中的 `SYSTEM_PROMPT` 字符串即可
- **阶段规则注入**：删除 `_STAGE_RULES` 字典和注入代码，恢复原来的一体化 prompt
- **缓存**：删除 `_cache.py` 文件和工具上的 `@cached_read` 装饰器
- **风险评估**：设置所有场景返回 `RiskLevel.HIGH` 即恢复当前行为
- **前端自动执行开关**：默认关闭，用户不感知

---

## 10. 实施计划

| 阶段 | 内容 | 预估工时 | 验收标准 |
|------|------|---------|---------|
| **P1-1** | Prompt 三层瘦身 + Skills 文件更新 | 1d | 测试套件通过，token 缩减 50%+ |
| **P1-2** | 对话内端点缓存 | 0.5d | 重复查询命中缓存 |
| **P1-3** | 执行邀约分级（后端评估 + 前端开关） | 1d | LOW/MEDIUM/HIGH 分级正确 |
| **P1-4** | 集成测试 + 手工验收 | 0.5d | 现有用例全部通过 |
| **P2-1** | 智能路由「前置评估」 | 1d | GET 端点走快速路径 |
| **P2-2** | 渐进式门禁 | 0.5d | Stage 1 WEAK 不阻塞 |
| **P2-3** | 前端差异化 UI（按风险等级） | 0.5d | LOW 不弹窗，HIGH 完整面板 |

**总计 Phase 1**: 3 个工作日
**总计 Phase 2**: 2 个工作日

---

## 附录 A: 瘦身前后的 Prompt 对比

### 瘦身前（当前，~100 行核心内容）

20 条红线全部内联，4 种工作流展开描述，工具速查表完整嵌入。

### 瘦身后（~35 行核心 + ~12 行阶段规则）

核心只保留角色定义、工作流骨架、7 条高危规则、工具门禁须知、Skills 速查表。

详细对比见 **3.2.1** 节。

---

## 附录 B: 关键决策记录

| 决策 | 结论 | 理由 |
|------|------|------|
| 是否移除"假阳性检测"规则 | **保留** | 无代码兜底，是唯一防止 AI 误报"全部通过"的防线 |
| 是否缓存 `get_endpoint_artifacts` | **缓存但 TTL=60s** | 可能刚保存了成果物，需要更快刷新 |
| 是否在工具内部集成缓存而非装饰器 | **装饰器** | 改动最小，不侵入工具逻辑 |
| LOW 风险是否自动执行 | **需要用户可配置的开关** | 不同用户对"自动"的容忍度不同 |
| 阶段规则注入用 middleware 还是 runtime context | **middleware** | 已有 APIContextInjectionMiddleware，拓展即可 |
