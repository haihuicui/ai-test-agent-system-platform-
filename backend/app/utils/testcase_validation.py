"""测试用例字段的确定性校验规则。

把质量红线的校验逻辑从 ``case_quality_middleware.py`` 中剥离出来，
避免工具层在导入 middleware 时触发 agent 层的循环导入。
"""

from __future__ import annotations

import re
from typing import Any

# 预期结果模糊词：整条预期结果去除引号/标点/空白后，完全由这些词构成时判为违规。
# 注意 "提示'登录成功'" 这类带具体文案的结果不会被误判（剥离后不在集合内）。
_FUZZY_RESULT_WORDS = {
    "正确", "成功", "正常", "通过", "无错误", "无异常", "符合预期", "符合要求",
    "正常使用", "显示正确", "操作成功", "返回正确", "结果正确", "提示正确",
    "功能正常", "数据正确", "有效", "正常显示", "正常返回", "运行正常",
}

# 测试数据占位词：test_data 的字符串值包含这些词时判为占位
_PLACEHOLDER_DATA_WORDS = (
    "有效数据", "合理值", "任意值", "测试数据", "待补充", "暂无", "待定",
    "xxx", "XXX", "...", "……", "N/A", "n/a", "TBD", "tbd",
)

# TC-[项目]-[模块]-[序号]，模块允许中文及内部连字符，不允许空段或连续连字符，序号至少 2 位
_CASE_NUMBER_PATTERN = re.compile(
    r"^TC-[A-Za-z0-9一-鿿]+-[A-Za-z0-9一-鿿]+(?:-[A-Za-z0-9一-鿿]+)*-\d{2,}$"
)

# 用于剥离预期结果首尾的引号与标点，再做模糊词精确匹配
_STRIP_CHARS = " \t\n\"'“”‘’，,。.!！?？:：;；~～。"


def _is_fuzzy_result(result: str) -> bool:
    """判断预期结果是否由纯模糊词构成。"""
    stripped = result.strip(_STRIP_CHARS)
    if not stripped:
        return True
    return stripped in _FUZZY_RESULT_WORDS


def _has_placeholder_data(test_data: dict[str, Any]) -> str | None:
    """返回首个命中占位词的字段名；无则返回 None。"""
    for key, value in test_data.items():
        if isinstance(value, str) and any(p in value for p in _PLACEHOLDER_DATA_WORDS):
            return key
    return None


def _validate_case(case: dict[str, Any]) -> list[str]:
    """校验单条用例参数，返回违规项描述列表（空列表表示通过）。"""
    violations: list[str] = []

    if not isinstance(case, dict):
        return ["用例参数不是有效对象"]

    # module 必填
    module = case.get("module")
    if not (isinstance(module, str) and module.strip()):
        violations.append("缺少所属模块 module（必填）")

    # case_number 必填且格式正确（兼容 case_id 别名）
    case_number = case.get("case_number") or case.get("case_id")
    if not case_number:
        violations.append("缺少用例编号 case_number（必填，格式 TC-[项目]-[模块]-[序号]）")
    elif not _CASE_NUMBER_PATTERN.match(str(case_number)):
        violations.append(
            f"用例编号 `{case_number}` 格式不符合 TC-[项目]-[模块]-[序号]（如 TC-PROJ-LOGIN-001）"
        )

    # test_data 必填、非空、无占位词
    test_data = case.get("test_data")
    if not test_data or (isinstance(test_data, dict) and not test_data):
        violations.append("缺少具体测试数据 test_data（禁止空对象，必须给出具体数据值）")
    elif isinstance(test_data, dict):
        placeholder_key = _has_placeholder_data(test_data)
        if placeholder_key is not None:
            violations.append(
                f"测试数据字段 `{placeholder_key}` 使用了占位描述（如“有效数据”），必须给出具体数据值"
            )

    # 普通用例（非 BDD）：步骤必填，且预期结果禁止模糊词
    template = case.get("template", "test_case")
    if template != "test_case_bdd":
        steps = case.get("test_case_steps")
        if not steps or not isinstance(steps, list):
            violations.append("缺少测试步骤 test_case_steps（普通测试用例必填）")
        else:
            for i, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                result = step.get("result")
                if result is None or _is_fuzzy_result(str(result)):
                    violations.append(
                        f"第 {i + 1} 步预期结果 `{result}` 不可客观判定"
                        "（禁止“正确/成功/正常”等模糊词，需写明可验证的具体表现）"
                    )

    return violations
