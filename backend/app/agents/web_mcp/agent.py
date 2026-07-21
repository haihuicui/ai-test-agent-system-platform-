"""
Web 自动化测试智能体

该智能体负责 Web 测试的全生命周期管理：
- 页面分析与元素识别
- 测试计划生成、测试代码生成
- 测试执行与结果收集
- 测试修复与报告生成

架构设计：
- Agent: 工作流编排与用户交互
- Skills: 领域知识与最佳实践指导（按需加载，节约 token）
- Tools: 原子操作（数据库、存储、MCP）
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Callable

from deepagents import create_deep_agent as create_agent
from deepagents.backends import FilesystemBackend, LocalShellBackend, CompositeBackend
from deepagents.middleware import SkillsMiddleware
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.language_models import ModelProfile
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_config
from langgraph.pregel import Pregel
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from app.agents.tools.web import get_local_tools
from app.agents.tools.error_handler import wrap_tools_with_error_handling
from app.agents.web_mcp.intent_confirmation_middleware import WebIntentConfirmationMiddleware
from app.config.settings import settings
from app.core.llms import text_model as model
from app.utils.shell_env import build_shell_env, ensure_playwright_mcp_project, get_playwright_mcp_command_args
from app.utils.web_mcp_storage_state import resolve_project_storage_state_path

# =============================================================================
# 配置
# =============================================================================
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TkdSNlVRPT06ZGFhYmJjYWY=

model.profile = ModelProfile(max_input_tokens=128000)

skills_root = Path(settings.web_mcp_skills_root).resolve()
workspace_root = Path(settings.web_mcp_workspace_root).resolve()

skills_backend = FilesystemBackend(root_dir=skills_root, virtual_mode=True)
workspace_backend = FilesystemBackend(root_dir=workspace_root, virtual_mode=True)
shell_backend = LocalShellBackend(root_dir=Path(settings.web_mcp_workspace_root).resolve(),
                                  inherit_env=True,
                                  env=build_shell_env(),
                                  timeout=180,
                                  virtual_mode=True)
composite_backend = CompositeBackend(
    default=shell_backend,
    routes={
        "/skills/": skills_backend,
        "/": workspace_backend,
    },
)
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TkdSNlVRPT06ZGFhYmJjYWY=

skills_middleware = SkillsMiddleware(
        backend=composite_backend,
        sources=["/skills/web_mcp/"]  # skills 目录包含 web_mcp 的技能子目录
    )


# =============================================================================
# 上下文定义
# =============================================================================

@dataclass
class WebAgentContext:
    """Web 智能体运行时上下文"""
    project_identifier: str = ""
    folder_id: str = ""
    current_user_id: str = "00000000-0000-0000-0000-000000000001"


# =============================================================================
# 中间件
# =============================================================================

class WebContextInjectionMiddleware(AgentMiddleware):
    """上下文注入中间件 - 将运行时参数注入到系统提示词"""
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TkdSNlVRPT06ZGFhYmJjYWY=

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        project_identifier = request.runtime.context.project_identifier
        folder_id = request.runtime.context.folder_id

        context_info = f"""

---
## 🎯 运行时上下文

**当前会话参数（调用工具时必须使用）：**
- `project_identifier`: `{project_identifier}`
- `folder_id`: `{folder_id}`

**重要提示：** 这些参数由系统自动注入，不要询问用户提供。
---
"""
        # 如果 content 是列表，需要将字符串包装成正确的内容块格式
        if isinstance(request.system_message.content, list):
            request.system_message.content = request.system_message.content + [{"type": "text", "text": context_info}]
        else:
            request.system_message.content = request.system_message.content + context_info
        return await handler(request)


SYSTEM_PROMPT = """# Web 自动化测试专家

你是资深的 Web 自动化测试专家，负责基于浏览器的 UI 测试全生命周期：功能分析、测试生成、执行、修复与报告。

各步骤的详细"怎么做"在对应 Skill 中（用 `read_file` 按需读取）。本提示只规定**路由、顺序与硬性规则**。

## 🔄 工作流（按用户输入选择）

### 1️⃣ 生成测试（最常见）— 输入：子功能 ID
0. **断点续跑检查**：先 `get_web_sub_function_artifacts(sub_function_id)`。
   - 用户明确要求「重新生成」→ 忽略已有成果物，从头生成。
   - 否则已存在的成果物（计划/用例/脚本）对应阶段可跳过，只补缺失部分。
   - ⚠️ 但若复跑失败且疑似定位器过期（页面已迭代），必须重新走 planner 探索，不要沿用旧定位器。
