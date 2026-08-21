"""
API 验证层主动探测规则引擎

基于 OpenAPI schema 生成单字段异常探测请求，每次只变异一个字段，
用于从目标系统的验证层响应中反推业务错误语义。
"""

import re
import uuid
from typing import Any, Optional


# 探测条件优先级（高优先级先执行）
_PROBE_PRIORITY = {
    "required_missing": 1,
    "invalid_enum": 2,
    "type_error": 3,
    "format_error": 4,
    "length_exceeded": 5,
    "length_below": 6,
    "out_of_range": 7,
    "pattern_mismatch": 8,
}


class ProbeRequest:
    """单个探测请求描述"""

    def __init__(
        self,
        name: str,
        field_path: str,
        condition: str,
        request_data: dict[str, Any],
        expected_status: Optional[int] = 400,
        priority: int = 99,
    ):
        self.name = name
        self.field_path = field_path
        self.condition = condition
        self.request_data = request_data
        self.expected_status = expected_status
        self.priority = priority

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "field_path": self.field_path,
            "condition": self.condition,
            "request_data": self.request_data,
            "expected_status": self.expected_status,
            "priority": self.priority,
        }


def _schema_type(schema: dict) -> str:
    """提取 JSON Schema 类型，兼容数组、缺失、或仅有结构关键字的情况。"""
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


def _generate_valid_value(schema: dict) -> Any:
    """根据 schema 生成一个合法的占位值。"""
    stype = _schema_type(schema)

    if stype == "string":
        fmt = schema.get("format", "")
        if fmt == "email":
            return "probe@example.com"
        if fmt == "uuid":
            return str(uuid.uuid4())
        if fmt in ("date", "date-time"):
            return "2024-01-01T00:00:00Z"
        if "pattern" in schema:
            return _generate_from_pattern(schema["pattern"]) or "valid"
        max_len = schema.get("maxLength")
        if isinstance(max_len, int) and max_len >= 0:
            return "a" * min(max_len, 10) if max_len > 0 else ""
        min_len = schema.get("minLength")
        if isinstance(min_len, int) and min_len > 0:
            return "a" * min_len
        return "valid-string"

    if stype == "integer":
        minimum = schema.get("minimum")
        if isinstance(minimum, int):
            return minimum
        maximum = schema.get("maximum")
        if isinstance(maximum, int):
            return maximum
        return 1

    if stype == "number":
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)):
            return float(minimum)
        maximum = schema.get("maximum")
        if isinstance(maximum, (int, float)):
            return float(maximum)
        return 1.0

    if stype == "boolean":
        return True

    if stype == "array":
        return []

    if stype == "object":
        return {}

    return "valid"


def _generate_from_pattern(pattern: str) -> Optional[str]:
    """极简化：根据常见正则生成一个匹配样例。"""
    # 数字串
    if pattern == "^\\d+$" or pattern == r"^\d+$":
        return "123456"
    # 手机号
    if "1[3-9]" in pattern:
        return "13800138000"
    # 邮箱
    if "@" in pattern or "email" in pattern.lower():
        return "probe@example.com"
    return None


def _generate_invalid_value(schema: dict, condition: str) -> Any:
    """根据条件生成非法值。"""
    stype = _schema_type(schema)

    if condition == "type_error":
        if stype in ("integer", "number"):
            return "not-a-number"
        if stype == "boolean":
            return "not-a-boolean"
        if stype == "array":
            return "not-an-array"
        if stype == "object":
            return "not-an-object"
        return 12345

    if condition == "format_error":
        fmt = schema.get("format", "")
        if fmt == "email":
            return "not-an-email"
        if fmt == "uuid":
            return "not-a-uuid"
        if fmt in ("date", "date-time"):
            return "not-a-date"
        return "invalid-format"

    if condition == "length_exceeded":
        max_len = schema.get("maxLength", 10)
        return "a" * (max_len + 1)

    if condition == "length_below":
        min_len = schema.get("minLength", 1)
        return "a" * max(0, min_len - 1)

    if condition == "out_of_range":
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)):
            if isinstance(minimum, int):
                return minimum - 1
            return minimum - 0.1
        if isinstance(maximum, (int, float)):
            if isinstance(maximum, int):
                return maximum + 1
            return maximum + 0.1
        return -1

    if condition == "pattern_mismatch":
        return "!!!invalid-pattern!!!"

    if condition == "invalid_enum":
        enum_vals = schema.get("enum", [])
        candidates = ["invalid_enum_value_probe", 99999, "__probe__"]
        for cand in candidates:
            if cand not in enum_vals:
                return cand
        return f"probe-{uuid.uuid4()}"

    return "invalid"


