"""
测试用例 Excel 导出工具

提供将测试用例导出为 Excel 文件的能力，支持企业级测试管理工具的导入格式。
"""

import json
from pathlib import Path
from typing import Any

from langchain.tools import tool
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side

from app.config.settings import settings
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWtSWGRBPT06OWM0ZDYxMTc=

# 与 agent.py 中 composite_backend 的 "/" 路由保持一致：
# Agent 在虚拟文件系统中看到的路径以 "/" 为根，实际落盘到 workspace_root。
_WORKSPACE_ROOT = Path(settings.testcase_workspace_root).resolve()

_HEADER_FILL = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
_HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)
_ALIGNMENT_WRAP = Alignment(vertical="top", wrap_text=True)
_ALIGNMENT_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

_DEFAULT_COLUMN_WIDTHS = {
    "A": 18,
    "B": 35,
    "C": 14,
    "D": 12,
    "E": 10,
    "F": 30,
    "G": 40,
    "H": 30,
    "I": 40,
    "J": 20,
}

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

# 优先级英文枚举 -> 中文标签（与 app/schemas/enums.py: Priority 保持一致）
_PRIORITY_LABELS = {
    "critical": "关键",
    "high": "高",
    "medium": "中",
    "low": "低",
}


def _localize_case_type(value: Any) -> Any:
    """把英文用例类型枚举值映射为中文标签；已是中文或未知值则原样返回。"""
    if isinstance(value, str):
        return _CASE_TYPE_LABELS.get(value.strip().lower(), value)
    return value


def _localize_priority(value: Any) -> Any:
    """把英文优先级枚举值映射为中文标签；P0/P1 等或未知值则原样返回。"""
    if isinstance(value, str):
        return _PRIORITY_LABELS.get(value.strip().lower(), value)
    return value


def _flatten_steps(steps: list[Any] | str | None) -> str:
    """将步骤列表转换为带序号的文本。

    兼容多种 LLM 产出格式：
      - 字典列表：[{"seq":1,"action":"...","target":"...","data":"..."}]
      - 字符串列表：["输入账号", "点击登录"]
      - 单个字符串："1. 输入账号\n2. 点击登录"
    """
    if not steps:
        return ""
    if isinstance(steps, str):
        return steps
    lines = []
    for step in steps:
        seq = len(lines) + 1
        if isinstance(step, dict):
            seq = step.get("seq", step.get("step", seq))
            action = step.get("action", step.get("操作描述", step.get("description", "")))
            target = step.get("target", step.get("操作对象", ""))
            data = step.get("data", "")
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


def _flatten_test_data(test_data: dict[str, Any] | str | None) -> str:
    """将测试数据转换为文本。"""
    if not test_data:
        return ""
    if isinstance(test_data, str):
        return test_data
    lines = [f"{k}: {v}" for k, v in test_data.items()]
    return "\n".join(lines)


def _flatten_expected_results(expected_results: list[str] | str | None) -> str:
    """将预期结果列表转换为文本。"""
    if not expected_results:
        return ""
    if isinstance(expected_results, str):
        return expected_results
    lines = []
    for idx, result in enumerate(expected_results, start=1):
        lines.append(f"{idx}. {result}")
    return "\n".join(lines)


def _flatten_preconditions(preconditions: list[str] | str | None) -> str:
    """将前置条件列表转换为文本。"""
    if not preconditions:
        return ""
    if isinstance(preconditions, str):
        return preconditions
    lines = []
    for idx, cond in enumerate(preconditions, start=1):
        lines.append(f"{idx}. {cond}")
    return "\n".join(lines)
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWtSWGRBPT06OWM0ZDYxMTc=


def _extract_field(case: dict[str, Any], *keys: str, default: Any = "") -> Any:
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


def _ensure_xlsx_suffix(path: Path) -> Path:
    """确保导出路径以 .xlsx 结尾，缺失时自动补全。"""
    if path.suffix.lower() != ".xlsx":
        return path.with_suffix(".xlsx")
    return path


def _to_virtual_path(real_path: Path) -> str:
    """把 workspace_root 下的真实路径反向映射为 Agent 可识别的虚拟路径。

    与 composite_backend 的虚拟文件系统一致：以 "/" 为根、使用正斜杠。
    """
    rel = real_path.resolve().relative_to(_WORKSPACE_ROOT)
    return "/" + rel.as_posix()


