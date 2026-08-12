"""校准报告：裁判分数 × 人工盲标 → 一致率 / Kappa / 分歧清单。

输入（均在 dataset/ 下）：
- regression_v1.jsonl   回归集（取 group 做分层分析）
- human_labels_v1.jsonl 人工盲标（make_blind_labels 生成骨架，标注者填 0/1）
- judge_scores_v1.jsonl 裁判落盘（run_judges 生成；盲标完成前禁止跑）

输出：
- stdout + dataset/calibration_report.md：一致率、Cohen's Kappa、混淆矩阵、
  分层一致率、启用决策建议
- dataset/disagreements.md：全部分歧样本（裁判理由 × 人工 note 并排），
  改 rubric/调阈值时逐条过

用法（cwd = backend）：
    ./.venv/Scripts/python.exe -m tests.eval.calibrate_report
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).parent / "dataset"
DATASET_PATH = EVAL_DIR / "regression_v1.jsonl"
LABELS_PATH = EVAL_DIR / "human_labels_v1.jsonl"
SCORES_PATH = EVAL_DIR / "judge_scores_v1.jsonl"
REPORT_PATH = EVAL_DIR / "calibration_report.md"
DISAGREE_PATH = EVAL_DIR / "disagreements.md"

# 维度 key ↔ 人工标签字段
DIMENSIONS = (
    ("assertability", "assertability_pass", "预期结果可断言性"),
    ("coverage", "coverage_pass", "异常与安全覆盖"),
)

# 启用决策线（README 校准节约定）：一致率 ≥0.8 且 Kappa ≥0.6 才允许切 strict 门禁
AGREEMENT_LINE = 0.8
KAPPA_LINE = 0.6
# 最小样本量：低于此数时即使一致率过线也不许切门禁（n 太小 Kappa 无意义，
# 一致率偶然性大——本闸防"标几条就收工"）
MIN_SAMPLES = 20


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def cohens_kappa(pairs: list[tuple[int, int]]) -> float | None:
    """pairs = [(judge_pass, human_pass), ...]，均为 0/1。样本太少时返回 None。"""
    n = len(pairs)
    if n < 5:
        return None
    po = sum(1 for j, h in pairs if j == h) / n
    j_pos = sum(j for j, _ in pairs) / n
    h_pos = sum(h for _, h in pairs) / n
    pe = j_pos * h_pos + (1 - j_pos) * (1 - h_pos)
    if pe == 1.0:  # 边际全同（如两边全 pass）——Kappa 无定义，一致率自证
        return None
    return (po - pe) / (1 - pe)


def confusion(pairs: list[tuple[int, int]]) -> dict[str, int]:
    return {
        "TP": sum(1 for j, h in pairs if j == 1 and h == 1),
        "FP": sum(1 for j, h in pairs if j == 1 and h == 0),  # 裁判放水
        "FN": sum(1 for j, h in pairs if j == 0 and h == 1),  # 裁判误杀
        "TN": sum(1 for j, h in pairs if j == 0 and h == 0),
    }


def fmt_kappa(k: float | None) -> str:
    return "n/a（边际全同或样本<5）" if k is None else f"{k:.2f}"


def main() -> None:
    labels = {r["id"]: r for r in load_jsonl(LABELS_PATH)}
    scores = {r["id"]: r for r in load_jsonl(SCORES_PATH)}
    groups = {s["id"]: s.get("group", "(旧样本)") for s in load_jsonl(DATASET_PATH)}

    if not labels:
        sys.exit(f"未找到人工标注：{LABELS_PATH}（先跑 make_blind_labels 并填完）")
    if not scores:
        sys.exit(f"未找到裁判落盘：{SCORES_PATH}（确认盲标填完后跑 run_judges）")

    unlabeled = [
        i for i, r in labels.items()
        if r.get("assertability_pass") is None or r.get("coverage_pass") is None
    ]
    if unlabeled:
        sys.exit(f"还有 {len(unlabeled)} 条未标完（如 {unlabeled[0]}）——盲标不完整时"
                 f"禁止看裁判对比，先把 human_labels_v1.jsonl 的 null 填完。")

    lines: list[str] = ["# 校准报告\n"]
    disagreements: list[str] = ["# 分歧样本清单（裁判 × 人工不一致）\n"]
    overall_ok = True
    dim_ns: dict[str, int] = {}

    for key, label_field, zh_name in DIMENSIONS:
        pairs: list[tuple[int, int]] = []
        judge_errors: list[str] = []
        by_group: dict[str, list[tuple[int, int]]] = {}
        score_dist: list[float] = []

        for sid, lab in labels.items():
            sc = scores.get(sid)
            if sc is None:
                continue  # 裁判没落盘的（新增样本）跳过
            cell = sc.get(key, {})
            if "error" in cell:
                judge_errors.append(sid)
                continue
            pair = (1 if cell["pass"] else 0, int(lab[label_field]))
            pairs.append(pair)
            score_dist.append(cell["score"])
            by_group.setdefault(groups.get(sid, "?"), []).append(pair)

            if pair[0] != pair[1]:
                kind = "裁判放水（应拦未拦）" if pair == (1, 0) else "裁判误杀（应放却拦）"
                disagreements.append(
                    f"\n## {sid} —— {zh_name}：{kind}\n\n"
                    f"- 裁判：score={cell['score']:.2f}（阈值 {cell['threshold']}）\n"
                    f"- 裁判理由：{cell.get('reason', '')[:800]}\n"
                    f"- 人工：{'pass' if pair[1] else 'fail'}"
                    + (f"（note：{lab['note']}）" if lab.get("note") else "")
                    + "\n"
                )

        if not pairs:
            lines.append(f"\n## {zh_name}\n\n无可对比样本（全为裁判错误或缺落盘）\n")
            overall_ok = False
            continue

        n = len(pairs)
        dim_ns[zh_name] = n
        agree = sum(1 for j, h in pairs if j == h) / n
        kappa = cohens_kappa(pairs)
        cm = confusion(pairs)
        ok = agree >= AGREEMENT_LINE and (kappa is None or kappa >= KAPPA_LINE)
        overall_ok = overall_ok and ok

        dist = sorted(score_dist)
        lines.append(
            f"\n## {zh_name}（{'✅ 达标' if ok else '❌ 未达标'}）\n\n"
            f"- 可对比样本：{n} 条（裁判 error 跳过 {len(judge_errors)} 条）\n"
            f"- 一致率：**{agree:.1%}**（门禁线 {AGREEMENT_LINE:.0%}）\n"
            f"- Cohen's Kappa：**{fmt_kappa(kappa)}**（门禁线 {KAPPA_LINE}）\n"
            f"- 混淆矩阵：TP={cm['TP']} FP(放水)={cm['FP']} FN(误杀)={cm['FN']} TN={cm['TN']}\n"
            f"- 裁判分数分布：min={dist[0]:.2f} 中位={dist[n // 2]:.2f} max={dist[-1]:.2f}\n"
            f"\n### 分层一致率\n\n"
        )
        for g in sorted(by_group):
            gp = by_group[g]
            g_agree = sum(1 for j, h in gp if j == h) / len(gp)
            lines.append(f"- {g}: {g_agree:.1%}（{len(gp)} 条）\n")
        if judge_errors:
            lines.append(f"\n裁判 error 样本（解析/调用失败，需单独看）："
                         f"{', '.join(judge_errors[:5])}{' …' if len(judge_errors) > 5 else ''}\n")

    lines.append("\n## 启用决策\n\n")
    min_n = min(dim_ns.values(), default=0)
    if overall_ok and min_n >= MIN_SAMPLES:
        lines.append("✅ 两维一致率与 Kappa 均过线、样本量达标——允许把 threshold 定为正式拦截线，"
                     "pytest 门禁从观测模式切 strict（CI 接入见 README）。\n")
    elif overall_ok:
        lines.append(f"⚠️ 一致率过线但样本量不足（最少维度 n={min_n} < {MIN_SAMPLES}）——"
                     "Kappa 在小样本下无统计意义，本结论仅供管线验证/分批试跑参考，"
                     "**禁止据此切门禁**；标满样本后重新出报告。\n")
    else:
        lines.append("❌ 未过线——不许切 strict。下一步：逐条过 disagreements.md，"
                     "判分歧主因是 rubric 措辞 / 阈值 / 同源自评偏好，"
                     "改 metrics.py 后【全量重跑】run_judges 再出报告（裁判改动必须重跑全量）。\n")

    report = "".join(lines)
    REPORT_PATH.write_text(report, encoding="utf-8")
    DISAGREE_PATH.write_text("".join(disagreements), encoding="utf-8")
    print(report)
    print(f"\n报告已写：{REPORT_PATH}")
    print(f"分歧清单：{DISAGREE_PATH}（{sum(1 for d in disagreements if d.startswith(chr(10) + '## '))} 条）")


if __name__ == "__main__":
    main()