def _extract_body_fields(request_body: Optional[dict]) -> list[tuple[str, dict, bool]]:
    """从 requestBody 中提取字段列表。

    返回 [(field_path, schema, required), ...]，field_path 形如 body.name。
    """
    if not isinstance(request_body, dict):
        return []

    content = request_body.get("content") or {}
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

    schema = media.get("schema") or {}
    if not isinstance(schema, dict):
        return []

    return _extract_schema_fields("body", schema, bool(request_body.get("required")))


def _extract_schema_fields(prefix: str, schema: dict, parent_required: bool) -> list[tuple[str, dict, bool]]:
    """递归提取对象 schema 的字段。"""
    if not isinstance(schema, dict):
        return []

    if "$ref" in schema:
        # $ref 未解析，无法生成字段级探测
        return []

    stype = _schema_type(schema)
    if stype != "object":
        return []

    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    results: list[tuple[str, dict, bool]] = []

    for prop_name, prop_schema in props.items():
        if not isinstance(prop_schema, dict):
            continue
        field_path = f"{prefix}.{prop_name}"
        is_required = prop_name in required
        results.append((field_path, prop_schema, is_required))

        # 只展开一层嵌套对象，避免组合爆炸
        nested = _extract_schema_fields(field_path, prop_schema, False)
        results.extend(nested)

    return results


def _extract_parameter_fields(parameters: Optional[list]) -> list[tuple[str, dict, bool]]:
    """从 parameters 中提取字段列表。

    返回 [(field_path, schema, required), ...]，field_path 形如 path.id / query.page / header.X-Api-Key。
    """
    results: list[tuple[str, dict, bool]] = []
    if not isinstance(parameters, list):
        return results

    for param in parameters:
        if not isinstance(param, dict):
            continue
        name = param.get("name")
        loc = param.get("in", "query")
        if not name or loc == "body":
            # body 参数走 request_body 处理
            continue
        pschema = param.get("schema") or {}
        required = bool(param.get("required", False))
        results.append((f"{loc}.{name}", pschema, required))

    return results


def _build_base_request(
    parameters: list[tuple[str, dict, bool]],
    body_fields: list[tuple[str, dict, bool]],
    request_body: Optional[dict],
) -> dict[str, Any]:
    """构造一个基础合法请求。"""
    req: dict[str, Any] = {
        "path": {},
        "query": {},
        "header": {},
        "body": {},
    }

    # 路径/查询/头参数
    for field_path, schema, required in parameters:
        loc, name = field_path.split(".", 1)
        if required:
            req[loc][name] = _generate_valid_value(schema)

    # 请求体
    if request_body and isinstance(request_body, dict):
        content = request_body.get("content") or {}
        if content:
            media = None
            for mime in ("application/json", "application/*+json", "*/*"):
                if mime in content:
                    media = content[mime]
                    break
            if media is None:
                media = next(iter(content.values()))
            schema = (media or {}).get("schema") if isinstance(media, dict) else None
            if isinstance(schema, dict):
                req["body"] = _build_base_object(schema)

    return req


def _build_base_object(schema: dict) -> dict[str, Any]:
    """根据对象 schema 构造合法请求体。"""
    if not isinstance(schema, dict) or "$ref" in schema:
        return {}

    stype = _schema_type(schema)
    if stype != "object":
        return {}

    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    result: dict[str, Any] = {}

    for prop_name, prop_schema in props.items():
        if not isinstance(prop_schema, dict):
            continue
        if prop_name in required:
            result[prop_name] = _generate_valid_value(prop_schema)

    return result


def _apply_mutation(req: dict[str, Any], field_path: str, value: Any) -> dict[str, Any]:
    """深拷贝请求并在指定字段应用变异。"""
    import copy
    new_req = copy.deepcopy(req)
    loc, *rest = field_path.split(".")
    if loc not in new_req:
        new_req[loc] = {}

    target = new_req[loc]
    for part in rest[:-1]:
        if part not in target:
            target[part] = {}
        target = target[part]

    if rest:
        target[rest[-1]] = value

    return new_req


def _apply_omission(req: dict[str, Any], field_path: str) -> dict[str, Any]:
    """深拷贝请求并删除指定字段。"""
    import copy
    new_req = copy.deepcopy(req)
    loc, *rest = field_path.split(".")
    if loc not in new_req:
        return new_req

    target = new_req[loc]
    for part in rest[:-1]:
        if part not in target:
            return new_req
        target = target[part]

    if rest and rest[-1] in target:
        del target[rest[-1]]

    return new_req


