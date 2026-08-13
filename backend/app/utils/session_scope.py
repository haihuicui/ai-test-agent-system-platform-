"""跨 Agent 统一的会话作用域（project + thread）传递。

所有 Agent 共享的会话隔离作用域：``project_identifier``（项目）与
``thread_id``（LangGraph 会话）。workspace 隔离、RAG space 映射、
Langfuse 打标等能力统一从本模块读取。

传递通道（按可靠性排序，沿用 testcase agent 2026-08 双会话实测结论）：
1. **平台原生 config 键（主通道）**：LangGraph 平台每次 run 自动注入
   ``config["configurable"]["thread_id"]``，且（langgraph_api ≥0.5 本地/自部署
   形态）会把 run 的 context 字段（project_identifier 等）合并进 configurable。
   该 configurable 由 run 配置派生，模型节点与工具节点均可读到同一组原生键。
2. ``set_session_scope`` 的写回/configvar 作为回退——注意仅靠 contextvar set
   或写回自定义键都不可靠：LangGraph 中模型调用与工具调用是兄弟 task（各自
   复制父 context 快照），且 patch_config 会重建 configurable 子 dict（中间件
   内写回的自定义键传播不到工具节点）。

本模块只依赖 langgraph.config 与标准库，不 import 任何 app 内模块——
可安全被 tools 包、agent 包、services 包任意方向引用，无循环 import 风险。

用法：
- 入口侧（ContextInjectionMiddleware / agent 工厂）：``set_session_scope(...)``
- 消费侧（工具/服务）：``get_session_project()`` / ``get_session_thread_id()``
"""

from __future__ import annotations

import contextvars
from typing import Optional

from langgraph.config import get_config

# config["configurable"] 写回键名（独立于平台原生字段，避免污染）
_CONFIG_PROJECT_KEY = "session_project"
_CONFIG_THREAD_KEY = "session_thread_id"

# 当前会话的项目标识（runtime context 的 project_identifier）
session_project_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "session_project",
    default=None,
)

# 当前会话的 LangGraph thread_id（config["configurable"]["thread_id"]，
# 平台每次 run 自动注入；非平台环境/单元测试中可能为 None）
session_thread_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "session_thread_id",
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
        _inject_trace_metadata(config, project_identifier, thread_id)


def _inject_trace_metadata(
    config: dict,
    project_identifier: Optional[str],
    thread_id: Optional[str],
) -> None:
    """向 run config 的 metadata 注入 Langfuse trace 维度（fail-open）。

    - ``langfuse_session_id``：v3 CallbackHandler 约定的会话维度键，
      用 thread_id 让同一会话的多次 run 聚合成一个 Langfuse session；
    - ``project_id``：非保留键，v3 handler 会并入 trace.metadata，
      供按项目过滤/成本分摊。

    不写 ``langfuse_tags``：图级 with_config 已注入 ``agent:<name>``，
    运行期 metadata 浅合并会覆盖同名键，追加反而丢掉 agent 标签。
    metadata 传递依赖 LangChain config 合并行为，写不进去也不影响功能。
    """
    try:
        metadata = config.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
            config["metadata"] = metadata
        if thread_id:
            metadata["langfuse_session_id"] = thread_id
        if project_identifier:
            metadata["project_id"] = project_identifier
    except Exception:
        pass


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
