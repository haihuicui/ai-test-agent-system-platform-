"""需求忠实度裁判（幻觉用例）：逐文件评估用例是否验证了需求里不存在的功能。

与 judge_coverage 的分工（一体两面）：
- judge_coverage：以 FP 为单位查「该有的有没有」（漏测/虚假声明）；
- 本工具：以产出文件为单位查「不该有的有没有」（幻觉用例）——覆盖不完整
  只是漏，幻觉用例是错：它会让执行者去验证一个根本不存在的需求。

数据源 = workspace 会话目录扫描，不用 v2 回归集：
v2 样本关联的是**项目级**矩阵，而多需求项目（PR-1/PR-2）的项目矩阵只覆盖
REQ-变更——拿它评其他需求的用例文件全是冤案（首跑 17/28 FAIL 全是基准错配，
非真幻觉）。会话目录天然是「一个需求 = 一个矩阵 = 一批用例文件」的配对，
基准正确性由目录结构保证。

配对纪律（防冤案比覆盖更要紧）：
- 会话目录（深度 ≥2）：直接配对（目录即需求证据）；
- 项目级散置文件（深度 1）：多需求混杂，仅当用例 REQ 主题与矩阵 source
  主题有交集才配对；无 REQ 引用的文件无法举证归属，跳过不评；
- 根目录：公认混杂组，不评。

防误判设计：合理衍生（对已有 FP 的异常/边界/安全/负面变体）不算幻觉。

用法（cwd = backend）：
    ./.venv/Scripts/python.exe -m tests.eval.judge_faithfulness              # 全部
    ./.venv/Scripts/python.exe -m tests.eval.judge_faithfulness --project PR-1
    ./.venv/Scripts/python.exe -m tests.eval.judge_faithfulness --max-files 3  # 试跑
断点续跑：已落盘的文件自动跳过，Ctrl+C 可中断。
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from deepeval.test_case import LLMTestCase

from tests.eval.coverage_audit import SKIP_PATTERNS, WORKSPACE, load_matrix
from tests.eval.judge_coverage import slim_case
from tests.eval.metrics import requirement_faithfulness_metric

EVAL_DIR = Path(__file__).parent
SCORES_PATH = EVAL_DIR / "dataset" / "judge_faithfulness_v1.jsonl"


def iter_units(project: str | None = None):
    """产出 (unit_id, matrix, case_file, skip_reason)：含矩阵目录 × 该目录直属用例文件。

    不递归子目录——会话子目录有自己的矩阵，各自独立成评估单元。
    skip_reason 非空表示基准无法配对（多需求混杂），调用侧跳过不评。
    """
    from app.agents.tools.testcase.coverage_tools import req_themes

    for matrix_path in sorted(WORKSPACE.rglob("feature_matrix.jsonl")):
        d = matrix_path.parent
        if d == WORKSPACE:
            continue  # 根目录是公认混杂组（多需求遗留堆积），基准无法配对
        rel = d.relative_to(WORKSPACE)
        if project and rel.parts[0] != project:
            continue
        matrix = load_matrix(matrix_path)
        if not matrix:
            continue
        matrix_themes = set()
        for fp in matrix:
            matrix_themes |= req_themes(str(fp.get("source") or ""))
        session_level = len(rel.parts) >= 2  # 会话目录：目录即需求证据
        for p in sorted(d.glob("*.jsonl")):
            if any(s in p.name.lower() for s in SKIP_PATTERNS):
                continue
            unit_id = f"{rel.as_posix()}/{p.name}"
            skip = ""
            if not session_level:
                # 项目级散置文件：多需求混杂，REQ 主题举证配对
                case_themes = set()
                for c in load_cases(p):
                    from app.agents.tools.testcase.coverage_tools import _case_text
                    case_themes |= req_themes(_case_text(c))
                if matrix_themes and case_themes and not (matrix_themes & case_themes):
                    skip = f"REQ 主题错位（用例 {sorted(case_themes)} vs 矩阵 {sorted(matrix_themes)}）"
                elif not case_themes:
                    skip = "项目级散置文件无 REQ 引用，无法举证归属需求"
            yield unit_id, matrix, p, skip


def load_cases(case_file: Path) -> list[dict]:
    from app.agents.tools.testcase.coverage_tools import _looks_like_case

    cases = []
    for line in case_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if _looks_like_case(obj):
            cases.append(obj)
    return cases


def matrix_summary(matrix: list[dict]) -> str:
    """矩阵压成裁判可读的基准清单（只留判定所需的字段）。"""
    return json.dumps(
        [
            {
                "id": fp.get("id"),
                "module": fp.get("module"),
                "feature": fp.get("feature"),
                "test_points": fp.get("test_points"),
            }
            for fp in matrix
        ],
        ensure_ascii=False,
    )


def judge_unit(unit_id: str, matrix: list[dict], cases: list[dict]) -> dict:
    """评一个文件：返回落盘行。裁判异常落 error 不中断整批。"""
    row = {"id": unit_id, "case_count": len(cases), "n_fp": len(matrix)}
    slimmed = [slim_case(c) for c in cases]
    test_case = LLMTestCase(
        input=matrix_summary(matrix),
        actual_output=json.dumps(slimmed, ensure_ascii=False),
    )
    last_exc: Exception | None = None
    for attempt in (1, 2):  # 裁判输出偶发 invalid JSON，重试一次
        try:
            requirement_faithfulness_metric.measure(test_case)
            row.update({
                "score": requirement_faithfulness_metric.score,
                "pass": bool(
                    requirement_faithfulness_metric.score is not None
                    and requirement_faithfulness_metric.score
                    >= requirement_faithfulness_metric.threshold
                ),
                "reason": requirement_faithfulness_metric.reason,
            })
            return row
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt == 1:
                time.sleep(2)
    row.update({"error": f"{type(last_exc).__name__}: {last_exc}"})
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="需求忠实度裁判（幻觉用例，文件级）")
    parser.add_argument("--project", default=None, help="只评指定项目（默认全部）")
    parser.add_argument("--max-files", type=int, default=None, help="限制新评文件数（试跑）")
    parser.add_argument("--scores-out", type=Path, default=SCORES_PATH)
    args = parser.parse_args()

    done: set[str] = set()
    if args.scores_out.exists():
        done = {
            json.loads(l)["id"]
            for l in args.scores_out.read_text(encoding="utf-8").splitlines()
            if l.strip()
        }

    t0 = time.time()
    n_new = n_skip = 0
    skipped: list[str] = []
    with args.scores_out.open("a", encoding="utf-8") as f:
        for unit_id, matrix, case_file, skip in iter_units(args.project):
            if unit_id in done:
                continue
            if args.max_files is not None and n_new >= args.max_files:
                break
            cases = load_cases(case_file)
            if not cases:
                continue
            if skip:
                n_skip += 1
                skipped.append(f"{unit_id}（{skip}）")
                continue
            row = judge_unit(unit_id, matrix, cases)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            n_new += 1
            if "error" in row:
                mark = f"ERR {row['error'][:60]}"
            else:
                mark = f"{row['score']:.2f}{'✓' if row['pass'] else '✗'}"
            print(f"  {unit_id}（{row['case_count']} 条）：{mark}", flush=True)

    print(f"\n完成：新评 {n_new} 个文件，基准无法配对跳过 {n_skip} 个"
          f"（耗时 {time.time() - t0:.0f}s）→ {args.scores_out}")
    if skipped:
        print("跳过清单（防冤案，不计入评分）：")
        for s in skipped[:20]:
            print(f"  - {s}")
        if len(skipped) > 20:
            print(f"  …等共 {len(skipped)} 个")


if __name__ == "__main__":
    main()