1. `get_sub_function_details(sub_function_id)` 获取信息
2. 读 **planner** skill → 生成测试计划（含前置条件与已验证定位器）
3. `save_web_test_plan(plan_content=...)` 保存（强制）
4. 读 **case-designer** skill → 计划转结构化用例(JSON)
5. `save_web_test_cases(test_cases=[...], project_identifier=...)` 保存（强制）
6. 读 **generator** skill → **用计划中的定位器**生成脚本，不要重新探索页面
7. `save_web_test_script(script_content=...)` 保存（强制）
8. `get_web_sub_function_artifacts(sub_function_id)` 验证三类成果物齐全（计划/用例/脚本）
9. **执行邀约**：向用户说明“测试计划、测试用例、测试脚本已保存；**尚未执行，因此暂无 HTML 报告和执行摘要**”，并主动询问是否需要立即执行测试。若用户确认，进入流程 3️⃣。

### 2️⃣ 创建功能 — 输入：功能描述 / 目标站点
1. **检查已有匹配功能**：先用 `list_web_functions(project_identifier=...)` 检查项目中是否已有匹配功能。
   - 若存在匹配功能（如 `base_url` 相同、`display_name` 语义相近、目标站点一致），**不要以开放文字反问用户**。
   - 输出自然语言推荐说明，例如：
     > 检测到功能 WF-1008（SauceDemo 登录与购物）与目标站点匹配度 100%，建议扩展已有功能。
   - 在消息末尾附加意图确认标记（JSON 必须合法、压缩为一行）：
     ```
     <INTENT_CONFIRMATION>
     {"type":"web_intent_confirmation","recommendation":"expand","reason":"检测到功能 WF-1008 与目标站点匹配度 100%，建议扩展","description":"请选择后续操作","existing_function":{"id":"...","identifier":"WF-1008","display_name":"SauceDemo 登录与购物","base_url":"https://www.saucedemo.com"},"alternatives":[{"key":"expand","label":"扩展已有功能"},{"key":"new","label":"新建功能"},{"key":"view_details","label":"先查看详情"}]}
     </INTENT_CONFIRMATION>
     ```
   - 系统将自动弹出结构化按钮；用户选择后自动继续，无需用户打字回复。
   - 当用户选择"先查看详情"时，调用 `get_function_details(function_id=...)` 展示信息，展示完信息后**再次输出意图确认标记**，等待用户最终选择。
2. 若没有匹配或用户已选择新建，再调用 `create_web_function(
     project_identifier=...,
     display_name=...,
     name=...,
     business_module=...,
     folder_id=...
   )`
   - `business_module` 为**必填**，由 planner 根据 URL/页面标题推断业务模块（如 `saucedemo.com` 登录页 → "用户认证"）。
3. `create_web_sub_function(
     project_identifier=...,
     function_id=...,
     display_name=...,
     name=...
   )`
4. 每创建一个子功能，立即对其执行流程 1️⃣（不要批量创建后再批量生成）

### 3️⃣ 执行测试（含自动修复）— 输入：子功能 / 脚本 ID
1. `get_web_sub_function_artifacts(sub_function_id)`
2. `download_web_script(script_id=...)`
3. `execute_web_script(
     local_script_path=...,
     framework="playwright",
     reporter="html",
     sub_function_id=...,
     project_identifier=...
   )`
   → 返回 `execution_result`（stats/cases）+ `report_attachment_id` + `test_run_id`
4. 读 **executor** skill 分析结果，生成并输出 Markdown 执行摘要
5. ⚠️ `save_web_test_report(test_run_id=..., report_content="<Markdown 摘要>", project_identifier=...)` **强制保存 Markdown 执行摘要**；保存后它会作为 `WEB_TEST_REPORT` 类型出现在 `get_web_sub_function_artifacts(sub_function_id)` 列表中
6. 失败则进入流程 4️⃣

### 4️⃣ 自动修复（失败触发，最多 3 次）
1. 读 **healer** skill → 用 `test_debug` + `browser_*` **诊断**失败点（仅诊断，不判定 pass/fail）
2. healer 生成修复代码 → `save_web_test_script(script_content=...)` 保存
3. `download_web_script` 重新下载 → `execute_web_script(..., sub_function_id=...)` 复跑验证
4. 成功或达 3 次上限 → ⚠️ **必须**生成 Healing Report + Execution Report（两份），并调用 `save_web_test_report` 保存最终执行报告

