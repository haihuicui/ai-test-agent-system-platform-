"""功能点覆盖漏测审计（离线版）。

复用运行时 compute_coverage 的确定性匹配（显式 FP 引用 + 同模块文本重叠），
但视角不同：运行时工具服务单次生成的 Phase 4 评审（本次用例 × 矩阵），
本工具做**存量全景审计**——整个项目的全部历史用例 × 项目矩阵，回答：

- 项目级覆盖率多少？哪些功能点至今零覆盖（漏测清单）？
- P0 未覆盖有几个？（最致命的缺口）
- 疑似覆盖（fuzzy）占比多少？（需人工确认的工作量）
- 哪些用例文件从未声明任何 FP 引用？（覆盖声明缺失的文件）

与 lint_cases.py 的分工：lint 查单条用例的规范，本工具查项目级的需求遗漏。

用法（cwd = backend）：
    ./.venv/Scripts/python.exe -m tests.eval.coverage_audit              # 全项目审计
    ./.venv/Scripts/python.exe -m tests.eval.coverage_audit --project PR-1
    ./.venv/Scripts/python.exe -m tests.eval.coverage_audit --json       # 机器可读（接 CI）
退出码：存在 P0 未覆盖 = 1，否则 0。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from app.agents.tools.testcase.coverage_tools import (
    _FP_ID_RE,
    _case_text,
    _looks_like_case,
    compute_coverage,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = BACKEND_ROOT / "workspace" / "testcase"

# 与 harvest/lint 同一口径：非用例文件不扫
SKIP_PATTERNS = ("feature_matrix", "expected_result", "manifest", "conversation")


def iter_project_cases(project_dir: Path):
    """产出 (file_name, case_dict)：递归扫项目目录全部用例，脏行/非用例跳过。"""
    for p in sorted(project_dir.rglob("*.jsonl")):
        if any(s in p.name.lower() for s in SKIP_PATTERNS):
            continue
        if "large_tool_results" in p.parts:  # 陈旧工具结果卸载区（运行时同款排除）
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if _looks_like_case(obj):
                yield p.name, obj


def load_matrix(matrix_path: Path) -> list[dict]:
    rows = []
    for line in matrix_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def audit_project(project: str) -> dict | None:
    """审计单个项目目录。无矩阵或无目录返回 None。"""
    project_dir = WORKSPACE / project
    matrix_path = project_dir / "feature_matrix.jsonl"
    if not project_dir.is_dir() or not matrix_path.exists():
        return None

    features = load_matrix(matrix_path)
    all_fp_ids = {str(fp.get("id") or "").upper() for fp in features if fp.get("id")}

    cases: list[dict] = []
    per_file: Counter = Counter()
    file_has_ref: set[str] = set()
    outside_ref_files: set[str] = set()  # 引用了矩阵外 FP（属同项目其他需求的文件）
    fp_ref_files: dict[str, set[str]] = {fid: set() for fid in all_fp_ids}
    for fname, case in iter_project_cases(project_dir):
        cases.append(case)
        per_file[fname] += 1
        refs = {m.upper() for m in _FP_ID_RE.findall(_case_text(case))}
        if refs & all_fp_ids:
            file_has_ref.add(fname)
            for r in refs & all_fp_ids:
                fp_ref_files[r].add(fname)
        if refs - all_fp_ids:
            outside_ref_files.add(fname)

    rows = compute_coverage(features, cases)

    covered = [r for r in rows if r["covered"]]
    uncovered = [r for r in rows if not r["covered"]]
    explicit = [r for r in covered if r["match_type"] == "explicit"]
    fuzzy = [r for r in covered if r["match_type"] == "fuzzy"]
    uncovered_p0 = [r for r in uncovered if r["priority"] == "P0"]
    files_without_ref = [f for f in per_file if f not in file_has_ref]
    # 无矩阵内引用的文件里，有些引用了矩阵外 FP——属多需求混杂而非无追溯习惯
    files_only_outside_ref = sorted(set(files_without_ref) & outside_ref_files)

    # 覆盖薄弱：显式引用仅落在 ≤2 个文件的 FP——声明链脆弱，
    # 个别文件的虚假声明（写了编号但内容没覆盖）即可制造"已覆盖"假象
    thin_coverage = [
        {"id": fid, "ref_files": len(files)}
        for fid, files in sorted(fp_ref_files.items())
        if 0 < len(files) <= 2
    ]

    # 陈旧矩阵信号（与运行时同精神）：零覆盖 + 模块零交集
    matrix_modules = {str(fp.get("module") or "").strip() for fp in features} - {""}
    case_modules = {str(c.get("module") or "").strip() for c in cases} - {""}
    stale_suspected = (
        not covered and bool(matrix_modules) and bool(case_modules)
        and matrix_modules.isdisjoint(case_modules)
    )

    return {
        "project": project,
        "total_features": len(rows),
        "total_cases": len(cases),
        "total_files": len(per_file),
        "coverage_rate": round(len(covered) / len(rows) * 100, 1) if rows else 0.0,
        "explicit_rate": round(len(explicit) / len(rows) * 100, 1) if rows else 0.0,
        "fuzzy_rate": round(len(fuzzy) / len(rows) * 100, 1) if rows else 0.0,
        "uncovered": [
            {"id": r["id"], "module": r["module"], "feature": r["feature"], "priority": r["priority"]}
            for r in uncovered
        ],
        "uncovered_p0": [r["id"] for r in uncovered_p0],
        "fuzzy_features": [r["id"] for r in fuzzy],
        "files_without_fp_ref": files_without_ref,
        "files_only_outside_ref": files_only_outside_ref,
        "thin_coverage": thin_coverage,
        "stale_matrix_suspected": stale_suspected,
        "rows": rows,
    }


def render_text(report: dict) -> str:
    lines = [
        f"\n===== {report['project']} 覆盖审计 =====",
        f"矩阵 {report['total_features']} FP × 用例 {report['total_cases']} 条"
        f"（{report['total_files']} 文件）",
        f"覆盖率 {report['coverage_rate']}%"
        f"（显式 {report['explicit_rate']}% / 疑似 {report['fuzzy_rate']}%）"
        "　※ 累积视角：历史全部用例合并，非单次生成质量",
    ]
    if report["stale_matrix_suspected"]:
        lines.append("⚠️ 疑似历史遗留矩阵：零覆盖且模块零交集——本报告覆盖率不可信，"
                     "矩阵可能属于同项目其他需求")
    if report["uncovered"]:
        lines.append(f"\n❌ 未覆盖功能点（{len(report['uncovered'])}）：")
        for u in report["uncovered"]:
            p0 = " 🔴P0" if u["priority"] == "P0" else ""
            lines.append(f"  {u['id']} [{u['priority']}]{p0} {u['module']} / {u['feature']}")
    else:
        lines.append("✅ 全部功能点均有覆盖")
    if report["thin_coverage"]:
        ids = ", ".join(f"{t['id']}({t['ref_files']}文件)" for t in report["thin_coverage"])
        lines.append(f"\n🟠 覆盖薄弱（显式引用仅 ≤2 个文件，声明链脆弱）：{ids}")
    if report["fuzzy_features"]:
        lines.append(f"\n🟡 疑似覆盖待人工确认（{len(report['fuzzy_features'])}）："
                     f"{', '.join(report['fuzzy_features'])}")
    if report["files_without_fp_ref"]:
        lines.append(f"\n📄 未声明任何矩阵内 FP 引用的文件（{len(report['files_without_fp_ref'])}）："
                     f"覆盖贡献不可追溯")
        for f in report["files_without_fp_ref"][:10]:
            lines.append(f"  {f}")
        if len(report["files_without_fp_ref"]) > 10:
            lines.append(f"  …等共 {len(report['files_without_fp_ref'])} 个")
        if report["files_only_outside_ref"]:
            lines.append(f"  其中 {len(report['files_only_outside_ref'])} 个引用了矩阵外 FP"
                         f"（属同项目其他需求的用例，非无追溯习惯）："
                         f"{', '.join(report['files_only_outside_ref'][:5])}"
                         + (" …" if len(report["files_only_outside_ref"]) > 5 else ""))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="功能点覆盖漏测审计（离线）")
    parser.add_argument("--project", default=None, help="只审计指定项目（默认全部有矩阵的项目）")
    parser.add_argument("--json", action="store_true", help="机器可读输出（接 CI）")
    args = parser.parse_args()

    if args.project:
        projects = [args.project]
    else:
        projects = sorted(
            p.name for p in WORKSPACE.iterdir()
            if p.is_dir() and (p / "feature_matrix.jsonl").exists()
        )
    if not projects:
        sys.exit("未找到任何带 feature_matrix.jsonl 的项目目录")

    reports = [r for r in (audit_project(p) for p in projects) if r]
    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=1))
    else:
        for r in reports:
            print(render_text(r))
        total_p0 = sum(len(r["uncovered_p0"]) for r in reports)
        print(f"\n{'=' * 40}\n总计：{len(reports)} 个项目，P0 未覆盖 {total_p0} 个"
              f"{'——存在致命缺口' if total_p0 else ''}")

    sys.exit(1 if any(r["uncovered_p0"] for r in reports) else 0)


if __name__ == "__main__":
    main()
