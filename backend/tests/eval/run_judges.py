"""裁判分数落盘——校准对比的前提（pytest 门禁只 assert 不留痕）。

【盲标纪律】必须等 human_labels_v1.jsonl 全部填完后再跑本脚本；
提前看到裁判分会污染人工判断，校准即失效。

逐条样本跑两个 G-Eval 裁判，把 score/reason 落盘 judge_scores_v1.jsonl：
- 落盘后 calibrate_report 可反复分析不重跑（裁判调用要花钱）
- 支持断点续跑：已落盘的 id 自动跳过（Ctrl+C 随时可中断）

用法（cwd = backend，需要平台 .env 里的模型配置）：
    ./.venv/Scripts/python.exe -m tests.eval.run_judges
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from deepeval.test_case import LLMTestCase

from tests.eval.metrics import JUDGES

EVAL_DIR = Path(__file__).parent
DATASET_PATH = EVAL_DIR / "dataset" / "regression_v1.jsonl"
SCORES_PATH = EVAL_DIR / "dataset" / "judge_scores_v1.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def score_sample(sample: dict) -> dict:
    """一条样本过全部裁判，返回落盘行。裁判异常不吞——落 error 字段，
    校准报告里单独列出（裁判解析失败本身是裁判健壮性的信号）。"""
    row: dict = {"id": sample["id"]}
    test_case = LLMTestCase(input=sample["input"], actual_output=sample["actual_output"])
    for key, metric in JUDGES:
        try:
            metric.measure(test_case)
            row[key] = {
                "score": metric.score,
                "threshold": metric.threshold,
                "pass": bool(metric.score is not None and metric.score >= metric.threshold),
                "reason": metric.reason,
            }
        except Exception as exc:  # noqa: BLE001——落盘继续跑，不让一条样本毁掉整批
            row[key] = {"error": f"{type(exc).__name__}: {exc}"}
    return row


def main() -> None:
    samples = load_jsonl(DATASET_PATH)
    if not samples:
        sys.exit(f"回归集为空：{DATASET_PATH}（先跑 harvest_samples）")

    done = {r["id"] for r in load_jsonl(SCORES_PATH)}
    todo = [s for s in samples if s["id"] not in done]
    print(f"回归集 {len(samples)} 条，已落盘 {len(done)} 条，本轮待跑 {len(todo)} 条")
    if not todo:
        print(f"无新增样本，分数文件已是最新：{SCORES_PATH}")
        return

    t0 = time.time()
    with SCORES_PATH.open("a", encoding="utf-8") as f:
        for i, sample in enumerate(todo, 1):
            row = score_sample(sample)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()  # 逐行落盘，中断不丢已完成部分
            marks = []
            for key, _ in JUDGES:
                cell = row[key]
                marks.append("ERR" if "error" in cell
                             else f"{cell['score']:.2f}{'✓' if cell['pass'] else '✗'}")
            print(f"[{i}/{len(todo)}] {row['id']}  {'  '.join(marks)}")

    print(f"\n完成：{len(todo)} 条 → {SCORES_PATH}（耗时 {time.time() - t0:.0f}s）")
    print("下一步：./.venv/Scripts/python.exe -m tests.eval.calibrate_report")


if __name__ == "__main__":
    main()
