"""Web MCP 浏览器工具守卫中间件。

针对 thread 681b9d01 实证的两类失控场景：

1. **MCP 工具调用无上限 hang**：目标站登录态中途失效返回
   ``401 + WWW-Authenticate: Basic`` 时，Chrome 弹原生 Basic Auth 弹窗，
   页面 JS 冻结，Playwright MCP 调用永不返回（实证单次调用卡死 28 分钟，
   最终靠重启 LangGraph 服务才终结 run）。这里给 browser_/planner_/generator_/test_
   工具加 ``asyncio.wait_for`` 超时，超时返回可见错误 ToolMessage，
   让 agent 走诊断路径而不是无声卡死。

2. **超时时确定性自动重建登录态**：若本 run 注入了项目登录态且环境保存了
   可用凭据（form_login/token_inject），超时后不等 LLM 决策，直接复用
   续期链路 ``execute_storage_state_renewal`` 后台重新登录生成新
   storageState，并原地覆盖运行中 playwright.config.ss-*.js 引用的旧文件——
   浏览器重启后自然读到新登录态，绕开上下文热刷新难题。每 run 限一次，
   失败则回退原超时诊断文案。

3. **browser_run_code_unsafe 连败盲探**：实证中 agent 连续 8+ 次用
   run_code_unsafe 盲探 DOM/API（含在 about:blank 上对业务 API 发 fetch 的
   origin null CORS 错误）。这里在下一次模型调用前检测「尾部连续 >=2 条
   run_code_unsafe 错误 ToolMessage」，注入一次性纠偏 SystemMessage，
   强制先 browser_snapshot 重建页面认知。
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage, ToolMessage

from app.config.settings import settings
from app.utils.sync_executor import run_sync

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

# 自动重建登录态的单次执行上限：续期链路要起一个 Playwright 登录脚本，
# 正常 <60s；给足余量但必须有界，否则守卫本身变成新的挂点。
_REGEN_TIMEOUT_SECONDS = 300.0

_REGEN_SUCCESS_NOTE = (
    "工具调用超时（{timeout}s），系统已用环境已存凭据**自动重建登录态**"
    "（耗时 {elapsed:.0f}s）。旧浏览器页面已被原生登录弹窗冻结，请严格按顺序恢复：\n"
    "1. `browser_close` 关闭旧浏览器；\n"
    "2. `planner_setup_page(project=\"chromium\")` 重新启动——新登录态已写入"
    "配置引用的 storageState 文件，重启后自动生效；\n"
    "3. `browser_navigate` 回到你刚才的目标 URL，用 browser_snapshot 确认页面"
    "恢复正常后继续任务。\n"
    "禁止在原冻结页面上继续任何 fetch/操作。"
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
    """MCP 浏览器工具超时保护 + 登录态自动重建 + run_code_unsafe 连败守卫。"""

    def __init__(self) -> None:
        # 中间件实例随 make_agent 每 run 新建，实例旗标即"每 run 限一次"
        self._regen_attempted = False
        self._regen_lock = asyncio.Lock()

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
                "[WebToolGuard] MCP 工具 %s 调用超时（%ds），尝试自动重建登录态。",
                tool_name,
                timeout,
            )
            regenerated, regen_note, elapsed = await self._try_regenerate_login_state()
            if regenerated:
                message = _REGEN_SUCCESS_NOTE.format(timeout=timeout, elapsed=elapsed)
                logger.info("[WebToolGuard] 登录态自动重建成功（%.0fs）。", elapsed)
            else:
                logger.warning("[WebToolGuard] 登录态自动重建跳过/失败：%s", regen_note)
                message = _TIMEOUT_ERROR_NOTE.format(timeout=timeout) + (
                    f"\n\n系统自动重建登录态未完成：{regen_note}"
                )
            content = json.dumps(
                {
                    "success": False,
                    "error": f"Tool '{tool_name}' timed out after {timeout}s",
                    "error_type": "ToolCallTimeout",
                    "login_state_regenerated": regenerated,
                    "message": message,
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
    # 登录态自动重建（每 run 限一次，确定性动作，不经 LLM 决策）
    # ------------------------------------------------------------------
    async def _try_regenerate_login_state(self) -> tuple[bool, str, float]:
        """超时时用环境已存凭据重新生成登录态并原地覆盖旧 storageState 文件。

        返回 (是否重建成功, 说明, 耗时秒)。成功判据：续期链路产出了新的
        completed job（新 output_path ≠ 本 run 注入的旧路径）——续期链路自身
        静默吞错，这是唯一可靠的外部信号。
        """
        started_at = asyncio.get_running_loop().time()

        def _result(ok: bool, note: str) -> tuple[bool, str, float]:
            return ok, note, asyncio.get_running_loop().time() - started_at

        async with self._regen_lock:
            if self._regen_attempted:
                return _result(False, "本 run 已尝试过一次自动重建，不重复执行")
            self._regen_attempted = True

        try:
            from langgraph.config import get_config

            cfg = get_config() or {}
            project_identifier = (cfg.get("configurable") or {}).get(
                "project_identifier", ""
            )
        except Exception:
            project_identifier = ""
        if not project_identifier:
            return _result(False, "无法从 run 配置解析 project_identifier")

        # 延迟 import：与 agent.py 启动路径保持一致，避免模块级循环依赖
        from app.config.database import async_session_factory
        from app.models.environment import AuthType
        from app.repositories.environment_repo import EnvironmentRepository
        from app.repositories.project_repo import ProjectRepository
        from app.utils.web_mcp_storage_state import (
            _login_state_cache,
            resolve_project_storage_state_path,
        )

        # 本 run 注入的旧路径：运行中 playwright.config.ss-*.js 引用的就是它，
        # 重建后要原地覆盖，浏览器重启才会读到新登录态。
        cached = _login_state_cache.get(project_identifier)
        old_path = cached[2] if cached else None
        if not old_path:
            return _result(False, "本 run 未注入项目登录态，无重建对象")

        try:
            async with async_session_factory() as session:
                project = await ProjectRepository(session).get_by_identifier(
                    project_identifier
                )
                if project is None:
                    return _result(False, f"项目不存在: {project_identifier}")
                env = await EnvironmentRepository(session).get_default_by_project(
                    project.id
                )
        except Exception as exc:
            return _result(False, f"查询项目/环境失败: {exc}")

        if env is None:
            return _result(False, "项目无默认环境")
        auth_config = env.auth_config or {}
        if env.auth_type != AuthType.FORM_LOGIN.value or not (
            env.auth_secret or auth_config.get("token_inject")
        ):
            return _result(False, "环境未保存可用登录凭据（form_login/token_inject）")

        try:
            from app.services.scheduler_service import TestRunSchedulerService

            await asyncio.wait_for(
                TestRunSchedulerService.execute_storage_state_renewal(str(env.id)),
                timeout=_REGEN_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            return _result(False, f"重建执行超时（{_REGEN_TIMEOUT_SECONDS:.0f}s）")
        except Exception as exc:
            return _result(False, f"重建执行异常: {type(exc).__name__}: {exc}")

        new_path = await resolve_project_storage_state_path(project_identifier, env.id)
        if not new_path or new_path == old_path:
            return _result(
                False, "重建未产出新的有效登录态（生成失败，详见 storage_state_jobs）"
            )

        await run_sync(shutil.copyfile, new_path, old_path)
        return _result(True, "ok")

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
