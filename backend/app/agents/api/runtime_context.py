"""
API Agent 运行时上下文共享模块

提供不依赖 agent.py 与 tools 的共享上下文变量，
用于在同一次 AI 对话的模型调用与工具调用之间传递会话标识。

会话标识读取顺序（2026-08 真实环境验证后收敛）：
1. ``config["configurable"]["conversation_id"]``——FastAPI 直调图路径
   （generate_from_schema）显式传入；
2. ``config["configurable"]["thread_id"]``——前端 SDK 直连路径下平台
   每次 run 自动注入，一个 thread 即一次会话；模型节点与工具节点共享
   同一组原生 config 键（中间件写回的自定义键会被 patch_config 重建
   丢弃，contextvar set 也传播不到兄弟 task——均实测确认）；
3. contextvar——单测/同 task 场景的回退通道。
"""

import asyncio
import contextvars
from typing import Optional

from langgraph.config import get_config

# 当前 AI 对话（会话）ID。
# 在 APIContextInjectionMiddleware 中设置，工具函数可通过 get_conversation_id() 读取。
conversation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "conversation_id",
    default=None,
)


def get_conversation_id() -> Optional[str]:
    """获取当前会话 ID，如果不在 Agent 调用上下文中则返回 None。"""
    try:
        config = get_config()
        if config and isinstance(config.get("configurable"), dict):
            conversation_id = config["configurable"].get("conversation_id")
            if conversation_id:
                return conversation_id
            # 前端聊天路径无显式 conversation_id：平台注入的 thread_id
            # 即会话标识（一个 thread 就是一次会话）
            thread_id = config["configurable"].get("thread_id")
            if thread_id:
                return thread_id
    except Exception:
        pass
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
