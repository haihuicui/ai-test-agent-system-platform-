"""模块级自检中间件。

在 ``batch_create_test_cases_tool`` 执行前自动触发模块级自检，把
``module_self_check_tool`` 的调用从"模型自觉"变成"代码强制"：

- 自动提取批量创建参数中的 ``test_cases``
- 复用 ``module_self_check_tool`` 的确定性校验逻辑
- 自检不通过时拦截本次批量创建，返回违规清单
- 自检通过后继续执行原有批量创建逻辑
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from app.agents.tools.testcase.module_check_tools import _perform_module_self_check

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langchain.agents.middleware.types import ToolCallRequest
    from langgraph.types import Command

logger = logging.getLogger(__name__)

__all__ = ["ModuleSelfCheckMiddleware"]

_TARGET_TOOL = "batch_create_test_cases_tool"


def _resolve_expected_module(test_cases: list[dict[str, Any]]) -> str | None:
    """从用例列表推断期望模块名：优先取 module 字段的众数。"""
    modules = [
        str(case.get("module", "")).strip()
        for case in test_cases
        if isinstance(case, dict) and str(case.get("module", "")).strip()
    ]
    if not modules:
        return None
    most_common = Counter(modules).most_common(1)[0][0]
    return most_common


def _build_error_tool_message(
    tool_call: dict[str, Any], result: dict[str, Any]
) -> ToolMessage:
    """根据自检结果构造拦截用的错误 ToolMessage。"""
    content = json.dumps(
        {
            "success": False,
            "error": "模块级自检未通过，本次批量创建未执行",
            "passed": result.get("passed"),
            "total": result.get("total"),
            "p0_count": result.get("p0_count"),
            "violations": result.get("violations", []),
            "summary": result.get("summary"),
            "message": (
                "系统在批量创建前自动执行了模块级自检。请根据 violations 修正问题后重新调用，"
                "不要跳过自检。质量红线：1) 预期结果必须可客观判定；"
                "2) 每条用例必须提供具体测试数据值；"
                "3) case_number 必填且格式为 TC-[项目]-[模块]-[序号]；"
                "4) module 必填且与当前模块一致；"
                "5) 同一模块内用例编号不能重复。"
            ),
        },
        ensure_ascii=False,
    )
    return ToolMessage(
        content=content,
        tool_call_id=tool_call.get("id"),
        name=_TARGET_TOOL,
        status="error",
    )


def _precheck(request: ToolCallRequest) -> ToolMessage | None:
    """批量创建前执行模块级自检；不通过时构造错误 ToolMessage 拦截。"""
    tool_call = request.tool_call
    name = tool_call.get("name")
    if name != _TARGET_TOOL:
        return None

    args = tool_call.get("args") or {}
    test_cases = args.get("test_cases") or []
    if not test_cases:
        return None

    expected_module = _resolve_expected_module(test_cases)
    if not expected_module:
        logger.info("模块自检中间件：无法推断 expected_module，跳过自检")
        return None

    # 中间件场景不掌握文件路径，传入空 set；与已保存其他文件的重复性检查
    # 由模型显式调用 module_self_check_tool 时覆盖。
    result = _perform_module_self_check(
        cases=test_cases,
        expected_module=expected_module,
        current_file_paths=set(),
        min_p0_count=3,
        check_cross_file_duplicates=False,
    )

    if result.get("passed"):
        logger.info(
            "模块自检中间件：%s 通过（%d 条用例，P0 %d 条）",
            expected_module,
            result.get("total", 0),
            result.get("p0_count", 0),
        )
        return None

    logger.info(
        "模块自检中间件拦截 %s：%d 条违规",
        _TARGET_TOOL,
        len([v for v in result.get("violations", []) if v.get("level") == "error"]),
    )
    return _build_error_tool_message(tool_call, result)


class ModuleSelfCheckMiddleware(AgentMiddleware):
    """批量创建测试用例前的模块级自检中间件。

    - wrap_tool_call（创建前）：对 ``batch_create_test_cases_tool`` 的 ``test_cases``
      自动执行模块级自检，不通过则拦截并返回违规清单。
    """

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        blocked = _precheck(request)
        if blocked is not None:
            return blocked
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        blocked = _precheck(request)
        if blocked is not None:
            return blocked
        return await handler(request)
