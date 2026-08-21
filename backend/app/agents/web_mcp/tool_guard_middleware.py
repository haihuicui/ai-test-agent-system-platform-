"""Web MCP 浏览器工具守卫中间件。

针对 thread 681b9d01 实证的两类失控场景：

1. **MCP 工具调用无上限 hang**：目标站登录态中途失效返回
   ``401 + WWW-Authenticate: Basic`` 时，Chrome 弹原生 Basic Auth 弹窗，
   页面 JS 冻结，Playwright MCP 调用永不返回（实证单次调用卡死 28 分钟，
   最终靠重启 LangGraph 服务才终结 run）。这里给 browser_/planner_/generator_/test_
   工具加 ``asyncio.wait_for`` 超时，超时返回可见错误 ToolMessage，
   让 agent 走诊断路径而不是无声卡死。

2. **browser_run_code_unsafe 连败盲探**：实证中 agent 连续 8+ 次用
   run_code_unsafe 盲探 DOM/API（含在 about:blank 上对业务 API 发 fetch 的
   origin null CORS 错误）。这里在下一次模型调用前检测「尾部连续 >=2 条
   run_code_unsafe 错误 ToolMessage」，注入一次性纠偏 SystemMessage，
   强制先 browser_snapshot 重建页面认知。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage, ToolMessage

from app.config.settings import settings

if TYPE_CHECKING:
    from langchain.agents.middleware.types import ModelRequest, ModelResponse
    from langgraph.types import Command

logger = logging.getLogger(__name__)

# 与 agent.py 中 wrap_tools_with_error_handling 的 tool_patterns 保持一致
_GUARDED_TOOL_PREFIXES = ("browser_", "planner_", "generator_", "test_")

# 连败守卫触发阈值：尾部连续 N 条 run_code_unsafe 错误
_RUN_CODE_FAIL_THRESHOLD = 2

# 连败守卫 nudge 标记：注入的消息带此前缀，避免同一轮重复注入
_GUARD_NUDGE_PREFIX = "[WebToolGuard]"

_TIMEOUT_ERROR_NOTE = (
    "工具调用超时（{timeout}s 未返回）。页面很可能被浏览器原生登录弹窗阻塞"
    "（目标站登录态失效返回 401 + WWW-Authenticate 时 Chrome 会弹出该弹窗，"
    "页面 JS 完全冻结，Playwright 无法自动关闭）。"
    "请立即用 browser_snapshot 检查页面状态：若确认登录态失效，"
    "按「运行时认证失效」约定重新 UI 登录或明确告知用户更新项目登录态后中止，"
    "禁止不做诊断直接重试同一工具。"
)

_RUN_CODE_NUDGE = (
    "[WebToolGuard] 你已连续 {count} 次 browser_run_code_unsafe 调用失败。"
    "停止盲探，按以下顺序恢复：\n"
    "1. 先用 browser_snapshot() 确认当前页面 URL 与内容——浏览器可能已重启到 "
    "about:blank（此前实证：在空页上 fetch 业务 API 会因 origin null 被 CORS 拦截）；\n"
    "2. 若页面是 about:blank 或已偏离目标页，先 browser_navigate 回目标 URL；\n"
    "3. 若快照显示登录页/加载卡死/弹窗迹象，按「运行时认证失效」约定处理；\n"
    "4. 确认页面正常后，优先用语义定位器 + browser_snapshot 完成任务，"
    "run_code_unsafe 仅作为最后手段。"
)


class WebToolGuardMiddleware(AgentMiddleware):
    """MCP 浏览器工具超时保护 + run_code_unsafe 连败守卫（正常路径零介入）。"""

    # ------------------------------------------------------------------
    # 工具超时
    # ------------------------------------------------------------------
    def wrap_tool_call(
        self,
        request: "Any",
        handler: "Callable[[Any], ToolMessage | Command[Any]]",
    ) -> "ToolMessage | Command[Any]":
        # 同步路径无法 await 超时控制，直接放行；本 runtime 走异步路径
        return handler(request)

    async def awrap_tool_call(
        self,
        request: "Any",
        handler: "Callable[[Any], Awaitable[ToolMessage | Command[Any]]]",
    ) -> "ToolMessage | Command[Any]":
        tool_call = getattr(request, "tool_call", None) or {}
        tool_name = tool_call.get("name") or ""
        if not tool_name.startswith(_GUARDED_TOOL_PREFIXES):
            return await handler(request)

        timeout = settings.web_mcp_tool_call_timeout_seconds
        try:
            # 注意：必须 await wait_for(...)，漏 await 会让整个工具链炸掉
            # 且 traceback 里看不到本中间件（历史教训）。
            return await asyncio.wait_for(handler(request), timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(
                "[WebToolGuard] MCP 工具 %s 调用超时（%ds），返回诊断错误。",
                tool_name,
                timeout,
            )
            content = json.dumps(
                {
                    "success": False,
                    "error": f"Tool '{tool_name}' timed out after {timeout}s",
                    "error_type": "ToolCallTimeout",
                    "message": _TIMEOUT_ERROR_NOTE.format(timeout=timeout),
                },
                ensure_ascii=False,
            )
            return ToolMessage(
                content=content,
                tool_call_id=tool_call.get("id", ""),
                name=tool_name,
                status="error",
            )

    # ------------------------------------------------------------------
    # run_code_unsafe 连败守卫
    # ------------------------------------------------------------------
    def _count_trailing_run_code_failures(self, messages: list[Any]) -> int:
        """统计消息尾部连续的 browser_run_code_unsafe 错误 ToolMessage 条数。"""
        count = 0
        for msg in reversed(messages):
            if isinstance(msg, ToolMessage):
                if (
                    msg.name == "browser_run_code_unsafe"
                    and msg.status == "error"
                ):
                    count += 1
                    continue
                # 其他工具的结果（成功或失败）都打断"连续盲探"计数
                break
            # AI/System 消息等其他类型：打断。纠偏 nudge 走 request.override
            # 不落 state，因此模型响应（AIMessage）天然打断计数，不会重复注入；
            # 若模型此后又连续失败则再次注入——这正是期望行为。
            break
        return count

    async def awrap_model_call(
        self,
        request: "ModelRequest",
        handler: "Callable[[ModelRequest], Awaitable[ModelResponse]]",
    ) -> "ModelResponse":
        messages = list(request.messages or [])
        failures = self._count_trailing_run_code_failures(messages)
        if failures >= _RUN_CODE_FAIL_THRESHOLD:
            logger.warning(
                "[WebToolGuard] browser_run_code_unsafe 连续 %d 次失败，注入纠偏指引。",
                failures,
            )
            nudge = SystemMessage(content=_RUN_CODE_NUDGE.format(count=failures))
            request = request.override(messages=[*messages, nudge])
        return await handler(request)
