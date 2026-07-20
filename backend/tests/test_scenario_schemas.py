"""Scenario 相关 Pydantic Schema 测试"""

import pytest

from app.schemas.scenario import StepAssertion


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
