"""功能点覆盖对照工具。

把 Phase 4 质量评审中「读 feature_matrix.jsonl + 扫全部用例 JSONL + 人工逐功能点
对照」这一高 token、易遗漏的步骤变成确定性计算：

- 读取 Phase 1 保存的结构化功能矩阵；
- 扫描（或按传入清单读取）已生成的用例 JSONL 文件；
- 通过「显式 FP 编号引用」+「同模块文本重叠」两级匹配，逐功能点输出覆盖状态；
- 产出可直接粘贴进评审报告的 Markdown 对照表和未覆盖 P0 清单。

匹配规则（确定性、可解释）：
1. explicit：用例的任意文本字段中出现 `FP-NNN` 编号（模型在 remarks / 名称中
   标注关联功能点），视为确定覆盖；
2. fuzzy：同模块下，功能点名称的字符二元组与用例文本重叠率 ≥ 阈值，或任一
   测试要点完整出现在用例文本中，视为疑似覆盖（报告中会标注，供人工确认）。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from app.agents.tools.testcase.excel_tools import (
    _parse_json_objects,
    _resolve_input_path,
)
from app.agents.tools.testcase.feature_matrix_tools import load_feature_matrix
from app.config.settings import settings

logger = logging.getLogger(__name__)

_WORKSPACE_ROOT = Path(settings.testcase_workspace_root).resolve()

# 自动扫描时排除的目录（陈旧工具结果卸载区不是用例数据）
_EXCLUDED_DIR_NAMES = {"large_tool_results"}

_FP_ID_RE = re.compile(r"FP-\d+", re.IGNORECASE)

# fuzzy 匹配的最低重叠率：功能点名称的字符二元组命中率
_DEFAULT_FUZZY_THRESHOLD = 0.5


def _looks_like_case(obj: Any) -> bool:
    """判断一个 JSON 对象是否像测试用例（区别于功能矩阵记录等其他 JSONL）。"""
    if not isinstance(obj, dict):
        return False
    if obj.get("case_number") or obj.get("case_id"):
        return True
    name = obj.get("name") or obj.get("title") or obj.get("用例名称")
    steps = obj.get("test_case_steps") or obj.get("steps")
    return bool(name and steps)


def _case_text(case: dict[str, Any]) -> str:
    """把用例的所有文本字段拼成一段可检索文本。"""
    parts: list[str] = []
    for key in (
        "name", "title", "case_number", "case_id", "module",
        "description", "remarks", "preconditions", "expected_result",
    ):
        value = case.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(v) for v in value)
    steps = case.get("test_case_steps") or case.get("steps") or []
    if isinstance(steps, list):
        for step in steps:
            if isinstance(step, dict):
                parts.extend(str(v) for v in step.values())
            else:
                parts.append(str(step))
    test_data = case.get("test_data")
    if isinstance(test_data, dict):
        parts.append(json.dumps(test_data, ensure_ascii=False))
    elif isinstance(test_data, str):
        parts.append(test_data)
    return "\n".join(parts)


def _bigrams(text: str) -> set[str]:
    """提取字符二元组集合（对中文友好的轻量相似度度量）。"""
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 2:
        return {compact} if compact else set()
    return {compact[i : i + 2] for i in range(len(compact) - 1)}


def _case_number_of(case: dict[str, Any]) -> str:
    return str(case.get("case_number") or case.get("case_id") or case.get("name") or "?")


def _load_cases(case_files: list[str] | None) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """加载用例数据。

    Returns:
        (cases, source_files, warnings)
    """
    cases: list[dict[str, Any]] = []
    sources: list[str] = []
    warnings: list[str] = []

    if case_files:
        paths = []
        for f in case_files:
            try:
                paths.append(_resolve_input_path(f))
            except Exception as e:
                warnings.append(f"用例文件路径无效：{f}（{e}）")
    else:
        paths = [
            p
            for p in _WORKSPACE_ROOT.rglob("*.jsonl")
            if not _EXCLUDED_DIR_NAMES.intersection(p.parts)
            and p.name != "feature_matrix.jsonl"
        ]

    for path in paths:
        if not path.is_file():
            warnings.append(f"用例文件不存在：{path}")
            continue
        try:
            text = path.read_text(encoding="utf-8").strip()
        except Exception as e:
            warnings.append(f"读取用例文件失败：{path}（{e}）")
            continue
        if not text:
            continue
        file_cases = [
            obj for obj in _parse_json_objects(text, str(path)) if _looks_like_case(obj)
        ]
        if file_cases:
            cases.extend(file_cases)
            sources.append(str(path))

    return cases, sources, warnings


def compute_coverage(
    features: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    fuzzy_threshold: float = _DEFAULT_FUZZY_THRESHOLD,
) -> list[dict[str, Any]]:
    """逐功能点计算覆盖状态（纯函数，供工具和测试复用）。

    Returns:
        每行 {id, module, feature, priority, covered, match_type, case_numbers}
        match_type: "explicit" | "fuzzy" | None
    """
    case_entries = [
        {
            "number": _case_number_of(case),
            "module": str(case.get("module") or "").strip(),
            "text": _case_text(case),
            "fp_refs": {m.upper() for m in _FP_ID_RE.findall(_case_text(case))},
        }
        for case in cases
    ]

    rows: list[dict[str, Any]] = []
    for fp in features:
        fp_id = str(fp.get("id") or "").strip().upper()
        fp_module = str(fp.get("module") or "").strip()
        feature_name = str(fp.get("feature") or "").strip()
        test_points = [str(p) for p in (fp.get("test_points") or []) if str(p).strip()]

        explicit_hits = [c["number"] for c in case_entries if fp_id and fp_id in c["fp_refs"]]

        fuzzy_hits: list[str] = []
        if not explicit_hits:
            feature_grams = _bigrams(feature_name)
            for c in case_entries:
                # 模块约束：用例声明了模块时必须与功能点同模块，避免跨模块误匹配
                if c["module"] and fp_module and c["module"] != fp_module:
                    continue
                if any(tp in c["text"] for tp in test_points):
                    fuzzy_hits.append(c["number"])
                    continue
                if feature_grams:
                    overlap = len(feature_grams & _bigrams(c["text"])) / len(feature_grams)
                    if overlap >= fuzzy_threshold:
                        fuzzy_hits.append(c["number"])

        match_type = "explicit" if explicit_hits else ("fuzzy" if fuzzy_hits else None)
        rows.append(
            {
                "id": fp.get("id"),
                "module": fp_module,
                "feature": feature_name,
                "priority": str(fp.get("priority") or "").strip(),
                "covered": match_type is not None,
                "match_type": match_type,
                "case_numbers": explicit_hits or fuzzy_hits,
            }
        )
    return rows


def _build_markdown_table(rows: list[dict[str, Any]]) -> str:
    """生成可直接粘贴进质量评审报告的覆盖对照表。"""
    lines = [
        "| 功能点 ID | 模块 | 功能点 | 优先级 | 是否已覆盖 | 对应用例编号 | 备注 |",
        "|----------|------|--------|--------|----------|------------|------|",
    ]
    for row in rows:
        if row["covered"]:
            covered = "✅ 已覆盖" if row["match_type"] == "explicit" else "🟡 疑似覆盖"
            cases = ", ".join(row["case_numbers"][:5])
            note = "" if row["match_type"] == "explicit" else "文本相似匹配，需人工确认"
        else:
            covered = "❌ 未覆盖"
            cases = "-"
            note = "🔴 严重问题：P0 未覆盖" if row["priority"] == "P0" else "需补充用例"
        lines.append(
            f"| {row['id']} | {row['module']} | {row['feature']} | {row['priority']}"
            f" | {covered} | {cases} | {note} |"
        )
    return "\n".join(lines)


@tool
async def compute_coverage_report(
    project_identifier: str = "",
    case_files: list[str] | None = None,
    matrix_file: str = "feature_matrix.jsonl",
) -> dict[str, Any]:
    """确定性计算功能矩阵与已生成用例的覆盖对照报告。

    在 Phase 4 质量评审时调用，替代「手动读取 feature_matrix.jsonl 和全部用例
    JSONL 再逐条对照」的做法。返回逐功能点覆盖状态、覆盖率、未覆盖 P0 清单，
    以及可直接粘贴进评审报告的 Markdown 对照表。

    匹配规则：
    - explicit：用例文本中出现 FP-NNN 编号（确定覆盖）；
    - fuzzy：同模块下功能点名称/测试要点与用例文本高度重叠（疑似覆盖，需人工确认）。

    Args:
        project_identifier: 项目标识符（与 save_feature_matrix_tool 传入的一致），
            用于定位项目隔离目录下的功能矩阵文件。
        case_files: 用例 JSONL 文件清单。不传时自动扫描工作区内全部用例文件
            （排除功能矩阵与系统目录）。
        matrix_file: 功能矩阵文件名，默认 feature_matrix.jsonl。

    Returns:
        {
          "success": bool,
          "coverage_rate": float,        # 0-100，explicit + fuzzy 均计入
          "total_features": int,
          "covered": int,
          "uncovered": int,
          "uncovered_p0": ["FP-001", ...],
          "rows": [逐功能点对照行],
          "markdown_table": "可直接粘贴进报告的对照表",
          "case_files_used": [...],
          "warnings": [...],
          "error": str                   # 仅失败时
        }
    """
    matrix = load_feature_matrix(
        project_identifier=project_identifier, output_file=matrix_file
    )
    if not matrix.get("success"):
        return {
            "success": False,
            "error": matrix.get("error", "功能矩阵读取失败"),
            "message": (
                "无法计算覆盖对照：功能矩阵不可用。"
                "若 Phase 1 未保存矩阵，请在评审报告中标注 "
                "'[无结构化矩阵] 覆盖度基于对话历史判断，可能存在遗漏'。"
            ),
        }

    cases, sources, warnings = _load_cases(case_files)
    if not cases:
        return {
            "success": False,
            "error": "未找到任何用例数据",
            "message": (
                "扫描工作区未找到用例 JSONL 文件。请确认 Phase 3 已将用例写入文件，"
                "或通过 case_files 参数显式传入文件清单。"
            ),
            "warnings": warnings,
        }

    rows = compute_coverage(matrix["features"], cases)
    covered = sum(1 for r in rows if r["covered"])
    total = len(rows)
    uncovered_p0 = [r["id"] for r in rows if not r["covered"] and r["priority"] == "P0"]

    return {
        "success": True,
        "matrix_file": matrix["file"],
        "total_features": total,
        "total_cases": len(cases),
        "covered": covered,
        "uncovered": total - covered,
        "coverage_rate": round(covered / total * 100, 1) if total else 0.0,
        "uncovered_features": [r["id"] for r in rows if not r["covered"]],
        "uncovered_p0": uncovered_p0,
        "rows": rows,
        "markdown_table": _build_markdown_table(rows),
        "case_files_used": sources,
        "warnings": warnings,
        "message": (
            f"覆盖对照完成：{total} 个功能点中 {covered} 个已覆盖"
            f"（{round(covered / total * 100, 1) if total else 0}%），"
            f"未覆盖 P0：{len(uncovered_p0)} 个。"
            "请将 markdown_table 粘贴到质量评审报告的「覆盖度分析」章节，"
            "🟡 疑似覆盖项需人工确认，❌ 未覆盖项（尤其 P0）需补充用例或在报告中说明。"
        ),
    }