def _resolve_workspace_path(output_path: str | Path) -> Path:
    """将 Agent 传入的（虚拟）路径映射到真实 workspace_root 下。

    与 composite_backend 的 "/" 路由保持一致：
      - 绝对/虚拟根路径（如 "/测试用例.xlsx"）按相对 workspace_root 处理；
      - 相对路径（如 "测试用例.xlsx"）也落到 workspace_root 下；
      - 已经位于 workspace_root 内的真实绝对路径保持不变；
      - 缺少 .xlsx 后缀时自动补全。
    并禁止通过 ".." 越权写到 workspace_root 之外。
    """
    raw = Path(output_path)

    # 已经是 workspace_root 内的真实绝对路径，直接使用
    if raw.anchor:
        try:
            if raw.is_absolute() and raw.resolve().is_relative_to(_WORKSPACE_ROOT):
                return _ensure_xlsx_suffix(raw.resolve())
        except (ValueError, OSError):
            pass
        # 其余带锚点的路径（虚拟根 "/xxx"、盘符根等）剥离锚点后按相对处理
        anchor_len = len(Path(raw.anchor).parts)
        rel = Path(*raw.parts[anchor_len:]) if len(raw.parts) > anchor_len else Path()
    else:
        rel = raw

    if not rel.parts:
        raise ValueError(f"导出路径无效：{output_path}")

    resolved = (_WORKSPACE_ROOT / rel).resolve()
    if not resolved.is_relative_to(_WORKSPACE_ROOT):
        raise ValueError(
            f"导出路径越权：{output_path} 解析后超出工作目录 {_WORKSPACE_ROOT}"
        )
    return _ensure_xlsx_suffix(resolved)


def _resolve_input_path(input_path: str | Path) -> Path:
    """将 Agent 传入的（虚拟）输入文件路径映射到真实 workspace_root 下。

    与 _resolve_workspace_path 的映射规则一致（虚拟根/相对/真实绝对路径都落到
    workspace_root），但**不**强制 .xlsx 后缀，用于读取用例数据文件（.jsonl/.json）。
    同样禁止通过 ".." 越权读取 workspace_root 之外的文件。
    """
    raw = Path(input_path)

    if raw.anchor:
        try:
            if raw.is_absolute() and raw.resolve().is_relative_to(_WORKSPACE_ROOT):
                return raw.resolve()
        except (ValueError, OSError):
            pass
        anchor_len = len(Path(raw.anchor).parts)
        rel = Path(*raw.parts[anchor_len:]) if len(raw.parts) > anchor_len else Path()
    else:
        rel = raw

    if not rel.parts:
        raise ValueError(f"输入文件路径无效：{input_path}")

    resolved = (_WORKSPACE_ROOT / rel).resolve()
    if not resolved.is_relative_to(_WORKSPACE_ROOT):
        raise ValueError(
            f"输入文件路径越权：{input_path} 解析后超出工作目录 {_WORKSPACE_ROOT}"
        )
    return resolved


def _load_test_cases_from_file(input_path: str | Path) -> list[dict[str, Any]]:
    """从工作目录下的数据文件读取测试用例列表。

    支持两种格式（自动识别）：
      - JSONL：每行一个 JSON 对象（推荐，便于 Agent 分批追加写入，永不超 token 上限）
      - JSON ：整个文件是一个 JSON 数组 [ {...}, {...} ]

    分批追加写入的 JSONL 不受单次 LLM 输出长度限制，从根本上规避「用例多时截断」。
    """
    real_path = _resolve_input_path(input_path)
    if not real_path.is_file():
        raise FileNotFoundError(f"用例数据文件不存在：{input_path}")

    text = real_path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"用例数据文件为空：{input_path}")

    cases: list[dict[str, Any]] = []

    if text.lstrip().startswith("["):
        # 整文件 JSON 数组
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError(f"用例数据文件顶层不是 JSON 数组：{input_path}")
        cases = data
    else:
        # JSONL：逐行解析，跳过空行
        for line_no, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"用例数据文件第 {line_no} 行不是合法 JSON：{e}"
                ) from e

    invalid = [i for i, c in enumerate(cases) if not isinstance(c, dict)]
    if invalid:
        raise ValueError(
            f"用例数据文件存在非对象元素（下标 {invalid[:5]}...），每条用例必须是 JSON 对象。"
        )
    return cases


