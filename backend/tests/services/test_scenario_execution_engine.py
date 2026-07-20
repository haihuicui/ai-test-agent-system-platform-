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
