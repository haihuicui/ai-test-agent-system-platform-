"""
TestCase Agent 运行时上下文共享模块

提供不依赖 agent.py 的共享上下文变量，用于在同一次会话的
模型调用与工具调用之间传递会话隔离作用域（project_identifier + thread_id），
实现 workspace 文件的会话级隔离（同项目并发会话互不覆盖文件）。

传递通道（按可靠性排序）：
1. **平台原生 config 键（主通道）**：LangGraph 平台每次 run 自动注入
   ``config["configurable"]["thread_id"]``，且（langgraph_api ≥0.5 本地/自部署
   形态）会把 run 的 context 字段（project_identifier 等）合并进 configurable。
   该 configurable 由 run 配置派生，模型节点与工具节点均可读到同一组原生键。
2. ContextInjectionMiddleware 的写回/configvar 作为回退——注意仅靠
   contextvar set 或写回自定义键都不可靠：LangGraph 中模型调用与工具调用是
   兄弟 task（各自复制父 context 快照），且 patch_config 会重建 configurable
   子 dict（中间件内写回的自定义键传播不到工具节点，2026-08 双会话验证实测）。

模式参考 app/agents/api/runtime_context.py。

注意：本模块必须放在 tools 包内且不 import 任何 agent 侧模块——
app/agents/testcase/__init__.py 会 import agent.py（进而 import 本 tools 包），
若本模块位于 agents/testcase/ 目录下会形成循环 import。
"""

import contextvars
from typing import Optional

from langgraph.config import get_config

# config["configurable"] 写回键名（独立于平台原生字段，避免污染）
_CONFIG_PROJECT_KEY = "testcase_session_project"
_CONFIG_THREAD_KEY = "testcase_session_thread_id"

# 当前会话的项目标识（TestCaseGeneratorContext.project_identifier）
session_project_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "testcase_session_project",
    default=None,
)

# 当前会话的 LangGraph thread_id（config["configurable"]["thread_id"]，
# 平台每次 run 自动注入；非平台环境/单元测试中可能为 None）
session_thread_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "testcase_session_thread_id",
    default=None,
)


def set_session_scope(
    project_identifier: Optional[str],
    thread_id: Optional[str],
    config: Optional[dict] = None,
) -> None:
    """写入当前会话的隔离作用域（每次模型调用前刷新，保证最新）。

    Args:
        project_identifier: 项目标识（来自 runtime context）。
        thread_id: LangGraph thread_id（来自平台注入的 config）。
        config: 当前 run 的 RunnableConfig。提供时把作用域写回
            ``config["configurable"]``——可变 dict 跨 task 共享，
            是工具侧读取的可靠主通道。
    """
    session_project_ctx.set(project_identifier or None)
    session_thread_ctx.set(thread_id or None)
    if config is not None:
        if not isinstance(config.get("configurable"), dict):
            config["configurable"] = {}
        config["configurable"][_CONFIG_PROJECT_KEY] = project_identifier or ""
        config["configurable"][_CONFIG_THREAD_KEY] = thread_id or ""


def _read_config(key: str) -> Optional[str]:
    """从 LangGraph 运行配置读取（工具调用上下文内的可靠通道）。"""
    try:
        config = get_config()
        if config and isinstance(config.get("configurable"), dict):
            value = config["configurable"].get(key)
            if value:
                return value
    except Exception:
        pass
    return None


def get_session_project() -> Optional[str]:
    """获取当前会话的项目标识，不在 Agent 调用上下文中时返回 None。

    优先读平台原生 config 键（context 合并进 configurable），
    回退中间件写回键，最后回退 contextvar（单测/直调注入通道）。
    """
    return (
        _read_config("project_identifier")
        or _read_config(_CONFIG_PROJECT_KEY)
        or session_project_ctx.get()
    )


def get_session_thread_id() -> Optional[str]:
    """获取当前会话的 thread_id，不在 Agent 调用上下文中时返回 None。

    优先读平台原生注入的 config["configurable"]["thread_id"]（工具节点
    与模型节点共享同一组原生键），回退中间件写回键与 contextvar。
    """
    return (
        _read_config("thread_id")
        or _read_config(_CONFIG_THREAD_KEY)
        or session_thread_ctx.get()
    )

