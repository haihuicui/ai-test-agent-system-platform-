"""schema 供给工具（schema_tools）与门禁契约识别的测试。

覆盖：
- _pick_media_schema：content 包装 / 直接 schema / schema 关键字形态；
- _deref：$ref 不可解析降级为 {}、本地 definitions 内联、循环深度保护；
- _flatten：required / enums / field_types / 数组元素 / allOf；
- 门禁对 validateSchema / validate_schema / jsonschema.validate 的识别（计为有效结构断言）；
- get_response_schema 的入参校验（非法 UUID）。
"""
from __future__ import annotations

import pytest

from app.agents.tools.api.assertion_analyzer import build_assertion_report
from app.agents.tools.api.schema_tools import (
    _deref,
    _flatten,
    _pick_media_schema,
    get_response_schema,
)


# ---------------------------------------------------------------------------
# _pick_media_schema
# ---------------------------------------------------------------------------

def test_pick_media_content_wrapped():
    resp = {"content": {"application/json": {"schema": {"type": "object", "properties": {"id": {"type": "string"}}}}}}
    s = _pick_media_schema(resp)
    assert s is not None and s["type"] == "object"


def test_pick_media_direct_schema_key():
    resp = {"schema": {"type": "array", "items": {"type": "integer"}}}
    s = _pick_media_schema(resp)
    assert s is not None and s["type"] == "array"


def test_pick_media_bare_schema():
    resp = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    s = _pick_media_schema(resp)
    assert s is not None and s["type"] == "object"


def test_pick_media_none_when_no_schema():
    assert _pick_media_schema({"description": "no body"}) is None
    assert _pick_media_schema(None) is None


# ---------------------------------------------------------------------------
# _deref
# ---------------------------------------------------------------------------

def test_deref_unresolvable_replaced_with_empty():
    schema = {"type": "object", "properties": {"user": {"$ref": "#/components/schemas/User"}, "name": {"type": "string"}}}
    unresolved: list[str] = []
    safe = _deref(schema, [schema], unresolved)
    assert unresolved == ["#/components/schemas/User"]
    assert safe["properties"]["user"] == {}
    assert safe["properties"]["name"] == {"type": "string"}


def test_deref_local_definitions_inlined():
    schema = {
        "type": "object",
        "properties": {"addr": {"$ref": "#/definitions/Addr"}},
        "definitions": {"Addr": {"type": "object", "properties": {"city": {"type": "string"}}}},
    }
    unresolved: list[str] = []
    safe = _deref(schema, [schema], unresolved)
    assert unresolved == []
    assert safe["properties"]["addr"]["properties"]["city"]["type"] == "string"


def test_deref_keeps_sibling_constraints():
    schema = {"properties": {"x": {"$ref": "#/nope", "description": "keep me"}}}
    unresolved: list[str] = []
    safe = _deref(schema, [schema], unresolved)
    assert safe["properties"]["x"].get("description") == "keep me"


def test_deref_depth_guard_no_recursion():
    # 自引用：A -> A
    schema = {"definitions": {"A": {"$ref": "#/definitions/A"}}, "properties": {"a": {"$ref": "#/definitions/A"}}}
    unresolved: list[str] = []
    safe = _deref(schema, [schema], unresolved)
    assert isinstance(safe, dict)  # 不崩溃即通过


# ---------------------------------------------------------------------------
# _flatten
# ---------------------------------------------------------------------------

def test_flatten_required_enums_types():
    schema = {
        "type": "object",
        "required": ["data"],
        "properties": {
            "success": {"type": "boolean"},
            "data": {
                "type": "object",
                "required": ["id"],
                "properties": {
                    "id": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "paid", "cancelled"]},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    }
    rf: list[str] = []
    ft: dict = {}
    en: dict = {}
    _flatten(schema, "", rf, ft, en)
    assert "data" in rf and "data.id" in rf
    assert en["data.status"] == ["pending", "paid", "cancelled"]
    assert ft["data"] == "object"
    assert ft["data.id"] == "string"
    assert ft["data.tags[]"] == "string"


# ---------------------------------------------------------------------------
# 门禁对 schema 校验调用的识别
# ---------------------------------------------------------------------------

def test_gate_recognizes_ts_validateSchema():
    content = """
import { validateSchema } from './_helpers/schema';
test('成功场景', async () => {
  expect(response.status).toBe(200);
  expect(validateSchema(body, SCHEMA).valid).toBe(true);
});
"""
    r = build_assertion_report(content)
    assert r["metrics"]["schema_validation_calls"] >= 1
    assert r["verdict"] == "OK"


def test_gate_recognizes_python_validate_schema():
    content = """
from _helpers.schema import validate_schema

def test_success():
    assert response.status_code == 200
    valid, errors = validate_schema(response.json(), SCHEMA)
    assert valid
"""
    r = build_assertion_report(content, "python", "pytest")
    assert r["metrics"]["schema_validation_calls"] >= 1


def test_gate_recognizes_jsonschema_validate():
    content = """
import jsonschema

def test_success():
    assert response.status_code == 200
    jsonschema.validate(response.json(), SCHEMA)
"""
    r = build_assertion_report(content, "python", "pytest")
    assert r["metrics"]["schema_validation_calls"] >= 1


# ---------------------------------------------------------------------------
# get_response_schema 入参校验（无需 DB 的早退路径）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_response_schema_invalid_uuid():
    result = await get_response_schema.ainvoke({"endpoint_id": "not-a-uuid"})
    assert result["success"] is False
    assert "Invalid endpoint_id" in result["error"]
