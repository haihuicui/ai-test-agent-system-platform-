"""
ScenarioExecutionEngine 核心解析逻辑单元测试

重点覆盖：
1. 模板变量兼容带空格写法（{{ $timestamp }} / {{ siteId }}）
2. 动态占位符解析（{{$uuid}} / {{$timestamp}} / {{$faker.name}}）
"""

import re
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.services.scenario_execution_engine import (
    DataDependencyResolver,
    ExecutionContext,
    ScenarioExecutionEngine,
)


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

    def test_compare_contains_with_none_actual_returns_false(self, engine):
        """header 未命中时 contains 不应抛 TypeError，安全降级为 False"""
        assert engine._compare(None, "application/json", "contains") is False

    def test_run_assertions_header_case_insensitive(self, engine):
        """httpx 响应头转 dict 后键全小写，断言写 Content-Type 也应命中"""
        response = {
            "status": 200,
            "body": {"code": 200},
            "headers": {"content-type": "application/json"},
        }
        assertions = [
            {"type": "header", "path": "Content-Type", "expected": "application/json", "operator": "contains"},
        ]
        results = engine._run_assertions(response, assertions)
        assert results[0]["passed"] is True
        assert results[0]["actual"] == "application/json"

    def test_run_assertions_header_missing_contains_fails_gracefully(self, engine):
        """header 缺失 + contains：断言失败但不抛异常、不产生 error 步骤"""
        response = {"status": 200, "body": {}, "headers": {}}
        assertions = [
            {"type": "header", "path": "Content-Type", "expected": "json", "operator": "contains"},
        ]
        results = engine._run_assertions(response, assertions)
        assert results[0]["passed"] is False
        assert "断言" in results[0]["message"]

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


class TestExportVariables:
    """测试步骤变量导出"""

    def test_export_from_request_sets_context_variable(self):
        engine = ScenarioExecutionEngine(session=None)  # type: ignore
        request = {
            "method": "POST",
            "url": "/sites",
            "body": {"name": "site_123"},
        }
        exports = [{"name": "siteName", "path": "$.body.name", "source": "request"}]

        result = engine._export_variables(request, exports, phase="request")

        assert result["siteName"] == "site_123"
        assert engine.context.get_variable("siteName") == "site_123"

    def test_export_from_response_sets_context_variable(self):
        engine = ScenarioExecutionEngine(session=None)  # type: ignore
        response = {"status": 200, "body": {"id": "abc"}}
        exports = [{"name": "siteId", "path": "$.body.id", "source": "response"}]

        result = engine._export_variables(response, exports, phase="response")

        assert result["siteId"] == "abc"
        assert engine.context.get_variable("siteId") == "abc"

    def test_export_with_string_body(self):
        engine = ScenarioExecutionEngine(session=None)  # type: ignore
        response = {"status": 200, "body": '{"id": "abc"}'}
        exports = [{"name": "siteId", "path": "$.body.id", "source": "response"}]

        result = engine._export_variables(response, exports, phase="response")

        assert result["siteId"] == "abc"

    def test_export_missing_value_records_warning(self):
        engine = ScenarioExecutionEngine(session=None)  # type: ignore
        response = {"status": 200, "body": {}}
        exports = [{"name": "siteId", "path": "$.body.id", "source": "response"}]

        result = engine._export_variables(response, exports, phase="response")

        assert result["siteId"] is None
        assert "_export_warnings" in result
        assert any(w["name"] == "siteId" for w in result["_export_warnings"])

    def test_export_empty_exports_returns_empty(self):
        engine = ScenarioExecutionEngine(session=None)  # type: ignore
        result = engine._export_variables({}, [], phase="request")
        assert result == {}


