"""RAG 控制中间件。

根据运行时上下文中的 `enable_rag` 开关，决定是否将 RAG 工具暴露给模型。
关闭 RAG 时，会过滤掉所有以 `rag_` 开头的工具，并在系统提示词中追加禁用说明，
防止模型尝试调用历史知识库。
"""
from langchain.agents.middleware import AgentMiddleware, ModelRequest


class RAGMiddleware(AgentMiddleware):
    """根据 enable_rag 开关动态控制 RAG 工具的注入与过滤。"""

    def _is_rag_enabled(self, request: ModelRequest) -> bool:
        runtime = getattr(request, "runtime", None)
        context = getattr(runtime, "context", None) if runtime else None
        return getattr(context, "enable_rag", True) if context else True

    def _filter_rag_tools(self, tools: list) -> list:
        """过滤掉名称以 rag_ 开头的 RAG 工具。"""
        return [t for t in tools if not getattr(t, "name", "").startswith("rag_")]

    def _append_system_note(self, request: ModelRequest, note: str) -> ModelRequest:
        """在 system_message 中追加一段文本提示。"""
        if isinstance(request.system_message.content, list):
            request.system_message.content = request.system_message.content + [
                {"type": "text", "text": note}
            ]
        else:
            request.system_message.content = request.system_message.content + note
        return request

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler,
    ):
        if self._is_rag_enabled(request):
            return await handler(request)

        # RAG 关闭：过滤工具并追加禁用提示
        tools = getattr(request, "tools", []) or []
        filtered_tools = self._filter_rag_tools(tools)
        note = (
            "\n\n[RAG 检索已关闭] 请勿调用任何 RAG 相关工具"
            "（如 rag_query、rag_query_data 等），直接基于用户提供的原始需求进行分析，"
            "无需检索历史知识库。"
        )
        request = self._append_system_note(request, note)

        if hasattr(request, "override"):
            request = request.override(tools=filtered_tools)
        else:
            request.tools = filtered_tools

        return await handler(request)
