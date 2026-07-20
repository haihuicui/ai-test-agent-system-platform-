"""场景测试质量校验中间件。

把场景测试的生成/执行质量红线从"靠模型自觉"升级为"系统强制拦截"：
- 在 execute_scenario 执行前调用 validate_scenario_design 做最终静态预检；
- 预检失败时直接拦截工具调用，返回错误 ToolMessage，模型当轮即可修正重试。

当前版本聚焦 execute_scenario 的最终拦截；add_scenario_step 等创建路径的
实时轻量校验由 backend/app/agents/tools/api/scenario_tools.py 在工具内部完成。
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langgraph.types import Command

    from langchain.agents.middleware.types import ToolCallRequest

logger = logging.getLogger(__name__)

_EXECUTE_SCENARIO = "execute_scenario"


def _parse_result_json(content: Any) -> dict[str, Any] | None:
    """容错解析工具结果 JSON。"""
    if not isinstance(content, str) or not content.strip().startswith("{"):
        return None
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


async def _precheck_execute_scenario(request: "ToolCallRequest") -> ToolMessage | None:
    """execute_scenario 执行前调用 validate_scenario_design 做最终静态预检。"""
    tool_call = request.tool_call
    args = tool_call.get("args") or {}

    # 用户显式要求跳过设计门禁时，不做拦截
    if args.get("skip_design_gate"):
        return None

    scenario_id = args.get("scenario_id")
    if not scenario_id:
        return None

    # 复用独立的校验工具
    from app.agents.tools.api.scenario_design_validator import validate_scenario_design

    try:
        result = await validate_scenario_design.ainvoke({"scenario_id": scenario_id})
    except Exception as exc:
        logger.warning("场景质量中间件调用 validate_scenario_design 失败: %s", exc)
        # 校验工具自身失败时不阻断执行，避免中间件 bug 导致场景完全无法跑
        return None

    data = _parse_result_json(result)
    if not data:
        return None

    if data.get("success") and data.get("data", {}).get("valid"):
        return None

    issues = data.get("data", {}).get("issues", []) if data.get("success") else []
    error_msg = data.get("error") if not data.get("success") else "场景设计静态预检未通过"

    logger.info("场景质量中间件拦截 execute_scenario: %s", error_msg)
    content = json.dumps({
        "success": False,
        "error": "场景质量中间件拦截：" + error_msg,
        "issues": issues,
        "message": (
            "请在执行前修复以上问题，或显式设置 skip_design_gate=true 绕过。"
            "修复建议：补充缺失的必填字段、建立路径参数映射、为创建类步骤添加 teardown。"
        ),
    }, ensure_ascii=False)
    return ToolMessage(
        content=content,
        tool_call_id=tool_call["id"],
        name=_EXECUTE_SCENARIO,
        status="error",
    )


class ScenarioQualityGateMiddleware(AgentMiddleware):
    """场景测试执行前的确定性质量门禁。

    - awrap_tool_call：execute_scenario 执行前复用 validate_scenario_design 做最终预检，
      失败则拦截并返回问题清单；
    - wrap_tool_call：同步版本同样处理（框架可能走同步路径）。
    """

    def wrap_tool_call(
        self,
        request: "ToolCallRequest",
        handler: Callable[["ToolCallRequest"], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        if request.tool_call.get("name") == _EXECUTE_SCENARIO:
            # 同步路径下无法 await，直接放行；异步路径由 awrap_tool_call 处理
            logger.debug("ScenarioQualityGateMiddleware 同步路径放行 %s", _EXECUTE_SCENARIO)
        return handler(request)

    async def awrap_tool_call(
        self,
        request: "ToolCallRequest",
        handler: Callable[["ToolCallRequest"], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        if request.tool_call.get("name") == _EXECUTE_SCENARIO:
            blocked = await _precheck_execute_scenario(request)
            if blocked is not None:
                return blocked
        return await handler(request)
