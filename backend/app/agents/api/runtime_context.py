"""
API Agent 运行时上下文共享模块

提供不依赖 agent.py 与 tools 的共享上下文变量，
用于在同一次 AI 对话的模型调用与工具调用之间传递会话标识。
"""

import asyncio
import contextvars
from typing import Optional

# 当前 AI 对话（会话）ID。
# 在 APIContextInjectionMiddleware 中设置，工具函数可通过 get_conversation_id() 读取。
conversation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "conversation_id",
    default=None,
)


def get_conversation_id() -> Optional[str]:
    """获取当前会话 ID，如果不在 Agent 调用上下文中则返回 None。"""
    return conversation_id_ctx.get()


# 执行并发锁注册表（进程内）：同一端点/场景的执行串行化。
# 防止并发会话互相覆盖脚本文件、执行统计交错，以及场景并发执行时
# teardown 误删对方步骤创建的资源。报告/trace 文件已按 uuid 隔离，不在此列。
_execution_locks: dict[str, asyncio.Lock] = {}


def get_execution_lock(key: str) -> asyncio.Lock:
    """获取按 key 隔离的执行锁。

    锁对象按 key 缓存复用；key 基数受端点/场景数量约束，不会无限增长。
    asyncio.Lock 在 3.10+ 不再绑定事件循环，LangGraph 单主循环下安全。
    """
    lock = _execution_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _execution_locks[key] = lock
    return lock
