"""RAG 控制中间件。

根据运行时上下文中的 `enable_rag` 开关，决定是否将 RAG 工具暴露给模型。
关闭 RAG 时，会过滤掉所有以 `rag_` 开头的工具，并在系统提示词中追加禁用说明，
防止模型尝试调用历史知识库。
"""
import re
from typing import Any

from deepagents.middleware import SkillsMiddleware
from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware import AgentMiddleware, ModelRequest

# RAG Skill 在虚拟文件系统中的路由前缀（见 agent.py 的 CompositeBackend 路由）
RAG_SKILL_SOURCE_PREFIX = "/rag/"


# ---------------------------------------------------------------------------
# 轻量级意图识别
# ---------------------------------------------------------------------------

def _extract_message_text(msg: Any) -> str:
    """从一条消息对象中提取纯文本内容。"""
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


def _looks_like_meta_question(text: str) -> bool:
    """判断用户是否在询问 Agent 的 skill / 能力 / 能做什么等元问题。

    这类问题不需要检索历史知识库；跳过 RAG 可以消除一次 ~8s 的检索延迟。
    """
    cleaned = re.sub(r"\s+", "", text.lower())
    patterns = [
        # 你有什么 skill / 技能 / 能力 / 功能 / 用 / 本事
        r"你(有|会)(什么|哪些)(skill|skills|技能|能力|功能|作用|用|本事)",
        # 你有什么 / 你会什么（直接以“什么/哪些”结尾，默认问能力）
        r"你(有|会)(什么|哪些)$",
        # 介绍一下你的能力 / 告诉我你会什么
        r"(介绍|说说|告诉|讲)(一下|我)?(你|你的)(skill|skills|技能|能力|功能|作用|会什么)",
        # 你能做什么 / 你可以做什么 / 你会做什么
        r"你(能|可以|会)做(什么|哪些|啥)",
        # 你能干什么 / 你可以干什么 / 你会干什么
        r"你(能|可以|会)干(什么|哪些|啥)",
        # 你是什么 agent / 助手
        r"你(是|做)什么(的|agent|助手)?",
        # 更口语化的表达
        r"你有什么skill",
        r"showskills",
    ]
    return any(re.search(p, cleaned) for p in patterns)


def resolve_enable_rag(messages: list[Any] | None, runtime: Any) -> bool:
    """解析 RAG 开关的唯一权威实现。

    优先级：最近一条 human 消息的 ``additional_kwargs.enable_rag``
    > 运行时上下文 ``context.enable_rag`` > 默认 True。

    注意：
    - 只从 human 消息读取开关，避免从 AI / tool 消息的 additional_kwargs
      中误读（两类中间件此前行为不一致的 bug 根源）。
    - 沿历史倒序找最近一条 human 消息，而不是只看 ``messages[-1]``——
      工具调用循环中最后一条可能是 ToolMessage，会导致开关在
      一轮对话中途翻转。
    - 若用户询问的是 Agent 自身的 skill / 能力等元问题，自动关闭 RAG，
      避免不必要的 ~8s 检索延迟。
    """
    for msg in reversed(messages or []):
        if getattr(msg, "type", None) == "human":
            ak = getattr(msg, "additional_kwargs", None) or {}
            if isinstance(ak, dict) and "enable_rag" in ak:
                return bool(ak["enable_rag"])

            # 元问题无需检索历史知识库，直接跳过 RAG 以减少延迟。
            text = _extract_message_text(msg)
            if _looks_like_meta_question(text):
                return False
            break  # 最近的 human 消息未携带开关 -> 回退到 context

    context = getattr(runtime, "context", None) if runtime else None
    return getattr(context, "enable_rag", True) if context else True


class RAGMiddleware(AgentMiddleware):
    """根据 enable_rag 开关动态控制 RAG 工具的注入与过滤。"""

    def _is_rag_enabled(self, request: ModelRequest) -> bool:
        return resolve_enable_rag(request.messages, getattr(request, "runtime", None))

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


class RagAwareSkillsMiddleware(SkillsMiddleware):
    """RAG 开关感知的 SkillsMiddleware。

    RAG 工具过滤（RAGMiddleware）只移除了 rag_* 工具，但 SkillsMiddleware
    仍会把 /rag/ 下的 rag-query Skill 注入系统提示词；该 Skill 内含
    "必须优先使用检索工具"等强指令，会在 enable_rag=False 时反向驱动模型
    执行检索，使开关失效。

    本中间件在渲染 skill 列表时按请求过滤掉 /rag/ 来源的 skill 及其
    source 位置行，保证 RAG 开关端到端一致。skill 加载（before_agent）
    不受影响——过滤发生在渲染层，开关打开时无需重新加载。
    """

    def modify_request(self, request: ModelRequest) -> ModelRequest:
        if resolve_enable_rag(request.messages, getattr(request, "runtime", None)):
            return super().modify_request(request)

        state = getattr(request, "state", None) or {}
        skills_metadata = [
            skill
            for skill in state.get("skills_metadata", [])
            if not str(skill.get("path", "")).startswith(RAG_SKILL_SOURCE_PREFIX)
        ]
        skills_load_errors = state.get("skills_load_errors", [])

        # source 位置行同样过滤掉 /rag/，避免模型按路径直接 read_file
        source_pairs = [
            (path, label)
            for path, label in zip(self.sources, self.source_labels, strict=True)
            if not path.startswith(RAG_SKILL_SOURCE_PREFIX)
        ]
        last = len(source_pairs) - 1
        skills_locations = "\n".join(
            f"**{label} Skills**: `{path}`{' (higher priority)' if i == last else ''}"
            for i, (path, label) in enumerate(source_pairs)
        )

        skills_section = self.system_prompt_template.format(
            skills_locations=skills_locations,
            skills_load_warnings=self._format_skills_load_warnings(skills_load_errors),
            skills_list=self._format_skills_list(skills_metadata),
        )
        return request.override(
            system_message=append_to_system_message(request.system_message, skills_section)
        )