@tool
def export_test_cases_to_excel(
    output_path: str | Path,
    test_cases: list[dict[str, Any]] | None = None,
    input_file: str | Path | None = None,
    sheet_name: str = "测试用例",
) -> str:
    """
    将测试用例导出为 Excel 文件。

    用例来源二选一（推荐使用 input_file 以规避「用例多时数据截断」）：
      - input_file: 工作目录下的用例数据文件路径（.jsonl 或 .json）。**用例数量多时优先用此方式**：
        先用文件写入工具分批把用例追加进一个 .jsonl 文件（每行一个 JSON 对象），
        再调用本工具读取该文件导出。分批写入不受单次模型输出长度限制，永不截断。
      - test_cases: 直接内联传入的用例字典列表。仅适用于用例较少（约 < 30 条）的场景；
        用例过多会因模型单次输出 token 上限导致 JSON 被截断、数据丢失。
    两者同时提供时，input_file 优先。

    支持的测试用例字段（兼容 JSON / CSV / Markdown 中定义的格式）：
      - id / 用例编号
      - title / 用例标题
      - module / 所属模块
      - type / 用例类型
      - priority / 优先级
      - preconditions / 前置条件
      - steps / 测试步骤
      - test_data / 测试数据
      - expected_results / 预期结果
      - remarks / 备注

    Args:
        output_path: 导出文件路径。相对/虚拟根路径（如 "测试用例.xlsx" 或
            "/测试用例.xlsx"）会映射到 Agent 工作目录（workspace_root）下，
            与其他文件工具看到的虚拟文件系统保持一致。缺少 .xlsx 后缀时自动补全。
        test_cases: 测试用例字典列表，每个字典描述一条用例（用例少时使用）。
        input_file: 用例数据文件（.jsonl/.json）路径，映射规则同 output_path（用例多时推荐）。
        sheet_name: 工作表名称，默认为 "测试用例"。

    Returns:
        导出文件的虚拟路径字符串（以 "/" 为根），可直接交给其他文件工具复用。
    """
    if input_file is not None:
        test_cases = _load_test_cases_from_file(input_file)

    if not test_cases:
        raise ValueError(
            "没有可导出的测试用例：请通过 input_file 提供用例数据文件，或通过 test_cases 内联传入用例列表。"
        )

    output_path = _resolve_workspace_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWtSWGRBPT06OWM0ZDYxMTc=

    wb = Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("无法创建工作表。")
    ws.title = sheet_name

    headers = [
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
    ws.append(headers)

    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = _ALIGNMENT_CENTER
        cell.border = _BORDER
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWtSWGRBPT06OWM0ZDYxMTc=

    for case in test_cases:
        row = [
            _extract_field(case, "id", "用例编号", "identifier", "case_id", "编号"),
            _extract_field(case, "title", "用例标题", "name", "标题", "用例名称"),
            _extract_field(case, "module", "所属模块", "module_name", "功能模块", "模块"),
            _localize_case_type(_extract_field(case, "type", "用例类型", "case_type", "测试类型", "类型")),
            _localize_priority(_extract_field(case, "priority", "优先级")),
            _flatten_preconditions(_extract_field(case, "preconditions", "前置条件", "precondition", default=None)),
            _flatten_steps(_extract_field(case, "steps", "测试步骤", "test_case_steps", "test_steps", default=None)),
            _flatten_test_data(_extract_field(case, "test_data", "测试数据", "data", default=None)),
            _flatten_expected_results(_extract_field(case, "expected_results", "预期结果", "expected_result", "expected", default=None)),
            _extract_field(case, "remarks", "备注", "remark", "note"),
        ]
        ws.append(row)
        row_idx = ws.max_row
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.alignment = _ALIGNMENT_WRAP
            cell.border = _BORDER

    for col_letter, width in _DEFAULT_COLUMN_WIDTHS.items():
        ws.column_dimensions[col_letter].width = width

    ws.row_dimensions[1].height = 24
    for row_idx in range(2, ws.max_row + 1):
        ws.row_dimensions[row_idx].height = 60

    wb.save(str(output_path))
    return _to_virtual_path(output_path)
