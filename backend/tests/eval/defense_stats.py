"""防线有效性统计——量化中间件体系到底拦住了多少问题。

DIMENSIONS.md 第三层（过程质量）的第一个工具：不评用例产出，评防线本身。
数据源全部是平台运行留下的真实痕迹，零 LLM、零 token：

1. 对话历史（conversation_history/*.md）里的门禁事件：
   - 单条红线拦截（CaseQualityGateMiddleware："用例质量校验未通过"）
   - 批量自检拦截（ModuleSelfCheckMiddleware："模块级自检未通过"）
   - 自检调用总量与通过率（module_self_check_tool 的 "passed" 输出）
   - 自检警告数（passed=true 但 violations 非空的放行事件，summary 话术解析）
   - 规范提示回传数（warning 通道，2026-08-13 ffb6f3c 上线）
2. 对抗评审汇总文件（adversarial_review_*summary*.md）：
   - 严重缺陷/可改进项合计（解析"合计"表行）
   - 信任度评估分布（整体可信度：高/中/低）

用法（cwd = backend）：
    ./.venv/Scripts/python.exe -m tests.eval.defense_stats          # 文本报告
    ./.venv/Scripts/python.exe -m tests.eval.defense_stats --json   # 机器可读
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
TESTCASE_WS = BACKEND_ROOT / "workspace" / "testcase"
HISTORY_DIR = TESTCASE_WS / "conversation_history"

# ── 门禁事件话术（与中间件源码中的拦截文案一一对应）────────────────────
_SINGLE_BLOCK = "用例质量校验未通过"        # case_quality_middleware._precheck
_BATCH_BLOCK = "模块级自检未通过"          # module_self_check_middleware._precheck
_HYGIENE_NOTE = "规范提示（不影响本次创建）"  # case_quality_middleware._hygiene_note

# module_self_check_tool 输出："passed": true/false, "total": ...
_PASSED_RE = re.compile(r'"passed": (true|false), "total"')
# 自检 summary："共检查 8 条用例，P0 8 条；发现 1 个警告；自检通过"
_SUMMARY_RE = re.compile(r'"summary": "共检查 (\d+) 条用例，P0 (\d+) 条；发现 (\d+) 个警告')

# 评审汇总表合计行：| **合计** | **9** | **20** |
_TOTAL_ROW_RE = re.compile(r"\*\*合计\*\*\s*\|\s*\**(\d+)\**\s*\|\s*\**(\d+)\**")
# 另一种汇总格式（标题计数）：## 🔴 严重缺陷汇总（17 个）
_SEVERE_HEADER_RE = re.compile(r"严重缺陷汇总[（(](\d+)")
_IMPROVE_HEADER_RE = re.compile(r"可改进项汇总[（(](\d+)")
# 信任度：整体可信度：低 / **整体可信度：中**
_CONFIDENCE_RE = re.compile(r"整体可信度[：:\*]+\s*([低中高])")


def collect_gate_events() -> dict:
    """扫对话历史，统计门禁事件。"""
    files = sorted(HISTORY_DIR.glob("*.md")) if HISTORY_DIR.is_dir() else []
    events = {
        "conversations": len(files),
        "single_blocks": 0,       # 单条红线拦截
        "batch_blocks": 0,        # 批量自检拦截（中间件话术）
        "self_check_pass": 0,     # 自检通过（工具输出 passed:true）
        "self_check_fail": 0,     # 自检未通过（工具输出 passed:false）
        "cases_checked": 0,       # 自检累计检查用例数
        "self_check_warnings": 0,  # 自检发现但放行的警告数
        "hygiene_notes": 0,       # warning 通道回传数
    }
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        events["single_blocks"] += text.count(_SINGLE_BLOCK)
        events["batch_blocks"] += text.count(_BATCH_BLOCK)
        events["hygiene_notes"] += text.count(_HYGIENE_NOTE)
        for m in _PASSED_RE.finditer(text):
            events["self_check_pass" if m.group(1) == "true" else "self_check_fail"] += 1
        for m in _SUMMARY_RE.finditer(text):
            events["cases_checked"] += int(m.group(1))
            events["self_check_warnings"] += int(m.group(3))
    total_checks = events["self_check_pass"] + events["self_check_fail"]
    events["block_rate"] = (
        round(events["self_check_fail"] / total_checks * 100, 1) if total_checks else None
    )
    return events


def collect_review_stats() -> dict:
    """扫对抗评审汇总文件，统计缺陷发现与信任度。"""
    summaries = sorted(TESTCASE_WS.rglob("adversarial_review*summary*.md"))
    batches = []
    for f in summaries:
        text = f.read_text(encoding="utf-8", errors="replace")
        total = _TOTAL_ROW_RE.search(text)
        # 兼容标题计数格式（无合计表行的批次）
        severe_h = _SEVERE_HEADER_RE.search(text)
        improve_h = _IMPROVE_HEADER_RE.search(text)
        conf = _CONFIDENCE_RE.search(text)
        batches.append({
            "file": f.relative_to(TESTCASE_WS).as_posix(),
            "severe": int(total.group(1)) if total else (int(severe_h.group(1)) if severe_h else None),
            "improvements": int(total.group(2)) if total else (int(improve_h.group(1)) if improve_h else None),
            "confidence": conf.group(1) if conf else None,
        })
    return {
        "batch_count": len(batches),
        "severe_total": sum(b["severe"] for b in batches if b["severe"] is not None),
        "improvements_total": sum(b["improvements"] for b in batches if b["improvements"] is not None),
        "confidence_dist": {c: sum(1 for b in batches if b["confidence"] == c) for c in ("高", "中", "低")},
        "batches": batches,
    }


def render_text(gates: dict, reviews: dict) -> str:
    lines = [
        "防线有效性统计（数据源：对话历史 + 评审文件，零 token）",
        "",
        f"== 创建门禁（{gates['conversations']} 个会话）==",
        f"单条红线拦截（CaseQualityGate）：{gates['single_blocks']} 次",
        f"批量自检拦截（ModuleSelfCheck）：{gates['batch_blocks']} 次",
        f"模块自检调用：{gates['self_check_pass'] + gates['self_check_fail']} 次"
        f"（通过 {gates['self_check_pass']} / 拦截 {gates['self_check_fail']}，"
        f"拦截率 {gates['block_rate'] if gates['block_rate'] is not None else 'n/a'}%）",
        f"自检累计检查用例：{gates['cases_checked']} 条；发现警告放行：{gates['self_check_warnings']} 个",
        f"规范提示回传（warning 通道）：{gates['hygiene_notes']} 次"
        + ("（ffb6f3c 上线不久，暂无数据）" if not gates["hygiene_notes"] else ""),
        "",
        f"== 对抗评审（{reviews['batch_count']} 个批次）==",
        f"严重缺陷：{reviews['severe_total']} 个；可改进项：{reviews['improvements_total']} 个",
        f"信任度分布：高×{reviews['confidence_dist']['高']} "
        f"中×{reviews['confidence_dist']['中']} 低×{reviews['confidence_dist']['低']}",
    ]
    for b in reviews["batches"]:
        lines.append(
            f"  {b['file']}：严重 {b['severe']} / 改进 {b['improvements']} / 信任度 {b['confidence'] or '?'}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="防线有效性统计")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    gates = collect_gate_events()
    reviews = collect_review_stats()
    if args.json:
        print(json.dumps({"gates": gates, "reviews": reviews}, ensure_ascii=False, indent=1))
    else:
        print(render_text(gates, reviews))


if __name__ == "__main__":
    main()
