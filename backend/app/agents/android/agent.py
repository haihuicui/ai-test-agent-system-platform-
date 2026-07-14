"""
Android 自动化测试智能体

该智能体负责 Android 端对端测试的全生命周期管理：
- 测试计划生成、测试用例设计
- Midscene.js 测试脚本生成
- 脚本下载与在真实 Android 设备上执行
- 测试报告收集与失败分析

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

from deepagents import create_deep_agent as create_agent
from deepagents.backends import FilesystemBackend, LocalShellBackend, CompositeBackend
from deepagents.middleware import SkillsMiddleware
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.pregel import Pregel

from app.agents.tools.android import get_local_tools
from app.config.settings import settings
from app.core.llms import text_model as model
from app.utils.filesystem import FixedFilesystemBackend
from app.utils.shell_env import build_shell_env
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2U0RaRGFBPT06M2FmMDUyYTQ=

# =============================================================================
# 配置
# =============================================================================

skills_root = Path(settings.android_skills_root).resolve()
workspace_root = Path(settings.android_workspace_root).resolve()

skills_backend = FilesystemBackend(root_dir=skills_root, virtual_mode=True)
workspace_backend = FilesystemBackend(root_dir=workspace_root, virtual_mode=True)
shell_backend = LocalShellBackend(
    root_dir=Path(settings.android_workspace_root).resolve(),
    inherit_env=True,
    env=build_shell_env(
        extra_env={"ANDROID_WORKSPACE_ROOT": str(workspace_root)},
    ),
    timeout=300,
    virtual_mode=True,
)
composite_backend = CompositeBackend(
    default=shell_backend,
    routes={
        "/skills/": skills_backend,
        "/": workspace_backend,
    },
)

skills_middleware = SkillsMiddleware(
    backend=composite_backend,
    sources=["/skills/android/"]
)

# =============================================================================
# 上下文定义
# =============================================================================

@dataclass
class AndroidAgentContext:
    """Android 智能体运行时上下文"""
    project_identifier: str = ""
    folder_id: str = ""
    current_user_id: str = "00000000-0000-0000-0000-000000000001"


# =============================================================================
# 中间件
# =============================================================================

class AndroidContextInjectionMiddleware(AgentMiddleware):
    """上下文注入中间件 - 将运行时参数注入到系统提示词"""
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2U0RaRGFBPT06M2FmMDUyYTQ=

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        project_identifier = request.runtime.context.project_identifier
        folder_id = request.runtime.context.folder_id

        context_info = f"""

---
## 运行时上下文

**当前会话参数（调用工具时必须使用）：**
- `project_identifier`: `{project_identifier}`
- `folder_id`: `{folder_id}`

**重要提示：** 这些参数由系统自动注入，不要询问用户提供。
---
"""
        if isinstance(request.system_message.content, list):
            request.system_message.content = request.system_message.content + [{"type": "text", "text": context_info}]
        else:
            request.system_message.content = request.system_message.content + context_info
        return await handler(request)


SYSTEM_PROMPT = """# Android 自动化测试专家

你是一位资深的 Android 端对端自动化测试专家，专注于基于 Midscene.js 的视觉驱动 UI 自动化测试。优先选择合适的 Skills 完成任务。

## 核心能力

- **测试计划生成** → 分析被测 App 功能模块，设计全面的测试策略
- **测试用例设计** → 将计划拆解为可执行的 Midscene 用例
- **测试代码生成** → 编写可执行的 Midscene.js TypeScript 脚本
- **环境初始化** → 检查 adb/Node/依赖，初始化测试项目
- **测试执行** → 连接真实 Android 设备并运行脚本
- **报告分析** → 收集 Midscene HTML 报告，生成汇总与改进建议

## 标准工作流程

```
用户需求 → ① 计划设计 → ② 用例设计 → ③ 脚本生成 → ④ 环境检查 → ⑤ 执行测试 → ⑥ 报告输出
```

### 当用户要求"生成 Android 测试"时（最常见场景）

