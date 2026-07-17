"""
API 测试用例骨架确定性推导工具

derive_test_skeleton：从端点的 OpenAPI schema 机械推导测试用例骨架，
把「要测哪些点」从 LLM 自由发挥变为确定性、可度量、可复现的规则推导。
LLM 只负责在骨架之上填充测试数据与断言表达式。

约束（重要）：端点的 parameters / request_body / responses 是解析时存入的
**原始 OpenAPI 片段，未做 $ref 解引用**（完整 spec 未持久化，schema_file_id
为空，见 api_endpoints.py 中 schema_file_id=None）。因此对 $ref 节点做优雅
降级——给出通用骨架并明确标注「需补充字段级用例」，而不是崩溃或臆造字段。

分层过程：
    derive_test_skeleton(endpoint_id)
      → 读取端点 OpenAPI 片段
      → 按字段/安全/响应推导骨架（每字段 N 个测试点）
      → 输出结构化骨架 list[TestCaseSkeleton]
      →（由 LLM）填充测试数据 + 断言表达式
"""

import json
from typing import Any, Optional
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select

from app.config.database import async_session_factory
from app.models.api_endpoint import APIEndpoint

# 视为成功的 2xx 状态码
_SUCCESS_STATUS = ("200", "201", "202", "204")

# 用例类别 → 优先级 映射
_CATEGORY_PRIORITY = {
    "functional": "P0",
    "security": "P1",
    "exception": "P1",
    "boundary": "P2",
}


def _priority(category: str) -> str:
    return _CATEGORY_PRIORITY.get(category, "P2")


def _make_point(
    name: str,
    category: str,
    target: str,
    test_point: str,
    expected_status: Optional[int],
    data_strategy: str,
    assertion_hints: list[str],
) -> dict:
    """构造一个标准化的用例骨架条目。"""
    return {
        "name": name,
        "category": category,
        "priority": _priority(category),
        "target": target,
        "test_point": test_point,
        "expected_status": expected_status,
        "data_strategy": data_strategy,
        "assertion_hints": assertion_hints,
    }


def _schema_type(schema: dict) -> str:
    """提取 JSON Schema 的类型，兼容 type 为数组、缺失、或仅有结构关键字的情况。"""
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), None)
    if t:
        return str(t)
    if "properties" in schema:
        return "object"
    if "items" in schema:
        return "array"
    if "enum" in schema:
        vals = [v for v in (schema.get("enum") or []) if v is not None]
        if vals:
            mapping = {str: "string", int: "integer", float: "number", bool: "boolean"}
            return mapping.get(type(vals[0]), "any")
    return "any"


