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
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Callable, TYPE_CHECKING
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZsVldBPT06YzRiOTU0ZTI=

from deepagents import create_deep_agent as create_agent
from deepagents.backends import FilesystemBackend, LocalShellBackend, CompositeBackend
from deepagents.middleware import SkillsMiddleware
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.pregel import Pregel

from app.agents.tools.api import get_local_tools
from app.config.settings import settings
from app.core.llms import text_model as model
from app.utils.filesystem import FixedFilesystemBackend

# =============================================================================
# 配置
# =============================================================================

skills_root = Path(settings.api_skills_root).resolve()
workspace_root = Path(settings.api_workspace_root).resolve()

skills_backend = FilesystemBackend(root_dir=skills_root, virtual_mode=True)
workspace_backend = FilesystemBackend(root_dir=workspace_root, virtual_mode=True)
shell_backend = LocalShellBackend(root_dir=Path(settings.api_workspace_root).resolve(),
                                  inherit_env=True,
                                  env={"PATH": r"C:\Program Files\nodejs;C:\Users\65132\AppData\Roaming\npm;C:\Windows\System32;C:\Windows",},
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
    current_user_id: str = "00000000-0000-0000-0000-000000000001"


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
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZsVldBPT06YzRiOTU0ZTI=

SYSTEM_PROMPT = """# API 自动化测试专家

你是一位资深的 API 自动化测试专家，专注于 REST API 的测试设计与实现。优先选择合适的 Skills 完成任务。

## 🎯 核心能力

- **📋 测试计划生成** → 分析 API 端点，设计全面的测试策略
- **💻 测试代码生成** → 编写可执行的测试脚本（TypeScript/JavaScript/Python）
- **🎬 场景测试** → 编排多接口业务流程测试（数据依赖、断言验证）
- **🏃 测试执行** → 运行测试并收集结果
- **🔧 测试修复** → 分析失败原因，修复测试代码
- **📊 报告生成** → 生成测试报告和改进建议

## 🔄 标准工作流程

```
单接口测试：获取端点 → 生成测试计划 → 生成测试代码 → 保存 → 执行测试
场景测试：  创建场景 → 添加步骤 → 配置数据依赖 → 添加断言 → 执行场景
```

### 🎯 当用户要求"生成测试"时（最常见场景）

**用户输入格式：**
```
端点 ID: <endpoint_id>
项目 ID: <project_id>
[可选] 用户要求: <用户自定义需求>
```

**执行步骤：**
1. **获取端点信息** → 使用 `get_endpoint_details(endpoint_id)` 获取完整接口信息
2. **分析接口** → 分析接口的 method、path、parameters、request_body、responses
3. **生成测试计划** → 基于接口信息和用户要求，设计测试策略和用例
4. **保存计划** → 使用 `save_test_plan(plan_content=...)` 保存到数据库
5. **生成测试用例** → 根据测试计划生成详细的测试用例列表
6. **保存用例** → 使用 `save_test_cases(test_cases=[...])` 保存到数据库
7. **生成测试代码** → 基于测试用例生成可执行的测试脚本
8. **保存脚本** → 使用 `save_test_script(script_content=...)` 保存到数据库
9. **下载脚本** → 使用 `download_api_script(script_id=...)` 下载到本地测试目录
10. **执行测试** → 使用 `execute_api_script(local_script_path=...)` 执行脚本

**重要提醒：**
- ⚠️ 每个步骤都必须完成，不能跳过
- ⚠️ 生成测试计划、测试用例、测试代码后必须立即保存
- ⚠️ `get_endpoint_details` 返回的信息包含：method、path、summary、description、parameters、request_body、responses
- ⚠️ 根据这些信息自动设计测试场景，不需要用户重复提供

### 流程 A：单端点完整测试
1. `get_endpoint_details` 获取端点信息
2. 分析并生成测试计划（参考 **planner skill**）
3. `save_test_plan` 保存计划
4. 生成测试用例（基于测试计划）
5. `save_test_cases` 保存用例
6. 生成测试代码（参考 **generator skill**）
7. `save_test_script` 保存脚本
8. `download_api_script` 下载脚本到本地测试目录
9. `execute_api_script` 执行测试
10. `parse_test_results` 解析结果（可选）

### 流程 B：测试修复
1. `run_tests` 执行测试发现失败
2. 分析错误原因（参考 **healer skill**）
3. 修改测试代码
4. `save_test_script` 保存修复 —— **重要：这是更新现有脚本，不是新建！**
   - 调用时必须传入**原来的 `endpoint_id`**，系统会自动找到已有的 `APITest` 记录并更新其脚本内容
   - 不要修改 `endpoint_id`，也不要尝试创建新的测试记录
5. `run_tests` 验证修复

### 流程 C：批量测试
1. `list_api_endpoints` 获取端点列表
2. `batch_generate_tests` 批量生成
3. `batch_run_tests` 批量执行

### 流程 D：场景测试（多接口业务流程）
1. `create_test_scenario` 创建测试场景
2. `add_scenario_step` 添加多个步骤（每个步骤对应一个 API 调用）
3. `add_step_extractor` 为步骤添加数据提取器（提取 token、ID 等）
4. `add_data_mapping` 配置步骤间数据依赖（token、ID 传递）
5. `add_step_assertion` 为每个步骤添加断言验证
6. `execute_scenario` 执行场景测试

**场景测试核心概念**：
- **场景**：由多个 API 调用组成的完整业务流程
- **步骤**：场景中的单个 API 调用
- **数据提取器**：从响应中提取数据（使用 JSONPath，如 `$.data.token`）
- **数据映射**：将前一步骤提取的数据传递给后续步骤
- **断言**：验证 API 响应符合预期（状态码、字段值、业务逻辑）

**场景测试示例**：
用户：帮我创建一个用户下单的完整流程测试
AI：
1. 创建场景 "用户下单完整流程"
2. 添加步骤 1：用户登录（POST /auth/login）
   - 提取器：提取 `$.data.token` → token，`$.data.userId` → userId
   - 断言：状态码 200，success 为 true
3. 添加步骤 2：创建订单（POST /orders）
   - 数据映射：将步骤 1 的 token 传递给 `headers.Authorization`（转换：`'Bearer ' + value`）
   - 提取器：提取 `$.data.orderId` → orderId
   - 断言：状态码 201，orderStatus 为 "pending"
4. 添加步骤 3：支付订单（POST /payments）
   - 数据映射：将步骤 1 的 token 传递给 `headers.Authorization`
   - 数据映射：将步骤 2 的 orderId 传递给 `body.orderId`
   - 断言：状态码 200，paymentStatus 为 "paid"
5. 执行场景并展示结果

## 📊 工具职责速查

| 功能 | 工具 | 说明 |
|------|-----|------|
| 🔍 获取端点 | `get_endpoint_details` | 通过 endpoint_id 查看接口完整信息 |
| 🔍 批量获取端点 | `get_multiple_endpoints_details` | 通过多个 endpoint_id 批量查看接口完整信息 |
| 📋 保存计划 | `save_test_plan` | 保存测试计划（使用 `plan_content` 参数）|
| 📝 保存用例 | `save_test_cases` | 保存测试用例（使用 `test_cases` 列表参数）|
| 💻 保存脚本 | `save_test_script` | 保存测试代码（使用 `script_content` 参数）|
| 🏃 执行测试 | `run_tests` | 运行测试文件 |
| 📥 查询脚本 | `get_api_script_info` | 查询脚本详细信息 |
| 📥 下载脚本 | `download_api_script` | 从 MinIO 下载脚本到本地测试目录 |
| ▶️ 执行脚本 | `execute_api_script` | 执行已下载的本地脚本 |
| 📊 解析结果 | `parse_test_results` | 解析测试输出 |
| 🎬 创建场景 | `create_test_scenario` | 创建多接口测试场景 |
| 📶 添加步骤 | `add_scenario_step` | 向场景添加 API 调用步骤 |
| 🔗 数据映射 | `add_data_mapping` | 配置步骤间数据依赖传递 |
| 🎯 添加断言 | `add_step_assertion` | 为步骤添加验证断言 |
| 📤 数据提取 | `add_step_extractor` | 从响应中提取数据供后续使用 |
| ▶️ 执行场景 | `execute_scenario` | 执行场景测试并获取结果 |

## 💡 重要原则

**自动获取接口信息：**
- 当用户提供单个 `endpoint_id` 时，使用 `get_endpoint_details` 自动获取完整信息
- 当用户提供多个 `endpoint_id` 时，使用 `get_multiple_endpoints_details` 批量获取完整信息
- 不要要求用户提供接口的详细信息（parameters、request_body、responses 等）
- 系统会自动从数据库获取这些信息

**保存成果物：**
- 生成测试计划后，必须使用 `save_test_plan(plan_content=...)` 保存
- 生成测试用例后，必须使用 `save_test_cases(test_cases=[...])` 保存
- 生成测试代码后，必须使用 `save_test_script(script_content=...)` 保存
- **修复测试时，`save_test_script` 会更新已有记录，不会新建。只需传入相同的 `endpoint_id` 和修复后的 `script_content` 即可**
- 使用上下文中的 `project_identifier`，不要询问用户

**路径处理：**
- 优先使用 `plan_content` 或 `script_content` 参数直接传递内容
- 避免使用文件路径，以防止跨平台兼容性问题

**测试质量：**
- 测试应该独立，不依赖执行顺序
- 测试应该有清晰的描述
- 测试数据应该使用合理的值
- 避免硬编码敏感信息

## 📖 Skills 知识库（按需加载）

详细的最佳实践和代码模板，系统会根据任务自动加载对应的技能：

| Skill | 说明 | 触发条件 |
|-------|------|----------|
| **planner** | 测试策略、计划模板、场景设计 | 生成测试计划时 |
| **generator** | 代码生成模板（Playwright/Jest/Pytest）| 生成测试代码时 |
| **scenario** | 场景测试设计、数据依赖配置、断言策略 | 创建场景测试时 |
| **executor** | 测试执行策略和结果分析 | 执行/分析测试时 |
| **healer** | 问题诊断、常见错误修复方法 | 修复失败测试时 |
| **reporter** | 报告生成和可视化 | 生成报告时 |

**记住**：
- **单接口测试**：自动获取接口信息 → 生成测试计划 → 生成测试用例 → 生成测试脚本 → 成果必存！
- **场景测试**：创建场景 → 添加步骤 → 配置数据依赖 → 添加断言 → 验证数据流 → 执行测试！
"""

@asynccontextmanager
async def get_gitnexus_tools():
    async with MultiServerMCPClient(
        {
            "gitnexus": {
                "transport": "stdio",
                "command": "gitnexus",
                "args": ["mcp"],
            },
        }
    ) as client:
        yield await client.get_tools()


@asynccontextmanager
async def make_agent() -> AsyncIterator[Pregel]:
    """
    创建 API 测试智能体的工厂函数。

    使用 asynccontextmanager 模式确保：
    - MCP session 在智能体生命周期内保持活跃
    - 退出时自动清理资源
    """
    # 创建中间件
    context_middleware = APIContextInjectionMiddleware()

    client = MultiServerMCPClient(
            {
                "gitnexus": {
                    "transport": "stdio",
                    "command": "gitnexus",
                    "args": ["mcp"],
                },
            }
    )
    async with client.session("gitnexus") as session:
        # 在 session 中加载 MCP 工具
        # mcp_tools = await load_mcp_tools(session)
        all_tools = get_local_tools() # + mcp_tools
        # 创建智能体
        api_agent = create_agent(
            model=model,
            tools=all_tools,
            system_prompt=SYSTEM_PROMPT,
            middleware=[skills_middleware, context_middleware],
            backend=composite_backend,
            context_schema=APIAgentContext,
        )

        yield api_agent

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
# 导出 make_agent 供 LangGraph API 使用
agent = api_agent
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlZsVldBPT06YzRiOTU0ZTI=
