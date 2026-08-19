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
from urllib.parse import urlparse
import asyncio
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
from app.core.tracing import with_langfuse_tracing
from app.utils.shell_env import (
    build_restricted_env,
    ensure_playwright_mcp_project,
    get_playwright_mcp_command_args,
    write_storage_state_config,
)
from app.utils.session_scope import set_session_scope
from app.utils.web_mcp_storage_state import resolve_effective_storage_state

logger = logging.getLogger(__name__)

# =============================================================================
# 配置
# =============================================================================
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TkdSNlVRPT06ZGFhYmJjYWY=

skills_root = Path(settings.web_mcp_skills_root).resolve()
workspace_root = Path(settings.web_mcp_workspace_root).resolve()

skills_backend = FilesystemBackend(root_dir=skills_root, virtual_mode=True)
workspace_backend = FilesystemBackend(root_dir=workspace_root, virtual_mode=True)
shell_backend = LocalShellBackend(root_dir=Path(settings.web_mcp_workspace_root).resolve(),
                                  inherit_env=False,
                                  env=build_restricted_env(),
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

        # 统一会话作用域：workspace 隔离 / RAG space 映射 / Langfuse 打标的公共通道。
        # 必须在下方幂等 return 之前执行——每次模型调用都刷新，避免交替会话串扰。
        _config = get_config()
        set_session_scope(
            project_identifier,
            ((_config.get("configurable") or {}).get("thread_id") if _config else None),
            _config,
        )

        context_info = f"""

---
## 🎯 运行时上下文

**当前会话参数（调用工具时必须使用）：**
- `project_identifier`: `{project_identifier}`
- `folder_id`: `{folder_id}`

**重要提示：** 这些参数由系统自动注入，不要询问用户提供。
---
"""
        # 幂等保护：若 system_message 已被注入过（上游复用 message 对象的场景），
        # 直接放行，避免每次模型调用重复追加导致提示词无限膨胀。
        existing = request.system_message.content
        if isinstance(existing, list):
            already_injected = any(
                isinstance(block, dict) and "## 🎯 运行时上下文" in str(block.get("text", ""))
                for block in existing
            )
        else:
            already_injected = "## 🎯 运行时上下文" in (existing or "")
        if already_injected:
            return await handler(request)

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

# =============================================================================
# 常驻 MCP server 连接辅助
# =============================================================================

async def _probe_tcp(url: str, timeout: float = 3.0) -> bool:
    """TCP 探测常驻 MCP server 是否可达，避免连接失败拖到 run 中途才暴露。"""
    try:
        parsed = urlparse(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(parsed.hostname, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


def _build_mcp_client(stdio_command: str, stdio_args: list[str]) -> MultiServerMCPClient:
    """按配置选择 MCP 传输方式并构建客户端。

    优先级：常驻 server（streamable_http，WEB_MCP_SERVER_URL 可达时）> per-run stdio。
    调用方需保证：解析到 storageState 的 run 不走常驻 server（登录态隔离）。
    """
    shared_url = (settings.web_mcp_server_url or "").strip()
    if shared_url:
        parsed = urlparse(shared_url)
        # Playwright MCP 有 Host 头校验（仅允许 localhost:<port>），跨容器访问需覆写
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return MultiServerMCPClient(
            {
                "web_mcp": {
                    "transport": "streamable_http",
                    "url": shared_url,
                    "headers": {"Host": f"localhost:{port}"},
                }
            }
        )
    return MultiServerMCPClient(
        {
            "web_mcp": {
                "transport": "stdio",
                "command": stdio_command,
                "args": stdio_args,
            }
        }
    )


# =============================================================================
# MCP 工具裁剪：86 个工具全量随每次模型调用发送，prefill 代价大。
# 核心集 = prompts/skills 实际引用到的工具 + 主流程（导航/点击/输入/快照/等待/
# 表单/断言/执行）所需工具。
# =============================================================================

CORE_MCP_TOOLS: frozenset[str] = frozenset({
    # 浏览器生命周期 / 导航
    "browser_navigate", "browser_navigate_back", "browser_reload",
    "browser_close", "browser_tabs",
    # 页面交互
    "browser_click", "browser_type", "browser_fill_form",
    "browser_press_key", "browser_press_sequentially",
    "browser_select_option", "browser_check", "browser_uncheck", "browser_hover",
    # 页面读取 / 等待 / 断言
    "browser_snapshot", "browser_wait_for", "browser_evaluate",
    "browser_take_screenshot", "browser_generate_locator",
    # 诊断
    "browser_network_requests", "browser_console_messages",
    "browser_handle_dialog", "browser_file_upload",
    # 逃生舱（复杂操作兜底）
    "browser_run_code_unsafe",
    # 测试编排（planner_save_plan / planner_submit_plan 已被下方 excluded 集合排除）
    "planner_setup_page",
    "generator_setup_page", "generator_write_test", "generator_read_log",
    "test_run", "test_list", "test_debug",
})


def parse_mcp_tool_whitelist(raw: str | None) -> frozenset[str] | None:
    """解析 WEB_MCP_TOOL_WHITELIST。返回 None 表示不过滤（全量）。"""
    raw = (raw or "").strip()
    if not raw:
        return CORE_MCP_TOOLS
    if raw.lower() in ("full", "all", "*"):
        return None
    return frozenset(x.strip() for x in raw.split(",") if x.strip())


def build_web_agent_model():
    """构建 web_agent 专用模型。

    提供方由 settings.web_llm_provider 切换：
    - deepseek（默认）：ChatDeepSeek。WEB_AGENT_DISABLE_THINKING=true 时通过
      extra_body 关闭 thinking（逐步浏览器决策无需深度推理，实测复杂单步
      13s→3s）。thinking 是请求级参数，不能复用共享 text_model 单例，
      需独立实例；开关关闭时直接返回共享单例。
    - qwen：自部署 vLLM 网关（数据不出网），ChatOpenAI 独立实例。
      关闭 thinking 走 chat_template_kwargs.enable_thinking=false。
    """
    if settings.web_llm_provider == "qwen":
        from langchain_openai import ChatOpenAI

        qwen_model = ChatOpenAI(
            base_url=settings.qwen_api_base,
            api_key=settings.qwen_api_key,
            model=settings.qwen_model,
            temperature=0.3,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout,
            max_tokens=settings.llm_max_tokens,
            stream_chunk_timeout=settings.llm_stream_chunk_timeout,
            extra_body=(
                {"chat_template_kwargs": {"enable_thinking": False}}
                if settings.web_agent_disable_thinking
                else None
            ),
        )
        # vLLM 侧 max_model_len=262144，预留 16K 输出配额后的可用输入上限
        qwen_model.profile = ModelProfile(max_input_tokens=245760)
        return qwen_model

    if not settings.web_agent_disable_thinking:
        return model
    from langchain_deepseek import ChatDeepSeek

    fast_model = ChatDeepSeek(
        model=settings.llm_model,
        temperature=0.3,
        max_retries=settings.llm_max_retries,
        timeout=settings.llm_timeout,
        max_tokens=settings.llm_max_tokens,
        stream_chunk_timeout=settings.llm_stream_chunk_timeout,
        extra_body={"thinking": {"type": "disabled"}},
    )
    fast_model.profile = ModelProfile(max_input_tokens=128000)
    return fast_model


# =============================================================================
# 项目登录态解析：已公共化到 app.utils.web_mcp_storage_state
# （resolve_effective_storage_state 与 execution_tools 执行链路共享语义与 60s 缓存）。
# =============================================================================


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

    # 解析生效的 storageState：项目/环境级优先，未配置登录态时回退全局配置
    # （公共解析逻辑，与 execute_web_script 执行链路保持一致，避免探索已登录
    # 但执行无登录态的语义分裂）。TCP 探测与 DB 查询并行，省 ~1s 串行等待。
    shared_url = (settings.web_mcp_server_url or "").strip()
    probe_task: asyncio.Task[bool] | None = (
        asyncio.create_task(_probe_tcp(shared_url)) if shared_url else None
    )

    storage_state = await resolve_effective_storage_state(project_identifier)

    # 确保 Playwright MCP 项目目录已初始化（共享配置固定为无登录态静态模板）
    await ensure_playwright_mcp_project(
        settings.web_mcp_root,
        headless=settings.web_mcp_headless,
    )

    # 登录态隔离：解析到 storageState 的 run 生成独立配置（playwright.config.ss-*.js），
    # 并发 run 不再互相覆盖共享 playwright.config.js（登录态丢失 / 跨项目串扰）。
    run_config_path: str | None = None
    if storage_state:
        run_config_path = await write_storage_state_config(
            settings.web_mcp_root,
            storage_state,
            headless=settings.web_mcp_headless,
            config_key=project_identifier or "global",
        )

    # 创建 MCP 客户端：优先连接常驻 server（streamable HTTP），否则 per-run stdio 启动。
    # 常驻 server 按无登录态配置启动，解析到 storageState 的 run 必须走 stdio 隔离，
    # 避免登录态跨项目/跨会话串扰。探测任务在上方已与 DB 查询并行启动。
    use_shared = bool(shared_url) and not storage_state
    probe_ok = await probe_task if probe_task is not None else False
    if use_shared and not probe_ok:
        logger.warning(
            "[WebMCPAgent] 常驻 MCP server 不可达 (%s)，回退 per-run stdio 启动。",
            shared_url,
        )
        use_shared = False

    if use_shared:
        logger.info("[WebMCPAgent] 使用常驻 MCP server: %s", shared_url)
        client = _build_mcp_client("", [])
    else:
        if shared_url and storage_state:
            logger.info(
                "[WebMCPAgent] 已解析 storageState，使用 stdio 隔离启动（不走常驻 server）。"
            )
        mcp_command, mcp_args = await get_playwright_mcp_command_args(
            settings.web_mcp_root,
            headless=settings.web_mcp_headless,
            config_path=run_config_path,
        )
        client = _build_mcp_client(mcp_command, mcp_args)

    # 使用 async with 保持 session 存活
    async with client.session("web_mcp") as session:
        # 在 session 中加载 MCP 工具
        # 过滤掉与本地 save_web_test_plan 职责重叠、且 schema 要求 suites 必填的
        # planner 工具，避免 LLM 误把 plan_content 传给 MCP 的 planner_save_plan /
        # planner_submit_plan 导致 suites 缺失而抛 ToolException。
        excluded_mcp_tools = {"planner_save_plan", "planner_submit_plan"}
        # 工具白名单裁剪（默认核心集 ~32 个，WEB_MCP_TOOL_WHITELIST=full 恢复全量）：
        # 工具 schema 随每次模型调用发送，86 → 32 约省 60% prefill token。
        whitelist = parse_mcp_tool_whitelist(settings.web_mcp_tool_whitelist)
        loaded_tools = await load_mcp_tools(session)
        mcp_tools = [
            t for t in loaded_tools
            if t.name not in excluded_mcp_tools
            and (whitelist is None or t.name in whitelist)
        ]
        logger.info(
            "[WebMCPAgent] MCP 工具 %d -> %d 个（%s）",
            len(loaded_tools),
            len(mcp_tools),
            "全量" if whitelist is None else "白名单裁剪",
        )
        if whitelist is not None:
            loaded_names = {t.name for t in loaded_tools}
            dropped = sorted(loaded_names - {t.name for t in mcp_tools})
            logger.debug("[WebMCPAgent] 被白名单裁掉的 MCP 工具: %s", ", ".join(dropped))
            # 白名单中列了但 server 未提供的工具：多半是 MCP 升级改名或拼写过时，
            # 需要同步维护 CORE_MCP_TOOLS / WEB_MCP_TOOL_WHITELIST。
            missing = sorted(whitelist - loaded_names)
            if missing:
                logger.warning(
                    "[WebMCPAgent] 白名单中的 %d 个工具未被 MCP server 提供（疑似过时）: %s",
                    len(missing),
                    ", ".join(missing),
                )
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
            model=build_web_agent_model(),
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
        yield with_langfuse_tracing(web_agent, "web")


# 导出 make_agent 供 LangGraph API 使用
agent = make_agent
