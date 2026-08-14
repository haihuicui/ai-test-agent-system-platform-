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

baseline 模式（存量冻结、只报新增——历史问题已确认不修的团队用法）：
    # 一次性：把当前存量违规冻结为基线
    ./.venv/Scripts/python.exe -m tests.eval.lint_cases --write-baseline
    # 日常/CI：只报基线之外的新增违规；新增 error 退出码 1，已消除的会计入"已修复"
    ./.venv/Scripts/python.exe -m tests.eval.lint_cases --baseline

退出码：有 error 级违规（baseline 模式下为新增 error）= 1，否则 0（warning 不阻断）。
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
BASELINE_PATH = Path(__file__).parent / "dataset" / "lint_baseline.json"

SKIP_PATTERNS = ("feature_matrix", "expected_result", "manifest", "conversation")

# ── 合法取值（大小写不敏感比较，报告里提示规范写法）─────────────────────
VALID_CASE_TYPES = {"functional", "security", "boundary", "exception",
                    "abnormal", "performance", "compatibility", "ui"}
EN_PRIORITY = {"critical", "high", "medium", "low"}
NUM_PRIORITY = {"p0", "p1", "p2", "p3"}
TRACE_RE = re.compile(r"REQ-|FP-|F-\d+")

MAX_STEPS = 10        # 超过该拆
CRITICAL_INFLATION = 0.5  # 文件内 critical/P0 占比超 50% 视为分级失效


def iter_cases(scan_root: Path, exclude_names: tuple[str, ...] = ()):
    """产出 (file_path, case_dict, line_no)。脏行跳过（与 harvest 同一容错口径）。
    exclude_names：路径段含其中任一字符串的文件不扫（如排除对照组会话目录）。"""
    for p in sorted(scan_root.rglob("*.jsonl")):
        if any(s in p.name.lower() for s in SKIP_PATTERNS):
            continue
        if exclude_names and any(seg in exclude_names for seg in p.parts):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not line.strip():
                continue
            try:
                yield p, json.loads(line), i
            except json.JSONDecodeError:
                continue


def lint(scan_root: Path, exclude_names: tuple[str, ...] = ()) -> list[dict]:
    scan_root = Path(scan_root).resolve()  # 统一绝对路径，relative_to 报告才稳
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

    for path, c, line_no in iter_cases(scan_root, exclude_names):
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


def fingerprint(issue: dict) -> str:
    """违规指纹：file|rule|case——case_number 稳定可跨行号漂移；
    文件级规则（case 为空）天然按 (file, rule) 去重。"""
    return f"{issue['file']}|{issue['rule']}|{issue['case']}"


def write_baseline(issues: list[dict]) -> None:
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "note": "存量违规冻结基线——历史问题不修，只拦新增。"
                "重生成：lint_cases --write-baseline（会接受当前全部存量）",
        "issues": sorted(fingerprint(i) for i in issues),
    }
    BASELINE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def load_baseline() -> set[str]:
    if not BASELINE_PATH.exists():
        sys.exit(f"基线不存在：{BASELINE_PATH}（先跑 --write-baseline 冻结存量）")
    return set(json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["issues"])


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
    parser.add_argument("--write-baseline", action="store_true",
                        help="把当前全部违规冻结为基线（确认存量不修时执行一次）")
    parser.add_argument("--baseline", action="store_true",
                        help="只报基线之外的新增违规（日常/CI 模式）")
    args = parser.parse_args()

    issues = lint(args.path)

    if args.write_baseline:
        write_baseline(issues)
        print(f"基线已冻结：{len(issues)} 条存量违规 → {BASELINE_PATH}")
        print("之后跑 lint_cases --baseline 只会报告新增违规。")
        return

    if args.baseline:
        baseline = load_baseline()
        current = {fingerprint(i): i for i in issues}
        new_issues = [i for fp, i in current.items() if fp not in baseline]
        fixed = baseline - set(current)
        if args.json:
            print(json.dumps({"new": new_issues, "fixed_count": len(fixed)},
                             ensure_ascii=False, indent=1))
        else:
            print(f"[baseline 模式] 基线 {len(baseline)} 条，已修复 {len(fixed)} 条，"
                  f"新增 {len(new_issues)} 条\n")
            if new_issues:
                print_report(new_issues)
            else:
                print("✅ 无新增违规——存量问题未恶化")
        sys.exit(1 if any(i["level"] == "error" for i in new_issues) else 0)

    if args.json:
        print(json.dumps(issues, ensure_ascii=False, indent=1))
    else:
        print_report(issues)
    sys.exit(1 if any(i["level"] == "error" for i in issues) else 0)


if __name__ == "__main__":
    main()
