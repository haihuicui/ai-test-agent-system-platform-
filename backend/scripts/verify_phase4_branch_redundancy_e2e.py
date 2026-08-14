"""Phase 4 分支覆盖导向 + 冗余审查新规 · 真实 LLM 端到端验证脚本。

验证目标（对应提交 2bc5b5d 的评审规则改造）：

新规则行为（本脚本核心断言/观察）：
  E1  最终评审报告含「冗余审查」小节（新模板强制小节，无冗余也须显式声明）
  E2  预埋同规则冗余对（TC-E2E-MENU-001 ↔ TC-E2E-MENU-002：步骤结构相同、
      仅数据表述不同）被冗余审查抓出
  E3  FP-001（P0 高风险、仅 3 条用例、分支全覆盖）不再被旧密度规则扣分
      ——报告不得对 FP-001 出现 "密度不足"/"≥6"/"仅 3 条" 类扣分措辞
      （旧规则下 3 条 <6 必被列系统性缺口）
  E4  FP-002（P0 高风险、2 条均正常流、41 字符越界拒绝分支零覆盖）被列
      分支覆盖缺口（新规则的核心防漏测职责）

链路回归（沿用 verify_phase4_review_contract.py 的断言面）：
  B1  主 Agent 调用 compute_coverage_report
  B2  主 Agent 调用 verify_review_citations
  B3  主 Agent 通过 task 启动 adversarial-reviewer 子代理
  A1  子代理逐模块写出 adversarial_review_m*.md
  A3  summary 含信任度评估

运行（root venv，真实 DeepSeek，预计 5-15 分钟）：
    d:/project/ai-test-agent/.venv/Scripts/python.exe backend/scripts/verify_phase4_branch_redundancy_e2e.py

说明：
- in-process 起 agent（make_agent 真实模型 + 真实中间件栈 + 真实子代理），
  不依赖运行中的 LangGraph 服务，不影响线上会话；
- RAG MCP 工具加载被 mock（与本次验证目标无关）；
- 现场隔离在 workspace 的 PR-E2E-BRANCH/ 项目目录，跑完保留供人工抽查；
- 返工铁律第 6 条（supplement 必要性声明）作用于 interrupt resume 后的返工
  阶段，in-process 无 checkpointer 无法 resume，不在本脚本验证范围内。
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
)

PROJECT_ID = "PR-E2E-BRANCH"

# ─────────────────────────────────────────────────────────────────────────────
# 预置现场：功能矩阵 + 3 个用例文件（针对新规则的三种场景）
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
        "test_points": ["40字符边界校验（41字符拒绝）", "空备注处理"],
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

# FP-001：3 条用例、两个 test_point 全覆盖（分支全覆盖）——旧规则会因 3<6 列密度不足，
# 新规则应判定达标。其中 MENU-001/002 为预埋同规则冗余对（步骤结构相同、仅数据表述不同）。
CASES_M01 = [
    {
        "name": "调试菜单含5个子项",
        "case_number": "TC-E2E-MENU-001",
        "module": "菜单结构重组",
        "priority": "critical",
        "case_type": "functional",
        "remarks": "关联 FP-001",
        "test_data": {"expected_items": "整机测试/单模块测试/队列进样/历史列表/老化调试"},
        "test_case_steps": [
            {"step": "展开「调试」菜单", "result": "显示整机测试/单模块测试/队列进样/历史列表/老化调试 5 个子项"},
        ],
    },
    {
        # 预埋冗余：与 MENU-001 验证同一规则（菜单含 5 子项），步骤结构相同、仅数据形式不同
        "name": "调试菜单子项数量与名称核对",
        "case_number": "TC-E2E-MENU-002",
        "module": "菜单结构重组",
        "priority": "high",
        "case_type": "functional",
        "remarks": "关联 FP-001",
        "test_data": {"expected_count": 5, "item_1": "整机测试", "item_2": "单模块测试", "item_3": "队列进样", "item_4": "历史列表", "item_5": "老化调试"},
        "test_case_steps": [
            {"step": "展开「调试」菜单，核对子项数量与名称", "result": "共 5 个子项，依次为整机测试/单模块测试/队列进样/历史列表/老化调试"},
        ],
    },
    {
        "name": "原调试更名老化调试",
        "case_number": "TC-E2E-MENU-003",
        "module": "菜单结构重组",
        "priority": "critical",
        "case_type": "functional",
        "remarks": "关联 FP-001",
        "test_data": {"old_name": "调试", "new_name": "老化调试"},
        "test_case_steps": [
            {"step": "查看侧边导航栏", "result": "原「调试」菜单显示为「老化调试」，不存在单独的「调试」菜单项"},
        ],
    },
]

# FP-002：2 条用例均为正常流——「41 字符越界拒绝」异常分支零覆盖。
# 新规则应列分支覆盖缺口（有"拒绝"规则却无拦截用例）；仅 2 条须辩护分支完整性。
CASES_M02 = [
    {
        "name": "备注40字符正常创建",
        "case_number": "TC-E2E-TASK-001",
        "module": "任务创建-备注",
        "priority": "critical",
        "case_type": "functional",
        "remarks": "关联 FP-002",
        "test_data": {"remark_40": "1234567890123456789012345678901234567890"},
        "test_case_steps": [
            {"step": "备注输入框输入 40 个字符并创建任务", "result": "创建成功，备注完整保存 40 字符"},
        ],
    },
    {
        "name": "空备注正常创建",
        "case_number": "TC-E2E-TASK-002",
        "module": "任务创建-备注",
        "priority": "high",
        "case_type": "functional",
        "remarks": "关联 FP-002",
        "test_data": {"remark": ""},
        "test_case_steps": [
            {"step": "备注留空并创建任务", "result": "创建成功，备注为空字符串"},
        ],
    },
]

CASES_M03 = [
    {
        "name": "谱图仅展示原始谱图",
        "case_number": "TC-E2E-CHART-001",
        "module": "谱图展示",
        "priority": "medium",
        "case_type": "functional",
        "remarks": "关联 FP-003",
        "test_data": {"sample": "SAMPLE-0001"},
        "test_case_steps": [
            {"step": "选择标本 SAMPLE-0001 查看谱图", "result": "谱图区域仅展示原始谱图，无其他类型谱图切换入口"},
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

请跳过 Phase 1-3，直接执行 Phase 4 质量评审。本次按标准模式执行完整流程：
四维度评分 + 交叉验证减分 + 隔离 Agent 评审 + 完整评审报告（严格按报告模板输出全部小节）。
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
    config = {"recursion_limit": 120, "configurable": {"thread_id": "phase4-branch-e2e-thread"}}

    print("\n=== 启动真实模型评审链路（make_agent in-process）===")
    async with make_agent() as agent:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": PROMPT}]},
            config=config,
            context=ctx,
        )

    # in-process 无 checkpointer，HITL interrupt 后无法 resume——
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

    # ── 硬断言：链路回归 ──
    print("\n=== 硬断言：链路回归 ===")
    check("B1 compute_coverage_report 被调用", "compute_coverage_report" in tool_calls)
    check("B2 verify_review_citations 被调用", "verify_review_citations" in tool_calls,
          "主 Agent 未做举证校验" if "verify_review_citations" not in tool_calls else "")
    check("B3 task 启动 adversarial-reviewer 子代理", "task" in tool_calls)
    check("A1 子代理逐模块写出 adversarial_review_m*.md（≥2 个）", len(review_files) >= 2,
          f"实际 {len(review_files)} 个")
    check("A3 summary 含信任度评估",
          bool(summary_files) and "信任度" in summary_files[0].read_text(encoding="utf-8"))

    # ── 硬断言：新规则契约 ──
    print("\n=== 硬断言：新规则契约 ===")
    check("E1 最终报告含「冗余审查」小节", "冗余审查" in final_text,
          "报告缺少新模板强制小节" if "冗余审查" not in final_text else "")

    # ── 软观察：新规则行为（人工判读） ──
    print("\n=== 软观察：新规则行为 ===")
    # E2 冗余对被抓：报告冗余审查小节或子代理产物同时提及两条用例编号
    review_corpus = "\n".join(f.read_text(encoding="utf-8") for f in review_files)
    e2_in_report = "TC-E2E-MENU-001" in final_text and "TC-E2E-MENU-002" in final_text
    e2_in_review = "TC-E2E-MENU-001" in review_corpus and "TC-E2E-MENU-002" in review_corpus
    observe("E2 预埋冗余对（MENU-001 ↔ MENU-002）被识别（报告或子代理产物）",
            e2_in_report or e2_in_review,
            f"报告={'命中' if e2_in_report else '未提'}，子代理产物={'命中' if e2_in_review else '未提'}")

    # E3 旧密度措辞回归检测：FP-001（3 条、分支全覆盖）不应再被密度规则扣分
    density_patterns = [r"密度不足", r"仅\s*3\s*条", r"≥\s*6", r"<\s*6", r"不足\s*6"]
    density_hits = [p for p in density_patterns if re.search(p, final_text)]
    observe("E3 FP-001（3 条分支全覆盖）未被旧密度规则扣分",
            not density_hits,
            f"命中旧措辞 {density_hits}" if density_hits else "报告无密度扣分措辞")

    # E4 FP-002 异常分支缺口被抓（41 字符拒绝分支零覆盖）
    e4_hit = "FP-002" in final_text and (
        "41" in final_text or "越界" in final_text or "拒绝" in final_text or "异常分支" in final_text
    )
    observe("E4 FP-002 异常分支缺口（41字符拒绝零覆盖）被抓出", e4_hit)

    # 附录逐条平铺的粗略信号（沿用原脚本 D2 观察）
    appendix_dump = bool(re.search(r"附录[^\n]*\n(\s*\|[^\n]*\n){3,}", final_text))
    observe("D2 报告未逐条平铺附录明细", not appendix_dump)

    print(f"\n最终评审报告（前 3000 字符）：\n{'─' * 60}\n{final_text[:3000]}\n{'─' * 60}")

    # 完整报告落盘（截断打印之外的完整证据，供回归比对与人工抽查）
    report_path = proj_dir / "phase4_review_report_final.md"
    report_path.write_text(final_text, encoding="utf-8")
    print(f"\n完整报告已落盘：{report_path}")

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
