"""推理模型输出截断兜底中间件（主 Agent 与评审子代理共用）。

背景：deepseek-v4 系列为推理模型，reasoning 与正文共享 max_tokens 配额。
主 Agent 在长上下文（数万 tokens 的 RAG 检索/文件读取结果）后进行深度规划时，
思考链可能耗尽全部输出配额，API 返回 finish_reason=length、正文 0 字符、无
tool_calls——react 循环把这条空消息视为"任务完成"，run 以 success 静默结束，
用户视角就是"agent 突然中断"（2026-08-06 thread e67525ea 实证：
input=67.9K，reasoning=8192/8192，content=0；同类问题此前已在子代理出现，
见 subagent_result_guard_middleware.py；2026-08-15 thread 894dddca 实证：
adversarial-reviewer 子代理在 16384 预算下仍撞顶，空返回后整个 task 重跑，
一次本可内部自愈的截断放大为 18 分钟假死）。

本中间件在每次模型调用后检查响应：若为空截断响应，则在请求副本上追加一条
提醒消息（request.override，不落 state）后重新调用模型；重试仍撞顶时返回
带可见诊断说明的 AI 消息，让 run 以用户可感知的信息结束而非无声消失。

2026-08-25 扩展：覆盖「带 tool_calls 的截断」（thread 6f08f7ab 实证：一次
序列化 33 条用例时 finish_reason=length，langchain 把截断的 tool_call 参数
修补成合法 JSON 放行给工具执行，JSONL 断弦报错，模型靠试错分批收敛）。
此类响应同样自动重试（nudge 引导缩小单次调用数据量）；重试耗尽后剥离
tool_calls 改写为诊断文本——绝不让截断的工具调用进入 tools 节点执行。
"""
from __future__ import annotations

import logging
from typing import Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

from app.config.settings import settings

logger = logging.getLogger(__name__)

# 空截断响应的最大自动重试次数（每次重试都是一轮完整模型调用，需克制）
_MAX_RETRIES = 2

_NUDGE_TEMPLATE = (
    "[系统提示] 你的上一次回复因输出 token 上限（max_tokens={max_tokens}）被思考链"
    "（reasoning）全部耗尽，正文未能产出任何内容（finish_reason=length），"
    "在用户视角等同于对话中断。请立即从断点处恢复工作，并严格遵守：\n"
    "1. 大幅压缩内部推理，禁止展开长篇规划——直接基于已有上下文产出下一步动作"
    "（工具调用或结论正文）；\n"
    "2. 需要长篇分析时，把分析过程用 write_file 写入工作区文件，正文只给摘要；\n"
    "3. 不要重复之前已成功执行的检索/读取类工具调用，直接利用已有结果继续。"
)

_TOOL_CALL_NUDGE_TEMPLATE = (
    "[系统提示] 你的上一次回复因输出 token 上限（max_tokens={max_tokens}）被截断"
    "（finish_reason=length），携带的工具调用参数 JSON 不完整，执行必然失败"
    "（该调用已被系统拦截、未执行）。请压缩推理后立即重发，并严格遵守：\n"
    "1. 若是 save_test_cases_file：单次调用不得超过 10 条用例，超出拆成多次调用"
    "（可并行），写入分片文件（如 test_cases_module_01_p1.jsonl、_p2.jsonl）；\n"
    "2. 大幅压缩内部推理，把 token 预算留给工具参数；\n"
    "3. 工具参数中的长文本（用例步骤、测试数据）保持精炼，禁止整段复述文档原文。"
)

_DIAGNOSIS_TEMPLATE = (
    "⚠️ 本轮生成被模型输出上限打断：思考链（reasoning）耗尽了全部 {max_tokens} "
    "输出配额，未能产出正文（finish_reason=length）。系统已自动重试 {retries} 次仍未恢复。\n\n"
    "**建议操作：**\n"
    "- 直接回复「继续」，我会从断点处接着执行；\n"
    "- 或把本次需求拆小后重新发起。\n\n"
    "（诊断：input_tokens={input_tokens}，reasoning_tokens={reasoning}，content=0）"
)

_TOOL_CALL_DIAGNOSIS_TEMPLATE = (
    "⚠️ 本轮工具调用被模型输出上限打断：参数 JSON 在 finish_reason=length 处截断，"
    "系统已自动重试 {retries} 次仍撞顶，相关调用未执行、未写入任何内容。\n\n"
    "**建议操作：**\n"
    "- 直接回复「继续」，我会改为小批量（每次不超过 10 条）重试；\n"
    "- 或把本次需求拆小后重新发起。\n\n"
    "（诊断：input_tokens={input_tokens}，reasoning_tokens={reasoning}，"
    "tool_calls={tool_names}）"
)


def _content_is_empty(content: object) -> bool:
    """判定 AIMessage.content 是否为空白（str / content-block list / None）。"""
    if content is None:
        return True
    if isinstance(content, str):
        return not content.strip()
    if isinstance(content, list):
        return not any(
            isinstance(block, dict)
            and block.get("type") == "text"
            and str(block.get("text", "")).strip()
            for block in content
        )
    return True


