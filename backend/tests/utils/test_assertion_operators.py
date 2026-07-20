import pytest

from app.utils.assertion_operators import normalize_operator, OPERATORS


class TestNormalizeOperator:
    """断言操作符归一化测试"""

    def test_canonical_values_return_unchanged(self):
        for op in OPERATORS:
            assert normalize_operator(op) == op

    def test_legacy_verbose_aliases_are_normalized(self):
        assert normalize_operator("equals") == "eq"
        assert normalize_operator("not_equals") == "ne"
        assert normalize_operator("greater_than") == "gt"
        assert normalize_operator("less_than") == "lt"

    def test_case_and_whitespace_are_normalized(self):
        assert normalize_operator("  EQ  ") == "eq"
        assert normalize_operator("Equals") == "eq"
        assert normalize_operator(" NOT_EQUALS ") == "ne"

    def test_none_returns_default(self):
        assert normalize_operator(None) == "eq"

    def test_empty_string_returns_default(self):
        assert normalize_operator("") == "eq"
        assert normalize_operator("   ") == "eq"

    def test_custom_default(self):
        assert normalize_operator(None, default="contains") == "contains"
        assert normalize_operator("", default="contains") == "contains"

    def test_invalid_operator_raises(self):
        with pytest.raises(ValueError, match="不支持的比较运算符"):
            normalize_operator("regex")

        with pytest.raises(ValueError, match="不支持的比较运算符"):
            normalize_operator("unknown")

    def test_error_message_includes_allowed_operators(self):
        with pytest.raises(ValueError) as exc_info:
            normalize_operator("regex")
        message = str(exc_info.value)
        for op in sorted(OPERATORS):
            assert op in message
