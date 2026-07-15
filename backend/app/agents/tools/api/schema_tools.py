"""响应 schema 供给工具（契约断言的数据底座）。

get_response_schema：从端点 responses 中提取指定状态码的响应 schema，
做 $ref 优雅降级（能解的内联展开，不能解的替换为 {} 并标注），并扁平化
必填字段 / 枚举 / 字段类型，供 LLM：
  1. 停止臆测字段名（拿到精确 schema）；
  2. 直接把 schemas['200'].schema 嵌入脚本，配合 expectSchema(body, SCHEMA)
     做一次调用的整体契约校验（门禁已识别该调用并计为有效结构断言）。

约束：responses / request_body 是解析时存入的**原始 OpenAPI 片段，未做 $ref
解引用**（完整 spec 未持久化，schema_file_id=None），故 $ref 只能尽力内联，
无法解析的必须明确标注而不是臆造。
"""
from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select

from app.agents.tools.api.skeleton_tools import _schema_type
from app.config.database import async_session_factory
from app.models.api_endpoint import APIEndpoint

_SUCCESS_STATUS = ("200", "201", "202", "204")


# ---------------------------------------------------------------------------
# schema 提取（兼容 content 包装与直接 schema 两种形态）
# ---------------------------------------------------------------------------

def _pick_media_schema(response: Any) -> Optional[dict]:
    """从单个响应定义中取 JSON schema。兼容：
    - OpenAPI 标准：{content: {mime: {schema: {...}}}}
    - 简化形态：{schema: {...}} 或直接就是 schema。
    """
    if not isinstance(response, dict):
        return None
    content = response.get("content")
    if isinstance(content, dict) and content:
        media = None
        for mime in ("application/json", "application/*+json", "*/*"):
            if mime in content:
                media = content[mime]
                break
        if media is None:
            media = next(iter(content.values()))
        if isinstance(media, dict) and isinstance(media.get("schema"), dict):
            return media["schema"]
    if isinstance(response.get("schema"), dict):
        return response["schema"]
    # 直接就是 schema（含 type/properties/items/enum 等关键字）
    if any(k in response for k in ("type", "properties", "items", "enum", "$ref", "allOf", "oneOf", "anyOf")):
        return response
    return None


# ---------------------------------------------------------------------------
# $ref 处理：尽力内联，不能解的替换为 {} 并收集
# ---------------------------------------------------------------------------

def _lookup_local_ref(ref: str, roots: list[dict]) -> Optional[dict]:
    """尝试在本片段内解析本地 $ref（#/definitions/X、#/components/schemas/X、#/$defs/X）。"""
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return None
    parts = [p for p in ref[2:].split("/") if p]
    for root in roots:
        node: Any = root
        ok = True
        for p in parts:
            if isinstance(node, dict) and p in node:
                node = node[p]
            else:
                ok = False
                break
        if ok and isinstance(node, dict):
            return node
    return None


def _deref(schema: Any, roots: list[dict], unresolved: list[str], _depth: int = 0) -> Any:
    """递归处理 $ref。可解析的内联展开；不可解析的替换为 {} 并记录到 unresolved。"""
    if _depth > 25:  # 防循环引用
        return {}
    if isinstance(schema, dict):
        if "$ref" in schema:
            ref = schema.get("$ref")
            target = _lookup_local_ref(ref, roots)
            if target is None:
                if ref not in unresolved:
                    unresolved.append(ref)
                # 保留除 $ref 外的同级约束（如 description），结构按“任意”处理
                rest = {k: _deref(v, roots, unresolved, _depth + 1)
                        for k, v in schema.items() if k != "$ref"}
                return rest if rest else {}
            # 内联展开（合并同级其它关键字）
            merged = {k: v for k, v in schema.items() if k != "$ref"}
            merged.update(target)
            return _deref(merged, roots, unresolved, _depth + 1)
        return {k: _deref(v, roots, unresolved, _depth + 1) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_deref(v, roots, unresolved, _depth + 1) for v in schema]
    return schema


# ---------------------------------------------------------------------------
# 元数据扁平化：required 字段路径 / 枚举 / 字段类型
# ---------------------------------------------------------------------------

def _flatten(schema: Any, prefix: str = "", required_fields: Optional[list] = None,
             field_types: Optional[dict] = None, enums: Optional[dict] = None,
             _depth: int = 0) -> None:
    if _depth > 12 or not isinstance(schema, dict):
        return
    required_fields = required_fields if required_fields is not None else []
    field_types = field_types if field_types is not None else {}
    enums = enums if enums is not None else {}

    stype = _schema_type(schema)
    if prefix:
        field_types[prefix] = stype
    enum_vals = schema.get("enum")
    if prefix and isinstance(enum_vals, list) and enum_vals:
        enums[prefix] = [v for v in enum_vals if v is not None]

    required = set(schema.get("required") or [])
    props = schema.get("properties")
    if isinstance(props, dict):
        for name, sub in props.items():
            path = f"{prefix}.{name}" if prefix else name
            if name in required:
                required_fields.append(path)
            if isinstance(sub, dict):
                _flatten(sub, path, required_fields, field_types, enums, _depth + 1)
    # 数组元素
    items = schema.get("items")
    if isinstance(items, dict):
        _flatten(items, f"{prefix}[]" if prefix else "[]", required_fields, field_types, enums, _depth + 1)
    # allOf 合并
    for comb in ("allOf",):
        subs = schema.get(comb)
        if isinstance(subs, list):
            for sub in subs:
                if isinstance(sub, dict):
                    _flatten(sub, prefix, required_fields, field_types, enums, _depth + 1)


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

