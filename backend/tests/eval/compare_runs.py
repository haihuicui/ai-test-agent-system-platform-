"""模型 A/B 对比评估：同一需求两版用例产出的质量对比报告。

适用场景：更换生成模型后，判断新模型在测试用例生成上是变好还是变差。
对照原则：同一需求、同一 prompt、同一 Agent 流程，唯一变量是模型——
差异才能归因到模型本身。

三维评估（全部复用现有设施，相对对比对裁判绝对精度要求低于门禁）：
1. lint 规范分（零 token）：error/warning 各规则命中数对比
2. 产出语义裁判（v1 裁判）：可断言性 + 异常与安全覆盖（聚合样本评分）
3. 需求覆盖裁判（FP 级 G-Eval）：同矩阵逐 FP 两版分数对比

用法（cwd = backend）：
    ./.venv/Scripts/python.exe -m tests.eval.compare_runs \
        --a-name "deepseek-v4-flash" --a-path workspace/testcase/PR-1 \
        --b-name "new-model"         --b-path workspace/testcase/PR-1/<new_thread_id> \
        --matrix workspace/testcase/PR-1/feature_matrix.jsonl
    # --a-exclude-threads 0345ddf1,...  可把 B 组会话目录从 A 组存量里排除
    # 加 --skip-judges 只跑零 token 的 lint 对比（快速预览）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from deepeval.test_case import LLMTestCase

from app.agents.tools.testcase.coverage_tools import _looks_like_case
from tests.eval.coverage_audit import SKIP_PATTERNS, load_matrix
from tests.eval.judge_coverage import (
    matrix_req_themes,
    relevant_cases,
    slim_case,
)
from tests.eval.lint_cases import lint
from tests.eval.metrics import (
    assertability_metric,
    coverage_faithfulness_metric,
    exception_coverage_metric,
)

# 聚合样本的用例数上限（控制裁判 prompt 体积；两版同规则截取保证公平）
MAX_SAMPLE_CASES = 40


def load_cases(path: Path, exclude_threads: set[str]) -> tuple[list[dict], int]:
    """读目录下全部用例；返回 (cases, 文件数)。exclude_threads 排除会话子目录。"""
    cases: list[dict] = []
    n_files = 0
    if path.is_file():
        parents_iter = [path]
    else:
        parents_iter = sorted(path.rglob("*.jsonl"))
    for p in parents_iter:
        if any(s in p.name.lower() for s in SKIP_PATTERNS):
            continue
        if "large_tool_results" in p.parts:
            continue
        if exclude_threads and any(seg in exclude_threads for seg in p.parts):
            continue
        file_cases = 0
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if _looks_like_case(obj):
                cases.append(obj)
                file_cases += 1
        n_files += bool(file_cases)
    return cases, n_files


def run_lint_compare(a_path: Path, b_path: Path, a_exclude: tuple[str, ...]) -> dict:
    from collections import Counter
    out = {}
    for key, path, excl in (("A", a_path, a_exclude), ("B", b_path, ())):
        issues = lint(path, exclude_names=excl)
        out[key] = dict(Counter(f"{i['level']}|{i['rule']}" for i in issues))
    return out


def judge_output_quality(name: str, cases: list[dict]) -> dict:
    """产出语义两裁判：聚合样本（按 case_number 排序取前 N，两版同规则）。"""
    sample = sorted(cases, key=lambda c: str(c.get("case_number") or ""))[:MAX_SAMPLE_CASES]
    tc = LLMTestCase(
        input=f"[模型 {name} 对同一需求的用例产出，共 {len(sample)} 条参评]",
        actual_output=json.dumps(sample, ensure_ascii=False),
    )
    row = {"n_cases_judged": len(sample)}
    for key, metric in (("assertability", assertability_metric),
                        ("exception_coverage", exception_coverage_metric)):
        try:
            metric.measure(tc)
            row[key] = {"score": metric.score,
                        "pass": bool(metric.score is not None and metric.score >= metric.threshold),
                        "reason": metric.reason}
        except Exception as exc:  # noqa: BLE001
            row[key] = {"error": f"{type(exc).__name__}: {exc}"}
    return row


def judge_coverage_compare(matrix: list[dict], a_cases: list[dict], b_cases: list[dict]) -> list[dict]:
    """FP 级覆盖对比：同一矩阵逐 FP 两版评分（复用 judge_coverage 的组装逻辑）。"""
    themes = matrix_req_themes(matrix)
    rows = []
    for fp in matrix:
        row = {"fp_id": fp.get("id"), "feature": fp.get("feature"),
               "priority": str(fp.get("priority") or "")}
        for key, cases in (("A", a_cases), ("B", b_cases)):
            relevant = relevant_cases(fp, cases, themes)
            if not relevant:
                row[key] = {"score": 0.0, "n_cases": 0, "note": "零相关用例（直接记 0）"}
                continue
            tc = LLMTestCase(
                input=json.dumps({
                    "功能点": fp.get("feature"), "模块": fp.get("module"),
                    "优先级": fp.get("priority"), "test_points": fp.get("test_points"),
                }, ensure_ascii=False),
                actual_output=json.dumps([slim_case(c) for c in relevant], ensure_ascii=False),
            )
            last_exc = None
            for attempt in (1, 2):
                try:
                    coverage_faithfulness_metric.measure(tc)
                    row[key] = {"score": coverage_faithfulness_metric.score,
                                "n_cases": len(relevant),
                                "reason": coverage_faithfulness_metric.reason}
                    break
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if attempt == 1:
                        time.sleep(2)
            else:
                row[key] = {"error": f"{type(last_exc).__name__}: {last_exc}",
                            "n_cases": len(relevant)}
        rows.append(row)
        a_s = row["A"].get("score", "ERR")
        b_s = row["B"].get("score", "ERR")
        a_t = f"{a_s:.2f}" if isinstance(a_s, float) else a_s
        b_t = f"{b_s:.2f}" if isinstance(b_s, float) else b_s
        print(f"  {row['fp_id']} [{row['priority']}] {str(row['feature'])[:22]}：A={a_t} / B={b_t}")
    return rows


def render_lint(lint_cmp: dict, a_name: str, b_name: str) -> list[str]:
    rules = sorted(set(lint_cmp["A"]) | set(lint_cmp["B"]))
    lines = [f"| 规则 | {a_name} | {b_name} | 差值 |", "|---|---|---|---|"]
    for r in rules:
        a_n, b_n = lint_cmp["A"].get(r, 0), lint_cmp["B"].get(r, 0)
        diff = b_n - a_n
        mark = f"{diff:+d}" + (" 🔺" if diff > 0 else (" ✅" if diff < 0 else ""))
        lines.append(f"| {r.replace('|', '/')} | {a_n} | {b_n} | {mark} |")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="模型 A/B 对比评估（同需求两版产出）")
    parser.add_argument("--a-name", required=True)
    parser.add_argument("--a-path", type=Path, required=True)
    parser.add_argument("--b-name", required=True)
    parser.add_argument("--b-path", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, default=None,
                        help="功能矩阵（提供则跑覆盖裁判对比）")
    parser.add_argument("--a-exclude-threads", default="",
                        help="A 组要排除的会话目录（如 B 组会话落在 A 目录下时），逗号分隔")
    parser.add_argument("--skip-judges", action="store_true", help="只跑 lint（零 token 快速预览）")
    parser.add_argument("--out", type=Path, default=None, help="报告输出 md 路径")
    args = parser.parse_args()

    exclude = {s.strip() for s in args.a_exclude_threads.split(",") if s.strip()}
    a_cases, a_files = load_cases(args.a_path, exclude)
    b_cases, b_files = load_cases(args.b_path, set())
    print(f"A 组（{args.a_name}）：{a_files} 文件 / {len(a_cases)} 条用例")
    print(f"B 组（{args.b_name}）：{b_files} 文件 / {len(b_cases)} 条用例")
    if not a_cases or not b_cases:
        sys.exit("某一组没用例，检查路径")

    report = [f"# 模型对比报告：{args.a_name} vs {args.b_name}\n",
              f"- A 组：{a_files} 文件 / {len(a_cases)} 条（`{args.a_path}`）",
              f"- B 组：{b_files} 文件 / {len(b_cases)} 条（`{args.b_path}`）\n"]

    print("\n[1/3] lint 规范对比（零 token）")
    lint_cmp = run_lint_compare(args.a_path, args.b_path, tuple(exclude))
    report.append("## 1. 规范分（lint）\n")
    report.extend(render_lint(lint_cmp, args.a_name, args.b_name))

    if not args.skip_judges:
        print("\n[2/3] 产出语义裁判（可断言性 / 异常覆盖）")
        quality = {}
        for key, name, cases in (("A", args.a_name, a_cases), ("B", args.b_name, b_cases)):
            quality[key] = judge_output_quality(name, cases)
            for dim in ("assertability", "exception_coverage"):
                cell = quality[key][dim]
                mark = f"{cell['score']:.2f}" if "score" in cell else "ERR"
                print(f"  {key}（{name}）{dim}: {mark}")
        report.append("\n## 2. 产出语义裁判\n")
        report.append(f"| 维度 | {args.a_name} | {args.b_name} |\n|---|---|---|")
        for dim, zh in (("assertability", "可断言性（阈值 0.8）"),
                        ("exception_coverage", "异常与安全覆盖（阈值 0.7）")):
            a_c, b_c = quality["A"][dim], quality["B"][dim]
            a_t = f"{a_c['score']:.2f}{'✓' if a_c.get('pass') else '✗'}" if "score" in a_c else "ERR"
            b_t = f"{b_c['score']:.2f}{'✓' if b_c.get('pass') else '✗'}" if "score" in b_c else "ERR"
            report.append(f"| {zh} | {a_t} | {b_t} |")
        report.append(f"\n> 参评用例：A {quality['A']['n_cases_judged']} 条 / "
                      f"B {quality['B']['n_cases_judged']} 条（按编号排序取前 {MAX_SAMPLE_CASES}）")

        if args.matrix and args.matrix.exists():
            print("\n[3/3] 需求覆盖裁判（FP 级对比）")
            matrix = load_matrix(args.matrix)
            cov_rows = judge_coverage_compare(matrix, a_cases, b_cases)
            report.append("\n## 3. 需求覆盖裁判（FP 级）\n")
            report.append(f"| FP | 优先级 | 功能点 | {args.a_name} | {args.b_name} |\n|---|---|---|---|---|")
            for r in cov_rows:
                def fmt(cell):
                    if "error" in cell:
                        return "ERR"
                    return f"{cell['score']:.2f}（{cell['n_cases']}例）"
                report.append(f"| {r['fp_id']} | {r['priority']} | {r['feature']} "
                              f"| {fmt(r['A'])} | {fmt(r['B'])} |")
        else:
            print("\n[3/3] 跳过覆盖裁判（未提供 --matrix）")

    text = "\n".join(report)
    out = args.out or Path(__file__).parent / "dataset" / "model_compare_report.md"
    out.write_text(text + "\n", encoding="utf-8")
    print(f"\n报告已写：{out}")


if __name__ == "__main__":
    main()
