"""Phase 3 模块自检 · 功能矩阵覆盖核对 · 真实 LLM 端到端验证脚本。

验证目标（对应提交 925fa7a 的密度双向锚定改造第 1+2 层）：

预置现场（登录认证模块，3 个 FP / 3 条用例）：
  FP-001 账号密码登录（2 test_point）——用例 001/002 显式标注且文本贴近 → 全命中
  FP-002 图片验证码校验（2 test_point）——用例 003 显式标注但措辞漂移 →
      test_point 疑似未覆盖 warning（软通道）
  FP-003 闲置会话自动登出（1 test_point）——零用例归属 → 零覆盖 error（硬拦截）

硬断言：
  H1  主 Agent 调用了 module_self_check_tool
  H2  调用 args 携带 project_identifier=PR-E2E-DENSITY
      （SYSTEM_PROMPT checkpoint 新契约 + 运行时上下文注入共同生效的证据；
       prompt 刻意不教参数名，模型须自发带上）
  H3  首轮矩阵核对（matrix_checked=True）抓出 FP-003 零用例覆盖 error
      容错：若模型在自检前已自行补设计 FP-003 用例（首轮自检直接通过），
      H3 记 SKIP——防线前置生效同样是正确行为，由 S1 承接证据
  H4  模型未无视 error：补充设计了 FP-003 用例（最终文件含 FP-003 引用）
      或最终输出对 FP-003 给出显式说明

软观察：
  S1  模型对覆盖 error 的处置路径（补用例并重跑自检 / 仅文字说明）
  S2  FP-002 的 test_point 措辞漂移 warning 出现（warning 通道实证）
  S3  补充用例的 remarks 标注了 FP-003（remarks 编号约定的遵守度）

运行（root venv，真实模型，预计 3-10 分钟）：
    d:/project/ai-test-agent/.venv/Scripts/python.exe backend/scripts/verify_phase3_matrix_coverage_e2e.py

说明：
- in-process 起 agent（make_agent 真实模型 + 真实中间件栈），不依赖运行中的
  LangGraph 服务，不影响线上会话；
- RAG MCP 工具加载被 mock（与验证目标无关）；
- 现场预置在 workspace 的 PR-E2E-DENSITY/phase3-density-e2e/ 会话目录
  （工具侧路径解析会叠加 project/thread 会话前缀，必须预置到带 thread 的目录），
  跑完保留供人工抽查；
- in-process 无 checkpointer，HITL interrupt 后无法 resume——产物在 interrupt
  前已生成，直接基于当前 state 断言（与 verify_phase4_branch_redundancy_e2e
  同款模式）。
"""
from __future__ import annotations

import asyncio
import json
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
from app.config.settings import settings  # noqa: E402

PROJECT_ID = "PR-E2E-DENSITY"
THREAD_ID = "phase3-density-e2e"
MODULE = "登录认证"
CASE_FILE_NAME = "test_cases_module_01_auth.jsonl"

_WORKSPACE_ROOT = Path(settings.testcase_workspace_root).resolve()
# 工具侧 apply_session_scope 会把纯文件名解析到 <project>/<thread>/ 下
SESSION_DIR = _WORKSPACE_ROOT / PROJECT_ID / THREAD_ID

# ─────────────────────────────────────────────────────────────────────────────
# 预置现场：功能矩阵 + 1 个用例文件（三种覆盖场景）
# ─────────────────────────────────────────────────────────────────────────────

FEATURES = [
    {
        "id": "FP-001",
        "module": MODULE,
        "feature": "账号密码登录",
        "test_points": ["正确账号密码登录成功并跳转首页", "错误密码拒绝登录并提示账号或密码错误"],
        "priority": "P0",
        "risk_level": "高",
        "test_type": ["功能"],
    },
    {
        "id": "FP-002",
        "module": MODULE,
        "feature": "图片验证码校验",
        "test_points": ["验证码有效期五分钟", "验证码连续错误三次锁定账号"],
        "priority": "P1",
        "risk_level": "中",
        "test_type": ["功能"],
    },
    {
        "id": "FP-003",
        "module": MODULE,
        "feature": "闲置会话自动登出",
        "test_points": ["页面闲置三十分钟后自动退出登录"],
        "priority": "P1",
        "risk_level": "中",
        "test_type": ["功能"],
    },
]