class TestExportedDataSnapshot:
    """测试需要持久化到 ScenarioStepResult.exported_data 的导出变量快照"""

    def test_build_exported_data_filters_internal_keys(self):
        engine = ScenarioExecutionEngine(session=None)  # type: ignore
        raw = {"siteName": "site_123", "_export_warnings": [{"name": "x"}]}

        exported_data = engine._build_exported_data(raw)

        assert exported_data == {"siteName": "site_123"}
        assert "_export_warnings" not in exported_data

    def test_exported_data_combines_request_and_response_exports(self):
        engine = ScenarioExecutionEngine(session=None)  # type: ignore
        request = {"body": {"name": "site_123"}}
        response = {"body": {"id": "abc"}}
        exports = [
            {"name": "siteName", "source": "request", "path": "$.body.name"},
            {"name": "siteId", "source": "response", "path": "$.body.id"},
        ]

        request_exported = engine._export_variables(
            request, [e for e in exports if e["source"] == "request"], phase="request"
        )
        response_exported = engine._export_variables(
            response, [e for e in exports if e["source"] == "response"], phase="response"
        )
        exported_data = {
            **engine._build_exported_data(request_exported),
            **engine._build_exported_data(response_exported),
        }

        assert exported_data == {"siteName": "site_123", "siteId": "abc"}

    def test_exported_data_excludes_warnings(self):
        engine = ScenarioExecutionEngine(session=None)  # type: ignore
        response = {"body": {}}
        exports = [{"name": "siteId", "source": "response", "path": "$.body.id"}]

        response_exported = engine._export_variables(response, exports, phase="response")
        exported_data = engine._build_exported_data(response_exported)

        assert exported_data == {"siteId": None}
        assert "_export_warnings" not in exported_data
        assert "_export_warnings" in response_exported


class TestCompareOperators:
    """_compare 比较运算符（含 ge/le）"""

    def _engine(self):
        return ScenarioExecutionEngine(session=None)

    def test_ge_le(self):
        engine = self._engine()
        assert engine._compare(1, 1, "ge") is True
        assert engine._compare(0, 1, "ge") is False
        assert engine._compare(2, 1, "ge") is True
        assert engine._compare(1, 1, "le") is True
        assert engine._compare(2, 1, "le") is False
        assert engine._compare(0, 1, "le") is True


