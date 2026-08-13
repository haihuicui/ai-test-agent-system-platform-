"""需求覆盖语义裁判：FP 级覆盖完整性评分。

与 coverage_audit 的分工：
- coverage_audit（代码，零 token）：有没有用例声明覆盖这个 FP；
- 本工具（G-Eval 裁判）：相关用例的内容是否真语义覆盖了该 FP 的每个
  test_point——抓「虚假声明」（写了编号但步骤没真测）与「覆盖不到位」。

数据直接扫 workspace 项目目录（全量用例，含会话子目录）——不用 v2 回归集：
v2 是采样样本（balanced 60 文件上限），覆盖评估必须全量，漏文件会误判零覆盖。

两个防误判设计：
- 评估单位 = 单个 FP，相关用例 = 显式引用 ∪ 同模块（显式优先），
  避免「登录模块用例对编辑地点 FP 打低分」的冤案；
- REQ 主题需求级对齐：FP 编号是需求级的（各需求都从 FP-001 起编），
  同项目多需求并存时编号撞车，先按矩阵 source 的 REQ 主题过滤用例池；
- 零相关用例的 FP 直接记 0 分（不调裁判，省 token 且结论明确）。

用法（cwd = backend）：
    ./.venv/Scripts/python.exe -m tests.eval.judge_coverage --project PR-1
    ./.venv/Scripts/python.exe -m tests.eval.judge_coverage              # 全部项目
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from deepeval.test_case import LLMTestCase

from app.agents.tools.testcase.coverage_tools import _FP_ID_RE, _case_text
from tests.eval.coverage_audit import WORKSPACE, iter_project_cases, load_matrix
from tests.eval.metrics import coverage_faithfulness_metric

EVAL_DIR = Path(__file__).parent
SCORES_PATH = EVAL_DIR / "dataset" / "judge_coverage_v1.jsonl"

# 单 FP 相关用例的体积控制：显式引用优先，超量截断（裁判 max_tokens 保护）
MAX_RELEVANT_CASES = 15
# 单条用例只保留裁判判覆盖所需的字段
_CASE_FIELDS = ("case_number", "name", "case_type", "priority",
                "preconditions", "test_data", "test_case_steps", "remarks")

# REQ 主题前缀（"REQ-变更②"→"REQ-变更"、"REQ-LOGIN-001"→"REQ-LOGIN"）：
# FP 编号是需求级的（各需求都从 FP-001 起编），同项目多需求并存时编号会撞车，
# 必须先用 REQ 主题做需求级对齐，否则登录用例会被误配给地点需求的 FP-001。
_REQ_RE = re.compile(r"REQ-[一-鿿A-Za-z]+")


def _req_themes(text: str) -> set[str]:
    return {m.rstrip("0-9①②③④⑤⑥⑦⑧⑨") for m in _REQ_RE.findall(text)}


def load_projects() -> dict[str, dict]:
    """扫 workspace 全部带矩阵的项目：{project: {"matrix": [...], "cases": [...]}}。"""
    projects: dict[str, dict] = {}
    for d in sorted(WORKSPACE.iterdir()):
        if d.is_dir() and (d / "feature_matrix.jsonl").exists():
            projects[d.name] = {
                "matrix": load_matrix(d / "feature_matrix.jsonl"),
                "cases": [c for _, c in iter_project_cases(d)],
            }
    return projects


def slim_case(case: dict) -> dict:
    """只保留判覆盖所需字段，控制裁判 prompt 体积。"""
    return {k: case[k] for k in _CASE_FIELDS if k in case}


def relevant_cases(fp: dict, cases: list[dict], matrix_themes: set[str]) -> list[dict]:
    """显式引用该 FP 的用例优先，同模块用例兜底补充。

    先按 REQ 主题做需求级对齐（matrix_themes 为空时退化为不过滤）：
    跨需求用例一律不入选——FP 编号需求级撞车，宁漏勿错拉。
    """
    fp_id = str(fp.get("id") or "").strip().upper()
    fp_module = str(fp.get("module") or "").strip()
    explicit, same_module = [], []
    for c in cases:
        if not isinstance(c, dict):
            continue
        text = _case_text(c)
        if matrix_themes and not (_req_themes(text) & matrix_themes):
            continue
        refs = {m.upper() for m in _FP_ID_RE.findall(text)}
        if fp_id and fp_id in refs:
            explicit.append(c)
        elif fp_module and str(c.get("module") or "").strip() == fp_module:
            same_module.append(c)
    return (explicit + same_module)[:MAX_RELEVANT_CASES]


def matrix_req_themes(matrix: list[dict]) -> set[str]:
    """矩阵的需求主题集合（从各行 source 字段提取）。"""
    themes: set[str] = set()
    for fp in matrix:
        themes |= _req_themes(str(fp.get("source") or ""))
    return themes


def load_scored_ids() -> set[str]:
    if not SCORES_PATH.exists():
        return set()
    return {
        f"{json.loads(l)['project']}|{json.loads(l)['fp_id']}"
        for l in SCORES_PATH.read_text(encoding="utf-8").splitlines() if l.strip()
    }


def judge_fp(project: str, fp: dict, cases: list[dict], matrix_themes: set[str]) -> dict:
    """评一个 FP：返回落盘行。裁判异常落 error 不中断整批。"""
    fp_id = str(fp.get("id") or "?")
    relevant = relevant_cases(fp, cases, matrix_themes)
    row = {
        "project": project,
        "fp_id": fp_id,
        "fp_feature": fp.get("feature"),
        "fp_module": fp.get("module"),
        "priority": str(fp.get("priority") or ""),
        "n_test_points": len(fp.get("test_points") or []),
        "n_relevant_cases": len(relevant),
    }
    if not relevant:
        row.update({"score": 0.0, "pass": False,
                    "reason": "零相关用例（REQ 需求级对齐后）：无显式引用且无同模块用例"
                              "（未调裁判，直接记 0）"})
        return row

    test_case = LLMTestCase(
        input=json.dumps({
            "功能点": fp.get("feature"), "模块": fp.get("module"),
            "优先级": fp.get("priority"), "test_points": fp.get("test_points"),
        }, ensure_ascii=False),
        actual_output=json.dumps([slim_case(c) for c in relevant], ensure_ascii=False),
    )
    last_exc: Exception | None = None
    for attempt in (1, 2):  # 裁判输出偶发 invalid JSON（围栏净化边缘 case），重试一次
        try:
            coverage_faithfulness_metric.measure(test_case)
            row.update({
                "score": coverage_faithfulness_metric.score,
                "pass": bool(coverage_faithfulness_metric.score is not None
                             and coverage_faithfulness_metric.score >= coverage_faithfulness_metric.threshold),
                "reason": coverage_faithfulness_metric.reason,
            })
            return row
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt == 1:
                time.sleep(2)
    row.update({"error": f"{type(last_exc).__name__}: {last_exc}"})
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="需求覆盖语义裁判（FP 级）")
    parser.add_argument("--project", default=None, help="只评指定项目（默认全部）")
    args = parser.parse_args()

    projects = load_projects()
    if not projects:
        sys.exit(f"未找到带 feature_matrix.jsonl 的项目目录（{WORKSPACE}）")
    if args.project:
        if args.project not in projects:
            sys.exit(f"项目 {args.project} 无矩阵（现有：{list(projects)}）")
        projects = {args.project: projects[args.project]}

    done = load_scored_ids()
    t0 = time.time()
    with SCORES_PATH.open("a", encoding="utf-8") as f:
        for proj, slot in projects.items():
            matrix, cases = slot["matrix"], slot["cases"]
            themes = matrix_req_themes(matrix)
            print(f"\n== {proj}：{len(matrix)} FP × {len(cases)} 条用例"
                  f"（需求主题：{sorted(themes) or '无，退化为不过滤'}）==")
            for fp in matrix:
                key = f"{proj}|{fp.get('id')}"
                if key in done:
                    print(f"  {fp.get('id')} 已落盘，跳过")
                    continue
                row = judge_fp(proj, fp, cases, themes)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                if "error" in row:
                    mark = f"ERR {row['error'][:60]}"
                else:
                    mark = f"{row['score']:.2f}{'✓' if row['pass'] else '✗'}"
                print(f"  {row['fp_id']} [{row['priority']}] {row['fp_feature'][:24]}："
                      f"{mark}（相关用例 {row['n_relevant_cases']} 条）")

    print(f"\n完成（耗时 {time.time() - t0:.0f}s）→ {SCORES_PATH}")
    print("汇总分析：jq 或读 dataset/judge_coverage_v1.jsonl 按 score/reason 过未覆盖清单")


if __name__ == "__main__":
    main()
