"""测试用例规范 lint——确定性代码检查，零 token 零校准，可直接接 CI。

与 G-Eval 裁判的分工：代码查规范（字段/编号/结构），裁判查语义。
规则全部源自 workspace 全量 1828 条用例的真实违规画像（2026-08 统计）：
- case_type 缺失 256 条、ui/UI 大小写混用
- priority 双轨（critical/high/medium/low 与 P0/P1/P2 并存）、critical 占 31% 分级通胀
- 0 步用例 229 条、1 步 143 条、12+ 步 152 条
- 16% 用例无 REQ-/FP-/F- 追溯编号；199 条命名为空

用法（cwd = backend）：
    ./.venv/Scripts/python.exe -m tests.eval.lint_cases              # 全量扫描
    ./.venv/Scripts/python.exe -m tests.eval.lint_cases --json       # 机器可读（接 CI）
    ./.venv/Scripts/python.exe -m tests.eval.lint_cases --path workspace/testcase/PR-1
退出码：有 error 级违规 = 1，否则 0（warning 不阻断）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCAN = BACKEND_ROOT / "workspace" / "testcase"

SKIP_PATTERNS = ("feature_matrix", "expected_result", "manifest", "conversation")

# ── 合法取值（大小写不敏感比较，报告里提示规范写法）─────────────────────
VALID_CASE_TYPES = {"functional", "security", "boundary", "exception",
                    "abnormal", "performance", "compatibility", "ui"}
EN_PRIORITY = {"critical", "high", "medium", "low"}
NUM_PRIORITY = {"p0", "p1", "p2", "p3"}
TRACE_RE = re.compile(r"REQ-|FP-|F-\d+")

MAX_STEPS = 10        # 超过该拆
CRITICAL_INFLATION = 0.5  # 文件内 critical/P0 占比超 50% 视为分级失效


def iter_cases(scan_root: Path):
    """产出 (file_path, case_dict, line_no)。脏行跳过（与 harvest 同一容错口径）。"""
    for p in sorted(scan_root.rglob("*.jsonl")):
        if any(s in p.name.lower() for s in SKIP_PATTERNS):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not line.strip():
                continue
            try:
                yield p, json.loads(line), i
            except json.JSONDecodeError:
                continue


def lint(scan_root: Path) -> list[dict]:
    issues: list[dict] = []

    def add(level: str, rule: str, path: Path, msg: str, case: str = "", line: int = 0):
        issues.append({
            "level": level, "rule": rule,
            "file": path.relative_to(BACKEND_ROOT).as_posix(),
            "case": case, "line": line, "message": msg,
        })

    # 文件级统计（双体系混用 / 分级通胀需要整文件视角）
    file_priority_systems: dict[Path, set] = defaultdict(set)
    file_priority_top: dict[Path, Counter] = defaultdict(Counter)
    file_case_count: Counter = Counter()

    for path, c, line_no in iter_cases(scan_root):
        num = str(c.get("case_number") or f"L{line_no}")
        file_case_count[path] += 1

        # E1/W1 case_type
        ct = str(c.get("case_type") or "").strip()
        if not ct:
            add("error", "E1-case_type缺失", path, "case_type 字段缺失", num, line_no)
        elif ct.lower() not in VALID_CASE_TYPES:
            add("warning", "W1-case_type非法值", path,
                f"case_type={ct!r} 不在合法集 {sorted(VALID_CASE_TYPES)}", num, line_no)
        elif ct != ct.lower():
            add("warning", "W1-case_type非法值", path,
                f"case_type={ct!r} 大小写不规范（应小写）", num, line_no)

        # E2 priority + 文件级体系统计
        pri = str(c.get("priority") or "").strip()
        if not pri:
            add("error", "E2-priority缺失", path, "priority 字段缺失", num, line_no)
        else:
            low = pri.lower()
            if low in EN_PRIORITY:
                file_priority_systems[path].add("en")
                file_priority_top[path][low] += 1
            elif low in NUM_PRIORITY:
                file_priority_systems[path].add("num")
                file_priority_top[path][low] += 1
            else:
                add("warning", "W2-priority非法值", path,
                    f"priority={pri!r} 既非英文系(critical/high/...)也非数字系(P0/P1/...)", num, line_no)

        # E3/W4/W5/W10/W11 步骤结构与数量
        steps = c.get("test_case_steps")
        if isinstance(steps, list):
            n_steps = len(steps)
            if n_steps == 0:
                add("error", "E3-无步骤", path, "test_case_steps 为空——用例不可执行", num, line_no)
            elif n_steps == 1:
                add("warning", "W4-单步骤", path,
                    "仅 1 步——疑似操作与断言合并，检查是否丢失过程断言", num, line_no)
            elif n_steps > MAX_STEPS:
                add("warning", "W5-步骤过多", path,
                    f"{n_steps} 步 > {MAX_STEPS}——一条用例验证过多检查点，建议拆分", num, line_no)
        elif isinstance(steps, str) and steps.strip():
            add("warning", "W10-步骤非结构化", path,
                "test_case_steps 为字符串而非 [{step,result}] 数组——逐步预期结果缺失，断言粒度丢失", num, line_no)
        elif c.get("steps") or c.get("expected_results"):
            add("warning", "W11-旧schema", path,
                "使用旧字段名（steps/expected_results/title）——与现行 schema（test_case_steps）不一致", num, line_no)
        else:
            add("error", "E3-无步骤", path, "无任何步骤字段——用例不可执行", num, line_no)

        # W6 追溯编号
        remarks = str(c.get("remarks") or "")
        if not TRACE_RE.search(remarks):
            add("warning", "W6-无追溯编号", path,
                f"remarks 无 REQ-/FP-/F- 编号：{remarks[:40]!r}", num, line_no)

        # E4/W7 命名
        name = str(c.get("name") or "").strip()
        if not name:
            add("error", "E4-命名为空", path, "name 字段为空", num, line_no)
        elif len(name) > 60 or name.lower().startswith("test"):
            add("warning", "W7-命名不规范", path, f"名称过长或 test 开头：{name[:50]!r}", num, line_no)

    # 文件级：priority 双体系混用
    for path, systems in file_priority_systems.items():
        if len(systems) > 1:
            add("warning", "W8-priority双体系混用", path,
                f"文件内英文系与数字系并存（{file_case_count[path]} 条用例）——应统一为一套")

    # 文件级：critical/P0 通胀
    for path, counter in file_priority_top.items():
        total = file_case_count[path]
        top_n = counter.get("critical", 0) + counter.get("p0", 0)
        if total >= 5 and top_n / total > CRITICAL_INFLATION:
            add("warning", "W9-优先级通胀", path,
                f"critical/P0 占 {top_n}/{total}（{top_n * 100 // total}%）——分级失效，全是最高优先级等于没有优先级")

    return issues


def print_report(issues: list[dict]) -> None:
    by_rule = Counter((i["level"], i["rule"]) for i in issues)
    errors = sum(1 for i in issues if i["level"] == "error")
    print(f"{'ERROR' if errors else 'OK'}：{errors} error / {len(issues) - errors} warning\n")
    print("== 按规则统计 ==")
    for (level, rule), n in sorted(by_rule.items(), key=lambda x: -x[1]):
        print(f"  [{level:7}] {rule:24} {n:5}")
    print("\n== 违规最多文件 TOP 10 ==")
    by_file = Counter(i["file"] for i in issues)
    for f, n in by_file.most_common(10):
        print(f"  {n:4}  {f}")
    print("\n== error 明细（前 20 条）==")
    for i in [x for x in issues if x["level"] == "error"][:20]:
        print(f"  {i['file']}:{i['line']}  {i['case']}  {i['message']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="测试用例规范 lint")
    parser.add_argument("--path", type=Path, default=DEFAULT_SCAN)
    parser.add_argument("--json", action="store_true", help="机器可读输出（接 CI）")
    args = parser.parse_args()

    issues = lint(args.path)
    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=1))
    else:
        print_report(issues)
    sys.exit(1 if any(i["level"] == "error" for i in issues) else 0)


if __name__ == "__main__":
    main()
