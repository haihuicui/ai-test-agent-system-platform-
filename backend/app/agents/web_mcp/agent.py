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
import logging

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
from app.agents.web_mcp.execution_invitation_middleware import WebExecutionInvitationMiddleware
from app.agents.web_mcp.intent_confirmation_middleware import WebIntentConfirmationMiddleware
from app.config.settings import settings
from app.core.llms import text_model as model
from app.models.environment import AuthType
from app.repositories.environment_repo import EnvironmentRepository
from app.utils.shell_env import build_shell_env, ensure_playwright_mcp_project, get_playwright_mcp_command_args
from app.utils.storage_state_validator import validate_storage_state
from app.utils.web_mcp_storage_state import resolve_project_storage_state_path
from app.repositories.project_repo import ProjectRepository
from app.config.database import async_session_factory

logger = logging.getLogger(__name__)

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
        # 兼容直接调用 agent 时未传入 runtime.context 的场景
        context = getattr(request.runtime, "context", None)
        project_identifier = getattr(context, "project_identifier", "") or ""
        folder_id = getattr(context, "folder_id", "") or ""

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


# 从 prompts/base.md 加载 Layer 0 核心提示词（始终加载，含铁律 + 路由决策树）
# Layer 1 工作流专属提示词由 WorkflowRouterMiddleware 按需动态注入
_base_prompt_path = Path(__file__).parent / "prompts" / "base.md"
if _base_prompt_path.exists():
    SYSTEM_PROMPT = _base_prompt_path.read_text(encoding="utf-8")
else:
    # 回退：内嵌最小化提示词，避免因文件缺失导致 Agent 启动失败
    SYSTEM_PROMPT = """# Web 自动化测试专家

你是资深的 Web 自动化测试专家，负责基于浏览器的 UI 测试全生命周期。

## ⚠️ 关键规则
- 所有 browser_* 工具前必须先 planner_setup_page
- 测试计划/用例/脚本/报告 必须调用对应的 save_* 工具保存
- execute_web_script 是唯一权威执行入口
- 生成完成后必须输出 <EXECUTION_INVITATION> 标记

请按需读取 Skill 获取详细操作指南。
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

    # 解析项目级 storageState。项目已配置登录态时强制走项目/环境级，避免回退到全局过期的文件；
    # 未配置登录态时不使用 storageState；仅在 project_identifier 为空或解析异常时才允许全局 fallback。
    storage_state: str | None = None
    use_global_fallback = False
    has_login_config = False

    if project_identifier:
        try:
            async with async_session_factory() as session:
                project = await ProjectRepository(session).get_by_identifier(
                    project_identifier
                )
                if project is not None:
                    env = await EnvironmentRepository(
                        session
                    ).get_default_by_project(project.id)
                    if env is not None:
                        if env.auth_type == AuthType.FORM_LOGIN.value:
                            has_login_config = True
                        else:
                            auth_config = env.auth_config or {}
                            has_login_config = bool(
                                auth_config.get("form_login")
                                or auth_config.get("storage_state")
                            )
                    if has_login_config:
                        storage_state = await resolve_project_storage_state_path(
                            project_identifier, env.id if env else None
                        )
                        if storage_state:
                            logger.info(
                                "[WebMCPAgent] 使用项目级 storageState: %s",
                                storage_state,
                            )
                        else:
                            logger.warning(
                                "[WebMCPAgent] 项目 %s 已配置 Web 登录但无有效项目级 "
                                "storageState，不使用全局 fallback，将依赖脚本自身登录逻辑。",
                                project_identifier,
                            )
                    else:
                        logger.info(
                            "[WebMCPAgent] 项目 %s 未配置 Web 登录，不使用 storageState。",
                            project_identifier,
                        )
        except Exception as exc:
            logger.warning(
                "[WebMCPAgent] 解析项目默认环境登录态失败: %s", exc
            )

    # 仅在未解析到项目/未配置登录态时，才允许回退到全局配置，且必须校验有效。
    if not storage_state and not has_login_config:
        global_ss = settings.web_mcp_storage_state
        if global_ss:
            validation = validate_storage_state(global_ss)
            if validation.is_valid:
                storage_state = global_ss
                use_global_fallback = True
                logger.info("[WebMCPAgent] 使用全局 storageState: %s", storage_state)
            else:
                logger.warning(
                    "[WebMCPAgent] 全局 storageState 无效，跳过注入: %s",
                    validation.reason,
                )

    # 确保 Playwright MCP 项目目录已初始化（配置、依赖），并注入登录态
    await ensure_playwright_mcp_project(
        settings.web_mcp_root,
        headless=settings.web_mcp_headless,
        storage_state=storage_state,
        use_global_storage_state_fallback=use_global_fallback,
    )

    # 创建 MCP 客户端连接到 Playwright 服务器
    mcp_command, mcp_args = await get_playwright_mcp_command_args(
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
            middleware=[
                skills_middleware,
                context_middleware,
                WebIntentConfirmationMiddleware(),
                WebExecutionInvitationMiddleware(),
            ],
            backend=composite_backend,
            context_schema=WebAgentContext,
        )

        # yield agent，session 会保持存活直到请求处理完成
        yield web_agent


# 导出 make_agent 供 LangGraph API 使用
agent = make_agent
