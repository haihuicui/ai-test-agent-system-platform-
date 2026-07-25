# Web 测试 AI 助手 — 详细优化方案

> **作者**: 资深测试开发工程师视角
> **日期**: 2026-07-25
> **版本**: v1.0
> **状态**: 草案

---

## 目录

1. [现状分析](#1-现状分析)
2. [优化总览](#2-优化总览)
3. [P0 — 快速见效（本周可交付）](#3-p0--快速见效本周可交付)
4. [P1 — 结构优化（本月可交付）](#4-p1--结构优化本月可交付)
5. [P2 — 能力升级（本季度可交付）](#5-p2--能力升级本季度可交付)
6. [P3 — 架构演进（下季度规划）](#6-p3--架构演进下季度规划)
7. [实施路线图](#7-实施路线图)
8. [成功度量](#8-成功度量)
9. [风险与应对](#9-风险与应对)

---

## 1. 现状分析

### 1.1 架构总览

```
┌──────────────────────────────────────────────────────────┐
│                     前端 UI 层                             │
│  AIChatContainer → ChatProvider → ChatInterface          │
│  AIGenerateDialog / CreateWebFunctionDialog               │
│  EnhancedTestArtifactsPanel                               │
└──────────────────────┬───────────────────────────────────┘
                       │ LangGraph SDK (HTTP)
┌──────────────────────▼───────────────────────────────────┐
│                    Agent 层 (web_agent)                     │
│  ┌──────────────────────────────────────────────────┐    │
│  │  SYSTEM_PROMPT (273行)                            │    │
│  │  ├── 工作流定义 (4 种模式)                        │    │
│  │  ├── 硬性规则 (8 条)                              │    │
│  │  ├── Skill 路由表                                 │    │
│  │  └── 协作要求                                     │    │
│  ├──────────────────────────────────────────────────┤    │
│  │  Middleware:                                       │    │
│  │  ├── SkillsMiddleware (Skills 按需加载)           │    │
│  │  ├── WebContextInjectionMiddleware (运行时注入)     │    │
│  │  ├── WebIntentConfirmationMiddleware (人机交互)    │    │
│  │  └── WebExecutionInvitationMiddleware (人机交互)   │    │
│  ├──────────────────────────────────────────────────┤    │
│  │  Tools (工具层):                                   │    │
│  │  ├── 本地工具 (16个):                             │    │
│  │  │   ├── 功能管理: list/create/get functions      │    │
│  │  │   ├── 成果物管理: save/get test plan/cases/     │    │
│  │  │   │   script/report                            │    │
│  │  │   ├── 脚本管理: download/delete scripts        │    │
│  │  │   └── 执行: execute_web_script                 │    │
│  │  └── MCP 工具 (Playwright):                       │    │
│  │      ├── browser_* (30+ 浏览器操作)               │    │
│  │      ├── planner_* (测试计划)                     │    │
│  │      └── generator_* / test_*                     │    │
│  └──────────────────────────────────────────────────┘    │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│                    基础设施层                               │
│  ├── Playwright MCP Server (浏览器自动化)                  │
│  ├── MinIO (成果物存储)                                    │
│  ├── PostgreSQL (WebFunction/WebTestRun/WebTestResult)     │
│  └── workspace (测试脚本执行目录)                           │
└──────────────────────────────────────────────────────────┘
```

### 1.2 痛点识别

以下痛点按影响程度从高到低排列：

| # | 痛点 | 影响 | 当前表现 |
|---|------|------|----------|
| 1 | **Agent 指令遵循度不稳定** | LLM 忽略关键规则 | 系统提示词 273 行，存在 lost-in-the-middle 效应；model 偶尔跳过 `save_web_test_plan` 或 `save_web_test_report` 等强制步骤 |
| 2 | **healer 修复效率低** | 同类错误反复诊断 | 每次失败从零开始，无经验复用；相同 testIdAttribute / 定位器过期问题重复分析 |
| 3 | **脚本质量无门禁** | 废脚本流入执行阶段 | 只有 `--list` 校验语法，不检查反模式（硬编码等待、废弃 API 等）；结构校验 `_validate_test_cases` 只看 JSON 字段有无，不看内容质量 |
| 4 | **执行缺乏智能调度** | 全量重跑浪费时间 | 每次执行全部用例，无增量执行、无变更感知、无失败优先排序 |
| 5 | **整块系统提示词** | 维护成本高、模型注意力分散 | 所有工作流规则平铺在单一 prompt，每次对话全部注入，浪费 token 且稀释关键信息密度 |
| 6 | **成本不可见** | 无法发现效率问题 | 无 token 消耗追踪，无法区分"正常探索"与"Agent 跑偏" |
| 7 | **测试结果缺乏趋势分析** | 报告价值仅限于单次 | 不与历史对比，无法自动发现回归、劣化、flaky |
| 8 | **MCP 故障无早期检测** | 后续操作连锁失败 | session 断裂后 browser_* 工具全部不可用，Agent 仍盲目调用直至超时 |

---

## 2. 优化总览

```
P0 (本周)          P1 (本月)            P2 (本季度)           P3 (下季度)
───────           ────────             ──────────            ──────────
┌──────────┐     ┌──────────┐        ┌──────────┐          ┌──────────┐
│ healer   │     │ 系统提示词│        │ 执行调度 │          │ 多Agent  │
│ 经验复用 │     │ 分层瘦身 │        │ 智能化   │          │ 架构     │
├──────────┤     ├──────────┤        ├──────────┤          ├──────────┤
│ 脚本质量 │     │ 执行报告 │        │ 失败知识 │          │ 模型微调 │
│ 门禁     │     │ 趋势对比 │        │ 图谱     │          │ 或 RL    │
├──────────┤     ├──────────┤        ├──────────┤          ├──────────┤
│ 执行报告 │     │ MCP健康  │        │ Token    │          │ 自愈闭环 │
│ 展示优化 │     │ 检查     │        │ 可观测性 │          │ (无LLM)  │
└──────────┘     └──────────┘        └──────────┘          └──────────┘
```

---

## 3. P0 — 快速见效（本周可交付）

### 3.1 Healer 经验复用机制

#### 问题
当前 healer 每次失败从零诊断。同类型错误（如 `testIdAttribute` 不匹配、定位器基于过期快照）每周可能出现数十次，每次都走完整诊断流程（`test_debug` → `browser_snapshot` → `browser_generate_locator` → `edit` → `execute`），平均消耗 8-12K tokens/次。

#### 方案

**3.1.1 在 healer SKILL.md 顶部增加经验库表格**

在 [healer SKILL.md](.claude/skills/web_mcp/healer/SKILL.md) 第 1 行（`---` frontmatter 之后）插入：

```markdown
## 📚 修复经验库（优先查阅 — Before Any Diagnostic Step）

> ⚠️ **强制规则**：在调用 `test_debug` 或 `browser_*` 之前，**必须**先检查以下经验库。
> 如果错误信息与经验库中的签名匹配，**直接应用修复策略**，跳过诊断步骤。

| # | 错误签名 (Error Signature) | 根因 | 修复策略 | 置信度 |
|---|---------------------------|------|----------|--------|
| 1 | `getByTestId('X') resolved to 0 elements` + 页面快照中有 `data-test="X"` | testIdAttribute 配置为默认 `data-testid`，但应用使用 `data-test` | 在 spec 顶部添加 `test.use({ testIdAttribute: 'data-test' })` | 95% |
| 2 | `getByTestId('X') resolved to 0 elements` + 页面快照中有 `data-cy="X"` | 同上，应用使用 `data-cy` | 在 spec 顶部添加 `test.use({ testIdAttribute: 'data-cy' })` | 95% |
| 3 | `Timeout waiting for selector` + stderr 显示页面有 loading spinner | 页面异步加载未完成 | 在导航后添加 `await page.waitForLoadState('networkidle')` | 85% |
| 4 | `Element is not attached to the DOM` + 操作前已 query 元素 | SPA 框架在操作间重渲染 | 将元素 query 移到操作前一行；或使用 locator-based 而非 element handle | 80% |
| 5 | `Error: expect(locator).toBeVisible()` 失败 + 页面快照中有该元素 | CSS 动画/过渡未完成 | 在断言前添加 `await expect(locator).toBeVisible({ timeout: 10000 })` | 75% |
| 6 | `Error: browser_*` 所有工具返回 "Must setup test before" | planner_setup_page 未调用或 session 过期 | 调用 `planner_setup_page(project="chromium")` | 99% |
| 7 | `auth_browser_initialize_plugin` 或类似 MCP 初始化错误 | MCP server session 断开 | **不要重试**；提示用户刷新页面重新连接 | 99% |

> **每次成功修复后**：在此表格末尾追加新条目。相同签名的后续修复会直接命中经验库。

**使用流程：**
```
1. 收到 execution_result，提取 error_message
2. 遍历经验库的 Error Signature 列，做子串/正则匹配
3. 命中 → 直接应用修复策略，跳过 test_debug + browser_* 诊断
4. 未命中 → 走现有诊断流程（test_debug → browser_snapshot → ...）
5. 修复成功后 → 追加经验条目到上表
```
```

**3.1.2 在系统提示词中增加"查表优先"硬性规则**

在 [agent.py](backend/app/agents/web_mcp/agent.py) 的 `SYSTEM_PROMPT` 硬性规则区新增一条：

```python

### 修复经验库优先（healer 效率硬性规则）

进入流程 4️⃣（自动修复）时：
1. **先查 healer skill 的经验库表格**，看错误签名是否命中
2. 命中 → **直接应用修复策略**，跳过 test_debug / browser_snapshot 诊断
3. 未命中 → 正常诊断
4. 修复成功后 → **必须**在经验库追加新条目（签名 + 策略）
```

#### 效果预估
- 命中经验库的修复：token 消耗从 ~10K 降至 ~2K（80%↓）
- 修复耗时从 ~90s 降至 ~20s（78%↓）
- 预期命中率：运行 2 周后达到 40%+（高频错误会被快速覆盖）

#### 涉及文件
| 文件 | 变更 |
|------|------|
| `.claude/skills/web_mcp/healer/SKILL.md` | 顶部新增经验库表格 + 使用流程 |
| `backend/app/agents/web_mcp/agent.py` | 硬性规则区新增"查表优先"规则 |

---

### 3.2 脚本质量门禁

#### 问题
当前从生成到执行之间只有 `playwright test --list` 的语法校验。低质量脚本（硬编码延迟、废弃 API、无等待策略）直接流入执行阶段，失败后再由 healer 修复，形成"生成 → 执行 → 失败 → 修复 → 重执行"的低效循环。

#### 方案

**3.2.1 扩展 `save_web_test_script` 增加脚本质量扫描**

在 [artifacts_tools.py](backend/app/agents/tools/web/artifacts_tools.py) 的 `save_web_test_script` 函数中，保存前执行非阻塞式扫描，返回 _warnings 供 Agent 自我修正：

```python
import re

# 反模式定义（基于 Playwright 最佳实践）
_SCRIPT_QUALITY_RULES = [
    {
        "id": "HARD_WAIT",
        "severity": "warning",
        "pattern": r"await\s+page\.waitForTimeout\(\s*(\d{4,})\s*\)",
        "message": "发现硬编码等待 {matched}ms（>1s），建议改用 waitForSelector / waitForResponse / waitForLoadState",
        "fix": "将 waitForTimeout({ms}) 替换为语义等待，如 waitForSelector('.loaded') 或 waitForLoadState('networkidle')",
    },
    {
        "id": "DEPRECATED_DOLLAR",
        "severity": "error",
        "pattern": r"page\.\$\(['\"]",
        "message": "使用了废弃的 page.$() API（element handle 模式），应改用基于 locator 的定位方式",
        "fix": "将 page.$('.foo') 替换为 page.locator('.foo')，并直接链式操作：page.locator('.foo').click()",
    },
    {
        "id": "UNSAFE_CLICK_NO_WAIT",
        "severity": "warning",
        "pattern": r"\.click\(\s*\)\s*;\s*\n\s*await\s+expect",
        "message": "click() 后直接断言，无中间等待——如果点击触发了页面跳转或异步渲染，断言可能因时序问题不稳定",
        "fix": "在 click() 和后续断言之间增加等待：await page.waitForLoadState('networkidle') 或 await expect(targetElement).toBeVisible()",
    },
    {
        "id": "TEXTCONTENT_ASSERTION",
        "severity": "info",
        "pattern": r"expect\(.*?\.textContent\(\)\)",
        "message": "使用 textContent() 做断言，Playwright 有更语义化的 API，如 toHaveText() / toContainText()",
        "fix": "将 expect(el.textContent()).toBe('X') 替换为 await expect(el).toHaveText('X')",
    },
    {
        "id": "MISSING_BEFOREEACH_ISOLATION",
        "severity": "info",
        "pattern": r"test\.describe\(.*?\{",
        "message": "检测到 test.describe，建议包含 beforeEach 做状态隔离（清缓存/重置数据），防止用例间相互污染",
        "fix": "在 test.describe 内添加 test.beforeEach：如 await page.goto('/'); await page.evaluate(() => localStorage.clear())",
    },
    {
        "id": "CSS_SELECTOR_ONLY",
        "severity": "warning",
        "pattern": r"page\.locator\(['\"](\.|#)[^'\"]+['\"]\)",
        "message": "使用纯 CSS class/id 选择器，页面样式变更会导致测试断裂，建议优先使用语义定位器",
        "fix": "将 page.locator('.submit-btn') 替换为 page.getByRole('button', { name: 'Submit' }) 或从测试计划中复制已验证的定位器",
    },
    {
        "id": "NO_SOFT_ASSERTION",
        "severity": "info",
        "pattern": r"(?<!\.soft\()expect\(.*?\)\.(toBe|toHave|toContain)",
        "message": "在整个测试步骤流程中，如果多个断言相互独立，可使用 expect.soft() 让后续断言继续执行而非立即终止",
        "fix": "将独立的 expect() 替换为 expect.soft()，以便在一次执行中收集完整的失败信息",
    },
]

def _scan_script_quality(script_content: str) -> list[dict]:
    """扫描脚本中的反模式并返回问题列表（非阻塞）。"""
    issues = []
    for rule in _SCRIPT_QUALITY_RULES:
        for match in re.finditer(rule["pattern"], script_content, re.MULTILINE):
            # 提取行号
            line_no = script_content[:match.start()].count('\n') + 1
            matched_text = match.group(0)[:80]  # 截断展示
            issues.append({
                "id": rule["id"],
                "severity": rule["severity"],
                "line": line_no,
                "matched": matched_text,
                "message": rule["message"].replace("{matched}", matched_text),
                "fix": rule["fix"].replace("{ms}", match.group(1) if match.lastindex else ""),
            })
    return issues
```

然后在 `save_web_test_script` 返回结果中追加：

```python
# 在 return 之前：
quality_issues = _scan_script_quality(script_content)
error_count = sum(1 for i in quality_issues if i["severity"] == "error")
warning_count = sum(1 for i in quality_issues if i["severity"] == "warning")

result = {
    "success": True,
    "attachment_id": str(attachment.id),
    # ... 现有字段 ...
    "quality": {
        "passed": error_count == 0,
        "errors": error_count,
        "warnings": warning_count,
        "issues": quality_issues[:10],  # 仅返回前 10 条，防止上下文溢出
        "message": f"脚本质量扫描: {error_count} 个错误, {warning_count} 个警告" if quality_issues else "脚本质量扫描通过 ✓",
    }
}
```

**3.2.2 扩展 `_validate_test_cases` 增加语义级校验**

在 [artifacts_tools.py](backend/app/agents/tools/web/artifacts_tools.py) 的 `_validate_test_cases` 中追加：

```python
def _validate_test_cases(test_cases: list) -> Optional[str]:
    # ... 现有结构校验 ...

    # 新增：语义级校验
    for i, tc in enumerate(test_cases):

        # 检查步骤是否引用了定位器（必须有 selector/ref 列）
        for j, step in enumerate(tc.get("steps", [])):
            if not isinstance(step, dict):
                continue
            # 如果 action 是 click/fill/type 等交互操作，应有 selector
            action = (step.get("action") or "").lower()
            if action in ("click", "fill", "type", "select", "check", "hover"):
                if not step.get("selector") and not step.get("locator"):
                    return (
                        f"test_cases[{i}].steps[{j}] 是交互操作 ({action})，"
                        "但缺少 selector/locator 字段。"
                        "请从测试计划中复制已验证的定位器。"
                    )

        # 检查验证点是否可量化
        for j, vp in enumerate(tc.get("verification_points", [])):
            if isinstance(vp, str):
                if len(vp.strip()) < 10:
                    return (
                        f"test_cases[{i}].verification_points[{j}] 过短（<10字符），"
                        f"当前值: '{vp}'。请描述具体可验证的期望结果。"
                    )
            elif isinstance(vp, dict):
                if not vp.get("expected") and not vp.get("assertion"):
                    return (
                        f"test_cases[{i}].verification_points[{j}] 缺少 expected/assertion 字段"
                    )

    return None  # 通过
```

**3.2.3 在系统提示词中增加门禁反馈要求**

```python

### 脚本与用例质量门禁

- `save_web_test_script` 保存后，检查返回的 `quality` 字段：
  - `quality.errors > 0` → **必须在保存后修复**，修复后再保存一次
  - `quality.warnings > 0` → 评估后决定是否修复，至少给出说明
- `save_web_test_cases` 保存失败（结构/语义校验不通过）→ 根据 error 信息修正后重试
```

#### 效果预估
- 拦截常见反模式，减少"执行后失败"的无效循环
- `error` 级别拦截率预计 60-80%（`page.$()` 等废弃 API 常见于 LLM 生成的脚本）
- 每次成功拦截节省 ~15K tokens（免去一轮 execute → fail → healer 流程）

#### 涉及文件
| 文件 | 变更 |
|------|------|
| `backend/app/agents/tools/web/artifacts_tools.py` | `_SCRIPT_QUALITY_RULES` 常量 + `_scan_script_quality` 函数；`save_web_test_script` 返回增加 `quality` 字段；`_validate_test_cases` 增加语义级校验 |
| `backend/app/agents/web_mcp/agent.py` | 硬性规则区新增"质量门禁"规则 |

---

### 3.3 执行报告增加摘要结构化字段

#### 问题
`save_web_test_report` 保存的报告 `description` 字段是自由文本（如："Web 测试报告 - XXX"），前端列表只能展示文件名。不利于快速判断报告价值。

#### 方案
在 `save_web_test_report` 的 Attachment `description` 中使用结构化格式：

```python
# 当前:
description = f"Web 测试报告 - {sub_function.display_name}\n执行时间: {duration:.2f}秒..."

# 优化后:
description = json.dumps({
    "type": "execution_summary",
    "passed": stats.get("passed", 0),
    "failed": stats.get("failed", 0),
    "skipped": stats.get("skipped", 0),
    "total": stats.get("total", 0),
    "duration_sec": round(duration, 1),
    "sub_function": sub_function.display_name,
    "status": "passed" if execution_result.get("success") else "failed",
    "execution_id": execution_id,
}, ensure_ascii=False)
```

前端 `EnhancedTestArtifactsPanel` 可解析此 JSON 渲染彩色状态标签和通过率进度条，无需额外 API 调用。

#### 涉及文件
| 文件 | 变更 |
|------|------|
| `backend/app/agents/tools/web/artifacts_tools.py` | `save_web_test_report` 的 description 使用 JSON 结构化 |
| `ui/components/web-tests/test-artifacts-panel-enhanced.tsx` | 解析 JSON description 渲染状态卡片 |

---

## 4. P1 — 结构优化（本月可交付）

### 4.1 系统提示词分层瘦身

#### 问题详解

当前 `SYSTEM_PROMPT` (273行) 的注意力热力图（基于典型 LLM 的 lost-in-the-middle 特性）：

```
高注意力 ──┬── 前 30 行: 身份定义 + 工作流概览    ← 模型最关注
           │
中注意力 ──┼── 30-150 行: 工作流详细步骤           ← 部分规则可能被忽略
           │
低注意力 ──┼── 150-230 行: 硬性规则 + Skill 路由    ← 关键规则在这里！
           │
中注意力 ──┴── 230-273 行: 结尾提示                  ← 近因效应略有回升
```

**致命问题**：最重要的硬性规则（如"save_web_test_report 强制调用"、"定位器铁律"）恰好处于最低注意力区域。

#### 方案：三层提示词架构

```
                        ┌───────────────────────────┐
                        │    Layer 0: 核心身份       │
                        │    (~15行, 始终加载)       │
                        │                           │
                        │  "你是 Web 自动化测试专家"  │
                        │  + 铁律 5 条 (不可违反)    │
                        │  + 工作流选择决策树        │
                        └───────────┬───────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
    ┌─────────▼────────┐  ┌────────▼───────┐  ┌─────────▼────────┐
    │ Layer 1A:         │  │ Layer 1B:      │  │ Layer 1C:        │
    │ workflow_gen.md   │  │ workflow_exec  │  │ workflow_heal.md │
    │ (~40行)           │  │ .md (~25行)    │  │ (~20行)          │
    │                   │  │                │  │                  │
    │ 生成模式全流程     │  │ 执行模式全流程  │  │ 修复模式全流程    │
    │ (← Router 按需    │  │ (← Router 按需 │  │ (← Router 按需   │
    │  注入此提示词)     │  │  注入此提示词)  │  │  注入此提示词)    │
    └───────────────────┘  └────────────────┘  └──────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────────┐
                        │    Layer 2: Skills        │
                        │    (现有 SkillsMiddleware) │
                        │                           │
                        │  按需加载: planner /      │
                        │  case-designer /          │
                        │  generator / executor /   │
                        │  healer                    │
                        └───────────────────────────┘
```

**Layer 0 — 核心身份 + 铁律**（独立文件 `backend/app/agents/web_mcp/prompts/base.md`）：

```markdown
# Web 自动化测试专家

你是资深的 Web 自动化测试专家，负责基于浏览器的 UI 测试全生命周期：功能分析、测试生成、执行、修复与报告。

## ⚡ 铁律（始终遵守，优先级最高）

1. **成果物强制落库**：测试计划/用例/脚本/报告生成后必须调用对应的 save_* 工具，不得跳过。
2. **执行入口唯一**：只有 `execute_web_script`(subprocess) 能判定 pass/fail；`test_debug`+`browser_*` 仅供诊断。
3. **生成完成必须邀约**：生成完计划+用例+脚本后立即输出 `<EXECUTION_INVITATION>` 标记。
4. **修复先查经验库**：进入 healer 流程后先匹配经验库，命中则直接应用，跳过诊断。
5. **运行时上下文勿问**：project_identifier、folder_id 由系统注入，不要向用户询问。

## 🔀 工作流路由

收到用户输入后，按以下决策树选择工作流（详细步骤在 Layer 1 提示词中）：

1. 输入是「子功能 ID」 → 进入 **生成模式** (Layer 1A)
2. 输入是「功能描述/URL」 → 进入 **创建模式** (Layer 1B)
3. 输入是「执行/运行」+ 子功能 ID → 进入 **执行模式** (Layer 1C)
4. 输入包含失败/报错 → 进入 **修复模式** (Layer 1D)

当前已是某种模式中时，按系统提示词中的流程继续，不要重新路由。
```

**Layer 1A — 生成模式**（独立文件 `backend/app/agents/web_mcp/prompts/workflow_generate.md`）：

```markdown
## 1️⃣ 生成测试（当前模式）

0. **断点续跑检查**：调用 `get_web_sub_function_artifacts(sub_function_id)`。
   - 用户明确要求「重新生成」→ 忽略已有成果物，从头生成。
   - 否则已存在的成果物可跳过，只补缺失部分。
   - ⚠️ 若复跑失败且疑似定位器过期（页面已迭代），必须重新走 planner 探索。

1. `get_sub_function_details(sub_function_id)` 获取子功能详情
2. 读 **planner** skill → 页面探索 + 定位器生成 + 测试计划
3. ⚠️ `save_web_test_plan(plan_content=...)` **强制保存**（失败则中断流程）
4. 读 **case-designer** skill → 计划转结构化用例 (JSON)
5. ⚠️ `save_web_test_cases(test_cases=[...], project_identifier=...)` **强制保存**
   → 检查返回是否包含 error（结构/语义校验不通过则修正后重试）
6. 读 **generator** skill → 用计划中的定位器生成脚本（禁止重新探索）
7. ⚠️ `save_web_test_script(script_content=...)` **强制保存**
   → 检查返回的 `quality` 字段：errors > 0 必须修复
8. `get_web_sub_function_artifacts(sub_function_id)` 验证四类成果物齐全
9. **执行邀约**：输出 `<EXECUTION_INVITATION>` 标记（JSON 单行）
   ```
   <EXECUTION_INVITATION>
   {"type":"execution_invitation","mode":"web","sub_function_id":"<ID>","script_name":"<文件名>","test_count":<N>,"description":"测试计划、测试用例、测试脚本已保存；尚未执行，因此暂无 HTML 测试报告和执行摘要。是否立即执行？","alternatives":[{"key":"execute","label":"立即执行"},{"key":"skip","label":"暂不执行"},{"key":"edit","label":"修改脚本"},{"key":"other","label":"其他"}]}
   </EXECUTION_INVITATION>
   ```
```

**实现方式** — 新增 `WorkflowRouterMiddleware`：

```python
# backend/app/agents/web_mcp/workflow_router_middleware.py

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"

class WorkflowRouterMiddleware(AgentMiddleware):
    """根据用户意图动态注入工作流专属提示词。"""

    @hook_config(can_jump_to=["model", "end"])
    def after_model(self, state, runtime):
        # ... 意图识别 + 动态注入 Layer 1 ...
        pass
```

> **渐进策略**：先创建 `prompts/` 目录和独立文件，中间件先读取文件内容追加到 system_message 末尾，验证效果后再做更精细的 Layer 0/1 分离。

#### 效果预估
- Layer 0 仅 ~15 行，铁律处于最高注意力位置
- 每次对话的 system prompt token 消耗减少 ~60%（从 ~2700 tokens 降至 ~1100 + 按需 ~500）
- 维护性提升：修改生成流程只需编辑 `workflow_generate.md`，不影响执行/修复流程

#### 涉及文件
| 文件 | 变更 |
|------|------|
| `backend/app/agents/web_mcp/prompts/base.md` | 新建，Layer 0 核心提示词 |
| `backend/app/agents/web_mcp/prompts/workflow_generate.md` | 新建，生成模式 |
| `backend/app/agents/web_mcp/prompts/workflow_create.md` | 新建，创建模式 |
| `backend/app/agents/web_mcp/prompts/workflow_execute.md` | 新建，执行模式 |
| `backend/app/agents/web_mcp/prompts/workflow_heal.md` | 新建，修复模式 |
| `backend/app/agents/web_mcp/workflow_router_middleware.py` | 新建，路由中间件 |
| `backend/app/agents/web_mcp/agent.py` | `SYSTEM_PROMPT` 替换为读取 base.md |

---

### 4.2 MCP 连接健康检查与优雅降级

#### 问题
MCP Playwright server session 断裂（进程崩溃、超时等）后，所有 `browser_*` 工具调用都会失败。当前 Agent 不知道 session 已断开，会持续调用直到超时或收到错误，浪费大量 token 和时间。

#### 方案

```python
# backend/app/agents/web_mcp/health.py

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_HEALTH_CHECK_RESULT: Optional[dict] = None
_HEALTH_CHECK_TIME: float = 0
_HEALTH_CHECK_TTL = 30  # 缓存 30 秒


async def check_mcp_health(
    session, timeout: float = 5.0
) -> dict:
    """检查 MCP Playwright server 是否存活。

    结果缓存 30 秒，避免每次工具调用前都探测。

    Returns:
        {
            "healthy": bool,
            "browser_tools_count": int,
            "error": str | None,
            "recommendation": str,
        }
    """
    global _HEALTH_CHECK_RESULT, _HEALTH_CHECK_TIME

    import time
    now = time.monotonic()
    if _HEALTH_CHECK_RESULT and (now - _HEALTH_CHECK_TIME) < _HEALTH_CHECK_TTL:
        return _HEALTH_CHECK_RESULT

    try:
        # 使用 session 的 list_tools 快速探测
        response = await asyncio.wait_for(
            session.list_tools(), timeout=timeout
        )
        browser_tools = [
            t for t in (response.tools or [])
            if t.name.startswith("browser_")
        ]
        result = {
            "healthy": len(browser_tools) > 0,
            "browser_tools_count": len(browser_tools),
            "error": None,
            "recommendation": "",
        }
        if not browser_tools:
            result["healthy"] = False
            result["recommendation"] = "MCP browser 工具数为 0，请检查 Playwright MCP server 配置"
    except asyncio.TimeoutError:
        result = {
            "healthy": False,
            "browser_tools_count": 0,
            "error": f"MCP 健康检查超时 ({timeout}s)",
            "recommendation": "MCP server 无响应。请刷新页面重新连接，或检查 Playwright MCP 进程是否存活。",
        }
    except Exception as e:
        result = {
            "healthy": False,
            "browser_tools_count": 0,
            "error": str(e)[:200],
            "recommendation": "MCP session 异常。请刷新页面重新连接。",
        }

    _HEALTH_CHECK_RESULT = result
    _HEALTH_CHECK_TIME = now
    return result
```

在 `make_agent` 中增加启动时健康检查和运行时中间件：

```python
# 在 make_agent 中，MCP 工具加载后
health = await check_mcp_health(session)
if not health["healthy"]:
    logger.warning("[WebMCPAgent] MCP 健康检查未通过: %s", health)
    # 注入告警到系统提示词末尾，告知 Agent 浏览器工具可能不可用
    SYSTEM_PROMPT += f"\n\n⚠️ **MCP 健康状态**：浏览器工具不可用 ({health.get('recommendation')})。如果用户请求探索/执行测试，请先告知用户此问题。"

# 每次 Agent 运行时，第一个 browser_* 调用前重新检查
```

#### 涉及文件
| 文件 | 变更 |
|------|------|
| `backend/app/agents/web_mcp/health.py` | 新建，健康检查逻辑 |
| `backend/app/agents/web_mcp/agent.py` | `make_agent` 中集成健康检查 |

---

### 4.3 执行报告趋势对比

#### 方案
在 executor SKILL.md 中增加"获取历史基线并对比"的步骤：

```markdown
# executor SKILL.md 新增内容

## 📊 历史趋势对比（在生成 Markdown 摘要后执行）

1. 获取当前子功能最近 5 次执行记录：
   ```
   SELECT wtr.status, wtr.passed_tests, wtr.failed_tests, wtr.duration_ms, wtr.created_at
   FROM web_test_runs wtr
   JOIN web_tests wt ON wtr.web_test_id = wt.id
   WHERE wt.sub_function_id = '<sub_function_id>'
   ORDER BY wtr.created_at DESC
   LIMIT 5
   ```

2. 在 Markdown 摘要末尾追加趋势分析：

```markdown
## 📈 趋势分析

| 指标 | 本次 | 上次 | 变化 |
|------|------|------|------|
| 通过率 | 85% (17/20) | 90% (18/20) | ↓ 5% |
| 执行时长 | 45.2s | 42.1s | +3.1s |
| 新增失败 | 2 个 | — | ⚠️ 疑似回归 |

**疑似回归用例**：
- `test_checkout_with_empty_cart`: 上次通过 → 本次失败 (Timeout waiting for selector '.cart-summary')
- `test_product_search_by_name`: 上次通过 → 本次失败 (Expected "Search Results" but got "No results found")
```
```

> **简化实现**：Agent 层已有 `async_session_factory` 访问数据库，可直接在 executor skill 中要求 Agent 使用 `get_sub_function_details` 返回的 `total_test_runs` / `last_run_status` 做轻量对比。完整的 SQL 查询可后续用本地工具封装。

#### 涉及文件
| 文件 | 变更 |
|------|------|
| `.claude/skills/web_mcp/executor/SKILL.md` | 新增"趋势对比"章节 |

---

## 5. P2 — 能力升级（本季度可交付）

### 5.1 智能化测试执行调度

#### 5.1.1 执行策略决策树

```
execute_web_script 被调用
    │
    ├── 脚本内容 hash == 上次执行 hash
    │   ├── 上次执行结果 == 全部通过 → 跳过执行，返回缓存结果
    │   └── 上次执行结果 == 有失败 → 仅重跑失败用例
    │
    ├── 脚本内容 hash != 上次执行 hash
    │   ├── diff 分析：仅 X 个定位器变更
    │   │   → 仅执行引用这些定位器的用例
    │   └── 变更范围不可判定
    │       → 全量执行
    │
    └── 无历史执行记录 → 全量执行（建立基线）
```

#### 5.1.2 实现方式

```python
# backend/app/agents/tools/web/execution_tools.py

import hashlib

def _compute_script_hash(script_path: Path) -> str:
    """计算脚本内容 SHA256 hash，用于变更检测。"""
    content = script_path.read_bytes()
    return hashlib.sha256(content).hexdigest()

async def _get_last_execution(sub_function_id: str) -> dict | None:
    """获取子功能最后一次执行记录。"""
    async with async_session_factory() as session:
        result = await session.execute(
            select(WebTestRun)
            .join(WebTest, WebTestRun.web_test_id == WebTest.id)
            .where(WebTest.sub_function_id == UUID(sub_function_id))
            .order_by(WebTestRun.created_at.desc())
            .limit(1)
        )
        run = result.scalar_one_or_none()
        if not run:
            return None
        return {
            "id": str(run.id),
            "status": run.status,
            "passed_tests": run.passed_tests,
            "failed_tests": run.failed_tests,
            "execution_config": run.execution_config or {},
        }

async def _compute_execution_strategy(
    sub_function_id: str,
    script_path: Path,
) -> dict:
    """计算最优执行策略。"""
    script_hash = _compute_script_hash(script_path)
    last = await _get_last_execution(sub_function_id)

    if not last:
        return {"strategy": "full", "reason": "无历史执行记录，全量执行建立基线"}

    last_hash = (last.get("execution_config") or {}).get("script_hash", "")
    last_all_passed = last.get("failed_tests", 1) == 0

    if script_hash == last_hash:
        if last_all_passed:
            return {
                "strategy": "skip",
                "reason": "脚本未变更且上次全部通过，跳过执行",
                "cached_result_id": last.get("id"),
            }
        else:
            return {
                "strategy": "failed_only",
                "reason": "脚本未变更但上次有失败，仅重跑失败用例",
                "grep_pattern": "上一次失败的用例标题列表",
            }

    return {"strategy": "full", "reason": "脚本已变更，全量执行"}
```

#### 效果预估
- 回归测试（脚本未变 + 全绿）场景跳过率可达 70%+
- 每次 skip 节省 ~60s 执行时间 + ~5K tokens（executor 分析报告）
- 减少 Playwright 浏览器实例的无效占用

#### 涉及文件
| 文件 | 变更 |
|------|------|
| `backend/app/agents/tools/web/execution_tools.py` | 新增 `_compute_script_hash` + `_get_last_execution` + `_compute_execution_strategy`；`execute_web_script` 调用策略决策 |

---

### 5.2 失败模式知识图谱

#### 方案架构

```
┌─────────────────────────────────────────────────────┐
│                  修复知识图谱                         │
│                                                     │
│  WebTestResult.error_message                        │
│         │                                           │
│         ▼                                           │
│  ┌─────────────┐     ┌──────────────────┐          │
│  │ 错误签名提取  │────▶│ 签名聚类 (向量)   │          │
│  │ (正则+归一化) │     │ 匹配已知修复策略   │          │
│  └─────────────┘     └────────┬─────────┘          │
│                               │                     │
│           ┌───────────────────┼───────────────┐     │
│           ▼                   ▼               ▼     │
│    ┌────────────┐    ┌────────────┐   ┌──────────┐ │
│    │ 选择器类    │    │ 时序类      │   │ 断言类    │ │
│    │ (45%)      │    │ (30%)      │   │ (15%)    │ │
│    │            │    │            │   │          │ │
│    │ • testId   │    │ • race      │   │ • text   │ │
│    │ • 过期定位器│    │ • timeout   │   │ • value  │ │
│    │ • CSS变更  │    │ • loading   │   │ • state  │ │
│    └─────┬──────┘    └─────┬──────┘   └────┬─────┘ │
│          │                 │               │        │
│          ▼                 ▼               ▼        │
│    ┌────────────┐    ┌────────────┐   ┌──────────┐ │
│    │ 修复策略库  │    │ 修复策略库  │   │ 修复策略库│ │
│    │ 置信度排序  │    │ 置信度排序  │   │ 置信度排序│ │
│    └────────────┘    └────────────┘   └──────────┘ │
└─────────────────────────────────────────────────────┘
```

#### 数据模型

```sql
-- 新建表：修复知识条目
CREATE TABLE web_healing_knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    error_signature VARCHAR(500) NOT NULL,       -- 规范化错误指纹
    error_category VARCHAR(50) NOT NULL,          -- selector / timing / assertion / environment / application
    fix_strategy TEXT NOT NULL,                   -- 修复策略描述（给 Agent 看）
    fix_code_template TEXT,                       -- 代码模板（可选，用于自动修复）
    confidence FLOAT DEFAULT 0.5,                 -- 成功率 (0-1)
    apply_count INT DEFAULT 0,                    -- 应用次数
    success_count INT DEFAULT 0,                  -- 成功次数
    last_applied_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_healing_signature ON web_healing_knowledge(error_signature);
CREATE INDEX idx_healing_category ON web_healing_knowledge(error_category);
```

#### Agent 交互流程

```python
# 新增本地工具
@tool
async def search_healing_knowledge(
    error_message: str,
    top_k: int = 3,
) -> dict:
    """在修复知识库中搜索匹配的修复策略。

    使用规范化错误签名匹配历史修复记录，返回置信度最高的策略。

    Args:
        error_message: 完整的错误信息
        top_k: 返回的最匹配策略数

    Returns:
        {"matches": [{"strategy": ..., "confidence": ..., "success_rate": ...}]}
    """
    signature = _normalize_error(error_message)
    # 精确匹配
    exact = await _query_knowledge(signature)
    if exact:
        return {"matches": exact}
    # 模糊匹配（子串 + 编辑距离）
    fuzzy = await _query_knowledge_fuzzy(signature, top_k)
    return {"matches": fuzzy}


@tool
async def record_healing_result(
    error_signature: str,
    error_category: str,
    fix_strategy: str,
    fix_code_template: str = "",
    success: bool = True,
) -> dict:
    """记录一次修复结果到知识库。

    Args:
        error_signature: 规范化错误指纹
        error_category: 错误类别 (selector/timing/assertion/environment/application)
        fix_strategy: 使用的修复策略
        fix_code_template: 代码模板（如 test.use({ testIdAttribute: 'data-test' })）
        success: 修复是否成功

    Returns:
        {"recorded": true}
    """
    # upsert + 更新置信度
    ...
```

#### 自动修复（高置信度）

当知识库中某条策略的 `confidence > 0.9` 且 `apply_count > 10` 时，healer 可**跳过 LLM 诊断**直接应用修复：

```python
# 在 healer 流程中
matches = await search_healing_knowledge(error_message, top_k=1)
if matches and matches[0]["confidence"] > 0.9:
    # 自动应用修复（不走 LLM 诊断）
    apply_fix(matches[0]["fix_code_template"])
    result = await execute_web_script(...)
    await record_healing_result(..., success=result["success"])
    return  # 修复完成
# 否则走正常 healer 流程
```

#### 涉及文件
| 文件 | 变更 |
|------|------|
| `backend/app/models/web_test.py` | 新增 `WebHealingKnowledge` 模型 |
| `backend/app/agents/tools/web/healing_tools.py` | 新建，`search_healing_knowledge` + `record_healing_result` |
| `backend/app/agents/tools/web/__init__.py` | 注册新工具 |
| `backend/app/agents/web_mcp/agent.py` | 集成到 healer 工作流 |

---

### 5.3 Token 成本可观测性

#### 方案

```python
# backend/app/agents/web_mcp/cost_middleware.py

class CostTrackingMiddleware(AgentMiddleware):
    """追踪每次 Agent 调用的 token 消耗并记录到数据库。"""

    @hook_config(can_jump_to=["model", "end"])
    def after_model(self, state, runtime):
        messages = state.get("messages", [])
        last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
        if not last_ai or not hasattr(last_ai, "usage_metadata"):
            return None

        usage = last_ai.usage_metadata
        project_identifier = runtime.context.project_identifier

        # 异步记录到数据库（不阻塞 Agent 流程）
        asyncio.create_task(_record_usage(
            project_identifier=project_identifier,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            model_name=getattr(last_ai, "model_name", "unknown"),
        ))
        return None
```

告警规则：
```python
# 在代价追踪中增加异常检测
if input_tokens > AVG_INPUT_TOKENS * 2.5:
    logger.warning(
        f"[CostAlert] Agent 输入 token 异常: {input_tokens} "
        f"(均值: {AVG_INPUT_TOKENS})。"
        f"可能原因: 对话历史过长 / 页面快照过大 / Agent 跑偏反复探索"
    )
```

#### 涉及文件
| 文件 | 变更 |
|------|------|
| `backend/app/agents/web_mcp/cost_middleware.py` | 新建 |
| `backend/app/agents/web_mcp/agent.py` | middleware 列表中加入 CostTrackingMiddleware |

---

## 6. P3 — 架构演进（下季度规划）

### 6.1 Supervisor 多智能体架构

#### 目标架构

```
                            ┌──────────────────────┐
                            │   Supervisor Agent    │
                            │                      │
                            │  职责:                 │
                            │  1. 意图识别           │
                            │  2. 任务路由           │
                            │  3. 多Agent编排        │
                            │  4. 上下文摘要传递      │
                            │  5. 全局铁律执行监督    │
                            └──────────┬───────────┘
                                       │
          ┌────────────────┬───────────┼───────────┬────────────────┐
          │                │           │           │                │
    ┌─────▼──────┐  ┌──────▼─────┐ ┌──▼────────┐ ┌▼──────────┐
    │  Planner   │  │  Generator │ │  Executor  │ │  Healer   │
    │  Agent     │  │  Agent     │ │  Agent     │ │  Agent    │
    │            │  │            │ │            │ │           │
    │  系统提示词 │  │  系统提示词 │ │  系统提示词 │ │  系统提示词│
    │  ~40行     │  │  ~25行     │ │  ~20行     │ │  ~30行    │
    │            │  │            │ │            │ │           │
    │  工具:     │  │  工具:     │ │  工具:     │ │  工具:    │
    │  browser_* │  │  save_*    │ │  execute_* │ │  browser_*│
    │  planner_* │  │  get_*     │ │  save_*    │ │  test_*   │
    │  get_*     │  │            │ │  get_*     │ │  save_*   │
    └─────┬──────┘  └──────┬─────┘ └──┬────────┘ └──┬───────┘
          │                │           │             │
          └────────────────┴───────────┴─────────────┘
                           │
                    ┌──────▼──────┐
                    │  共享工具层  │
                    │  (本地+MCP)  │
                    └─────────────┘
```

#### 关键设计

1. **Planner Agent**：只负责页面探索和测试计划生成。上下文只含目标 URL + 页面快照，天然隔离。
2. **Generator Agent**：输入是测试计划（含定位器），输出是 Playwright 脚本。不需要 browser_* 工具。
3. **Executor Agent**：输入是脚本路径 + 子功能 ID，输出是执行报告。不需要 browser_* 工具。
4. **Healer Agent**：输入是执行失败信息 + 脚本内容，输出是修复后的脚本。需要 browser_* 工具。

各 Agent 的上下文窗口不会互相污染，单 Agent 内 prompt 集中且短小，极大提升指令遵循度。

#### 过渡策略
先以**单一 Agent + 动态提示词注入**（P1 优化）运行 1-2 个月，验证"分层是否有效"。如果效果显著（Agent 指令遵循度提升 >30%），再投入做 Supervisor 多 Agent 拆分。

---

### 6.2 自愈闭环（无 LLM 参与的高频修复）

#### 目标
当知识图谱中某类修复的置信度 > 0.95 时，将其从 LLM Agent 流程中剥离，直接在 `execute_web_script` 的错误处理中自动执行。

```python
# 在 execute_web_script 的失败处理中：
if not execution_result["success"]:
    auto_fix = await _try_auto_heal(execution_result, script_path)
    if auto_fix["applied"]:
        # 自动应用后重跑
        execution_result = await _execute_script_internal(...)
        # 无论结果如何都记录
        await record_healing_result(..., success=execution_result["success"])
```

自动修复规则示例：
```python
_AUTO_HEAL_RULES = [
    {
        "name": "testIdAttribute 自动适配",
        "error_pattern": r"getByTestId\('.*?'\) resolved to 0 elements",
        "fix": "detect_and_set_test_id_attribute(page, script_content)",
        "min_confidence": 0.95,
        "min_success_count": 20,  # 历史上成功修复过 20 次以上
    },
    {
        "name": "过期定位器自动刷新",
        "error_pattern": r"Timeout .* waiting for (locator|selector)",
        "fix": "regenerate_locator_and_patch(page, script_content, error_line)",
        "min_confidence": 0.85,
        "min_success_count": 10,
    },
]
```

---

## 7. 实施路线图

```
                                Q3 2026                          Q4 2026
                    ┌─────────────────────────────┬─────────────────────────────┐
Week 1-2 (P0)       │ Week 3-4 (P0)            │ Month 2-3 (P1)              │ Month 4-6 (P2)
────────────────────┼──────────────────────────┼────────────────────────────┼────────────────────────────
                    │                          │                            │
✅ healer 经验库     │ ✅ 脚本质量门禁           │ ✅ 系统提示词分层            │ ✅ 智能执行调度
   (SKILL.md 改)    │    (artifacts_tools 改)    │    (prompts/ 目录拆分)       │    (execution_tools 改)
                    │                          │                            │
✅ 经验库查表规则     │ ✅ 用例语义校验           │ ✅ MCP 健康检查             │ ✅ 失败知识图谱
   (agent.py 规则)   │    (_validate_test_cases)  │    (health.py)              │    (healing_tools + 新表)
                    │                          │                            │
                    │ ✅ 报告结构化              │ ✅ 趋势对比              │ ✅ Token 成本追踪
                    │    (save_test_report 改)    │    (executor SKILL 改)      │    (cost_middleware)
                    │                          │                            │
                    │                          │                            ├────────────────────────────
                    │                          │                            │ Month 7+ (P3)
                    │                          │                            │
                    │                          │                            │ 🔮 Supervisor 多Agent
                    │                          │                            │ 🔮 自愈闭环
                    │                          │                            │ 🔮 模型微调/RL 探索
                    └──────────────────────────┴────────────────────────────┴────────────────────────────

验证节点:
  P0 交付后    → 测量: healer 修复成功率、脚本反模式拦截率
  P1 交付后    → 测量: Agent 指令遵循度（save 漏调率）、MCP 故障发现时间
  P2 交付后    → 测量: 跳过执行率、自动修复率、token 成本
  P3 立项前    → 评估: 现有分层方案是否满足需求，决定是否投入 Supervisor 重构
```

---

## 8. 成功度量

| 指标 | 当前值（估算） | P0 后目标 | P1 后目标 | P2 后目标 |
|------|-------------|----------|----------|----------|
| Healer 平均修复耗时 | ~90s | <40s | <25s | <10s (含自动修复) |
| Healer 平均 token 消耗 | ~10K | <5K | <3K | <1K |
| 脚本反模式首次拦截率 | 0% | >60% | >80% | >90% |
| Agent 强制 save 步骤遗漏率 | ~15% (估算) | <10% | <5% | <3% |
| 无变更回归跳过执行率 | 0% | — | 0% | >70% |
| MCP 故障发现时间 | 执行超时后 (~120s) | — | <5s (主动探测) | <5s |
| Token 成本可见性 | 无追踪 | — | — | 按子功能/工作流可查 |

---

## 9. 风险与应对

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| **经验库冷启动期命中率低** | 高 | 低 | 预设 6-7 条高频错误的经验（见 P0 方案），确保前两周即有 30%+ 命中率 |
| **脚本质量规则误报** | 中 | 中 | 所有规则仅作为 warning 返回，不阻断保存；设置 `quality.errors > 0` 才要求修复（errors 规则仅覆盖确认的反模式，如废弃 API） |
| **系统提示词分层后 Agent 行为变化** | 中 | 高 | 先做 A/B 对比（同一任务同时跑新旧两版），确认无退化后再全量切换 |
| **失败知识图谱需要大量数据才能生效** | 中 | 中 | P0 的经验库表格 + P2 的知识图谱形成渐进式数据积累；前 100 条记录靠 Agent 手动追加 |
| **Supervisor 多 Agent 引入额外延迟** | 低 | 中 | Planner → Generator → Executor 为串行流程，不引入额外开销；并行场景暂不启用 |
| **Playwright MCP 版本升级导致工具签名变化** | 中 | 中 | 在 MCP 健康检查中新增版本探测，版本变化时告警；工具加载时过滤不可用工具而非 crash |

---

## 附录 A：文件变更清单汇总

### P0 变更
| 文件路径 | 操作 | 说明 |
|----------|------|------|
| `.claude/skills/web_mcp/healer/SKILL.md` | 修改 | 顶部新增经验库表格 + 使用流程 |
| `backend/app/agents/web_mcp/agent.py` | 修改 | 硬性规则区新增"查表优先"+ "质量门禁"两条规则 |
| `backend/app/agents/tools/web/artifacts_tools.py` | 修改 | 新增 `_SCRIPT_QUALITY_RULES`、`_scan_script_quality`；扩展 `_validate_test_cases`；`save_web_test_report` description JSON 结构化 |
| `ui/components/web-tests/test-artifacts-panel-enhanced.tsx` | 修改 | 解析 JSON description 渲染状态卡片 |

### P1 变更
| 文件路径 | 操作 | 说明 |
|----------|------|------|
| `backend/app/agents/web_mcp/prompts/base.md` | 新建 | Layer 0 核心提示词 |
| `backend/app/agents/web_mcp/prompts/workflow_generate.md` | 新建 | 生成模式 |
| `backend/app/agents/web_mcp/prompts/workflow_create.md` | 新建 | 创建模式 |
| `backend/app/agents/web_mcp/prompts/workflow_execute.md` | 新建 | 执行模式 |
| `backend/app/agents/web_mcp/prompts/workflow_heal.md` | 新建 | 修复模式 |
| `backend/app/agents/web_mcp/workflow_router_middleware.py` | 新建 | 路由中间件 |
| `backend/app/agents/web_mcp/agent.py` | 修改 | SYSTEM_PROMPT 替换为读取 base.md |
| `backend/app/agents/web_mcp/health.py` | 新建 | MCP 健康检查 |
| `.claude/skills/web_mcp/executor/SKILL.md` | 修改 | 新增"趋势对比"章节 |

### P2 变更
| 文件路径 | 操作 | 说明 |
|----------|------|------|
| `backend/app/agents/tools/web/execution_tools.py` | 修改 | 新增执行策略决策（hash比较、跳过缓存） |
| `backend/app/models/web_test.py` | 修改 | 新增 `WebHealingKnowledge` 模型 |
| `backend/app/agents/tools/web/healing_tools.py` | 新建 | `search_healing_knowledge` + `record_healing_result` |
| `backend/app/agents/tools/web/__init__.py` | 修改 | 注册新工具 |
| `backend/app/agents/web_mcp/cost_middleware.py` | 新建 | Token 代价追踪 |

### P3 变更（规划中，暂不列出具体文件）

---

## 附录 B：关键代码片段索引

| 代码片段 | 文件 | 行号 | 用途 |
|----------|------|------|------|
| `SYSTEM_PROMPT` | `agent.py` | 128-273 | 当前 273 行的系统提示词 |
| `_validate_test_cases` | `artifacts_tools.py` | 248-291 | 用例结构校验（需扩展） |
| `_static_check_script` | `execution_tools.py` | 325-379 | `--list` 语法校验 |
| `_save_test_report` | `artifacts_tools.py` | 677-800 | 报告打包保存全流程 |
| `_persist_structured_run` | `execution_tools.py` | 555-674 | 执行结果落库 |
| `wrap_tool_with_error_handling` | `error_handler.py` | 62-158 | MCP 工具异常包装 |
| `WebExecutionInvitationMiddleware` | `execution_invitation_middleware.py` | 127-186 | 执行邀约中间件 |
