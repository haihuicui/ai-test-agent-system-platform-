"""TestCase Agent 运行时上下文（薄代理）。

实现已上移至 ``app.utils.session_scope``（跨 Agent 统一的会话作用域模块），
本模块仅 re-export 以保持既有 import 路径可用。

注意：本模块必须放在 tools 包内且不 import 任何 agent 侧模块——
app/agents/testcase/__init__.py 会 import agent.py（进而 import 本 tools 包），
若本模块位于 agents/testcase/ 目录下会形成循环 import。
"""

from app.utils.session_scope import (
    get_session_project,
    get_session_thread_id,
    session_project_ctx,
    session_thread_ctx,
    set_session_scope,
)

__all__ = [
    "set_session_scope",
    "get_session_project",
    "get_session_thread_id",
    "session_project_ctx",
    "session_thread_ctx",
]