def generate_probe_requests(
    endpoint_path: str,
    method: str,
    parameters: Optional[list],
    request_body: Optional[dict],
    budget: int = 20,
) -> list[dict[str, Any]]:
    """基于端点 schema 生成探测请求列表。

    Args:
        endpoint_path: API 路径
        method: HTTP 方法
        parameters: OpenAPI parameters 列表
        request_body: OpenAPI requestBody 对象
        budget: 最大探测数

    Returns:
        探测请求字典列表，按优先级排序并已截断至 budget
    """
    body_fields = _extract_body_fields(request_body)
    param_fields = _extract_parameter_fields(parameters)
    all_fields = param_fields + body_fields

    base_req = _build_base_request(param_fields, body_fields, request_body)

    probes: list[ProbeRequest] = []

    for field_path, schema, required in all_fields:
        stype = _schema_type(schema)

        # 1) 必填缺失
        if required:
            probes.append(ProbeRequest(
                name=f"缺少必填字段 {field_path}",
                field_path=field_path,
                condition="required_missing",
                request_data=_apply_omission(base_req, field_path),
                expected_status=400,
                priority=_PROBE_PRIORITY["required_missing"],
            ))

        # 2) 非法枚举
        enum_vals = schema.get("enum")
        if isinstance(enum_vals, list) and enum_vals:
            probes.append(ProbeRequest(
                name=f"{field_path} 非法枚举值",
                field_path=field_path,
                condition="invalid_enum",
                request_data=_apply_mutation(
                    base_req, field_path, _generate_invalid_value(schema, "invalid_enum")
                ),
                expected_status=400,
                priority=_PROBE_PRIORITY["invalid_enum"],
            ))

        # 3) 类型错误（仅对强类型字段）
        if stype in ("integer", "number", "boolean", "array", "object"):
            probes.append(ProbeRequest(
                name=f"{field_path} 类型错误",
                field_path=field_path,
                condition="type_error",
                request_data=_apply_mutation(
                    base_req, field_path, _generate_invalid_value(schema, "type_error")
                ),
                expected_status=400,
                priority=_PROBE_PRIORITY["type_error"],
            ))

        # 4) 字符串格式错误
        if stype == "string" and schema.get("format") in ("email", "uuid", "date", "date-time"):
            probes.append(ProbeRequest(
                name=f"{field_path} 格式错误",
                field_path=field_path,
                condition="format_error",
                request_data=_apply_mutation(
                    base_req, field_path, _generate_invalid_value(schema, "format_error")
                ),
                expected_status=400,
                priority=_PROBE_PRIORITY["format_error"],
            ))

        # 5) 字符串长度
        if stype == "string":
            max_len = schema.get("maxLength")
            if isinstance(max_len, int) and max_len >= 0:
                probes.append(ProbeRequest(
                    name=f"{field_path} 超过最大长度",
                    field_path=field_path,
                    condition="length_exceeded",
                    request_data=_apply_mutation(
                        base_req, field_path, _generate_invalid_value(schema, "length_exceeded")
                    ),
                    expected_status=400,
                    priority=_PROBE_PRIORITY["length_exceeded"],
                ))
            min_len = schema.get("minLength")
            if isinstance(min_len, int) and min_len > 0:
                probes.append(ProbeRequest(
                    name=f"{field_path} 低于最小长度",
                    field_path=field_path,
                    condition="length_below",
                    request_data=_apply_mutation(
                        base_req, field_path, _generate_invalid_value(schema, "length_below")
                    ),
                    expected_status=400,
                    priority=_PROBE_PRIORITY["length_below"],
                ))

        # 6) 数值范围
        if stype in ("integer", "number"):
            if "minimum" in schema or "maximum" in schema:
                probes.append(ProbeRequest(
                    name=f"{field_path} 超出范围",
                    field_path=field_path,
                    condition="out_of_range",
                    request_data=_apply_mutation(
                        base_req, field_path, _generate_invalid_value(schema, "out_of_range")
                    ),
                    expected_status=400,
                    priority=_PROBE_PRIORITY["out_of_range"],
                ))

        # 7) 正则不匹配
        if stype == "string" and schema.get("pattern"):
            probes.append(ProbeRequest(
                name=f"{field_path} 正则不匹配",
                field_path=field_path,
                condition="pattern_mismatch",
                request_data=_apply_mutation(
                    base_req, field_path, _generate_invalid_value(schema, "pattern_mismatch")
                ),
                expected_status=400,
                priority=_PROBE_PRIORITY["pattern_mismatch"],
            ))

    # 按优先级排序并截断
    probes.sort(key=lambda p: p.priority)
    if len(probes) > budget:
        probes = probes[:budget]

    return [p.to_dict() for p in probes]
