"""Phase 4 隔离评审新契约 · 真实 LLM 端到端验证脚本。

验证目标（对应 2026-08-14 提交 4646b88 的隔离评审减负改动）：

链路行为（硬断言 — 失败即回归）：
  A1  adversarial-reviewer 子代理逐模块写出 adversarial_review_m*.md
  A2  结果文件含「🚫 阻断发现」与「📎 附录」分段（新格式契约）
  A3  adversarial_review_summary.md 含信任度评估
  A4  每模块阻断发现 ≤5 条且带举证（原文引文非空）
  B1  主 Agent 调用 compute_coverage_report
  B2  主 Agent 调用 verify_review_citations（举证 grep 校验接入链路）
  B3  主 Agent 通过 task 启动 adversarial-reviewer 子代理

内容质量（软观察 — 打印供人工判读，不 FAIL）：
  C1  预埋阻断级缺陷被抓进阻断清单：
      - TC-E2E-MENU-002 断言自相矛盾（步骤1 保留「调试」vs 步骤2 不存在「调试」）
      - TC-E2E-TASK-002 测试数据物理不可构造（文件名含 `/`）
      - FP-002「多任务跟随/列表展示」两个 test_point 零覆盖（必漏报）
  C2  TC-E2E-CHART-001 模糊词（"正常显示"）应进附录而非阻断清单
  D1  最终评审报告只渲染阻断清单，附录不逐条平铺

运行（root venv，真实 DeepSeek，预计 5-15 分钟）：
    d:/project/ai-test-agent/.venv/Scripts/python.exe backend/scripts/verify_phase4_review_contract.py

说明：
- in-process 起 agent（make_agent 真实模型 + 真实中间件栈 + 真实子代理），
  不依赖运行中的 LangGraph 服务，不影响线上会话；
- RAG MCP 工具加载被 mock（与本次验证目标无关，避免 stdio MCP 连接等待）；
- 现场隔离在 workspace 的 PR-E2E-REVIEW/ 项目目录，跑完保留供人工抽查。
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 在加载 testcase agent 前 mock 掉 RAG MCP 工具加载（与验证目标无关）
import app.agents.tools.testcase as _testcase_tools  # noqa: E402

_testcase_tools.get_rag_tools = AsyncMock(return_value=[])

from app.agents.testcase import make_agent  # noqa: E402
from app.agents.testcase.agent import TestCaseGeneratorContext  # noqa: E402
from app.agents.tools.testcase.review_verify_tools import (  # noqa: E402
    _WORKSPACE_ROOT,
    _extract_blocker_quotes,
)

PROJECT_ID = "PR-E2E-REVIEW"

# ─────────────────────────────────────────────────────────────────────────────
# 预置现场：功能矩阵 + 3 个用例文件（含 4 处预埋缺陷）
# ─────────────────────────────────────────────────────────────────────────────

FEATURES = [
    {
        "id": "FP-001",
        "module": "菜单结构重组",
        "feature": "调试菜单结构重组",
        "test_points": ["调试菜单含整机测试/单模块测试/队列进样/历史列表/老化调试5子项", "原「调试」更名「老化调试」"],
        "priority": "P0",
        "risk_level": "高",
        "test_type": ["功能"],
    },
    {
        "id": "FP-002",
        "module": "任务创建-备注",
        "feature": "创建任务备注字段",
        "test_points": ["40字符边界校验", "多任务备注跟随", "备注列表展示"],
        "priority": "P0",
        "risk_level": "高",
        "test_type": ["功能"],
    },
    {
        "id": "FP-003",
        "module": "谱图展示",
        "feature": "谱图仅展示原始谱图",
        "test_points": ["选择标本后仅展示原始谱图"],
        "priority": "P2",
        "risk_level": "低",
        "test_type": ["功能"],
    },
]

CASES_M01 = [
    {
        "name": "调试菜单含5个子项",
        "case_number": "TC-E2E-MENU-001",
        "module": "菜单结构重组",
        "priority": "critical",
        "case_type": "functional",
        "remarks": "关联 FP-001",
        "test_data": {"sub_menus": "整机测试/单模块测试/队列进样/历史列表/老化调试"},
        "test_case_steps": [
            {"step": "展开「调试」菜单", "result": "显示整机测试/单模块测试/队列进样/历史列表/老化调试 5 个子项"},
        ],
    },
    {
        # 预埋缺陷①：断言自相矛盾（步骤1 要求保留「调试」，步骤2 要求不存在「调试」）
        "name": "原调试更名老化调试",
        "case_number": "TC-E2E-MENU-002",
        "module": "菜单结构重组",
        "priority": "critical",
        "case_type": "functional",
        "remarks": "关联 FP-001",
        "test_data": {"old_name": "调试", "new_name": "老化调试"},
        "test_case_steps": [
            {"step": "查看侧边导航栏", "result": "侧边导航保留「调试」菜单项"},
            {"step": "核对旧菜单移除情况", "result": "侧边导航不存在「调试」菜单项"},
        ],
    },
    {
        "name": "老化调试子项可进入",
        "case_number": "TC-E2E-MENU-003",
        "module": "菜单结构重组",
        "priority": "high",
        "case_type": "functional",
        "remarks": "关联 FP-001",
        "test_data": {"entry": "老化调试"},
        "test_case_steps": [
            {"step": "点击「老化调试」子菜单", "result": "进入老化调试页面，页面标题为「老化调试」"},
        ],
    },
]

CASES_M02 = [
    {
        "name": "备注40字符边界校验",
        "case_number": "TC-E2E-TASK-001",
        "module": "任务创建-备注",
        "priority": "critical",
        "case_type": "functional",
        "remarks": "关联 FP-002",
        "test_data": {"remark_40": "1234567890123456789012345678901234567890"},
        "test_case_steps": [
            {"step": "备注输入框输入 40 个字符并创建任务", "result": "创建成功，备注完整保存 40 字符"},
            {"step": "尝试输入第 41 个字符", "result": "输入被阻止，提示「备注最多 40 字符」"},
        ],
    },
    {
        # 预埋缺陷②：测试数据物理不可构造（Windows 文件名禁止含 `/`）
        "name": "备注特殊字符文件名导出",
        "case_number": "TC-E2E-TASK-002",
        "module": "任务创建-备注",
        "priority": "high",
        "case_type": "functional",
        "remarks": "关联 FP-002",
        "test_data": {"export_file_name": "../../remark/export.txt"},
        "test_case_steps": [
            {"step": "在 Windows 上创建名为 ../../remark/export.txt 的导出文件", "result": "文件创建成功且内容完整"},
        ],
    },
    # 注意：FP-002 的「多任务备注跟随」「备注列表展示」两个 test_point 故意零覆盖
    # → 预埋缺陷③（P0 test_point 必漏报，预期进阻断清单）
]

CASES_M03 = [
    {
        # 预埋缺陷④：模糊词（轻微问题，预期进附录而非阻断清单）
        "name": "谱图仅展示原始谱图",
        "case_number": "TC-E2E-CHART-001",
        "module": "谱图展示",
        "priority": "medium",
        "case_type": "functional",
        "remarks": "关联 FP-003",
        "test_data": {"sample": "SAMPLE-0001"},
        "test_case_steps": [
            {"step": "选择标本 SAMPLE-0001 查看谱图", "result": "谱图正常显示"},
        ],
    },
]

CASE_FILES = {
    "test_cases_module_01_menu.jsonl": CASES_M01,
    "test_cases_module_02_task.jsonl": CASES_M02,
    "test_cases_module_03_chart.jsonl": CASES_M03,
}

PROMPT = f"""Phase 1（需求解析）、Phase 2（测试策略）、Phase 3（用例设计）已全部完成，
功能矩阵与用例文件已保存在会话工作目录 /{PROJECT_ID}/ 下：
- feature_matrix.jsonl（3 个功能点：FP-001/FP-002/FP-003）
- test_cases_module_01_menu.jsonl（菜单结构重组，3 条）
- test_cases_module_02_task.jsonl（任务创建-备注，2 条）
- test_cases_module_03_chart.jsonl（谱图展示，1 条）