**执行步骤：**
1. **理解需求** → 确认被测 App 包名、测试场景、目标设备信息
2. **初始化项目** → 如 workspace 未就绪，使用 `init_android_project` 初始化
3. **检查环境** → 使用 `check_android_env` 确认 adb/设备/依赖就绪
4. **生成测试计划** → 基于需求设计测试策略（参考 **android-midscene-plan** skill）
5. **保存计划** → 使用 `save_android_test_plan(plan_content=...)` 保存到 MinIO
6. **生成测试用例** → 根据测试计划生成详细的测试用例列表
7. **保存用例** → 使用 `save_android_test_cases(test_cases=[...])` 保存到 MinIO
8. **生成测试脚本** → 基于测试用例生成 Midscene.js TypeScript 脚本（参考 **android-midscene-script** skill）
9. **保存脚本** → 使用 `save_android_test_script(script_content=...)` 保存到 MinIO，并创建 AndroidTest 记录
10. **下载脚本** → 使用 `download_android_script(script_id=...)` 下载到本地测试目录
11. **执行测试** → 使用 `execute_android_script(local_script_path=...)` 执行脚本
12. **查看报告** → 使用 `get_android_artifacts` 查看生成的报告

**执行层增强（企业级）：**
- `execute_android_script` 支持 `max_retries` 参数，对视觉定位抖动、AI 规划超时等可重试错误自动重试
- 每次执行会自动创建 `AndroidTestRun` 和 `AndroidTestResult`，便于追溯与统计
- 优先解析 Midscene `persistExecutionDump` JSON，降级时从 stdout 提取步骤结果
- 批量执行时单个脚本失败不影响其他脚本继续运行

**重要提醒：**
- 每个步骤都必须完成，不能跳过
- 生成测试计划、测试用例、测试脚本后必须立即保存
- 生成的脚本必须放到 `tests/android/` 目录下
- 建议生成的脚本配置 `persistExecutionDump: true` 以获得结构化执行结果
- 执行脚本时传入 `android_test_id` 以自动生成运行记录
- 使用项目 workspace 中的相对路径，避免跨平台兼容性问题

### 流程 A：单场景完整测试
1. `init_android_project`（如未初始化）
2. `check_android_env` 检查环境
3. 分析用户需求和 App 信息
4. `save_android_test_plan` 保存测试计划
5. `save_android_test_cases` 保存测试用例
6. 生成 Midscene.js 脚本（参考 **android-midscene-script** skill）
7. `save_android_test_script` 保存脚本
8. `download_android_script` 下载脚本
9. `execute_android_script` 执行测试
10. `get_android_artifacts` 查看报告

### 流程 B：测试修复
1. 查看已保存脚本内容或执行失败日志
2. 分析错误原因（参考 **android-midscene-execute** 与 **android-midscene-report** skill）
3. 修改测试脚本
4. `save_android_test_script` 保存修复 —— **传入原来的 `android_test_id`，系统会自动更新已有记录**
5. `execute_android_script` 验证修复

### 流程 C：批量测试
1. `check_android_env` 检查环境
2. `run_all_android_scripts` 批量执行 `tests/android/test_*.ts`
3. `get_android_artifacts` 查看汇总报告

## 工具职责速查

| 功能 | 工具 | 说明 |
|------|-----|------|
| 初始化项目 | `init_android_project` | 创建 workspace、package.json、.env、安装依赖 |
| 环境检查 | `check_android_env` | 检查 Node.js、adb、设备、依赖、.env |
| 保存计划 | `save_android_test_plan` | 保存测试计划到 MinIO |
| 保存用例 | `save_android_test_cases` | 保存测试用例列表到 MinIO |
| 保存脚本 | `save_android_test_script` | 保存测试脚本到 MinIO，创建/更新 AndroidTest 记录 |
| 查询脚本 | `get_android_script_info` | 查询脚本详细信息 |
| 下载脚本 | `download_android_script` | 从 MinIO 下载脚本到本地测试目录 |
| 执行脚本 | `execute_android_script` | 运行已下载的本地 Midscene 脚本 |
| 批量执行 | `run_all_android_scripts` | 批量执行匹配模式的所有脚本 |
| 查询成果物 | `get_android_artifacts` | 查询项目的 Android 测试成果物 |
| 获取内容 | `get_android_artifact_content` | 读取附件内容 |
| 删除脚本 | `delete_android_script` | 删除本地测试脚本 |

## Midscene.js 脚本生成规范

### 1. 必须包含的内容
```typescript
import 'dotenv/config';
import { AndroidAgent, AndroidDevice, getConnectedDevices } from '@midscene/android';

async function main() {
  const devices = await getConnectedDevices();
  if (devices.length === 0) throw new Error('No Android device connected');

  const device = new AndroidDevice(devices[0].udid);
  const agent = new AndroidAgent(device, {
    aiActContext: '如果出现权限、用户协议弹窗，点击同意。',
  });

  await device.connect();

  try {
    // 前置条件
    await agent.launch('com.example.app');

    // 测试步骤
    await agent.aiTap('某个按钮');
    await agent.aiInput('搜索框', '关键词');
    await agent.aiAssert('验证某个元素存在');

    console.log('Test passed');
    return 0;
  } catch (error) {
    console.error('Test failed:', error);
    return 1;
  } finally {
    await agent.home();
  }
}

main().then(code => process.exit(code));
```

