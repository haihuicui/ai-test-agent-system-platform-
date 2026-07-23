"""测试用例导出通用工具函数。

抽离自 excel_tools.py，供 Excel、CSV、JSON、Markdown 等多种导出格式复用，
避免各格式生成器重复实现字段提取、步骤拍平、枚举本地化等逻辑。
"""

from typing import Any

# 用例类型英文枚举 -> 中文标签（与 app/schemas/enums.py: TestCaseType 保持一致）
_CASE_TYPE_LABELS = {
    "acceptance": "验收测试",
    "accessibility": "可访问性测试",
    "compatibility": "兼容性测试",
    "destructive": "破坏性测试",
    "functional": "功能测试",
    "other": "其他类型",
    "performance": "性能测试",
    "regression": "回归测试",
    "security": "安全测试",
    "smoke_sanity": "冒烟和健全性测试",
    "usability": "可用性测试",
}

# 优先级英文枚举 -> P0/P1/P2/P3 标签
_PRIORITY_LABELS = {
    "critical": "P0",
    "high": "P1",
    "medium": "P2",
    "low": "P3",
}

# 标准导出表头（与 Excel 导出保持一致，CSV / Markdown 直接复用）
EXPORT_HEADERS = [
    "用例编号",
    "用例标题",
    "所属模块",
    "用例类型",
    "优先级",
    "前置条件",
    "测试步骤",
    "测试数据",
    "预期结果",
    "备注",
]


def localize_case_type(value: Any) -> Any:
    """把英文用例类型枚举值映射为中文标签；已是中文或未知值则原样返回。"""
    if isinstance(value, str):
        return _CASE_TYPE_LABELS.get(value.strip().lower(), value)
    return value


def localize_priority(value: Any) -> Any:
    """把英文优先级枚举值映射为 P0/P1/P2/P3 标签；P0/P1 等或未知值则原样返回。"""
    if isinstance(value, str):
        return _PRIORITY_LABELS.get(value.strip().lower(), value)
    return value


def flatten_steps(steps: list[Any] | str | None) -> str:
    """将步骤列表转换为带序号的文本。

    兼容多种 LLM 产出格式：
      - agent.py 系统提示中的标准格式：
        [{"step": "输入账号", "result": "预期结果"}, ...]
      - output-formatter Skill 中的格式：
        [{"seq": 1, "action": "...", "target": "...", "data": "..."}]
      - 字符串列表：["输入账号", "点击登录"]
      - 单个字符串："1. 输入账号\\n2. 点击登录"
    """
    if not steps:
        return ""
    if isinstance(steps, str):
        return steps
    lines = []
    for step in steps:
        seq = len(lines) + 1
        if isinstance(step, dict):
            # 优先使用 agent.py 系统提示中的 "step" 字段作为操作描述
            action = step.get("step") or step.get("action") or step.get("操作描述") or step.get("description", "")
            target = step.get("target", step.get("操作对象", ""))
            data = step.get("data", "")
            seq = step.get("seq", seq)
            line = f"{seq}. {action}"
            if target:
                line += f" [{target}]"
            if data:
                line += f"（数据：{data}）"
        else:
            # 字符串或其他标量，直接转文本
            line = f"{seq}. {step}"
        lines.append(line)
    return "\n".join(lines)


def extract_expected_results_from_steps(steps: list[Any] | str | None) -> str:
    """当用例没有独立的 expected_results 字段时，从步骤的 result 字段聚合预期结果。"""
    if not steps or isinstance(steps, str):
        return ""
    lines = []
    for idx, step in enumerate(steps, start=1):
        if isinstance(step, dict):
            result = step.get("result", step.get("expected_result", step.get("预期结果", "")))
            if result:
                lines.append(f"{idx}. {result}")
    return "\n".join(lines)


def flatten_test_data(test_data: dict[str, Any] | str | None) -> str:
    """将测试数据转换为文本。"""
    if not test_data:
        return ""
    if isinstance(test_data, str):
        return test_data
    lines = [f"{k}: {v}" for k, v in test_data.items()]
    return "\n".join(lines)


def flatten_expected_results(expected_results: list[str] | str | None) -> str:
    """将预期结果列表转换为文本。"""
    if not expected_results:
        return ""
    if isinstance(expected_results, str):
        return expected_results
    lines = []
    for idx, result in enumerate(expected_results, start=1):
        lines.append(f"{idx}. {result}")
    return "\n".join(lines)


def flatten_preconditions(preconditions: list[str] | str | None) -> str:
    """将前置条件列表转换为文本。"""
    if not preconditions:
        return ""
    if isinstance(preconditions, str):
        return preconditions
    lines = []
    for idx, cond in enumerate(preconditions, start=1):
        lines.append(f"{idx}. {cond}")
    return "\n".join(lines)


def extract_field(case: dict[str, Any], *keys: str, default: Any = "") -> Any:
    """从字典中按多个候选键提取值。

    跳过缺失、None 及空字符串的候选键，继续尝试下一个别名，
    避免某个键存在但值为空时直接返回空、覆盖掉后面的有效别名。
    """
    for key in keys:
        if key in case:
            value = case[key]
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value
    return default


def case_key(case: dict[str, Any]) -> Any:
    """提取用例的去重标识：优先用例编号，其次标题/名称；都没有则返回 None（不去重）。"""
    return extract_field(
        case,
        "id", "用例编号", "identifier", "case_id", "编号",
        "title", "用例标题", "name", "标题", "用例名称",
        default=None,
    )
