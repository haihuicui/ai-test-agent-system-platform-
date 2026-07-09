"""
API Agent 运行时上下文共享模块

提供不依赖 agent.py 与 tools 的共享上下文变量，
用于在同一次 AI 对话的模型调用与工具调用之间传递会话标识。
"""

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