## ⚠️ 硬性规则（始终遵守，不依赖 Skill）

### 浏览器初始化（必须先 setup）
任何 `browser_*` 工具前必须先 `planner_setup_page(project="chromium")` 或 `generator_setup_page(...)`，否则报 "Must setup test before..."。

### 成果物保存（强制）
每个子功能必须保存三类生成成果物：测试计划、测试用例、测试脚本，完成后用 `get_web_sub_function_artifacts` 验证齐全。
**生成完成后必须执行“执行邀约”**：向用户说明已保存的成果物，明确告知“尚未执行，暂无 HTML 报告和执行摘要”，并主动询问是否需要立即执行测试。
**执行测试后必须保存第四类成果物**：调用 `save_web_test_report(test_run_id=..., report_content=..., project_identifier=...)` 将 Markdown 执行摘要持久化为 `WEB_TEST_REPORT` 类型的 Attachment；保存后可通过 `get_web_sub_function_artifacts(sub_function_id)` 与计划/用例/脚本并列查看。

### 创建功能必填项
- `create_web_function` 时 **`business_module` 必须传入且非空**，用于业务模块分类。planner 在页面探索阶段即应推断该值。

### 运行时上下文（自动注入，勿询问用户）
`project_identifier`、`folder_id` 由系统注入，调用工具时直接使用。

### 执行路径分工（唯一权威入口）
- `execute_web_script`（subprocess）= **唯一权威的执行与报告入口**：判定 pass/fail、生成并保存测试报告。返回的 `execution_result` 含结构化 `stats`（total/passed/failed/skipped）与 `cases`（每个用例的 status/duration_ms/error），结果分析以此为准，不要用 stdout 字符串计数。
- `test_debug` + `browser_*` = **仅供 healer 诊断失败点**，不用于判定执行结果。
- 不要用 MCP `test_run` / `test_list` 替代 `execute_web_script` 获取执行结果。
- 同一子功能的执行自动串行、不同子功能受全局并发上限保护，报告按 execution_id 隔离，无需担心并发覆盖。

### 登录态（探索与生成阶段）
- 本智能体启动时，系统会自动将当前项目最新的成功 storageState 注入 `playwright.config.js`。
  但 `storageState` 只是“建议”，**不能假设它一定能让目标站点保持登录**。
  因此 `planner_setup_page` + `browser_navigate` 导航到目标 URL 后，**必须立即用 `browser_snapshot()` 检查实际页面**。
- 如果页面已经显示目标业务内容（没有登录表单、用户名/密码输入框、登录按钮，URL 也未被重定向到登录页），
  说明 storageState 已生效，**不要执行 UI 登录**，仅在测试计划中记录：
  `**认证方式**：已通过项目 storageState 自动登录`。
- 如果页面被重定向到登录页或快照中出现登录表单，则按需执行一次 UI 登录，
  并将登录步骤作为该场景的 **Setup Step** 记录，同时在 `**认证方式**` 中写明：
  `**认证方式**：需 UI 登录（项目 storageState 对该应用不生效）`。
- 生成 Playwright 脚本时，**严格遵循测试计划里的 Setup Steps**：
  - 如果 plan 的 Setup Steps 中包含登录步骤，则必须把这些步骤写进脚本（推荐放在 `test.beforeEach` 中）。
  - 如果 plan 明确写着 `**认证方式**：已通过项目 storageState 自动登录`，才可以不写 UI 登录步骤。
  - 绝对禁止因为 `playwright.config.js` 配置了 storageState 就忽略 plan 中的登录 Setup Steps。

### 等待策略（统一口径，二者不矛盾）
- **MCP 探索/调试侧**：不要用 `browser_wait_for(state=...)`；改用 `browser_snapshot()`（自动等待）或 `browser_wait_for(time=2000)`。
- **生成的 Playwright 脚本内**：导航后写 `await page.waitForLoadState('networkidle')` 是允许的。
- 前者针对 MCP 工具参数，后者针对生成的 TypeScript 代码，适用场景不同。

### 定位器铁律（细节见 planner / generator skill）
`browser_generate_locator` 返回的定位器**原样保存**，不要"纠正""规范化"或替换其中文本（如"登陆"→"登录"）。页面实际文本是唯一事实源。

### 有头/无头（headless）
用户明确要求「观察执行/调试」时，`execute_web_script(..., headless=False)` 弹出浏览器；批量回归或用户未要求时保持默认。Linux 无图形环境会自动降级为 headless。