def _field_test_points(name: str, schema: dict, required: bool, location: str) -> list[dict]:
    """针对单个字段（路径/查询/头参数 或 请求体属性）推导边界与异常测试点。

    location ∈ {"path", "query", "header", "body"}，仅用于生成可读描述。
    """
    points: list[dict] = []
    schema = schema or {}
    kind = "字段" if location == "body" else "参数"

    # $ref 未解析：优雅降级，给出提示而非臆造
    if "$ref" in schema:
        points.append(_make_point(
            name=f"待补充 - {name}（$ref 未解析）",
            category="exception",
            target=name,
            test_point=(
                f"{name} 为 $ref 引用（{schema['$ref']}），完整 spec 未持久化无法解析；"
                f"请结合 get_endpoint_details 返回的原始 schema 补充该{kind}的字段级用例"
            ),
            expected_status=None,
            data_strategy="待解析 $ref 后确定",
            assertion_hints=[],
        ))
        return points

    stype = _schema_type(schema)

    # 1) 必填缺失（异常）
    if required:
        points.append(_make_point(
            name=f"异常 - 缺少必填{kind} {name}",
            category="exception",
            target=name,
            test_point=f"请求中省略必填{kind} {name}，应返回参数校验错误",
            expected_status=400,
            data_strategy=f"构造请求时不包含 {name}",
            assertion_hints=["断言状态码为 400", "断言错误信息指明缺少该字段"],
        ))

    # 2) 枚举非法值（异常）
    enum_vals = schema.get("enum")
    if isinstance(enum_vals, list) and enum_vals:
        points.append(_make_point(
            name=f"异常 - {name} 非法枚举值",
            category="exception",
            target=name,
            test_point=f"{name} 传入枚举外的非法值（合法值: {enum_vals}），应被拒绝",
            expected_status=400,
            data_strategy="传入不在 enum 内的值",
            assertion_hints=["断言状态码为 400"],
        ))

    # 3) 字符串长度边界
    if stype == "string":
        max_len = schema.get("maxLength")
        min_len = schema.get("minLength")
        if isinstance(max_len, int) and max_len >= 0:
            points.append(_make_point(
                name=f"边界 - {name} 超过最大长度",
                category="boundary",
                target=name,
                test_point=f"{name} 传入长度 {max_len}+1 的字符串（上限 {max_len}）",
                expected_status=400,
                data_strategy=f"生成长度为 {max_len + 1} 的字符串",
                assertion_hints=["断言状态码为 400，或被正确截断/拒绝"],
            ))
        if isinstance(min_len, int) and min_len > 0:
            points.append(_make_point(
                name=f"边界 - {name} 低于最小长度",
                category="boundary",
                target=name,
                test_point=f"{name} 传入长度小于 {min_len} 的字符串",
                expected_status=400,
                data_strategy="传入空字符串或过短字符串",
                assertion_hints=["断言状态码为 400"],
            ))

    # 4) 数值边界与越界
    if stype in ("integer", "number"):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)):
            points.append(_make_point(
                name=f"边界 - {name} 取最小值",
                category="boundary",
                target=name,
                test_point=f"{name} 取最小值 {minimum}，应正常处理",
                expected_status=None,
                data_strategy=f"传入 {minimum}",
                assertion_hints=["断言响应符合成功 schema"],
            ))
            points.append(_make_point(
                name=f"异常 - {name} 低于最小值",
                category="exception",
                target=name,
                test_point=f"{name} 传入小于 {minimum} 的值",
                expected_status=400,
                data_strategy=f"传入 {minimum} - 1",
                assertion_hints=["断言状态码为 400"],
            ))
        if isinstance(maximum, (int, float)):
            points.append(_make_point(
                name=f"边界 - {name} 取最大值",
                category="boundary",
                target=name,
                test_point=f"{name} 取最大值 {maximum}，应正常处理",
                expected_status=None,
                data_strategy=f"传入 {maximum}",
                assertion_hints=["断言响应符合成功 schema"],
            ))
            points.append(_make_point(
                name=f"异常 - {name} 超过最大值",
                category="exception",
                target=name,
                test_point=f"{name} 传入大于 {maximum} 的值",
                expected_status=400,
                data_strategy=f"传入 {maximum} + 1",
                assertion_hints=["断言状态码为 400"],
            ))

    # 5) 强类型字段的类型错误（异常）
    if stype in ("integer", "number", "boolean"):
        points.append(_make_point(
            name=f"异常 - {name} 类型错误",
            category="exception",
            target=name,
            test_point=f"{name} 传入错误类型（应为 {stype}，改传字符串）",
            expected_status=400,
            data_strategy="传入字符串类型的非法值",
            assertion_hints=["断言状态码为 400"],
        ))

    # 6) 数组边界
    if stype == "array":
        points.append(_make_point(
            name=f"边界 - {name} 空数组",
            category="boundary",
            target=name,
            test_point=f"{name} 传入空数组 []，应正常处理或被明确拒绝",
            expected_status=None,
            data_strategy="传入 []",
            assertion_hints=["断言响应符合成功 schema，或返回 400"],
        ))
        max_items = schema.get("maxItems")
        if isinstance(max_items, int) and max_items >= 0:
            points.append(_make_point(
                name=f"边界 - {name} 超过最大元素数",
                category="boundary",
                target=name,
                test_point=f"{name} 传入 {max_items}+1 个元素（上限 {max_items}）",
                expected_status=400,
                data_strategy=f"构造 {max_items + 1} 个元素的数组",
                assertion_hints=["断言状态码为 400"],
            ))

    return points


def _extract_request_body_schema(request_body: Optional[dict]) -> tuple[Optional[dict], bool, bool]:
    """从原始 OpenAPI requestBody 中提取 JSON schema。

    返回 (schema, body_required, is_ref)。
    原始形态：{content: {mime: {schema: {...}}}, required: bool, description: str}
    """
    if not isinstance(request_body, dict):
        return None, False, False
    body_required = bool(request_body.get("required", False))
    content = request_body.get("content") or {}
    if not isinstance(content, dict) or not content:
        return None, body_required, False
    # 优先 application/json，否则取第一个 content 条目
    media = None
    for mime in ("application/json", "application/*+json", "*/*"):
        if mime in content:
            media = content[mime]
            break
    if media is None:
        media = next(iter(content.values()))
    schema = (media or {}).get("schema") if isinstance(media, dict) else None
    is_ref = isinstance(schema, dict) and "$ref" in schema
    return schema, body_required, is_ref


