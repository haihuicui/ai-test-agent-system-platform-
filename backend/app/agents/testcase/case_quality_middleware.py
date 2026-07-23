"""用例质量校验中间件。

在 ``create_test_case_tool`` / ``batch_create_test_cases_tool`` 执行前做
**确定性**质量校验（零 token 成本），把 SYSTEM_PROMPT 中的质量红线从
"靠模型自觉"变成"代码强制"：

- 预期结果禁止"正确""成功""正常"等模糊词，必须可客观判定
- 每条用例必须提供具体测试数据值（禁止空 test_data / 占位描述）
- case_number 必须符合 ``TC-[项目]-[模块]-[序号]`` 格式
- module（所属模块）必填

校验不通过时拦截工具调用，返回错误 ToolMessage，模型当轮即可修正重试。
创建成功后比对"提交数量 vs 成功数量"，有失败时追加提示让模型补全。
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from app.utils.testcase_validation import _is_fuzzy_result, _validate_case

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langgraph.types import Command

    from langchain.agents.middleware.types import ToolCallRequest

logger = logging.getLogger(__name__)

__all__ = ["CaseQualityGateMiddleware", "_validate_case", "_is_fuzzy_result"]

# 只在创建路径上强制校验；update 允许部分字段更新，不拦截
_CREATE_TOOLS = {"create_test_case_tool", "batch_create_test_cases_tool"}
_BATCH_TOOL = "batch_create_test_cases_tool"


def _precheck(request: ToolCallRequest) -> ToolMessage | None:
    """创建前校验；不通过时构造错误 ToolMessage 拦截本次调用。"""
    tool_call = request.tool_call
    name = tool_call.get("name")
    if name not in _CREATE_TOOLS:
        return None

    args = tool_call.get("args") or {}
    cases = args.get("test_cases") if name == _BATCH_TOOL else [args]
    if not cases:
        return None

    all_violations = []
    for index, case in enumerate(cases):
        violations = _validate_case(case if isinstance(case, dict) else {})
        if violations:
            all_violations.append({
                "index": index,
                "name": case.get("name") if isinstance(case, dict) else None,
                "violations": violations,
            })

    if not all_violations:
        return None

    logger.info("用例质量校验拦截 %s：%d 条违规", name, len(all_violations))
    content = json.dumps({
        "success": False,
        "error": "用例质量校验未通过，本次创建未执行",
        "violations": all_violations,
        "message": (
            "请修正以上违规项后重新调用工具。质量红线："
            "1) 预期结果必须可客观判定，禁止“正确/成功/正常”等模糊词；"
            "2) 每条用例必须提供具体测试数据值，禁止空 test_data 或占位描述；"
            "3) case_number 必填且格式为 TC-[项目]-[模块]-[序号]；"
            "4) module 必填。"
        ),
    }, ensure_ascii=False)
    return ToolMessage(
        content=content,
        tool_call_id=tool_call["id"],
        name=name,
        status="error",
    )


def _parse_result_json(content: Any) -> dict[str, Any] | None:
    """容错解析工具结果 JSON（dict 结果经 _stringify 序列化为 JSON 字符串）。"""
    if not isinstance(content, str) or not content.strip().startswith("{"):
        return None
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _postprocess(result: ToolMessage | Command[Any], request: ToolCallRequest) -> ToolMessage | Command[Any]:
    """创建后比对：批量创建有失败时，在结果末尾追加失败清单提示。"""
    if not isinstance(result, ToolMessage) or result.status == "error":
        return result
    if request.tool_call.get("name") != _BATCH_TOOL:
        return result

    data = _parse_result_json(result.content)
    inner = data.get("data") if data else None
    if not isinstance(inner, dict):
        return result

    total = inner.get("total", 0)
    succeeded = inner.get("succeeded", 0)
    failed = inner.get("failed", 0)
    if not failed:
        return result

    failed_items = [
        {"index": r.get("index"), "name": r.get("name"), "error": r.get("error")}
        for r in inner.get("results", [])
        if isinstance(r, dict) and not r.get("success")
    ]
    note = (
        f"\n\n[系统提示] 本次提交 {total} 条用例，成功 {succeeded} 条、失败 {failed} 条。"
        f"失败清单：{json.dumps(failed_items, ensure_ascii=False)}。"
        "请修正失败用例的参数后重新批量创建（仅补失败项，不要重复创建已成功用例）。"
    )
    return result.model_copy(update={"content": str(result.content) + note})


class CaseQualityGateMiddleware(AgentMiddleware):
    """用例创建工具调用的确定性质量门禁。

    - wrap_tool_call（创建前）：校验质量红线，违规则拦截并返回违规清单；
    - 创建后：批量创建存在失败项时，向结果追加失败清单提示模型补全。
    """

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        blocked = _precheck(request)
        if blocked is not None:
            return blocked
        return _postprocess(handler(request), request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        blocked = _precheck(request)
        if blocked is not None:
            return blocked
        return _postprocess(await handler(request), request)