def _classify_truncation(response: ModelResponse) -> str | None:
    """分类截断响应："empty"（空正文无工具调用）/ "tool_calls"（带工具调用）/ None。"""
    messages = getattr(response, "result", None) or []
    if not messages:
        return None
    msg = messages[-1]
    if getattr(msg, "type", None) != "ai":
        return None
    finish_reason = (getattr(msg, "response_metadata", None) or {}).get("finish_reason")
    if finish_reason != "length":
        return None
    if getattr(msg, "tool_calls", None) or getattr(msg, "invalid_tool_calls", None):
        return "tool_calls"
    if _content_is_empty(getattr(msg, "content", None)):
        return "empty"
    return None


def _is_empty_length_truncation(response: ModelResponse) -> bool:
    """识别「finish_reason=length 且正文为空且无工具调用」的截断响应。"""
    return _classify_truncation(response) == "empty"


def _usage(msg: AIMessage) -> tuple[int | None, int | None]:
    usage = getattr(msg, "usage_metadata", None) or {}
    details = usage.get("output_token_details") or {}
    return usage.get("input_tokens"), details.get("reasoning")


class TruncationRetryMiddleware(AgentMiddleware):
    """主 Agent 空截断响应的自动重试与可见诊断（正常路径零介入）。

    Args:
        max_tokens: nudge/诊断文案中展示的输出上限。主 Agent 与评审子代理的
            预算不同（后者见 ADVERSARIAL_REVIEWER_MAX_TOKENS），须如实告知模型，
            否则 nudge 中的数字会误导其压缩幅度；None 时用 settings.llm_max_tokens。
    """

    def __init__(self, max_tokens: int | None = None) -> None:
        self._max_tokens = max_tokens

    @property
    def _effective_max_tokens(self) -> int:
        return self._max_tokens if self._max_tokens is not None else settings.llm_max_tokens

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        response = await handler(request)

        attempts = 0
        kind = _classify_truncation(response)
        while kind is not None and attempts < _MAX_RETRIES:
            attempts += 1
            msg = response.result[-1]
            input_tokens, reasoning = _usage(msg)
            logger.warning(
                "main agent %s truncation detected (finish_reason=length, "
                "input_tokens=%s, reasoning=%s); retry %d/%d with nudge",
                kind, input_tokens, reasoning, attempts, _MAX_RETRIES,
            )
            template = (
                _TOOL_CALL_NUDGE_TEMPLATE if kind == "tool_calls" else _NUDGE_TEMPLATE
            )
            nudge = HumanMessage(
                content=template.format(max_tokens=self._effective_max_tokens)
            )
            # 请求副本注入提醒，不写 state；每次都从原始请求派生，只带一条提醒
            retry_request = request.override(messages=[*(request.messages or []), nudge])
            response = await handler(retry_request)
            kind = _classify_truncation(response)

        if kind is None:
            return response

        # 重试耗尽：改写为可见诊断，避免 run 静默结束 / 截断工具调用被执行
        msg = response.result[-1]
        input_tokens, reasoning = _usage(msg)
        logger.error(
            "main agent %s truncation persisted after %d retries "
            "(input_tokens=%s, reasoning=%s); returning visible diagnosis",
            kind, _MAX_RETRIES, input_tokens, reasoning,
        )
        if kind == "tool_calls":
            # 剥离截断的 tool_calls——绝不让参数不完整的调用进入 tools 节点
            # （thread 6f08f7ab 实证：langchain 会把截断参数修补成合法 JSON
            # 放行执行，JSONL 断弦报错后模型靠试错分批收敛）。
            tool_names = "、".join(
                tc.get("name", "?") if isinstance(tc, dict) else getattr(tc, "name", "?")
                for tc in getattr(msg, "tool_calls", None) or []
            ) or "（未解析）"
            stripped = msg.model_copy()
            stripped.tool_calls = []
            stripped.invalid_tool_calls = []
            ak = dict(getattr(stripped, "additional_kwargs", {}) or {})
            ak.pop("tool_calls", None)
            stripped.additional_kwargs = ak
            diagnosis = stripped.model_copy(update={
                "content": _TOOL_CALL_DIAGNOSIS_TEMPLATE.format(
                    max_tokens=self._effective_max_tokens,
                    retries=_MAX_RETRIES,
                    input_tokens=input_tokens,
                    reasoning=reasoning,
                    tool_names=tool_names,
                )
            })
        else:
            diagnosis = msg.model_copy(update={
                "content": _DIAGNOSIS_TEMPLATE.format(
                    max_tokens=self._effective_max_tokens,
                    retries=_MAX_RETRIES,
                    input_tokens=input_tokens,
                    reasoning=reasoning,
                )
            })
        return ModelResponse(result=[*response.result[:-1], diagnosis])