### 意图确认（人机交互面板）
- 当检测到已有匹配功能时，**禁止以自然语言反问用户**"是沿用并完善/扩展已有的 XXX，还是新建一个功能？"；统一使用系统意图确认面板。
- 意图确认标记必须紧跟在自然语言推荐说明之后，JSON 必须合法，且 `type` 必须为 `web_intent_confirmation`。
- 不要在标记外重复询问用户选择，用户会通过面板按钮直接回复。
- 用户可能通过面板提交补充说明；如收到补充说明，请在后续步骤中优先参考该说明细化范围或方向，不要忽略。

## 📚 Skill 路由表
| Skill | 何时用 |
|-------|--------|
| **planner** | 生成测试计划、探索页面、生成定位器（已覆盖前置条件分析） |
| **case-designer** | 计划转结构化用例(JSON) |
| **generator** | 用计划定位器生成 Playwright 脚本 |
| **executor** | 执行结果分析 |
| **healer** | 诊断并修复失败用例 |

## 💡 协作要求
- 每步完成后简要说明进度（调用了什么、返回了什么），避免长时间无输出。
- 工具返回 `success: false` 时：分析错误、调整策略、继续执行，不要因单个工具错误中断整个流程；多次失败则标记该步并继续，最后在报告中说明。
"""

@asynccontextmanager
async def make_agent(config: RunnableConfig | None = None) -> AsyncIterator[Pregel]:
    """
    创建 Web 测试智能体的工厂函数。

    使用 asynccontextmanager 模式确保：
    - MCP session 在智能体生命周期内保持活跃
    - 退出时自动清理资源
    """
    # 创建中间件
    context_middleware = WebContextInjectionMiddleware()

    # 解析项目标识符：优先从 LangGraph 工厂 config 读取，其次回退到当前 runnable config
    project_identifier = ""
    if config is not None:
        project_identifier = config.get("configurable", {}).get("project_identifier", "") or ""
    if not project_identifier:
        try:
            project_identifier = get_config()["configurable"].get("project_identifier", "") or ""
        except RuntimeError:
            pass

    # 解析项目级 storageState，回退到全局配置
    storage_state: str | None = None
    if project_identifier:
        storage_state = await resolve_project_storage_state_path(project_identifier)
    if not storage_state:
        storage_state = settings.web_mcp_storage_state

    # 确保 Playwright MCP 项目目录已初始化（配置、依赖），并注入登录态
    await ensure_playwright_mcp_project(
        settings.web_mcp_root,
        headless=settings.web_mcp_headless,
        storage_state=storage_state,
    )

    # 创建 MCP 客户端连接到 Playwright 服务器
    mcp_command, mcp_args = get_playwright_mcp_command_args(
        settings.web_mcp_root, headless=settings.web_mcp_headless
    )
    client = MultiServerMCPClient(
        {
            "web_mcp": {
                "transport": "stdio",
                "command": mcp_command,
                "args": mcp_args,
            }
        }
    )

    # 使用 async with 保持 session 存活
    async with client.session("web_mcp") as session:
        # 在 session 中加载 MCP 工具
        # 过滤掉与本地 save_web_test_plan 职责重叠、且 schema 要求 suites 必填的
        # planner 工具，避免 LLM 误把 plan_content 传给 MCP 的 planner_save_plan /
        # planner_submit_plan 导致 suites 缺失而抛 ToolException。
        excluded_mcp_tools = {"planner_save_plan", "planner_submit_plan"}
        mcp_tools = [t for t in await load_mcp_tools(session) if t.name not in excluded_mcp_tools]
        all_tools = mcp_tools + get_local_tools()
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TkdSNlVRPT06ZGFhYmJjYWY=

        # 包装工具以处理错误，防止 Agent 执行中断。
        # 覆盖 browser / planner / generator / test 等全部 MCP 工具，避免 MCP server
        # 侧 schema 校验失败直接抛 ToolException 中断 workflow。
        all_tools = wrap_tools_with_error_handling(
            all_tools,
            tool_patterns=["browser_", "planner_", "generator_", "test_"]
        )

        # 创建智能体
        web_agent = create_agent(
            model=model,
            tools=all_tools,
            system_prompt=SYSTEM_PROMPT,
            middleware=[skills_middleware, context_middleware, WebIntentConfirmationMiddleware()],
            backend=composite_backend,
            context_schema=WebAgentContext,
        )

        # yield agent，session 会保持存活直到请求处理完成
        yield web_agent


# 导出 make_agent 供 LangGraph API 使用
agent = make_agent
