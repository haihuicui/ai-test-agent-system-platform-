"""轨迹审计 CLI：对 thread 消息转储批量执行轨迹规则。

与 lint_cases 同哲学：
- 零 token、秒级，可进 pre-push hook；
- 门禁范围只覆盖 golden 样本（文件名 *.golden.json，人工确认过流程合规的
  标杆轨迹）——golden 出现 error 级违规 = 防线或规则被破坏，阻断；
- 非 golden 样本（harvest 来的真实翻车/历史轨迹）只报告不阻断，
  用于观察防线绕过率趋势。

用法（cwd = backend）：
    ./.venv/Scripts/python.exe -m tests.eval.traj_audit                 # 文本报告
    ./.venv/Scripts/python.exe -m tests.eval.traj_audit --json          # 机器可读
    ./.venv/Scripts/python.exe -m tests.eval.traj_audit --dir <目录>    # 指定样本目录
    ./.venv/Scripts/python.exe -m tests.eval.traj_audit --agent web     # 强制 Agent 类型（跳过自动识别）
    ./.venv/Scripts/python.exe -m tests.eval.traj_audit file.json       # 审计单个文件
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tests.eval.traj_extract import detect_agent, extract
from tests.eval.traj_rules import RULES_BY_AGENT, run_rules

DEFAULT_DIR = Path(__file__).resolve().parent / "dataset" / "trajectories"


def audit_file(path: Path, agent_override: str = "") -> dict:
    """审计单个转储文件，返回结构化结果。"""
    try:
        messages = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {"file": path.name, "agent": "unknown", "error": f"解析失败: {exc}", "violations": []}
    if not isinstance(messages, list):
        return {"file": path.name, "agent": "unknown", "error": "转储不是消息数组", "violations": []}

    traj = extract(messages)
    agent = agent_override or detect_agent(traj, path.name)
    violations = run_rules(traj, agent) if agent != "unknown" else []
    return {
        "file": path.name,
        "agent": agent,
        "golden": path.stem.endswith(".golden"),
        "messages": len(messages),
        "tool_calls": len(traj.calls),
        "violations": [
            {"rule": v.rule_id, "severity": v.severity, "message": v.message, "at": v.msg_index}
            for v in violations
        ],
    }


def render_text(results: list[dict]) -> str:
    lines = [
        f"轨迹审计（{len(results)} 条轨迹，零 token）",
        "",
        f"已注册规则：" + " / ".join(
            f"{agent}:{len(rules)}" for agent, rules in sorted(RULES_BY_AGENT.items())
        ),
        "",
    ]
    total_err = total_warn = 0
    for r in results:
        if r.get("error"):
            lines.append(f"⚠️ {r['file']}：{r['error']}")
            continue
        errs = [v for v in r["violations"] if v["severity"] == "error"]
        warns = [v for v in r["violations"] if v["severity"] == "warning"]
        total_err += len(errs)
        total_warn += len(warns)
        tag = " [golden]" if r.get("golden") else ""
        status = "✅" if not errs else "❌"
        lines.append(
            f"{status} {r['file']}{tag} agent={r['agent']} "
            f"消息 {r['messages']} / 工具调用 {r['tool_calls']} / "
            f"error {len(errs)} / warning {len(warns)}"
        )
        for v in r["violations"]:
            loc = f"（消息 #{v['at']}）" if v["at"] is not None else ""
            lines.append(f"    [{v['rule']}] {v['severity']}: {v['message']}{loc}")
    lines += [
        "",
        f"合计：error {total_err} / warning {total_warn}"
        f"（golden 样本 error > 0 时退出码 1）",
    ]
    return "\n".join(lines)


def main() -> None:
    # hook 环境默认 GBK 控制台，✅/❌ 会炸 UnicodeEncodeError（与 pre-push 同坑）
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    parser = argparse.ArgumentParser(description="Agent 轨迹合规审计")
    parser.add_argument("files", nargs="*", help="指定转储文件（缺省扫描默认样本目录）")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="样本目录")
    parser.add_argument("--agent", default="", choices=["", "testcase", "web", "api"],
                        help="强制 Agent 类型（跳过自动识别）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    paths = ([Path(f) for f in args.files] if args.files
             else sorted(p for p in args.dir.glob("*.json") if not p.name.startswith(".")))
    if not paths:
        print(f"未找到轨迹样本（{args.dir}）。先跑 tests.eval.traj_harvest 采集。")
        sys.exit(0)

    results = [audit_file(p, args.agent) for p in paths]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
    else:
        print(render_text(results))

    golden_errors = sum(
        1 for r in results if r.get("golden")
        for v in r["violations"] if v["severity"] == "error"
    )
    if golden_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
