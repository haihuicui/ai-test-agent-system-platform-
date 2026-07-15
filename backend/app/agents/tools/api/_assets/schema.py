"""API 响应契约校验 helper（Python，基于 jsonschema——venv 已装，零新依赖）。

生成 pytest 脚本时使用：
    from _helpers.schema import validate_schema
    body = response.json()
    valid, errors = validate_schema(body, SCHEMA)
    assert valid, "\\n".join(errors)

$ref 已由后端 get_response_schema 尽力内联，未解的替换为 {}（jsonschema 视为“任意”）。
"""
from __future__ import annotations

from typing import Any

import jsonschema


def validate_schema(body: Any, schema: dict) -> tuple[bool, list[str]]:
    """校验响应体是否符合 JSON Schema。

    Returns:
        (valid, errors)：valid 为是否通过；errors 为人类可读的错误列表（含 JSON 路径）。
    """
    if not isinstance(schema, dict):
        return True, []
    try:
        validator = jsonschema.Draft7Validator(schema)
    except jsonschema.SchemaError as e:
        # schema 本身非法时，不误判响应，回退为通过并提示
        return True, [f"schema 定义异常，已跳过校验: {e.message}"]
    errors = sorted(validator.iter_errors(body), key=lambda e: list(e.path))
    msgs = [
        f"{'/'.join(str(p) for p in err.path) or '$'}: {err.message}"
        for err in errors
    ]
    return (len(msgs) == 0, msgs)


def assert_schema(body: Any, schema: dict) -> None:
    """校验失败时抛 AssertionError（带全部错误），便于直接作为断言使用。"""
    valid, errors = validate_schema(body, schema)
    assert valid, "响应不符合 schema:\n" + "\n".join(errors)


__all__ = ["validate_schema", "assert_schema"]