class TestTeardownResults:
    """teardown 执行结果收集与持久化（结果不再静默吞掉）"""

    def _engine(self):
        return ScenarioExecutionEngine(session=None)

    @pytest.mark.asyncio
    async def test_results_persisted_to_runtime_variables(self, monkeypatch):
        engine = self._engine()
        responses = iter([
            {"index": 1, "name": "删除测试单", "success": False, "status_code": 409,
             "error": None, "assertion_results": []},
            {"index": 2, "name": "验证已删除", "success": True, "status_code": 404,
             "error": None, "assertion_results": []},
        ])

        async def fake_execute(step_def, idx):
            return next(responses)

        monkeypatch.setattr(engine, "_execute_teardown_step", fake_execute)

        from types import SimpleNamespace
        scenario = SimpleNamespace(
            identifier="TS-0001",
            teardown_config={"steps": [
                {"name": "删除测试单"},
                {"name": "验证已删除"},
            ]},
        )
        run = SimpleNamespace(runtime_variables={"baseUrl": "http://x"})

        await engine._run_teardown(scenario, run)

        results = run.runtime_variables["teardown_results"]
        assert len(results) == 2
        assert results[0]["success"] is False
        assert results[0]["status_code"] == 409
        assert results[1]["success"] is True
        # 原有变量不被覆盖
        assert run.runtime_variables["baseUrl"] == "http://x"

    @pytest.mark.asyncio
    async def test_exception_recorded_and_continues(self, monkeypatch):
        engine = self._engine()
        calls = []

        async def fake_execute(step_def, idx):
            calls.append(idx)
            if idx == 1:
                raise RuntimeError("连接超时")
            return {"index": idx, "name": step_def["name"], "success": True,
                    "status_code": 200, "error": None, "assertion_results": []}

        monkeypatch.setattr(engine, "_execute_teardown_step", fake_execute)

        from types import SimpleNamespace
        scenario = SimpleNamespace(
            identifier="TS-0001",
            teardown_config={"steps": [{"name": "A"}, {"name": "B"}]},
        )
        run = SimpleNamespace(runtime_variables={})

        await engine._run_teardown(scenario, run)

        assert calls == [1, 2]  # 默认 continue_on_failure=true，异常后继续
        results = run.runtime_variables["teardown_results"]
        assert results[0]["success"] is False
        assert "连接超时" in results[0]["error"]
        assert results[1]["success"] is True

    @pytest.mark.asyncio
    async def test_continue_on_failure_false_stops_on_http_failure(self, monkeypatch):
        """非异常失败（如 4xx）也应触发 continue_on_failure=false 的中断"""
        engine = self._engine()
        calls = []

        async def fake_execute(step_def, idx):
            calls.append(idx)
            return {"index": idx, "name": step_def["name"], "success": False,
                    "status_code": 409, "error": None, "assertion_results": []}

        monkeypatch.setattr(engine, "_execute_teardown_step", fake_execute)

        from types import SimpleNamespace
        scenario = SimpleNamespace(
            identifier="TS-0001",
            teardown_config={"steps": [
                {"name": "A", "continue_on_failure": False},
                {"name": "B"},
            ]},
        )
        run = SimpleNamespace(runtime_variables={})

        await engine._run_teardown(scenario, run)

        assert calls == [1]
        assert len(run.runtime_variables["teardown_results"]) == 1

    @pytest.mark.asyncio
    async def test_step_success_judged_by_assertions(self, monkeypatch):
        """配置断言时以断言结果判定成功，而非状态码"""
        engine = self._engine()

        async def fake_load_endpoint(endpoint_id, step):
            return SimpleNamespace(id=None)

        async def fake_resolve(step_like, endpoint, session):
            return {"method": "GET", "url": "/x/1", "headers": {}, "params": {}, "body": None}

        async def fake_send(request):
            # 删除后再读返回 200（资源仍在），断言预期 404 → 应判失败
            return {"status": 200, "headers": {}, "body": {}, "timing": 1}

        monkeypatch.setattr(engine, "_load_endpoint", fake_load_endpoint)
        monkeypatch.setattr(engine.resolver, "resolve_request", fake_resolve)
        monkeypatch.setattr(engine, "_send_request", fake_send)

        result = await engine._execute_teardown_step({
            "name": "验证已删除",
            "request_override": {"method": "GET", "path": "/x/1"},
            "assertions": [{"type": "status", "expected": 404, "operator": "eq"}],
        }, 1)

        assert result["success"] is False
        assert result["status_code"] == 200
        assert len(result["assertion_results"]) == 1
        assert result["assertion_results"][0]["passed"] is False

    @pytest.mark.asyncio
    async def test_step_success_judged_by_status_code_without_assertions(self, monkeypatch):
        """未配置断言时 4xx/5xx 判定清理失败"""
        engine = self._engine()

        async def fake_load_endpoint(endpoint_id, step):
            return SimpleNamespace(id=None)

        async def fake_resolve(step_like, endpoint, session):
            return {"method": "DELETE", "url": "/x/1", "headers": {}, "params": {}, "body": None}

        async def fake_send(request):
            return {"status": 409, "headers": {}, "body": {"message": "已签收"}, "timing": 1}

        monkeypatch.setattr(engine, "_load_endpoint", fake_load_endpoint)
        monkeypatch.setattr(engine.resolver, "resolve_request", fake_resolve)
        monkeypatch.setattr(engine, "_send_request", fake_send)

        result = await engine._execute_teardown_step({
            "name": "删除测试单",
            "request_override": {"method": "DELETE", "path": "/x/1"},
        }, 1)

        assert result["success"] is False
        assert result["status_code"] == 409
        assert result["assertion_results"] == []