# 001/002 的文本与 FP-001 两个 test_point 高度对齐（真实场景：Phase 1 从需求
# 原文提炼 test_point，Phase 3 围绕它写用例）→ 全命中，不产生 warning。
# 003 显式标注 FP-002 但措辞漂移（"有效期五分钟" → "等待 6 分钟...已失效"）
# → bigram 重叠 < 0.6，触发 test_point 疑似未覆盖 warning。
# 三条用例的文本都不含 闲置/会话/登出/三十分钟 → FP-003 零归属 → error。
CASES = [
    {
        "name": "正确账号密码登录",
        "case_number": "TC-E2E-AUTH-001",
        "module": MODULE,
        "priority": "critical",
        "case_type": "functional",
        "remarks": "关联需求 REQ-LOGIN；覆盖 FP-001",
        "test_data": {"账号": "admin", "密码": "Admin@123"},
        "test_case_steps": [
            {
                "step": "在登录页输入正确账号密码 admin/Admin@123，点击登录",
                "result": "登录成功并跳转首页，顶部导航显示当前账号 admin",
            },
        ],
    },
    {
        "name": "错误密码拒绝登录",
        "case_number": "TC-E2E-AUTH-002",
        "module": MODULE,
        "priority": "high",
        "case_type": "functional",
        "remarks": "关联需求 REQ-LOGIN；覆盖 FP-001",
        "test_data": {"账号": "admin", "密码": "WrongPass1"},
        "test_case_steps": [
            {
                "step": "输入正确账号 admin 和错误密码 WrongPass1，点击登录",
                "result": "拒绝登录并提示账号或密码错误，页面停留在登录页",
            },
        ],
    },
    {
        "name": "验证码超期失效",
        "case_number": "TC-E2E-AUTH-003",
        "module": MODULE,
        "priority": "high",
        "case_type": "functional",
        "remarks": "关联需求 REQ-LOGIN；覆盖 FP-002",
        "test_data": {"账号": "admin", "等待时长": "6 分钟"},
        "test_case_steps": [
            {
                "step": "获取图片验证码后等待 6 分钟，再输入该验证码提交登录",
                "result": "提示验证码已失效，需重新获取验证码",
            },
        ],
    },
]

# 刻意不教参数名/不给答案：模型须按 SYSTEM_PROMPT 的 checkpoint 契约
# 自发携带 project_identifier 并处理覆盖 error。
PROMPT = f"""Phase 1（需求解析）与 Phase 2（测试策略）已完成并通过评审，功能矩阵已保存。
当前处于 Phase 3 用例设计阶段：「{MODULE}」模块的 3 条用例已设计完成并保存为
{CASE_FILE_NAME}。

请按 Phase 3 模块级 checkpoint 完成该模块的收尾自检；若自检发现问题，
按返回的 violations 修正后重新自检；全部通过后输出 ## 测试用例生成完成。

本任务无需 RAG 检索。"""


# ─────────────────────────────────────────────────────────────────────────────
# 断言辅助
# ─────────────────────────────────────────────────────────────────────────────

passed: list[str] = []
failed: list[str] = []
skipped: list[str] = []
observed: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    (passed if cond else failed).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if not cond and detail else ""))


def skip(name: str, reason: str):
    skipped.append(name)
    print(f"  [SKIP] {name}  -- {reason}")


def observe(name: str, ok: bool, detail: str = ""):
    observed.append(name)
    print(f"  [{'OK' if ok else 'WARN'}] {name}" + (f"  -- {detail}" if detail else ""))


def setup_fixtures() -> Path:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    (SESSION_DIR / "feature_matrix.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in FEATURES) + "\n",
        encoding="utf-8",
    )
    (SESSION_DIR / CASE_FILE_NAME).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in CASES) + "\n",
        encoding="utf-8",
    )
    print(f"现场预置完成：{SESSION_DIR}")
    return SESSION_DIR


