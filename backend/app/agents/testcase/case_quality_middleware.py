"""用例质量校验中间件。

对 ``create_test_case_tool`` 在创建前做**确定性**质量校验（零 token 成本），
把 SYSTEM_PROMPT 中的质量红线从"靠模型自觉"变成"代码强制"：

- 预期结果禁止"正确""成功""正常"等模糊词，必须可客观判定
- 每条用例必须提供具体测试数据值（禁止空 test_data / 占位描述）
- case_number 必须符合 ``TC-[项目]-[模块]-[序号]`` 格式
- module（所属模块）必填；name（用例名称）必填

另设 warning 通道（``validate_case_hygiene``，不阻断创建）：case_type/priority
缺失、单步骤、步骤过多、无追溯编号、名称过长——把 normalize_* 的静默修正
显式化回传给模型，驱动后续生成自我修正（规则与离线 tests/eval/lint_cases.py
呼应）。

批量创建（``batch_create_test_cases_tool``）的创建前校验统一由
``ModuleSelfCheckMiddleware`` 执行（规则为本校验的超集），本中间件只做
批量创建的后处理：比对"提交数量 vs 成功数量"，有失败时追加提示让模型补全。
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from app.utils.testcase_validation import _is_fuzzy_result, _validate_case, validate_case_hygiene

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langgraph.types import Command

    from langchain.agents.middleware.types import ToolCallRequest

logger = logging.getLogger(__name__)

__all__ = ["CaseQualityGateMiddleware", "_validate_case", "_is_fuzzy_result"]

# 质量门禁分工（避免同一调用被两道门禁先后拦截、模型修一轮又被拦一轮）：
# - 单条创建（create_test_case_tool）：本中间件做创建前校验；
# - 批量创建（batch_create_test_cases_tool）：创建前校验统一由
#   ModuleSelfCheckMiddleware 执行（其规则包含 _validate_case，是本校验的超集）；
# - 本中间件仍负责批量创建的「后处理」：部分失败时在结果末尾追加失败清单。
_SINGLE_CREATE_TOOL = "create_test_case_tool"
_BATCH_TOOL = "batch_create_test_cases_tool"


def _precheck(request: ToolCallRequest) -> ToolMessage | None:
    """创建前校验；不通过时构造错误 ToolMessage 拦截本次调用。"""
    tool_call = request.tool_call
    name = tool_call.get("name")
    if name != _SINGLE_CREATE_TOOL:
        return None

    args = tool_call.get("args") or {}
    cases = [args]
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


# 批量路径 warning 聚合时的规则短文案（单条路径直接用 validate_case_hygiene 的 message）
_HYGIENE_RULE_LABEL = {
    "case_type缺失": "缺 case_type（已按 functional 归类）",
    "priority缺失": "缺 priority（已按默认 medium 处理）",
    "单步骤": "仅 1 步（疑似操作与断言合并）",
    "步骤过多": "步骤数 >10（建议拆分）",
    "无追溯编号": "缺 REQ-/FP- 追溯编号",
    "名称过长": "名称超 60 字",
}


def _hygiene_note(request: ToolCallRequest) -> str:
    """创建成功后的规范提示（warning 通道，不阻断）。

    把 normalize_* 的静默修正显式化：单条路径逐条列提示；批量路径按规则
    聚合计数（避免 30 条各列一遍淹没结果）。无提示返回空串。
    """
    tool_name = request.tool_call.get("name")
    args = request.tool_call.get("args") or {}

    if tool_name == _SINGLE_CREATE_TOOL:
        hints = validate_case_hygiene(args)
        if not hints:
            return ""
        items = "；".join(h["message"] for h in hints)
        return f"\n\n[系统提示] 本条用例规范提示（不影响本次创建）：{items}。"

    if tool_name == _BATCH_TOOL:
        counter: Counter[str] = Counter()
        for case in args.get("test_cases") or []:
            if not isinstance(case, dict):
                continue
            for h in validate_case_hygiene(case):
                counter[h["rule"]] += 1
        if not counter:
            return ""
        items = "；".join(
            f"{n} 条{_HYGIENE_RULE_LABEL.get(rule, rule)}" for rule, n in counter.most_common()
        )
        return (
            f"\n\n[系统提示] 本批用例规范提示（不影响本次创建）：{items}。"
            "建议后续创建时显式补全这些字段。"
        )

    return ""


def _postprocess(result: ToolMessage | Command[Any], request: ToolCallRequest) -> ToolMessage | Command[Any]:
    """创建后处理：批量部分失败追加失败清单（error 级反馈）；
    单条/批量成功但有规范问题时追加 warning 提示（规范级反馈）。"""
    if not isinstance(result, ToolMessage) or result.status == "error":
        return result
    if request.tool_call.get("name") not in (_SINGLE_CREATE_TOOL, _BATCH_TOOL):
        return result

    note = ""
    if request.tool_call.get("name") == _BATCH_TOOL:
        data = _parse_result_json(result.content)
        inner = data.get("data") if data else None
        if isinstance(inner, dict):
            total = inner.get("total", 0)
            succeeded = inner.get("succeeded", 0)
            failed = inner.get("failed", 0)
            if failed:
                failed_items = [
                    {"index": r.get("index"), "name": r.get("name"), "error": r.get("error")}
                    for r in inner.get("results", [])
                    if isinstance(r, dict) and not r.get("success")
                ]
                note += (
                    f"\n\n[系统提示] 本次提交 {total} 条用例，成功 {succeeded} 条、失败 {failed} 条。"
                    f"失败清单：{json.dumps(failed_items, ensure_ascii=False)}。"
                    "请修正失败用例的参数后重新批量创建（仅补失败项，不要重复创建已成功用例）。"
                )

    note += _hygiene_note(request)
    if not note:
        return result
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
