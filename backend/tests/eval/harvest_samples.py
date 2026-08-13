"""从 workspace 历史产出采集回归样本。

扫描 backend/workspace/testcase/**/*.jsonl，把真实生成的用例文件打包成
回归集条目（input 留占位，G-Eval 裁判只看 actual_output 即可评分）。

用法：
    backend/.venv/Scripts/python.exe -m tests.eval.harvest_samples
    backend/.venv/Scripts/python.exe -m tests.eval.harvest_samples --max-files 5 --max-cases 30
    # 校准扩采：分层均衡抽样，防单项目霸榜（PR-2 占 workspace 近半文件）
    backend/.venv/Scripts/python.exe -m tests.eval.harvest_samples --strategy balanced --max-files 40
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

# 本文件位于 backend/tests/eval/，向上 3 级为 backend/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = BACKEND_ROOT / "workspace" / "testcase"
DATASET_PATH = Path(__file__).parent / "dataset" / "regression_v1.jsonl"
DATASET_PATH_V2 = Path(__file__).parent / "dataset" / "regression_v2.jsonl"

# 跳过非用例文件（矩阵/预期结果聚合/对话历史等）
SKIP_PATTERNS = ("feature_matrix", "expected_result", "manifest", "conversation")

ROOT_GROUP = "(root)"  # 直接挂在 workspace/testcase 下的散文件


def top_group(path: Path) -> str:
    """文件的顶层分组（workspace/testcase 下的第一级目录名；散文件归 (root)）。"""
    rel = path.relative_to(WORKSPACE)
    return rel.parts[0] if len(rel.parts) > 1 else ROOT_GROUP


def list_case_files() -> list[Path]:
    return sorted(
        (p for p in WORKSPACE.rglob("*.jsonl")
         if not any(s in p.name.lower() for s in SKIP_PATTERNS)),
        key=lambda p: p.stat().st_size,
        reverse=True,  # 大文件优先——用例越多，裁判可评的样本越充分
    )


def iter_case_files(max_files: int) -> list[Path]:
    """size 策略：全局大文件优先（历史默认行为，单项目易霸榜）。"""
    return list_case_files()[:max_files]


def iter_case_files_balanced(max_files: int, per_dir_cap: int | None) -> list[Path]:
    """balanced 策略：按顶层目录分组轮询抽样——组内仍大文件优先，
    但每轮每组至多取一个，保证校准集的场景多样性（一致率按组分层的前提）。"""
    groups: dict[str, list[Path]] = defaultdict(list)
    for p in list_case_files():
        groups[top_group(p)].append(p)
    if per_dir_cap is None:
        # 自动上限：组数均摊 +1 余量，小组取完后名额自动让给大组
        per_dir_cap = max(2, max_files // len(groups) + 1)

    picked: list[Path] = []
    taken: dict[str, int] = defaultdict(int)
    while len(picked) < max_files:
        progressed = False
        for name in sorted(groups):
            if len(picked) >= max_files:
                break
            if taken[name] < per_dir_cap and groups[name]:
                picked.append(groups[name].pop(0))
                taken[name] += 1
                progressed = True
        if not progressed:  # 全部组取空或触顶
            break
    return picked


def find_matrix(path: Path) -> Path | None:
    """用例文件所属项目的功能矩阵：按顶层目录归属（PR-1/PR-2 有项目级矩阵）。
    root 散文件是多项目历史混杂，无法可靠关联，返回 None（裁判对无矩阵样本
    跳过覆盖类维度，宁缺毋滥）。"""
    rel = path.relative_to(WORKSPACE)
    if len(rel.parts) == 1:
        return None
    m = WORKSPACE / rel.parts[0] / "feature_matrix.jsonl"
    return m if m.exists() else None


def load_matrix(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def pack_sample(path: Path, max_cases: int, with_matrix: bool = False) -> dict | None:
    """把一个 JSONL 用例文件打包成回归样本（截断到 max_cases 条控制 prompt 体积）。"""
    cases = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            cases.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # 脏行跳过（工具允许脏拼接，采集时宁缺毋滥）
        if len(cases) >= max_cases:
            break
    if len(cases) < 3:
        return None  # 太少的文件没有评估价值
    rel = path.relative_to(BACKEND_ROOT).as_posix()
    # id 含父目录避免跨项目同名文件冲突（如 PR-1/PR-2 下的 module_01）
    slug = path.relative_to(WORKSPACE).with_suffix("").as_posix().replace("/", "-")
    group = top_group(path)
    sample = {
        "id": f"ws-{slug}",
        "input": f"[采集自 {rel}，需求原文未保留；裁判仅依据 actual_output 评分]",
        "actual_output": json.dumps(cases, ensure_ascii=False, indent=1),
        "source": rel,
        "case_count": len(cases),
        "group": group,  # 分层一致率分析用（PR-1 / PR-2 / (root)）
    }
    if with_matrix:
        m = find_matrix(path)
        rows = load_matrix(m) if m else None
        sample["feature_matrix"] = rows  # None = 无项目矩阵，覆盖类裁判跳过本样本
        if rows:
            # 需求侧输入回填：矩阵的 test_points 即需求的功能点级转述，
            # 覆盖完整性/需求忠实度裁判以此为基准
            sample["input"] = (
                f"[项目 {group} 用例；功能矩阵 {len(rows)} 个功能点存于 feature_matrix 字段，"
                f"覆盖/忠实度裁判以 test_points 为需求基准]"
            )
    return sample


def main() -> None:
    parser = argparse.ArgumentParser(description="从 workspace 采集回归样本")
    parser.add_argument("--max-files", type=int, default=10)
    parser.add_argument("--max-cases", type=int, default=30, help="每个文件最多取多少条用例")
    parser.add_argument("--strategy", choices=("size", "balanced"), default="size",
                        help="size=全局大文件优先（默认）；balanced=按顶层目录轮询均衡，校准扩采用")
    parser.add_argument("--per-dir-cap", type=int, default=None,
                        help="balanced 策略下单目录最多取几个（默认按组数自动均摊）")
    parser.add_argument("--with-matrix", action="store_true",
                        help="关联所属项目的 feature_matrix 回填样本（覆盖/忠实度裁判用），"
                             "默认输出切到 regression_v2.jsonl")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if args.out is None:
        args.out = DATASET_PATH_V2 if args.with_matrix else DATASET_PATH

    args.out.parent.mkdir(parents=True, exist_ok=True)
    existing_ids = set()
    if args.out.exists():
        for line in args.out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing_ids.add(json.loads(line)["id"])

    if args.strategy == "balanced":
        candidates = iter_case_files_balanced(args.max_files, args.per_dir_cap)
    else:
        candidates = iter_case_files(args.max_files)

    added = 0
    with args.out.open("a", encoding="utf-8") as f:
        for path in candidates:
            sample = pack_sample(path, args.max_cases, with_matrix=args.with_matrix)
            if sample is None or sample["id"] in existing_ids:
                continue
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            added += 1
            matrix_mark = ""
            if args.with_matrix:
                n = len(sample["feature_matrix"]) if sample["feature_matrix"] else 0
                matrix_mark = f"  矩阵:{n}FP" if n else "  矩阵:无"
            print(f"+ {sample['id']}  [{sample['group']}] "
                  f"({sample['case_count']} 条用例, {len(sample['actual_output'])} 字符){matrix_mark}")

    print(f"\n采集完成：新增 {added} 条 → {args.out}")
    print("提示：input 为占位的样本可直接用（裁判只看 actual_output）；"
          "有需求原文时回填 input 字段可解锁更多评估维度。")


if __name__ == "__main__":
    main()