def _parse_tool_payload(content) -> dict | None:
    """解析 module_self_check_tool ToolMessage 的 JSON payload。"""
    if isinstance(content, list):
        content = "".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        )
    if not isinstance(content, str) or not content.strip():
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    setup_fixtures()

    ctx = TestCaseGeneratorContext(
        project_identifier=PROJECT_ID,
        folder_id="",
        template_type="test_case",
        enable_rag=False,
        auto_approve_threshold=100.0,  # 关闭自动审批，interrupt 正常弹出
    )
    config = {"recursion_limit": 100, "configurable": {"thread_id": THREAD_ID}}

    print("\n=== 启动真实模型链路（make_agent in-process）===")
    async with make_agent() as agent:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": PROMPT}]},
            config=config,
            context=ctx,
        )

    if isinstance(result, dict) and result.get("__interrupt__"):
        print("\n=== 流程停在 HITL interrupt（预期行为，产物已生成，直接断言）===")

    messages = result.get("messages", []) if isinstance(result, dict) else []

    # ── 收集证据：工具调用序列 + 自检 ToolMessage ──
    tool_calls: list[tuple[str, dict]] = []
    self_check_payloads: list[dict] = []
    final_text = ""
    for msg in messages:
        for tc in getattr(msg, "tool_calls", None) or []:
            tool_calls.append((tc.get("name", ""), tc.get("args") or {}))
        if getattr(msg, "type", "") == "tool" and getattr(msg, "name", "") == "module_self_check_tool":
            payload = _parse_tool_payload(getattr(msg, "content", None))
            if payload is not None:
                self_check_payloads.append(payload)
        if getattr(msg, "type", "") == "ai":
            content = getattr(msg, "content", "")
            if isinstance(content, str) and content.strip():
                final_text = content

    print(f"\n工具调用序列（{len(tool_calls)} 次）：")
    print("  " + " → ".join(name for name, _ in tool_calls) if tool_calls else "  （无）")
    print(f"module_self_check_tool 调用 {len(self_check_payloads)} 轮")

    # ── 硬断言 ──
    print("\n=== 硬断言 ===")
    check("H1 module_self_check_tool 被调用", bool(self_check_payloads),
          f"工具调用序列：{[n for n, _ in tool_calls]}" if not self_check_payloads else "")

    sc_calls = [(n, a) for n, a in tool_calls if n == "module_self_check_tool"]
    h2_ok = any(str(a.get("project_identifier", "")).strip() == PROJECT_ID for _, a in sc_calls)
    check("H2 自检调用携带 project_identifier=PR-E2E-DENSITY（提示词契约生效）", h2_ok,
          f"实际 args：{[a for _, a in sc_calls]}" if sc_calls and not h2_ok else "")

    matrix_checked_any = any(p.get("matrix_checked") for p in self_check_payloads)
    fp003_error_any = any(
        p.get("matrix_checked")
        and any(
            v.get("level") == "error" and "FP-003" in " ".join(v.get("messages", []))
            for v in p.get("violations", [])
        )
        for p in self_check_payloads
    )
    if fp003_error_any:
        check("H3 矩阵核对抓出 FP-003 零用例覆盖 error", True)
    elif matrix_checked_any:
        # 矩阵核对执行了但没抓出 FP-003：若模型已前置补设计则为正确行为（SKIP），
        # 否则是工具核对失效（FAIL）
        final_cases_text = (SESSION_DIR / CASE_FILE_NAME).read_text(encoding="utf-8")
        extra_files = list(SESSION_DIR.glob("test_cases_module_*.jsonl"))
        fp003_pre_filled = "FP-003" in final_cases_text or any(
            f.name != CASE_FILE_NAME and "FP-003" in f.read_text(encoding="utf-8")
            for f in extra_files
        )
        if fp003_pre_filled:
            skip("H3 FP-003 零覆盖 error 未出现", "模型在自检前已自行补设计 FP-003——防线前置生效")
        else:
            check("H3 矩阵核对抓出 FP-003 零用例覆盖 error", False,
                  "matrix_checked=True 但未抓出零覆盖 FP，工具核对逻辑失效")
    else:
        check("H3 矩阵核对抓出 FP-003 零用例覆盖 error", False,
              "所有自检轮次 matrix_checked=False，矩阵未加载")

    # H4 模型未无视 error：补用例（文件中出现 FP-003 引用）或最终输出显式说明
    final_cases_text = (SESSION_DIR / CASE_FILE_NAME).read_text(encoding="utf-8")
    all_case_text = final_cases_text + "\n".join(
        f.read_text(encoding="utf-8")
        for f in SESSION_DIR.glob("test_cases_module_*.jsonl")
        if f.name != CASE_FILE_NAME
    )
    fp003_addressed_in_files = "FP-003" in all_case_text
    fp003_explained_in_output = "FP-003" in final_text
    check("H4 模型未无视覆盖 error（补设计用例或显式说明）",
          fp003_addressed_in_files or fp003_explained_in_output or not fp003_error_any,
          "FP-003 error 出现后模型既未补用例也未说明" if fp003_error_any else "")

    # ── 软观察 ──
    print("\n=== 软观察 ===")
    rechecked_after_error = fp003_error_any and len(self_check_payloads) >= 2
    observe("S1 模型对 error 的处置："
            + ("补设计后重跑自检" if rechecked_after_error else
               ("文字说明/其他" if fp003_explained_in_output else "见 H4")),
            rechecked_after_error or fp003_explained_in_output)

    fp002_warning_any = any(
        any(
            v.get("level") == "warning" and "疑似未覆盖" in " ".join(v.get("messages", []))
            and "FP-002" in " ".join(v.get("messages", []))
            for v in p.get("violations", [])
        )
        for p in self_check_payloads
    )
    observe("S2 FP-002 test_point 措辞漂移 warning 出现（warning 通道实证）", fp002_warning_any)

    observe("S3 补充用例 remarks 标注 FP-003", fp003_addressed_in_files)

    if self_check_payloads:
        print(f"\n首轮自检结果摘要：{json.dumps(self_check_payloads[0], ensure_ascii=False)[:1200]}")
    print(f"\n最终 AI 输出（前 1500 字符）：\n{'─' * 60}\n{final_text[:1500]}\n{'─' * 60}")

    # ── 汇总 ──
    print(f"\n{'=' * 60}")
    print(f"硬断言：{len(passed)} PASS / {len(failed)} FAIL / {len(skipped)} SKIP")
    if failed:
        print("FAIL 项：")
        for name in failed:
            print(f"  - {name}")
    print(f"软观察：{len(observed)} 项（见上，WARN 需人工判读）")
    print(f"产物目录：{SESSION_DIR}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
