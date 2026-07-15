"""Tests for CaseQualityGateMiddleware 的确定性校验函数。

覆盖 _is_fuzzy_result（模糊预期结果判定）与 _validate_case（单条用例质量红线校验）。
"""
from __future__ import annotations

import pytest

from app.agents.testcase.case_quality_middleware import (
    _is_fuzzy_result,
    _validate_case,
)


def _valid_case() -> dict:
    """构造一条完全合规的普通测试用例。"""
    return {
        "name": "正确凭证登录成功",
        "case_number": "TC-PROJ-LOGIN-001",
        "module": "登录模块",
        "test_data": {"username": "test001", "password": "Test@123"},
        "test_case_steps": [
            {
                "step": "输入正确用户名密码并点击登录",
                "result": "页面跳转至 /home 并显示昵称 test001",
            },
        ],
    }


class TestIsFuzzyResult:
    @pytest.mark.parametrize(
        "result",
        ["正确", "成功", "正常", "通过", "无错误", "符合预期", "操作成功", "功能正常"],
    )
    def test_pure_fuzzy_words(self, result):
        assert _is_fuzzy_result(result) is True

    def test_empty_and_blank(self):
        assert _is_fuzzy_result("") is True
        assert _is_fuzzy_result("   ") is True

    def test_wrapped_in_quotes_and_punctuation(self):
        # 首尾引号/标点剥离后仍是纯模糊词
        assert _is_fuzzy_result("“成功”。") is True
        assert _is_fuzzy_result("'正常'，") is True

    @pytest.mark.parametrize(
        "result",
        [
            "提示'登录成功'",  # 带具体文案，剥离后不在模糊词集合内
            "页面跳转至 /home",
            "返回状态码 200",
            "显示错误信息“密码不能为空”",
            "操作成功，并跳转至订单列表页",  # 包含模糊词但有具体内容
        ],
    )
    def test_concrete_results_not_fuzzy(self, result):
        assert _is_fuzzy_result(result) is False


class TestValidateCase:
    def test_valid_case_passes(self):
        assert _validate_case(_valid_case()) == []

    def test_non_dict_input(self):
        assert _validate_case(None) == ["用例参数不是有效对象"]
        assert _validate_case("not-a-dict") == ["用例参数不是有效对象"]

    def test_empty_case_reports_all_violations(self):
        violations = _validate_case({})
        assert len(violations) == 4
        assert any("module" in v for v in violations)
        assert any("case_number" in v for v in violations)
        assert any("test_data" in v for v in violations)
        assert any("test_case_steps" in v for v in violations)

    def test_module_blank_or_non_string(self):
        case = _valid_case()
        case["module"] = "   "
        assert any("module" in v for v in _validate_case(case))

        case = _valid_case()
        case["module"] = 123
        assert any("module" in v for v in _validate_case(case))

    def test_case_number_required(self):
        case = _valid_case()
        del case["case_number"]
        assert any("case_number" in v for v in _validate_case(case))

    def test_case_id_alias_accepted(self):
        case = _valid_case()
        case["case_id"] = case.pop("case_number")
        assert _validate_case(case) == []

    def test_case_number_allows_chinese_segments(self):
        case = _valid_case()
        case["case_number"] = "TC-项目-登录模块-01"
        assert _validate_case(case) == []

    @pytest.mark.parametrize(
        "bad_number",
        [
            "TC-PROJ-LOGIN-1",    # 序号不足 2 位
            "TC-PROJ-001",        # 缺少模块段
            "PROJ-LOGIN-001",     # 缺少 TC- 前缀
            "tc-proj-login-001",  # 前缀必须大写
            "TC--LOGIN-001",      # 项目段为空
        ],
    )
    def test_case_number_format_rejected(self, bad_number):
        case = _valid_case()
        case["case_number"] = bad_number
        assert any("格式不符合" in v for v in _validate_case(case))

    def test_test_data_missing_or_empty(self):
        case = _valid_case()
        case["test_data"] = None
        assert any("test_data" in v for v in _validate_case(case))

        case = _valid_case()
        case["test_data"] = {}
        assert any("test_data" in v for v in _validate_case(case))

    @pytest.mark.parametrize(
        "value", ["有效数据", "合理值", "任意值", "待补充", "TBD", "xxx", "N/A"]
    )
    def test_test_data_placeholder_rejected(self, value):
        case = _valid_case()
        case["test_data"] = {"username": value}
        violations = _validate_case(case)
        assert any("占位" in v and "username" in v for v in violations)

    def test_test_data_non_string_values_ignored(self):
        case = _valid_case()
        case["test_data"] = {"retry": 3, "enabled": True}
        assert _validate_case(case) == []

    def test_steps_missing_empty_or_not_list(self):
        case = _valid_case()
        del case["test_case_steps"]
        assert any("test_case_steps" in v for v in _validate_case(case))

        case = _valid_case()
        case["test_case_steps"] = []
        assert any("test_case_steps" in v for v in _validate_case(case))

        case = _valid_case()
        case["test_case_steps"] = "not-a-list"
        assert any("test_case_steps" in v for v in _validate_case(case))

    def test_fuzzy_step_result_rejected_with_position(self):
        case = _valid_case()
        case["test_case_steps"] = [
            {"step": "s1", "result": "页面跳转至 /home"},
            {"step": "s2", "result": "成功"},
        ]
        violations = _validate_case(case)
        assert len(violations) == 1
        assert "第 2 步" in violations[0]

    def test_step_result_none_rejected(self):
        case = _valid_case()
        case["test_case_steps"] = [{"step": "s1"}]
        violations = _validate_case(case)
        assert any("第 1 步" in v for v in violations)

    def test_non_dict_step_skipped(self):
        case = _valid_case()
        case["test_case_steps"] = [
            "not-a-dict",
            {"step": "s", "result": "返回状态码 200"},
        ]
        assert _validate_case(case) == []

    def test_bdd_template_skips_step_validation(self):
        case = _valid_case()
        case["template"] = "test_case_bdd"
        del case["test_case_steps"]
        assert _validate_case(case) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