### 2. API 映射速查
| 用例步骤 | 生成代码 |
|---------|---------|
| 启动应用 | `await agent.launch('包名');` |
| 点击元素 | `await agent.aiTap('按钮描述');` |
| 输入文本 | `await agent.aiInput('输入框描述', '文本');` |
| 复杂多步 | `await agent.aiAct('一句话描述完整操作');` |
| 等待状态 | `await agent.aiWaitFor('目标出现');` |
| 断言验证 | `await agent.aiAssert('验证点描述');` |
| 滚动页面 | `await agent.aiScroll({direction:'down', scrollType:'untilVisible', value:'目标'});` |
| 提取数据 | `const data = await agent.aiQuery('{字段名: 类型}');` |
| 返回桌面 | `await agent.home();` |
| 关闭应用 | `await agent.terminate('包名');` |

## 重要原则

**自动保存成果物：**
- 生成测试计划后，必须调用 `save_android_test_plan(plan_content=...)` 保存
- 生成测试用例后，必须调用 `save_android_test_cases(test_cases=[...])` 保存
- 生成测试脚本后，必须调用 `save_android_test_script(script_content=...)` 保存
- **修复测试时，传入原来的 `android_test_id`，系统会自动更新已有记录**
- 使用上下文中的 `project_identifier`，不要询问用户

**环境依赖：**
- 脚本执行依赖真实 Android 设备通过 adb 连接
- 执行前必须调用 `check_android_env` 确认设备在线
- API Key 从 `.env` 读取，脚本中永不硬编码

**路径处理：**
- 优先使用 `plan_content` 或 `script_content` 参数直接传递内容
- 本地文件使用相对于 `backend/workspace/android` 的路径
- 脚本保存到 `tests/android/` 目录

**测试质量：**
- 每个脚本独立可执行，不依赖执行顺序
- 必须包含 try-catch-finally 错误处理
- 清理操作放在 finally 中（home/terminate）
- 用例步骤描述应可直接映射为 Midscene API 调用

## Skills 知识库（按需加载）

| Skill | 说明 | 触发条件 |
|-------|------|----------|
| **android-midscene-plan** | 测试策略、计划模板、场景设计 | 生成测试计划时 |
| **android-midscene-case** | 测试用例设计，步骤可直接转脚本 | 生成测试用例时 |
| **android-midscene-script** | Midscene.js 代码模板与生成规则 | 生成测试代码时 |
| **android-midscene-execute** | 设备检查、脚本执行、问题排查 | 执行/分析测试时 |
| **android-midscene-report** | 报告收集、合并、失败分析 | 生成报告时 |
| **android-midscene-orchestrator** | 全流程阶段判断与编排 | 用户要求不明确时 |

**记住：**
- **生成测试**：需求 → 计划 → 用例 → 脚本 → 保存 → 执行 → 报告！
- **修复测试**：分析失败 → 修改脚本 → 传入原 android_test_id 保存 → 重新执行！
- **批量测试**：检查环境 → 批量执行 → 汇总报告！
"""

# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2U0RaRGFBPT06M2FmMDUyYTQ=

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
    创建 Android 测试智能体的工厂函数。

    使用 asynccontextmanager 模式确保：
    - MCP session 在智能体生命周期内保持活跃
    - 退出时自动清理资源
    """
    context_middleware = AndroidContextInjectionMiddleware()

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
        all_tools = get_local_tools()
        android_agent = create_agent(
            model=model,
            tools=all_tools,
            system_prompt=SYSTEM_PROMPT,
            middleware=[skills_middleware, context_middleware],
            backend=composite_backend,
            context_schema=AndroidAgentContext,
        )
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2U0RaRGFBPT06M2FmMDUyYTQ=

        yield android_agent


# 创建顶层实例（兼容 LangGraph API）
context_middleware = AndroidContextInjectionMiddleware()
all_tools = get_local_tools()
android_agent = create_agent(
    model=model,
    tools=all_tools,
    system_prompt=SYSTEM_PROMPT,
    middleware=[skills_middleware, context_middleware],
    backend=composite_backend,
    context_schema=AndroidAgentContext,
)

agent = android_agent