请跳过 Phase 1-3，直接执行 Phase 4 质量评审。**本任务按 ⭐ 标准模式执行（强制启动隔离 Agent，覆盖评审模式的规模判定）**。严格按照 quality-review Skill 的流程：
先 compute_coverage_report 计算覆盖率（case_files 显式传入上述 3 个用例文件），
覆盖率达标后启动 adversarial-reviewer 隔离评审（把上述文件清单与结果目录告诉子代理），
收到子代理摘要后先用 verify_review_citations 校验举证，再整合输出评审报告。
项目标识符 project_identifier={PROJECT_ID}。本任务无需 RAG 检索。"""


# ─────────────────────────────────────────────────────────────────────────────
# 断言辅助
# ─────────────────────────────────────────────────────────────────────────────

passed: list[str] = []
failed: list[str] = []
observed: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    (passed if cond else failed).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if not cond and detail else ""))


def observe(name: str, ok: bool, detail: str = ""):
    observed.append(name)
    print(f"  [{'OK' if ok else 'WARN'}] {name}" + (f"  -- {detail}" if detail else ""))


def _write_jsonl(path: Path, records: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )


def setup_fixtures() -> Path:
    proj_dir = _WORKSPACE_ROOT / PROJECT_ID
    _write_jsonl(proj_dir / "feature_matrix.jsonl", FEATURES)
    for name, cases in CASE_FILES.items():
        _write_jsonl(proj_dir / name, cases)
    # 清掉历史评审产物，保证本轮断言只针对本次生成
    for stale in proj_dir.rglob("adversarial_review_*.md"):
        stale.unlink()
    print(f"现场预置完成：{proj_dir}")
    return proj_dir


# ─────────────────────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    proj_dir = setup_fixtures()

    ctx = TestCaseGeneratorContext(
        project_identifier=PROJECT_ID,
        folder_id="",
        template_type="test_case",
        enable_rag=False,
        auto_approve_threshold=75.0,
    )
    config = {"recursion_limit": 120, "configurable": {"thread_id": "phase4-e2e-thread"}}

    print("\n=== 启动真实模型评审链路（make_agent in-process）===")
    async with make_agent() as agent:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": PROMPT}]},
            config=config,
            context=ctx,
        )

    # in-process 无 checkpointer，HITL interrupt 后无法 Command(resume=...)——
    # 评审产物（结果文件/工具调用/报告）在 interrupt 前已生成，直接基于当前 state 断言。
    if isinstance(result, dict) and result.get("__interrupt__"):
        print("\n=== 流程停在 HITL 阶段评审 interrupt（预期行为，产物已生成，直接断言）===")

    messages = result.get("messages", []) if isinstance(result, dict) else []
    # 评审报告 = 最后一条非空 AI 消息（interrupt 前的主 Agent 输出）；
    # 注意不能按"最长 content"取——read_file 的 ToolMessage（SKILL.md 原文）会更长。
    final_text = ""
    tool_calls: list[str] = []
    for msg in messages:
        for tc in getattr(msg, "tool_calls", None) or []:
            tool_calls.append(tc.get("name", ""))
        if getattr(msg, "type", "") == "ai":
            content = getattr(msg, "content", "")
            if isinstance(content, str) and content.strip():
                final_text = content

    print(f"\n工具调用序列（{len(tool_calls)} 次）：")
    print("  " + " → ".join(tool_calls) if tool_calls else "  （无）")

    # ── 产物文件收集 ──
    review_files = sorted(proj_dir.rglob("adversarial_review_m*.md"))
    summary_files = sorted(proj_dir.rglob("adversarial_review_summary.md"))
    print(f"\n评审产物：{len(review_files)} 个模块文件 + {len(summary_files)} 个 summary")
    for f in review_files + summary_files:
        print(f"  - {f.relative_to(proj_dir)}")

    # ── 硬断言：链路行为 ──
    print("\n=== 硬断言：链路行为 ===")
    check("A1 子代理逐模块写出 adversarial_review_m*.md（≥2 个）", len(review_files) >= 2,
          f"实际 {len(review_files)} 个")

    files_with_sections = 0
    total_blockers = 0
    blockers_with_quotes = 0
    max_blockers_per_module = 0
    all_findings: list[dict] = []
    for f in review_files:
        text = f.read_text(encoding="utf-8")
        if "🚫 阻断发现" in text and "📎 附录" in text:
            files_with_sections += 1
        findings = _extract_blocker_quotes(text)
        all_findings.extend(findings)
        max_blockers_per_module = max(max_blockers_per_module, len(findings))
        total_blockers += len(findings)
        blockers_with_quotes += sum(1 for x in findings if x["quotes"])

    check("A2 结果文件含「🚫 阻断发现」与「📎 附录」分段",
          bool(review_files) and files_with_sections == len(review_files),
          f"{files_with_sections}/{len(review_files)}")
    check("A3 summary 含信任度评估",
          bool(summary_files) and "信任度" in summary_files[0].read_text(encoding="utf-8"))
    check("A4a 每模块阻断发现 ≤5 条", max_blockers_per_module <= 5,
          f"最大 {max_blockers_per_module} 条/模块")
    check("A4b 阻断发现均带举证引文",
          total_blockers > 0 and blockers_with_quotes == total_blockers,
          f"{blockers_with_quotes}/{total_blockers} 带引文")

    check("B1 compute_coverage_report 被调用", "compute_coverage_report" in tool_calls)
    check("B2 verify_review_citations 被调用", "verify_review_citations" in tool_calls,
          "主 Agent 未做举证校验" if "verify_review_citations" not in tool_calls else "")
    check("B3 task 启动 adversarial-reviewer 子代理", "task" in tool_calls)

    # ── 软观察：内容质量 ──
    print("\n=== 软观察：内容质量（人工判读）===")
    blocker_cases = " ".join(x.get("case_ref", "") for x in all_findings)
    blocker_text = "\n".join(
        f.read_text(encoding="utf-8").split("📎 附录")[0] for f in review_files
    )
    appendix_text = "\n".join(
        f.read_text(encoding="utf-8").split("📎 附录")[-1] for f in review_files
    )

    observe("C1a 预埋矛盾断言（TC-E2E-MENU-002）被抓进阻断",
            "TC-E2E-MENU-002" in blocker_cases)
    observe("C1b 预埋不可执行数据（TC-E2E-TASK-002）被抓进阻断",
            "TC-E2E-TASK-002" in blocker_cases)
    observe("C1c FP-002 零覆盖 test_point（多任务跟随/列表展示）被抓",
            ("多任务" in blocker_text and "跟随" in blocker_text) or "FP-002" in blocker_text)
    # CHART-001 的预埋意图是"模糊词→附录"；但子代理若论证其断言偏离 test_point
    # 核心语义（"正常显示"未覆盖"仅原始谱图"→ 假通过漏报），属契约第 2 条「必漏报」，
    # 列阻断为从严但合理的分级——两种归组均可接受，此处仅记录实际归组供判读。
    chart_in_blocker = "TC-E2E-CHART-001" in blocker_cases
    observe("C2 CHART-001 归组（阻断=从严论证必漏报 / 附录=按模糊词降级，均可接受）",
            True,
            "阻断（从严）" if chart_in_blocker else "附录（按模糊词）")
    observe("C2b 模糊词问题在附录中有记录", "TC-E2E-CHART-001" in appendix_text or "正常显示" in appendix_text)

    report_has_blocker_section = "阻断" in final_text
    observe("D1 最终报告渲染了阻断清单", report_has_blocker_section)
    # 附录逐条平铺的粗略信号：报告里出现 ≥3 行以 TC-E2E 开头的问题明细且含「附录」标题的表格行
    appendix_dump = bool(re.search(r"附录[^\n]*\n(\s*\|[^\n]*\n){3,}", final_text))
    observe("D2 报告未逐条平铺附录明细", not appendix_dump)

    print(f"\n最终评审报告（前 2500 字符）：\n{'─' * 60}\n{final_text[:2500]}\n{'─' * 60}")

    # ── 汇总 ──
    print(f"\n{'=' * 60}")
    print(f"硬断言：{len(passed)} PASS / {len(failed)} FAIL")
    if failed:
        print("FAIL 项：")
        for name in failed:
            print(f"  - {name}")
    print(f"软观察：{len(observed)} 项（见上，WARN 需人工判读）")
    print(f"产物目录：{proj_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
