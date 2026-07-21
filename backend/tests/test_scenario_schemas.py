"""Scenario 相关 Pydantic Schema 测试"""

from datetime import datetime
from uuid import uuid4

import pytest

from app.schemas.scenario import ScenarioStepResultResponse, StepAssertion, StepVariableExport


class TestStepAssertion:
    """测试断言 schema 对 operator 的归一化"""

    def test_defaults_missing_operator_to_eq(self):
        assertion = StepAssertion(type="status", expected=200)
        assert assertion.operator == "eq"

    def test_keeps_canonical_operator(self):
        assertion = StepAssertion(type="status", expected=200, operator="ne")
        assert assertion.operator == "ne"

    @pytest.mark.parametrize("alias,expected", [
        ("equals", "eq"),
        ("not_equals", "ne"),
        ("greater_than", "gt"),
        ("less_than", "lt"),
        ("contains", "contains"),
    ])
    def test_normalizes_legacy_aliases(self, alias, expected):
        assertion = StepAssertion(type="status", expected=200, operator=alias)
        assert assertion.operator == expected

    def test_normalizes_empty_string_to_default(self):
        assertion = StepAssertion(type="status", expected=200, operator="")
        assert assertion.operator == "eq"

    def test_rejects_unknown_operator(self):
        with pytest.raises(ValueError):
            StepAssertion(type="status", expected=200, operator="regex")


class TestStepVariableExport:
    """测试步骤变量导出 schema"""

    def test_valid_request_export(self):
        export = StepVariableExport(name="siteName", source="request", path="$.body.name")
        assert export.name == "siteName"
        assert export.source == "request"
        assert export.path == "$.body.name"
        assert export.type == "jsonpath"

    def test_valid_response_export(self):
        export = StepVariableExport(name="siteId", source="response", path="$.data.id")
        assert export.source == "response"

    def test_defaults_source_to_request(self):
        export = StepVariableExport(name="x", path="$.body.x")
        assert export.source == "request"

    def test_rejects_invalid_source(self):
        with pytest.raises(ValueError):
            StepVariableExport(name="x", source="body", path="$.body.x")

    def test_rejects_empty_name(self):
        with pytest.raises(ValueError):
            StepVariableExport(name="", source="request", path="$.body.x")

    def test_rejects_empty_path(self):
        with pytest.raises(ValueError):
            StepVariableExport(name="x", source="request", path="")


class TestScenarioStepResultResponse:
    """测试步骤执行结果响应 schema"""

    def test_includes_exported_data(self):
        result = ScenarioStepResultResponse(
            id=uuid4(),
            run_id=uuid4(),
            step_id=uuid4(),
            endpoint_id=None,
            step_order=1,
            step_name="test",
            full_url="http://example.com/test",
            status="passed",
            duration_ms=100,
            error_message=None,
            error_stack=None,
            created_at=datetime.utcnow(),
            request_data=None,
            response_data=None,
            extracted_data={},
            exported_data={"siteId": "abc", "siteName": "site_123"},
            assertion_results=[],
        )
        assert result.exported_data == {"siteId": "abc", "siteName": "site_123"}

    def test_exported_data_defaults_to_empty_dict(self):
        result = ScenarioStepResultResponse(
            id=uuid4(),
            run_id=uuid4(),
            step_id=uuid4(),
            endpoint_id=None,
            step_order=1,
            step_name="test",
            full_url=None,
            status="passed",
            duration_ms=None,
            error_message=None,
            error_stack=None,
            created_at=datetime.utcnow(),
            request_data=None,
            response_data=None,
            extracted_data={},
            exported_data={},
            assertion_results=[],
        )
        assert result.exported_data == {}