def _extract_response_fields(responses: Optional[dict], status_code: int) -> list[tuple[str, str]]:
    """从 responses 中提取指定状态码响应的字段名与类型。

    返回 [(field_name, field_type), ...]，最多返回 5 个字段；$ref 未解析时返回空列表。
    """
    if not isinstance(responses, dict):
        return []
    response = responses.get(str(status_code))
    if not isinstance(response, dict):
        return []
    content = response.get("content") or {}
    if not isinstance(content, dict) or not content:
        return []

    media = None
    for mime in ("application/json", "application/*+json", "*/*"):
        if mime in content:
            media = content[mime]
            break
    if media is None:
        media = next(iter(content.values()))
    if not isinstance(media, dict):
        return []

    schema = media.get("schema")
    if not isinstance(schema, dict):
        return []
    if "$ref" in schema:
        return []

    props = schema.get("properties")
    if not isinstance(props, dict):
        return []

    fields: list[tuple[str, str]] = []
    for prop_name, prop_schema in props.items():
        if not isinstance(prop_schema, dict):
            continue
        if "$ref" in prop_schema:
            fields.append((prop_name, "object"))
        else:
            fields.append((prop_name, _schema_type(prop_schema)))
    return fields[:5]


def _build_success_assertion_hints(responses: Optional[dict], success_status: int) -> list[str]:
    """构造正向用例的断言提示，优先使用 responses schema 中的具体字段。"""
    hints = [f"断言状态码为 {success_status}"]
    fields = _extract_response_fields(responses, success_status)
    if fields:
        for fname, ftype in fields:
            hints.append(f"断言响应体包含字段 {fname}（类型 {ftype}）")
    else:
        hints.append("断言响应体结构与 2xx schema 一致（字段存在性 + 类型）")
    hints.append("断言 body.code（或 body.success）等于成功值——根据文档中 {} 响应的 schema 确定具体值（如 0/'0'/200/'success'/true）。这是正向用例最重要的断言，禁止退化为 typeof 类型检查——'4009'也是 string 但表示业务失败".format(success_status))
    return hints


def _build_error_assertion_hints(responses: Optional[dict], status_code: int) -> list[str]:
    """构造异常用例的断言提示，优先使用 error schema 中的具体字段。"""
    hints = [f"断言状态码为 {status_code}"]
    fields = _extract_response_fields(responses, status_code)
    if fields:
        for fname, _ in fields[:3]:
            hints.append(f"断言错误响应包含字段 {fname}")
    else:
        hints.append("断言错误信息符合 error schema（如 message / error / code）")
    return hints


