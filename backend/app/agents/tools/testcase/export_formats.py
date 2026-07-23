"""测试用例多格式导出字节生成器。

提供 JSON、CSV 等文本格式的字节流生成能力，与 Excel 生成器保持一致的输入约定：
接收经过 `_test_case_info_to_export_dict` 扁平化后的字典列表。
"""

import csv
import io
import json
from typing import Any

from app.agents.tools.testcase.export_common import EXPORT_HEADERS

# CSV 表头映射：英文内部键 -> 中文展示表头
# 顺序与 EXPORT_HEADERS 保持一致
_CSV_HEADER_MAPPING: list[tuple[str, str]] = [
    ("id", "用例编号"),
    ("title", "用例标题"),
    ("module", "所属模块"),
    ("type", "用例类型"),
    ("priority", "优先级"),
    ("preconditions", "前置条件"),
    ("steps", "测试步骤"),
    ("test_data", "测试数据"),
    ("expected_results", "预期结果"),
    ("remarks", "备注"),
]

# JSON 输出使用的英文键（机器可读，便于对接外部系统）
_JSON_KEYS = [key for key, _ in _CSV_HEADER_MAPPING]


def generate_test_cases_json_bytes(
    test_cases: list[dict[str, Any]],
    pretty: bool = True,
) -> bytes:
    """将测试用例列表转换为 UTF-8 JSON 字节流。

    步骤字段保持结构化对象列表（seq / action / target / data / expected_result），
    其余字段拍平为字符串，便于外部系统解析与导入。
    """
    rows = []
    for case in test_cases:
        row: dict[str, Any] = {}
        for key in _JSON_KEYS:
            value = case.get(key, "")
            # 步骤字段在 JSON 中尽量保持结构化
            if key == "steps" and isinstance(value, str) and value:
                row[key] = _parse_flat_steps(value)
            else:
                row[key] = value
        rows.append(row)

    indent = 2 if pretty else None
    text = json.dumps(rows, ensure_ascii=False, indent=indent, default=str)
    return text.encode("utf-8")


def _parse_flat_steps(text: str) -> list[dict[str, Any]]:
    """把拍平后的步骤文本还原为结构化列表（仅用于 JSON 导出）。

    兼容 flatten_steps 产出的格式：
      "1. 输入账号 [目标]（数据：xxx）\\n2. 点击登录"
    还原为 [{"seq": 1, "action": "...", "target": "...", "data": "..."}, ...]。
    非结构化或无法解析的行，action 保留原行文本。
    """
    if not text:
        return []
    parsed: list[dict[str, Any]] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # 尝试匹配 "N. action [target]（数据：data）"
        seq: Any = None
        action = line
        target = ""
        data = ""

        # 提取序号
        if ". " in line:
            head, rest = line.split(". ", 1)
            if head.isdigit():
                seq = int(head)
                action = rest

        # 提取 target：[...]
        if " [" in action and action.endswith("]"):
            action, target_part = action.rsplit(" [", 1)
            target = target_part[:-1]

        # 提取 data：（数据：...）
        if "（数据：" in action and action.endswith("）"):
            action, data_part = action.rsplit("（数据：", 1)
            data = data_part[:-1]

        parsed.append({
            "seq": seq if seq is not None else len(parsed) + 1,
            "action": action.strip(),
            "target": target,
            "data": data,
        })
    return parsed


def generate_test_cases_csv_bytes(test_cases: list[dict[str, Any]]) -> bytes:
    """将测试用例列表转换为 UTF-8 BOM CSV 字节流。

    表头使用中文，与 Excel 导出对齐；字段内部含换行、逗号、双引号时
    由 csv 模块自动加引号处理，避免 Excel/WPS 打开后列断裂。
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")

    # 中文表头
    writer.writerow([label for _, label in _CSV_HEADER_MAPPING])

    for case in test_cases:
        row = [case.get(key, "") for key, _ in _CSV_HEADER_MAPPING]
        writer.writerow(row)

    # UTF-8 + BOM，确保 Excel/WPS 双击打开时中文不乱码
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")
