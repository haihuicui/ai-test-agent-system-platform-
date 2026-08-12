"""
TestCase Agent 运行时上下文共享模块

提供不依赖 agent.py 的共享上下文变量，用于在同一次会话的
模型调用与工具调用之间传递会话隔离作用域（project_identifier + thread_id），
实现 workspace 文件的会话级隔离（同项目并发会话互不覆盖文件）。

值由 ContextInjectionMiddleware 在每次模型调用前写入；react 循环中
工具调用前必有模型调用，因此工具执行时读到的必然是当前会话的值。
模式与 app/agents/api/runtime_context.py 一致。

注意：本模块必须放在 tools 包内且不 import 任何 agent 侧模块——
app/agents/testcase/__init__.py 会 import agent.py（进而 import 本 tools 包），
若本模块位于 agents/testcase/ 目录下会形成循环 import。
"""

import contextvars
from typing import Optional

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
) -> None:
    """写入当前会话的隔离作用域（每次模型调用前刷新，保证最新）。"""
    session_project_ctx.set(project_identifier or None)
    session_thread_ctx.set(thread_id or None)


def get_session_project() -> Optional[str]:
    """获取当前会话的项目标识，不在 Agent 调用上下文中时返回 None。"""
    return session_project_ctx.get()


def get_session_thread_id() -> Optional[str]:
    """获取当前会话的 thread_id，不在 Agent 调用上下文中时返回 None。"""
    return session_thread_ctx.get()
