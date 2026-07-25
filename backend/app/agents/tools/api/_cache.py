"""
会话级工具调用缓存

在同一个 AI 对话（conversation）内缓存确定性读操作的返回结果，
避免同一端点信息、响应 schema、环境配置被反复查询。

设计原则：
- 只缓存无副作用的读操作（get_* / list_*），写操作（save_*/execute_*/delete_*）不缓存
- TTL=300s，覆盖单次完整对话，过期自动淘汰
- 按 (conversation_id, tool_name, args) 复合键隔离
- 对话结束时可通过 clear_conversation_cache 主动清理
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any

from app.agents.api.runtime_context import get_conversation_id

logger = logging.getLogger(__name__)

# {key: (expires_at, value)}
_cache: dict[str, tuple[float, Any]] = {}

# 缓存 TTL（秒）：5分钟，覆盖单次完整对话
_CACHE_TTL = 300

# 写操作后需要刷新的工具（缩短 TTL）
_SHORT_TTL = 60


def _build_key(conversation_id: str, tool_name: str, args: tuple, kwargs: dict) -> str:
    """构造缓存 key。"""
    kwargs_sorted = tuple(sorted(kwargs.items()))
    return f"{conversation_id}:{tool_name}:{args}:{kwargs_sorted}"


def cached_read(tool_name: str, ttl: int | None = None):
    """装饰器：对读操作做会话级缓存。

    Args:
        tool_name: 工具名（用于日志和缓存 key）
        ttl: 自定义 TTL（秒），为 None 则用默认 300s；写操作影响到的工具建议传 60
    """

    effective_ttl = ttl if ttl is not None else _CACHE_TTL

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            conv_id = get_conversation_id()
            if not conv_id:
                # 无 conversation_id（如批量接口调用），不做缓存
                return await func(*args, **kwargs)

            key = _build_key(conv_id, tool_name, args, kwargs)
            now = time.time()

            if key in _cache:
                expires, val = _cache[key]
                if now < expires:
                    logger.debug("Cache HIT: %s", tool_name)
                    return val
                del _cache[key]
                logger.debug("Cache EXPIRED: %s", tool_name)

            result = await func(*args, **kwargs)
            _cache[key] = (now + effective_ttl, result)
            logger.debug("Cache SET: %s (entries=%d)", tool_name, len(_cache))
            return result

        return wrapper

    return decorator


def clear_conversation_cache(conversation_id: str | None = None) -> int:
    """清除指定会话的缓存。不传则清除所有。

    Returns:
        清除的条目数
    """
    if not conversation_id:
        count = len(_cache)
        _cache.clear()
        logger.debug("Cache CLEAR ALL: %d entries", count)
        return count

    prefix = f"{conversation_id}:"
    keys = [k for k in _cache if k.startswith(prefix)]
    for k in keys:
        del _cache[k]
    logger.debug("Cache CLEAR conversation=%s: %d entries", conversation_id, len(keys))
    return len(keys)


def cache_stats() -> dict:
    """返回缓存统计信息（用于调试）。"""
    now = time.time()
    total = len(_cache)
    expired = sum(1 for _, (expires, _) in _cache.items() if now >= expires)
    return {"total_entries": total, "expired_entries": expired, "active_entries": total - expired}