@tool
async def get_response_schema(endpoint_id: str, status: Optional[str] = None) -> dict:
    """获取端点响应 schema，用于生成契约断言（expectSchema 整体校验响应体）。

    生成测试脚本时调用：拿到精确的响应 schema（字段名/类型/必填/枚举），
    既避免臆测字段，又可直接把返回的 schema 嵌入脚本，调用 expectSchema(body, SCHEMA)
    一次校验整体响应（门禁已识别该调用并计为有效结构断言）。

    Args:
        endpoint_id: API 端点 ID（UUID）
        status: 可选，指定状态码（如 "200"）；不传则返回所有已定义状态码的 schema

    Returns:
        JSON: {success, endpoint, success_status, schemas{status: {schema, required_fields,
               field_types, enums, unresolved_refs, has_inline_schema}}, notes, usage_hint}
    """
    try:
        endpoint_uuid = UUID(endpoint_id)
    except (ValueError, AttributeError):
        return {"success": False, "error": f"Invalid endpoint_id format: {endpoint_id}"}

    async with async_session_factory() as session:
        try:
            stmt = select(APIEndpoint).where(APIEndpoint.id == endpoint_uuid)
            result = await session.execute(stmt)
            endpoint = result.scalar_one_or_none()
            if not endpoint:
                return {"success": False, "error": f"端点 {endpoint_id} 不存在"}

            responses = endpoint.responses if isinstance(endpoint.responses, dict) else {}
            if not responses:
                return {
                    "success": False,
                    "error": "该端点没有 responses 定义，无法供给 schema",
                    "hint": "可退回到 derive_test_skeleton 推导用例，或手写字段断言。",
                }

            # 确定要返回的状态码集合
            status_keys = [k for k in responses.keys() if str(k).isdigit() or str(k).lower() == "default"]
            if status:
                targets = [str(status)] if str(status) in responses else []
                if not targets:
                    return {
                        "success": False,
                        "error": f"responses 中没有状态码 {status} 的定义",
                        "available_statuses": status_keys,
                    }
            else:
                targets = status_keys

            success_status = next((k for k in status_keys if str(k) in _SUCCESS_STATUS), None)

            schemas: dict[str, Any] = {}
            notes: list[str] = []
            for sk in targets:
                resp_def = responses.get(sk)
                raw_schema = _pick_media_schema(resp_def)
                if raw_schema is None:
                    schemas[sk] = {
                        "schema": None, "has_inline_schema": False,
                        "required_fields": [], "field_types": {}, "enums": {},
                        "unresolved_refs": [],
                    }
                    notes.append(f"状态码 {sk} 未找到 JSON schema（可能无响应体或非 JSON）。")
                    continue

                unresolved: list[str] = []
                # roots 用于本地 $ref 解析：schema 自身 + 响应定义（可能携带 components/definitions）
                roots = [raw_schema]
                if isinstance(resp_def, dict):
                    roots.append(resp_def)
                safe_schema = _deref(raw_schema, roots, unresolved)

                required_fields: list[str] = []
                field_types: dict[str, str] = {}
                enums: dict[str, list] = {}
                _flatten(safe_schema, "", required_fields, field_types, enums)

                schemas[sk] = {
                    "schema": safe_schema,
                    "has_inline_schema": True,
                    "required_fields": required_fields,
                    "field_types": field_types,
                    "enums": enums,
                    "unresolved_refs": unresolved,
                }
                if unresolved:
                    notes.append(
                        f"状态码 {sk} 有 {len(unresolved)} 个 $ref 无法解析（完整 spec 未持久化），"
                        f"对应结构已按“任意”处理：{', '.join(unresolved[:5])}。"
                        f"这些部分的字段级断言请结合 get_endpoint_details 补充。"
                    )

            return {
                "success": True,
                "endpoint": {
                    "id": str(endpoint.id),
                    "method": endpoint.method,
                    "path": endpoint.path,
                    "display_name": endpoint.display_name,
                },
                "success_status": success_status,
                "schemas": schemas,
                "notes": notes,
                "usage_hint": (
                    "在脚本中嵌入 schemas['<status>'].schema 为 const SCHEMA，"
                    "成功响应用例调用 validateSchema(body, SCHEMA).valid（TS，helper 在 tests/_helpers/schema.ts）"
                    "或 validate_schema(body, SCHEMA)（Python，tests/_helpers/schema.py）做整体契约校验；"
                    "field_types/enums/required_fields 可用于补充针对性断言。"
                ),
            }
        except Exception as e:
            return {"success": False, "error": f"获取响应 schema 失败: {str(e)}"}


__all__ = ["get_response_schema"]
