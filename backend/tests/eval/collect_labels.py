"""回收盲标工作表（blind_worksheet.md）里填写的判定，写回 human_labels_v1.jsonl。

一体式填法的配套回收器：工作表每条样本末尾有一行
    > 判定：assertability=_ coverage=_ note=
把 _ 改成 0/1 后跑本脚本：
- md 里填了非 _ 的维度 → 覆盖 jsonl 同名字段；留 _ 的不动（可与 jsonl 直填混用）
- note 非空才覆盖 jsonl 的 note
- 非法值（非 0/1/_）报错并指出样本 id，不写任何文件——答题卡永不写脏

用法（cwd = backend）：
    ./.venv/Scripts/python.exe -m tests.eval.collect_labels
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).parent / "dataset"
WORKSHEET_PATH = EVAL_DIR / "blind_worksheet.md"
LABELS_PATH = EVAL_DIR / "human_labels_v1.jsonl"

SECTION_RE = re.compile(r"^## \d+\. (\S+)\s*$", re.MULTILINE)
LABEL_RE = re.compile(r"^> 判定：assertability=(\S+)\s+coverage=(\S+?)(?:\s+note=(.*))?$", re.MULTILINE)
VALID = {"0", "1", "_"}


def parse_worksheet(text: str) -> dict[str, dict]:
    """按「## N. id」分节，在每节内找判定行。返回 {id: {assertability, coverage, note}}。"""
    sections = list(SECTION_RE.finditer(text))
    filled: dict[str, dict] = {}
    for idx, m in enumerate(sections):
        sid = m.group(1)
        end = sections[idx + 1].start() if idx + 1 < len(sections) else len(text)
        seg = text[m.start():end]
        lm = LABEL_RE.search(seg)
        if not lm:
            continue
        a, c, note = lm.group(1), lm.group(2), (lm.group(3) or "").strip()
        if a not in VALID or c not in VALID:
            sys.exit(f"样本 {sid} 判定行非法：assertability={a!r} coverage={c!r}"
                     f"（只允许 0/1/_）。未写任何文件，请修正后重跑。")
        filled[sid] = {"assertability": a, "coverage": c, "note": note}
    return filled


def main() -> None:
    if not WORKSHEET_PATH.exists():
        sys.exit(f"未找到工作表：{WORKSHEET_PATH}（先跑 make_blind_labels）")
    if not LABELS_PATH.exists():
        sys.exit(f"未找到答题卡：{LABELS_PATH}（先跑 make_blind_labels）")

    filled = parse_worksheet(WORKSHEET_PATH.read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in LABELS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

    updated = 0
    for row in rows:
        f = filled.get(row["id"])
        if not f:
            continue
        changed = False
        if f["assertability"] != "_":
            row["assertability_pass"] = int(f["assertability"])
            changed = True
        if f["coverage"] != "_":
            row["coverage_pass"] = int(f["coverage"])
            changed = True
        if f["note"]:
            row["note"] = f["note"]
            changed = True
        updated += changed

    with LABELS_PATH.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    done = sum(1 for r in rows
               if r["assertability_pass"] is not None and r["coverage_pass"] is not None)
    print(f"从工作表回收 {updated} 条 → {LABELS_PATH}")
    print(f"总进度：{done}/{len(rows)} 条已完整标注"
          + ("——全部完成，可以跑 run_judges 了" if done == len(rows)
             else "——继续标，未齐前禁止跑 run_judges"))


if __name__ == "__main__":
    main()
