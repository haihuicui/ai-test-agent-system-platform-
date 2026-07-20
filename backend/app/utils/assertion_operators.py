"""断言操作符归一化工具。

前后端对比较运算符的表示存在差异：
- 执行引擎只识别短值：eq / ne / gt / lt / contains
- 历史前端/AI 可能使用长值：equals / not_equals / greater_than / less_than

本模块提供统一的归一化入口，保证入库与运行时使用的都是 canonical 短值。
"""

from typing import Any


OPERATORS = frozenset({"eq", "ne", "gt", "lt", "contains"})

OPERATOR_ALIASES = {
    # canonical values
    "eq": "eq",
    "ne": "ne",
    "gt": "gt",
    "lt": "lt",
    "contains": "contains",
    # legacy verbose aliases used by old UI / AI
    "equals": "eq",
    "not_equals": "ne",
    "greater_than": "gt",
    "less_than": "lt",
}


def normalize_operator(value: Any, default: str = "eq") -> str:
    """将操作符归一化为后端执行引擎能识别的 canonical 值。

    Args:
        value: 原始操作符值，可能是 str、None 等。
        default: 当值为空或 None 时的默认值。

    Returns:
        canonical operator，例如 "eq" / "ne" / "gt" / "lt" / "contains"。

    Raises:
        ValueError: 当操作符既不是 canonical 值也不是已知别名时。
    """
    if value is None:
        return default

    if isinstance(value, str) and value.strip() == "":
        return default

    normalized = OPERATOR_ALIASES.get(str(value).strip().lower())
    if normalized is None:
        raise ValueError(
            f"不支持的比较运算符: {value!r}，可选值: {', '.join(sorted(OPERATORS))}"
        )

    return normalized
