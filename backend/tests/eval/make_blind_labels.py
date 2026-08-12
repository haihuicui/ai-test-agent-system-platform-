"""从回归集生成盲标材料（人工校准的第一步）。

产出两个文件：
1. dataset/human_labels_v1.jsonl —— 标注骨架，标注者只填这个文件：
     {"id": "...", "assertability_pass": null, "coverage_pass": null, "note": ""}
   null = 未标注；1 = 人工认为通过；0 = 人工认为不通过。
2. dataset/blind_worksheet.md —— 阅读工作表（含每条样本的用例全文），
   标注时对照它看，在 jsonl 里填分。

盲标纪律（校准有效性全押在这上面）：
- 先看 worksheet 填完所有标签，【之后】才允许跑 run_judges 看裁判分；
- 工作表与骨架均不含裁判分数，行序已用固定 seed 打乱，与采集顺序无关；
- 判定标准只以下方「判定规则」为准，不要凭感觉浮动。

用法：
    backend/.venv/Scripts/python.exe -m tests.eval.make_blind_labels
    backend/.venv/Scripts/python.exe -m tests.eval.make_blind_labels --seed 7
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

EVAL_DIR = Path(__file__).parent
DATASET_PATH = EVAL_DIR / "dataset" / "regression_v1.jsonl"
LABELS_PATH = EVAL_DIR / "dataset" / "human_labels_v1.jsonl"
WORKSHEET_PATH = EVAL_DIR / "dataset" / "blind_worksheet.md"

# 与 test_testcase_quality.py 两个裁判一一对应：
# assertability_pass ↔ 「预期结果可断言性」(threshold 0.8)
# coverage_pass      ↔ 「异常与安全覆盖」(threshold 0.7)
# 人工判 pass=1 的语义 = 「我认为裁判应该给过线分」——这样 pass/fail 层面可直接算一致率。
JUDGING_RULES = """\
## 判定规则（与两个 G-Eval 裁判一一对应）

### assertability_pass —— 预期结果可断言性（对应裁判阈值 0.8）

逐条看预期结果（expected_result 或 steps 里的 result）：

- 可客观断言 = 含具体数值 / 状态码 / 确切文案 / 明确的页面元素或状态变化
- 出现 ≥2 处模糊词（「正确」「成功」「正常」「合理」「显示无误」「符合预期」
  这类无法客观判定 Pass/Fail 的措辞）→ 判 0
- 预期结果与步骤因果断裂（步骤没操作却断言了结果）≥1 处 → 判 0
- 偶发 1 处模糊、其余全部可断言 → 可判 1（0.8 阈值容忍每处 -0.15 约 1 处）

### coverage_pass —— 异常与安全覆盖（对应裁判阈值 0.7）

- 异常流用例（空值/非法格式/超长/Unicode/emoji/重复提交/并发）< 2 条 → 判 0
- 功能涉及用户输入但完全无安全用例（SQL 注入/XSS/越权/未授权）→ 判 0
  （纯查询类、无输入面的功能缺失安全用例不扣）
- 有明确取值范围的字段完全没碰边界（min/max 附近一个都没有）→ 判 0
- 全是 Happy Path → 坚决判 0

### 填法

- 1 = 通过（裁判应该给过线分）；0 = 不通过；null = 未标注
- note 可空；判 0 时建议写一句锚点（如「TC-03 预期结果是'显示正常'」），
  分歧分析时要靠它定位
"""


def load_dataset() -> list[dict]:
    return [
        json.loads(line)
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_existing_labels() -> dict[str, dict]:
    """已存在的标注（断点续标）：已填的行保持原位，不在文件里的 id 才算新样本。"""
    if not LABELS_PATH.exists():
        return {}
    labels = {}
    for line in LABELS_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            labels[row["id"]] = row
    return labels


def write_labels(samples: list[dict], seed: int) -> tuple[int, int]:
    """写标注骨架。返回 (已有标注保留数, 新增待标数)。"""
    existing = load_existing_labels()
    kept = [existing.pop(s["id"]) for s in samples if s["id"] in existing]
    new_rows = [
        {"id": s["id"], "assertability_pass": None, "coverage_pass": None, "note": ""}
        for s in samples
        if s["id"] not in {r["id"] for r in kept}
    ]
    random.Random(seed).shuffle(new_rows)  # 固定 seed 打乱，与采集/裁判顺序无关
    with LABELS_PATH.open("w", encoding="utf-8") as f:
        for row in [*kept, *new_rows]:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(kept), len(new_rows)


def write_worksheet(samples: list[dict]) -> None:
    parts = [
        "# 盲标工作表（不含裁判分数——打完标签前不要跑 run_judges）\n",
        JUDGING_RULES,
        "\n---\n\n# 样本正文\n",
    ]
    for i, s in enumerate(samples, 1):
        group = s.get("group") or "(旧样本)"
        parts.append(
            f"\n## {i}. {s['id']}\n\n"
            f"- 来源：`{s.get('source', '?')}`　分组：{group}　用例数：{s.get('case_count', '?')}\n\n"
            f"```json\n{s['actual_output']}\n```\n"
        )
    WORKSHEET_PATH.write_text("".join(parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="生成盲标工作表与标注骨架")
    parser.add_argument("--seed", type=int, default=42, help="新行打乱 seed（固定可复现）")
    args = parser.parse_args()

    samples = load_dataset()
    kept, added = write_labels(samples, args.seed)
    write_worksheet(samples)

    labeled = sum(
        1 for line in LABELS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
        and json.loads(line)["assertability_pass"] is not None
        and json.loads(line)["coverage_pass"] is not None
    )
    print(f"回归集样本：{len(samples)} 条")
    print(f"标注骨架：{LABELS_PATH}（保留已标 {kept}，新增待标 {added}，已完整标注 {labeled}）")
    print(f"阅读工作表：{WORKSHEET_PATH}")
    print("下一步：对照 worksheet 填 jsonl 里的 null；全部填完后才允许跑 run_judges。")


if __name__ == "__main__":
    main()
