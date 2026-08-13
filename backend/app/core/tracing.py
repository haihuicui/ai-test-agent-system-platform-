"""Langfuse LLM 观测接入（fail-open）。

三条铁律：
1. 观测代码任何异常都不能影响 Agent 运行（fail-open）；
2. 总开关 LANGFUSE_ENABLED 默认关闭，未安装 langfuse 包时静默跳过；
3. 回调挂在 graph 级 config（Pregel.with_config 返回 Pregel 副本，
   checkpointer / interrupt / history 行为不变），不进中间件热路径、
   回调内不写任何自定义 I/O（v3 SDK 后台批量上报，不阻塞事件循环）。
"""
from __future__ import annotations

import logging
from typing import Any

from app.config.settings import settings

logger = logging.getLogger(__name__)

_handler: Any = None
_init_failed = False


def _truncate_strings(data: Any, max_chars: int) -> Any:
    """递归截断超长字符串，防止大 payload（累积消息历史/长文档）撑爆单条 trace。"""
    if isinstance(data, str):
        return data if len(data) <= max_chars else data[:max_chars] + f"…[截断,原长{len(data)}]"
    if isinstance(data, dict):
        return {k: _truncate_strings(v, max_chars) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [_truncate_strings(item, max_chars) for item in data]
    return data


def _get_handler() -> Any | None:
    """惰性创建 Langfuse LangChain 回调 handler（进程级单例）。

    初始化失败时记录一次告警并永久关闭（避免每次 graph 构建都重试）。
    """
    global _handler, _init_failed
    if _handler is not None or _init_failed:
        return _handler
    try:
        from langfuse import Langfuse

        client_kwargs: dict[str, Any] = {
            "public_key": settings.langfuse_public_key,
            "secret_key": settings.langfuse_secret_key,
            "host": settings.langfuse_host,
        }
        max_chars = settings.langfuse_trace_max_chars
        if max_chars > 0:
            client_kwargs["mask"] = lambda data: _truncate_strings(data, max_chars)
        try:
            Langfuse(**client_kwargs)  # 初始化默认客户端（后台批量上报）
        except TypeError:
            # 旧版 SDK 不支持 mask 参数时降级为不截断
            client_kwargs.pop("mask", None)
            Langfuse(**client_kwargs)
        _handler = _get_session_enriched_handler_class()()
        logger.info("[Langfuse] 观测已启用: host=%s", settings.langfuse_host)
    except Exception:
        _init_failed = True
        logger.warning(
            "[Langfuse] 初始化失败，本次进程关闭观测（不影响 Agent 运行）", exc_info=True
        )
    return _handler


def _make_session_enriched_handler_class():
    """构建从平台注入 metadata 派生会话/项目维度的 CallbackHandler 子类。

    为什么需要：中间件写回 ``config["metadata"]`` 在 LangGraph patch_config
    语义下传播不到回调（与 configurable 自定义键写回断裂同类，2026-08-13
    E2E 实测确认 trace 无 session_id）。但 LangGraph Server 会把 run 的
    ``thread_id`` 与 context 字段（``project_identifier`` 等）注入回调可见的
    metadata——直接从那里派生，零侵入 run 创建链路：
    - ``session_id`` ← thread_id（同一会话的多次 run 聚合成 Langfuse session）
    - ``tags`` 追加 ``project:<identifier>``（项目维度过滤/成本分摊）
    """
    from langfuse.langchain import CallbackHandler

    class SessionEnrichedCallbackHandler(CallbackHandler):
        def _parse_langfuse_trace_attributes_from_metadata(self, metadata):
            attributes = super()._parse_langfuse_trace_attributes_from_metadata(metadata)
            if not metadata:
                return attributes
            if "session_id" not in attributes:
                thread_id = metadata.get("thread_id")
                if isinstance(thread_id, str) and thread_id:
                    attributes["session_id"] = thread_id
            project = metadata.get("project_identifier")
            if isinstance(project, str) and project:
                tags = list(attributes.get("tags") or [])
                project_tag = f"project:{project}"
                if project_tag not in tags:
                    tags.append(project_tag)
                attributes["tags"] = tags
            return attributes

    return SessionEnrichedCallbackHandler


_SessionEnrichedCallbackHandler = None


def _get_session_enriched_handler_class():
    """惰性解析子类（langfuse 未安装时保持 None，由 _get_handler fail-open）。"""
    global _SessionEnrichedCallbackHandler
    if _SessionEnrichedCallbackHandler is None:
        _SessionEnrichedCallbackHandler = _make_session_enriched_handler_class()
    return _SessionEnrichedCallbackHandler


def with_langfuse_tracing(agent: Any, agent_name: str) -> Any:
    """给编译后的 Pregel graph 挂 Langfuse 回调；任何失败都原样返回 agent。

    Pregel.with_config 返回 Pregel 副本（非 RunnableBinding），LangGraph Server
    加载、checkpointer、interrupt、history 行为均不变；callbacks 沿 config 继承
    传播到子代理与工具调用，一次 run 聚合成一棵完整 trace 树。
    """
    if not settings.langfuse_enabled:
        return agent
    try:
        handler = _get_handler()
        if handler is None:
            return agent
        return agent.with_config(
            config={
                "callbacks": [handler],
                # langfuse_* 为 v3 handler 约定的 trace 属性元数据键
                "metadata": {"langfuse_tags": [f"agent:{agent_name}"]},
                "run_name": agent_name,
            }
        )
    except Exception:
        logger.warning(
            "[Langfuse] 回调注入失败（agent=%s），按无观测运行", agent_name, exc_info=True
        )
        return agent
