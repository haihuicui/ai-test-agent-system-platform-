"""
ScenarioExecutionEngine 核心解析逻辑单元测试

重点覆盖：
1. 模板变量兼容带空格写法（{{ $timestamp }} / {{ siteId }}）
2. 动态占位符解析（{{$uuid}} / {{$timestamp}} / {{$faker.name}}）
"""

import re
from uuid import UUID

import pytest

from app.services.scenario_execution_engine import DataDependencyResolver, ExecutionContext


class TestTemplateVariableParsing:
    """测试 {{variable}} 和 {{$dynamic}} 模板变量解析"""

    @pytest.fixture
    def resolver(self):
        ctx = ExecutionContext()
        ctx.set_variable("siteId", "12345")
        ctx.set_variable("baseUrl", "https://api.example.com")
        return DataDependencyResolver(ctx)

    def test_substitute_variable_without_spaces(self, resolver):
        assert resolver._substitute_variables("/items/{{siteId}}") == "/items/12345"

    def test_substitute_variable_with_spaces(self, resolver):
        assert resolver._substitute_variables("/items/{{ siteId }}") == "/items/12345"

    def test_substitute_nested_variable_with_spaces(self, resolver):
        ctx = ExecutionContext()
        ctx.set_variable("data", {"id": "abc"})
        resolver = DataDependencyResolver(ctx)
        # 当前只支持单层变量名，data.id 会被当作整体变量名
        assert resolver._substitute_variables("/items/{{ data.id }}") == "/items/{{ data.id }}"

    def test_substitute_preserves_unknown_variable(self, resolver):
        assert resolver._substitute_variables("/items/{{ unknown }}") == "/items/{{ unknown }}"

    def test_resolve_dynamic_timestamp_without_spaces(self, resolver):
        result = resolver._resolve_dynamic_placeholders("{{$timestamp}}")
        assert result.isdigit()
        assert len(result) == 13

    def test_resolve_dynamic_timestamp_with_spaces(self, resolver):
        result = resolver._resolve_dynamic_placeholders("{{ $timestamp }}")
        assert result.isdigit()
        assert len(result) == 13

    def test_resolve_dynamic_uuid_with_spaces(self, resolver):
        result = resolver._resolve_dynamic_placeholders("{{ $uuid }}")
        # 验证是合法 UUID
        assert UUID(result).version == 4

    def test_resolve_dynamic_random_string_with_spaces(self, resolver):
        result = resolver._resolve_dynamic_placeholders("{{ $randomString(8) }}")
        assert len(result) == 8
        assert re.match(r"^[a-z0-9]+$", result)

    def test_resolve_dynamic_faker_with_spaces(self, resolver):
        result = resolver._resolve_dynamic_placeholders("{{ $faker.name }}")
        assert len(result) > 0
        assert "{{" not in result

    def test_resolve_dynamic_mixed_with_regular_variable(self, resolver):
        ctx = ExecutionContext()
        ctx.set_variable("prefix", "test")
        resolver = DataDependencyResolver(ctx)
        # 真实执行流程：先解析动态占位符，再替换普通变量
        after_dynamic = resolver._resolve_dynamic_placeholders("{{prefix}}_{{ $timestamp }}")
        result = resolver._substitute_variables(after_dynamic)
        assert result.startswith("test_")
        assert result[5:].isdigit()

    def test_resolve_dynamic_placeholders_in_dict(self, resolver):
        payload = {
            "name": "测试_{{ $timestamp }}",
            "uuid": "{{$uuid}}",
            "count": 1,
        }
        result = resolver._resolve_dynamic_placeholders(payload)
        assert result["name"].startswith("测试_")
        assert result["name"][3:].isdigit()
        assert UUID(result["uuid"]).version == 4
        assert result["count"] == 1


class TestAssertionOperators:
    """测试断言操作符归一化与执行"""

    @pytest.fixture
    def engine(self):
        # _compare / _run_assertions 不依赖 session，可直接传 None
        from app.services.scenario_execution_engine import ScenarioExecutionEngine
        return ScenarioExecutionEngine(session=None)

    def test_compare_canonical_operators(self, engine):
        assert engine._compare(200, 200, "eq") is True
        assert engine._compare(200, 201, "ne") is True
        assert engine._compare(201, 200, "gt") is True
        assert engine._compare(199, 200, "lt") is True
        assert engine._compare([1, 2, 3], 2, "contains") is True

    def test_compare_returns_false_for_mismatch(self, engine):
        assert engine._compare(200, 201, "eq") is False
        assert engine._compare(200, 200, "ne") is False
        assert engine._compare(199, 200, "gt") is False
        assert engine._compare(201, 200, "lt") is False
        assert engine._compare([1, 2, 3], 4, "contains") is False

    def test_compare_raises_for_unknown_operator(self, engine):
        with pytest.raises(ValueError, match="不支持的比较运算符"):
            engine._compare(200, 200, "regex")

    def test_run_assertions_normalizes_legacy_aliases(self, engine):
        response = {"status": 200, "body": {"success": True}, "headers": {}}
        assertions = [
            {"type": "status", "expected": 200, "operator": "equals"},
            {"type": "jsonpath", "path": "$.success", "expected": True, "operator": "equals"},
        ]
        results = engine._run_assertions(response, assertions)
        assert len(results) == 2
        assert all(r["passed"] for r in results)

    def test_run_assertions_defaults_missing_operator_to_eq(self, engine):
        response = {"status": 200, "body": {}, "headers": {}}
        assertions = [{"type": "status", "expected": 200}]
        results = engine._run_assertions(response, assertions)
        assert results[0]["passed"] is True

    def test_run_assertions_fails_with_message_for_invalid_operator(self, engine):
        response = {"status": 200, "body": {}, "headers": {}}
        assertions = [{"type": "status", "expected": 200, "operator": "regex"}]
        results = engine._run_assertions(response, assertions)
        assert results[0]["passed"] is False
        assert "不支持的比较运算符" in results[0]["message"]
