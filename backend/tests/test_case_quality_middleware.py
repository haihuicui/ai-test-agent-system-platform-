"""Tests for CaseQualityGateMiddleware 的确定性校验函数。

覆盖 _is_fuzzy_result（模糊预期结果判定）、_validate_case（单条用例质量红线校验）、
validate_case_hygiene（规范级 warning 通道）与 _hygiene_note（中间件提示生成）。
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import ToolMessage

from app.agents.testcase.case_quality_middleware import (
    CaseQualityGateMiddleware,
    _hygiene_note,
    _is_fuzzy_result,
    _postprocess,
    _validate_case,
)
from app.utils.testcase_validation import validate_case_hygiene


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
        assert len(violations) == 5
        assert any("name" in v for v in violations)
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
        "number",
        [
            "TC-PRJ-CLOUD-EXPORT-001",   # 模块段含连字符（子模块划分）
            "TC-PRJ-METRIX-CALIB-001",
            "TC-PRJ-CLINIC-EXPORT-001",
            "TC-PROJ-A-B-C-099",         # 模块段多个连字符
        ],
    )
    def test_case_number_allows_hyphen_in_module(self, number):
        case = _valid_case()
        case["case_number"] = number
        assert _validate_case(case) == []

    @pytest.mark.parametrize(
        "bad_number",
        [
            "TC-PROJ-LOGIN-1",    # 序号不足 2 位
            "TC-PROJ-001",        # 缺少模块段
            "PROJ-LOGIN-001",     # 缺少 TC- 前缀
            "tc-proj-login-001",  # 前缀必须大写
            "TC--LOGIN-001",      # 项目段为空
            "TC-PROJ--LOGIN-001", # 模块段出现空段
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

    def test_top_level_expected_result_fuzzy_rejected(self):
        """顶层 expected_result 使用模糊词时被拦截。"""
        case = _valid_case()
        case["expected_result"] = "成功"
        violations = _validate_case(case)
        assert any("顶层预期结果" in v for v in violations)

    def test_top_level_expected_result_concrete_passes(self):
        """顶层 expected_result 为具体可验证描述时通过。"""
        case = _valid_case()
        case["expected_result"] = "页面跳转至 /home 并显示昵称 test001"
        assert _validate_case(case) == []

    def test_top_level_expected_result_aliases(self):
        """兼容 expected / 预期结果 等顶层字段别名。"""
        case = _valid_case()
        case["预期结果"] = "成功"
        violations = _validate_case(case)
        assert any("顶层预期结果" in v for v in violations)

    def test_name_required(self):
        """name 缺失或空白时拦截（批量路径 dict 内字段无工具 schema 兜底）。"""
        case = _valid_case()
        del case["name"]
        assert any("name" in v for v in _validate_case(case))

        case = _valid_case()
        case["name"] = "   "
        assert any("name" in v for v in _validate_case(case))


class TestValidateCaseHygiene:
    """规范级 warning：只提示不拦截，把 normalize_* 的静默修正显式化。"""

    def _rules(self, case: dict) -> set[str]:
        return {h["rule"] for h in validate_case_hygiene(case)}

    def test_fully_specified_case_no_hints(self):
        case = _valid_case()
        case.update({"case_type": "security", "priority": "high", "remarks": "REQ-1 FP-001"})
        case["test_case_steps"].append({"step": "点击退出", "result": "返回登录页"})
        assert validate_case_hygiene(case) == []

    def test_missing_case_type_priority_remarks(self):
        # _valid_case() 无 case_type/priority/remarks，且仅 1 步
        rules = self._rules(_valid_case())
        assert {"case_type缺失", "priority缺失", "无追溯编号", "单步骤"} <= rules

    def test_too_many_steps(self):
        case = _valid_case()
        case["test_case_steps"] = [
            {"step": f"步骤{i}", "result": f"结果{i}"} for i in range(12)
        ]
        assert "步骤过多" in self._rules(case)

    def test_legacy_f_number_trace_recognized(self):
        """F-11 这类旧编号体系也算有效追溯（存量数据真实存在）。"""
        case = _valid_case()
        case["remarks"] = "关联需求 F-11"
        assert "无追溯编号" not in self._rules(case)

    def test_long_name(self):
        case = _valid_case()
        case["name"] = "验" * 61
        assert "名称过长" in self._rules(case)

    def test_non_dict_returns_empty(self):
        assert validate_case_hygiene(None) == []


class TestHygieneNote:
    """中间件 warning 提示：单条逐条列，批量按规则聚合计数。"""

    def _req(self, name: str, args: dict):
        return SimpleNamespace(tool_call={"name": name, "args": args})

    def test_single_create_lists_messages(self):
        note = _hygiene_note(self._req("create_test_case_tool", _valid_case()))
        assert "不影响本次创建" in note
        assert "case_type" in note and "priority" in note

    def test_batch_aggregates_by_rule(self):
        cases = [_valid_case() for _ in range(3)]
        note = _hygiene_note(
            self._req("batch_create_test_cases_tool", {"test_cases": cases})
        )
        assert "3 条缺 case_type" in note
        assert "3 条缺 priority" in note

    def test_clean_input_returns_empty(self):
        case = _valid_case()
        case.update({"case_type": "functional", "priority": "high", "remarks": "FP-001"})
        case["test_case_steps"].append({"step": "点击退出", "result": "返回登录页"})
        assert _hygiene_note(self._req("create_test_case_tool", case)) == ""

    def test_other_tool_ignored(self):
        assert _hygiene_note(self._req("read_file", {"path": "x"})) == ""


class TestPostprocess:
    """_postprocess 的 warning 拼接：成功结果尾部追加提示，与失败清单共存。"""

    def _req(self, name: str, args: dict):
        return SimpleNamespace(tool_call={"name": name, "args": args, "id": "call-1"})

    def _ok_msg(self, content: dict) -> ToolMessage:
        return ToolMessage(content=json.dumps(content, ensure_ascii=False),
                           tool_call_id="call-1", name="batch_create_test_cases_tool")

    def test_batch_success_appends_hygiene_note(self):
        cases = [_valid_case(), _valid_case()]  # 均缺 case_type/priority/remarks
        result = self._ok_msg({"success": True,
                               "data": {"total": 2, "succeeded": 2, "failed": 0, "results": []}})
        out = _postprocess(result, self._req("batch_create_test_cases_tool",
                                             {"test_cases": cases}))
        assert "2 条缺 case_type" in out.content
        assert "不影响本次创建" in out.content

    def test_batch_partial_failure_keeps_both_notes(self):
        cases = [_valid_case()]
        result = self._ok_msg({"success": True, "data": {
            "total": 2, "succeeded": 1, "failed": 1,
            "results": [{"index": 1, "name": "X", "success": False, "error": "重复编号"}],
        }})
        out = _postprocess(result, self._req("batch_create_test_cases_tool",
                                             {"test_cases": cases}))
        assert "失败清单" in out.content       # 原有的失败提示保留
        assert "规范提示" in out.content       # warning 提示共存

    def test_clean_batch_returns_original(self):
        case = _valid_case()
        case.update({"case_type": "functional", "priority": "high", "remarks": "FP-001"})
        case["test_case_steps"].append({"step": "b", "result": "c"})
        result = self._ok_msg({"success": True,
                               "data": {"total": 1, "succeeded": 1, "failed": 0, "results": []}})
        out = _postprocess(result, self._req("batch_create_test_cases_tool",
                                             {"test_cases": [case]}))
        assert out.content == result.content  # 无提示时原样返回

    def test_error_result_not_touched(self):
        result = ToolMessage(content="boom", tool_call_id="call-1",
                             name="batch_create_test_cases_tool", status="error")
        out = _postprocess(result, self._req("batch_create_test_cases_tool",
                                             {"test_cases": [_valid_case()]}))
        assert out.content == "boom"


class TestWrapToolCall:
    """中间件类级接线验证：wrap_tool_call 全链路（precheck → handler → postprocess）。"""

    def _req(self, name: str, args: dict):
        return SimpleNamespace(tool_call={"name": name, "args": args, "id": "call-1"})

    def _ok_handler(self, request):
        return ToolMessage(content='{"success": true, "data": {"total": 1, "succeeded": 1, "failed": 0}}',
                           tool_call_id="call-1",
                           name=request.tool_call["name"])

    def test_error_violation_blocks_before_handler(self):
        """error 级违规：handler 不执行，直接返回拦截消息。"""
        case = _valid_case()
        case["test_case_steps"] = [{"step": "登录", "result": "成功"}]  # 模糊词
        called = []
        out = CaseQualityGateMiddleware().wrap_tool_call(
            self._req("create_test_case_tool", case),
            lambda req: called.append(req) or self._ok_handler(req),
        )
        assert not called  # handler 未被调用
        assert out.status == "error"
        assert "质量校验未通过" in out.content

    def test_clean_call_passes_with_hygiene_note(self):
        """规范问题（缺 case_type/priority/remarks）：放行但结果尾部追加提示。"""
        out = CaseQualityGateMiddleware().wrap_tool_call(
            self._req("create_test_case_tool", _valid_case()),
            self._ok_handler,
        )
        assert out.status != "error"
        assert '"success": true' in out.content
        assert "规范提示" in out.content  # warning 通道已接线


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
