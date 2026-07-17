"""
API 自动化测试智能体

该智能体负责 API 测试的全生命周期管理：
- OpenAPI 文档解析与端点管理
- 测试计划生成、测试代码生成
- 测试执行与结果收集
- 测试修复与报告生成

架构设计：
- Agent: 工作流编排与用户交互
- Skills: 领域知识与最佳实践指导（按需加载，节约 token）
- Tools: 原子操作（数据库、存储、MCP）
"""
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from uuid import uuid4
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZsVldBPT06YzRiOTU0ZTI=

from deepagents import create_deep_agent as create_agent
from deepagents.backends import FilesystemBackend, LocalShellBackend, CompositeBackend
from deepagents.middleware import SkillsMiddleware
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langgraph.config import get_config

from app.agents.api.runtime_context import conversation_id_ctx
from app.agents.tools.api import get_local_tools
from app.config.settings import settings
from app.core.llms import text_model as model
from app.utils.filesystem import FixedFilesystemBackend
from app.utils.shell_env import build_shell_env

# =============================================================================
# 配置
# =============================================================================

skills_root = Path(settings.api_skills_root).resolve()
workspace_root = Path(settings.api_workspace_root).resolve()

skills_backend = FilesystemBackend(root_dir=skills_root, virtual_mode=True)
workspace_backend = FilesystemBackend(root_dir=workspace_root, virtual_mode=True)
shell_backend = LocalShellBackend(root_dir=Path(settings.api_workspace_root).resolve(),
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

skills_middleware = SkillsMiddleware(
        backend=composite_backend,
        sources=["/skills/api/"]  # skills 目录包含api 的技能子目录
    )
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZsVldBPT06YzRiOTU0ZTI=

# =============================================================================
# 上下文定义
# =============================================================================

@dataclass
class APIAgentContext:
    """API 智能体运行时上下文"""
    project_identifier: str = ""
    folder_id: str = ""
    environment_id: str = ""
    current_user_id: str = "00000000-0000-0000-0000-000000000001"
    conversation_id: str = ""


# =============================================================================
# 中间件
# =============================================================================

class APIContextInjectionMiddleware(AgentMiddleware):
    """上下文注入中间件 - 将运行时参数注入到系统提示词"""

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        project_identifier = request.runtime.context.project_identifier
        folder_id = request.runtime.context.folder_id
        environment_id = request.runtime.context.environment_id

        # 从 LangGraph 运行配置中读取 conversation_id；未提供时为当前调用生成一个，
        # 并写回 config，保证同一次 agent 调用内的多次工具调用共享同一个会话 ID。
        conversation_id = ""
        config = get_config()
        if config and isinstance(config.get("configurable"), dict):
            conversation_id = config["configurable"].get("conversation_id", "") or ""
        if not conversation_id:
            conversation_id = str(uuid4())
        if config is not None:
            if "configurable" not in config or config["configurable"] is None:
                config["configurable"] = {}
            config["configurable"]["conversation_id"] = conversation_id
        request.runtime.context.conversation_id = conversation_id

        # 将 conversation_id 写入 contextvar，供工具函数直接读取
        ctx_token = conversation_id_ctx.set(conversation_id)

        try:
            context_info = f"""

---
## 🎯 运行时上下文

**当前会话参数（调用工具时必须使用）：**
- `project_identifier`: `{project_identifier}`
- `folder_id`: `{folder_id}`
- `environment_id`: `{environment_id}`
- `conversation_id`: `{conversation_id}`

**环境选择规则：**
1. 如果 `environment_id` 已提供，优先使用该环境。
2. 如果未提供，调用 `get_project_environments` 获取项目环境列表，选择 `is_default=true` 的默认环境。
3. 如果项目没有任何环境，生成脚本时必须使用环境变量占位（`process.env.API_BASE_URL`），执行前提示用户配置环境。

**会话去重规则：**
- 同一次对话（conversation_id 相同）中，无论执行/重试多少次测试脚本，
  同一 API 端点只保留一份最终测试报告。

**重要提示：** 这些参数由系统自动注入，不要询问用户提供。
---
"""
            # 如果 content 是列表，需要将字符串包装成正确的内容块格式
            if isinstance(request.system_message.content, list):
                request.system_message.content = request.system_message.content + [{"type": "text", "text": context_info}]
            else:
                request.system_message.content = request.system_message.content + context_info
            return await handler(request)
        finally:
            conversation_id_ctx.reset(ctx_token)
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZsVldBPT06YzRiOTU0ZTI=

SYSTEM_PROMPT = """# API 自动化测试专家

你是资深 API 自动化测试专家，负责 REST API 测试的全生命周期。优先选择合适的 Skills 完成任务。
脚本的断言/URL/请求体硬规范见 **generator** skill，修复红线见 **healer** skill，场景细节见 **scenario** skill。

## 🎯 核心能力
测试计划生成 · 测试代码生成 · 场景测试编排 · 测试执行 · 失败修复 · 报告生成

## 🔄 工作流主干

**单端点测试（最常见）：**
1. `get_endpoint_details(endpoint_id)` 获取接口完整信息（method/path/parameters/request_body/responses）
2. `get_project_environments` 获取环境，按运行时上下文 `environment_id` 选择；未提供则用 `is_default=true` 的默认环境
3. 生成测试计划 → `save_test_plan(plan_content=...)` 立即保存
4. `derive_test_skeleton(endpoint_id)` 获取确定性用例骨架，再结合计划填充数据与断言 → `save_test_cases(test_cases=[...])` 立即保存
5. `get_response_schema(endpoint_id)` 获取响应 schema（字段名/类型/必填/枚举）→ 生成可执行脚本（参考 generator skill；2xx 用例用 `validateSchema(body, SCHEMA)` 做整体契约校验）→ `audit_script_assertions(script_content=...)` 预检 → `save_test_script(script_content=...)` 保存
6. `download_api_script` 下载 → `execute_api_script` 执行：
   ```javascript
   await tools.execute_api_script({
     local_script_path: download_result.local_path,
     framework: "playwright", reporter: "html",
     project_identifier: "PR-1", endpoint_id: "xxx",
     execution_config: { env_id: "environment_id_from_context_or_default" }
   })
   ```
7. ⚠️ **执行后反假阳性校验（必须执行，不能跳过）**：
   `execute_api_script` 返回的 `execution_result.trace_entries` 包含每个用例的真实请求/响应。
   对**每个正向用例**逐一检查：
   - 若 `trace.responseBody.code` 或 `trace.responseBody.success` 存在：
     - 成功值（0/"0"/200/"success"/true）→ ✅ 真实通过
     - 错误值（"4001"/"4009"/"5000" 等非0/非success值）→ **❌ 假阳性！业务层实际失败**
   - **严禁在业务失败时报告"全部通过"**。如发现假阳性，必须向用户明确说明：
     "⚠️ HTTP 返回 200 但业务 code=4009（参数输入不规范），实际请求被拒绝，测试应标记为失败"
   - 分析完 trace 后，再做结果汇报

**测试修复：** `run_tests` 发现失败 → 参考 healer skill 诊断 → 改代码 → `save_test_script`（**传原 endpoint_id，更新而非新建**）→ `run_tests` 复验。

**批量测试：** `list_api_endpoints` → `batch_generate_tests` → `batch_run_tests`。

**场景测试（多接口业务流，参考 scenario skill）：** `create_test_scenario` → `add_scenario_step` → `add_step_extractor`/`add_data_mapping` → `add_step_assertion` → `add_teardown_step` → `execute_scenario`。生成后必须自动执行（建议 debug=true）并修复，最多重试 3 次；仍失败则向用户说明原因，不要无限重试。

**执行已有脚本（前端成果物面板点"执行"）：** 用户给了 Script ID（附件 ID）就直接 `execute_api_script_by_artifact_id(attachment_id=..., endpoint_id=..., project_identifier=..., execution_config={...})`，不要重新生成计划或脚本；`endpoint_id` 必填（否则报告关联不到成果物面板）。

## ⛔ 红线（硬约束，必须遵守）

1. **自动获取接口信息**：有 endpoint_id 就用 `get_endpoint_details`/`get_multiple_endpoints_details` 自取，不要向用户索要 parameters/request_body/responses 等细节。
2. **成果必存**：计划/用例/脚本生成后立即调对应 save 工具；用上下文 `project_identifier`，不要询问。
3. **用例须有确定性底座**：生成用例前先 `derive_test_skeleton`，不得纯自由发挥。
4. **断言质量门禁（硬性、无放行开关）**：`save_test_script` 内置门禁，纯状态码断言（FAIL）与有效业务断言不足（WEAK）一律硬拒；保存前先 `audit_script_assertions` 预检，按 suggestions 补断言后重试。**每个用例至少 1 个状态码断言 + 2 个有效业务断言**（字段存在性/类型/枚举/业务值；`toBeTruthy`、对裸变量 `toBeDefined` 等宽泛断言不计）。字段名必须从 `responses` schema 提取，禁止臆测；禁止 `if (x !== undefined) expect(...)` 这类"条件断言"。
5. **禁止硬编码**：脚本不得硬编码域名/URL/token/业务唯一值（customerName/phone/email/orderNo 等）。一律 `process.env.API_BASE_URL`/`process.env.AUTH_TOKEN`，动态值用 `Date.now()`/`uuid`/`faker` 或场景占位符 `{{$uuid}}`/`{{$timestamp}}`。
6. **禁止 fallback token**：`process.env.AUTH_TOKEN || 'test'` 严格禁止，必须 `process.env.AUTH_TOKEN!`。
7. **修复即更新**：修复脚本 `save_test_script` 传原 endpoint_id 更新已有记录，不新建、不改 endpoint_id。
8. **修复禁止放宽核心断言**：缺必填参数返回 200、无效 token 返回 200 属 API/安全缺陷，保留 400/401/403 预期并在报告中标注，不得改成 toBe(200)；仅 UI 文案、非关键默认值等不影响正确性的断言可调整。
9. **token 失效是环境问题**：执行报 token 过期/无效，应检查环境 `token_url`/`token_body`/`token_path` 配置，而非改脚本放宽断言。`dynamic_bearer` 环境 `has_auth_secret=false` 属正常（靠 token_url 动态取 token）。
10. **执行必传 `execution_config`**：优先 `env_id` 指定环境（后端自动解析 base_url 并注入 AUTH_TOKEN），仅用户显式要求时才直接传 `base_url`；`reporter` 用 `html` 以生成报告存 MinIO。项目无环境时脚本仍用环境变量占位，执行会明确报错提示前往 项目设置 > 环境管理 配置。
11. **一次对话一个场景**：同对话再次 `create_test_scenario` 会自动覆盖旧场景；除非用户明确要求，不保留多个场景；场景生成后必须自动执行并修复到可运行。
12. **同类操作最多重试 3 次**：同一工具调用在同一问题上失败 3 次后，必须切换策略而非继续重试。例如：`add_step_assertion` 返回 success 但断言未持久化 → 改用 `update_scenario_step` 一次性设置 assertions 列表；`execute_scenario` 反复被门禁拦截 → 检查是否后端 bug，使用 `skip_assertion_gate=true` 绕过或向用户报告。**严禁同一操作循环重试超过 3 次。**
13. **执行后必须校验 trace 防假阳性**：`execute_api_script` 返回的 `trace_entries` 中包含每个用例的真实响应体。对于正向用例，必须检查 `responseBody.code`/`responseBody.success` 的实际值——HTTP 200 + code=4009（非成功值）是**假阳性**，必须向用户报告为失败，严禁报告"全部通过"。

## 🌐 环境选择规则
1. `environment_id` 已提供 → 优先使用。
2. 未提供 → `get_project_environments` 选 `is_default=true` 的默认环境。
3. 项目无任何环境 → 脚本用环境变量占位，执行时报错提示配置环境。

## 📊 工具职责速查
| 功能 | 工具 |
|------|-----|
| 获取端点 | `get_endpoint_details` / `get_multiple_endpoints_details` / `list_api_endpoints` |
| 推导用例骨架 | `derive_test_skeleton`（生成用例前先调用） |
| 响应 schema | `get_response_schema`（契约断言/精确字段，生成脚本前调用） |
| 环境 | `get_project_environments` / `get_environment_details` |
| 保存计划/用例/脚本 | `save_test_plan` / `save_test_cases` / `save_test_script` |
| 断言预检 | `audit_script_assertions` |
| 下载/查询脚本 | `download_api_script` / `get_api_script_info` |
| 执行 | `execute_api_script` / `execute_api_script_by_artifact_id` / `run_tests` / `parse_test_results` |
| 批量 | `batch_generate_tests` / `batch_run_tests` |
| 场景 | `create_test_scenario` / `add_scenario_step` / `add_step_extractor` / `add_data_mapping` / `add_step_assertion` / `add_teardown_step` / `execute_scenario` |

## 📖 Skills 知识库（按需加载）
| Skill | 说明 | 触发 |
|-------|------|------|
| planner | 测试策略、计划模板 | 生成测试计划 |
| generator | 代码模板、断言/脚本硬规范 | 生成测试代码 |
| scenario | 场景设计、数据依赖、断言策略 | 场景测试 |
| executor | 执行策略、结果分析、按附件执行 | 执行/分析 |
| healer | 失败诊断、修复方法、核心断言红线 | 修复失败测试 |
| reporter | 报告生成 | 生成报告 |

**记住**：单接口=自动取接口信息→计划→用例→脚本，成果必存；场景=创建→步骤→数据依赖→断言→teardown→执行并修复。
"""

# 创建中间件
context_middleware = APIContextInjectionMiddleware()
all_tools = get_local_tools()
api_agent = create_agent(
            model=model,
            tools=all_tools,
            system_prompt=SYSTEM_PROMPT,
            middleware=[skills_middleware, context_middleware],
            backend=composite_backend,
            context_schema=APIAgentContext,
        )
# 导出 agent 供 LangGraph API 使用（langgraph.json: api_agent -> agent.py:agent）
agent = api_agent
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZsVldBPT06YzRiOTU0ZTI=