def _derive_skeletons(
    method: str,
    path: str,
    parameters: Optional[list],
    request_body: Optional[dict],
    responses: Optional[dict],
    security: Optional[list],
) -> dict:
    """纯函数：由 OpenAPI 片段推导用例骨架。不访问数据库，便于单元测试。"""
    skeletons: list[dict] = []
    notes: list[str] = []
    method = (method or "").upper()

    # ---- 预期状态码（来自 responses 的 key） ----
    status_keys = []
    if isinstance(responses, dict):
        status_keys = [k for k in responses.keys() if str(k).isdigit() or str(k).startswith(("2", "4", "5"))]
    success_status = next((int(k) for k in status_keys if str(k) in _SUCCESS_STATUS), 200)

    # ---- 1) 正向用例（必有） ----
    skeletons.append(_make_point(
        name="正向 - 有效请求",
        category="functional",
        target="request",
        test_point="使用符合 schema 的有效参数与请求体调用，验证成功响应",
        expected_status=success_status,
        data_strategy="按 schema 类型生成合法值；唯一字段用 faker/uuid/时间戳动态生成",
        assertion_hints=_build_success_assertion_hints(responses, success_status),
    ))

    # ---- 2) 参数（path/query/header）推导 ----
    if isinstance(parameters, list):
        for param in parameters:
            if not isinstance(param, dict):
                continue
            pname = param.get("name")
            if not pname:
                continue
            ploc = param.get("in", "query")
            prequired = bool(param.get("required", False))
            pschema = param.get("schema") or {}
            skeletons.extend(_field_test_points(pname, pschema, prequired, ploc))

    # ---- 3) 请求体推导 ----
    body_schema, body_required, body_is_ref = _extract_request_body_schema(request_body)
    if body_required:
        skeletons.append(_make_point(
            name="异常 - 空请求体",
            category="exception",
            target="request_body",
            test_point="提交空请求体（body 为必填），应返回校验错误",
            expected_status=400,
            data_strategy="发送空 JSON {} 或不带 body",
            assertion_hints=_build_error_assertion_hints(responses, 400),
        ))
    if body_is_ref:
        notes.append(
            "request_body 为 $ref 引用，完整 spec 未持久化无法解析字段；"
            "已生成通用骨架，字段级用例请结合 get_endpoint_details 补充。"
        )
        skeletons.append(_make_point(
            name="待补充 - 请求体字段级用例（$ref 未解析）",
            category="exception",
            target="request_body",
            test_point="请求体为 $ref，需解析后对各必填字段/约束补充字段级边界与异常用例",
            expected_status=None,
            data_strategy="待解析 $ref 后确定",
            assertion_hints=[],
        ))
    elif isinstance(body_schema, dict):
        props = body_schema.get("properties")
        required_list = body_schema.get("required") or []
        if isinstance(props, dict) and props:
            for prop_name, prop_schema in props.items():
                preq = prop_name in required_list
                skeletons.extend(_field_test_points(prop_name, prop_schema or {}, preq, "body"))
        elif "$ref" not in body_schema and body_schema:
            notes.append("request_body schema 无 properties（可能为数组或任意对象），仅生成通用用例。")

    # ---- 4) 安全推导 ----
    has_security = bool(security)  # security 为 [{schemeName: [scopes]}]
    if has_security:
        skeletons.append(_make_point(
            name="安全 - 无认证凭证",
            category="security",
            target="authorization",
            test_point="不提供 Authorization / 凭证调用受保护接口，应返回未授权",
            expected_status=401,
            data_strategy="请求头中不带 Authorization",
            assertion_hints=_build_error_assertion_hints(responses, 401),
        ))
        skeletons.append(_make_point(
            name="安全 - 无效/过期凭证",
            category="security",
            target="authorization",
            test_point="使用无效或过期 token 调用，应返回未授权",
            expected_status=401,
            data_strategy="Authorization: Bearer invalid-token",
            assertion_hints=_build_error_assertion_hints(responses, 401),
        ))
    else:
        notes.append("端点未声明 security（或为公开接口），未生成认证类用例。")

    # ---- 汇总 ----
    coverage = {"functional": 0, "boundary": 0, "exception": 0, "security": 0}
    for s in skeletons:
        cat = s.get("category")
        if cat in coverage:
            coverage[cat] += 1

    return {
        "endpoint": {"method": method, "path": path},
        "success_status": success_status,
        "expected_status_codes": sorted({int(k) for k in status_keys if str(k).isdigit()}),
        "skeletons": skeletons,
        "coverage_summary": coverage,
        "total_skeletons": len(skeletons),
        "derivation_notes": notes,
    }


@tool
async def derive_test_skeleton(endpoint_id: str) -> str:
    """
    从端点的 OpenAPI schema 确定性推导测试用例骨架。

    把「要测哪些点」交给规则推导（required/enum/类型/数值边界/字符串长度/数组/安全），
    而不是 LLM 自由发挥。返回结构化骨架后，LLM 只需据此填充测试数据与断言，
    再调用 save_test_cases / 生成脚本。

    适用时机：在「生成测试计划 / 生成测试用例」之前调用，作为用例设计的确定性底座。

    注意：request_body 若为 $ref 引用（完整 spec 未持久化无法解析），会降级为通用骨架
    并在 derivation_notes 中标注，字段级用例需结合 get_endpoint_details 补充。

    Args:
        endpoint_id: API 端点 ID（UUID）

    Returns:
        JSON：{endpoint, success_status, expected_status_codes, skeletons[],
               coverage_summary, total_skeletons, derivation_notes}
    """
    try:
        endpoint_uuid = UUID(endpoint_id)
    except (ValueError, AttributeError):
        return json.dumps({"success": False, "error": f"Invalid endpoint_id format: {endpoint_id}"}, ensure_ascii=False)

    async with async_session_factory() as session:
        try:
            stmt = select(APIEndpoint).where(APIEndpoint.id == endpoint_uuid)
            result = await session.execute(stmt)
            endpoint = result.scalar_one_or_none()
            if not endpoint:
                return json.dumps({"success": False, "error": f"端点 {endpoint_id} 不存在"}, ensure_ascii=False)

            derived = _derive_skeletons(
                method=endpoint.method,
                path=endpoint.path,
                parameters=endpoint.parameters,
                request_body=endpoint.request_body,
                responses=endpoint.responses,
                security=endpoint.security,
            )
            derived["success"] = True
            derived["endpoint"]["id"] = str(endpoint.id)
            derived["endpoint"]["display_name"] = endpoint.display_name
            return json.dumps(derived, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"success": False, "error": f"推导用例骨架失败: {str(e)}"}, ensure_ascii=False)
