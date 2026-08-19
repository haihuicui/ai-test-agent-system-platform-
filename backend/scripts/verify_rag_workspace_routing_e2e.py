"""PR-1 会话 RAG workspace 路由 · 端到端验证脚本。

验证目标（多项目知识库隔离的平台 Agent 链路）：

  PR-1 会话 → _wrap_rag_tools_with_session_space 注入 space_id=PR-1
  → 103 rag-server 写 LIGHTRAG-WORKSPACE 头 → 103 lightrag 补丁版路由 PR_1 实例

硬断言：
  H1  Agent 至少发起一次 rag_query_data / rag_query 调用
  H2  「登录流程」查询的原始工具返回命中 PR_1 库特征内容（登录锁定/30 分钟/登录按钮）
  H3  「支付流程」查询的原始工具返回**不含** PR_2 库特征内容（购物车/退款）
      ——PR-1 会话不可见 PR-2 数据（反向隔离）

现场说明：
  PR_1 库现有「登录流程测试文档」（8-19 验证素材：密码错误 5 次锁定 30 分钟等）；
  PR_2 库现有「支付流程测试文档」（购物车/退款 7 个工作日）；默认库为空。
  本脚本不写入任何数据（rag_* 全只读），无现场清理负担。

运行（root venv，真实模型，预计 1-3 分钟）：
    d:/project/ai-test-agent/.venv/Scripts/python.exe backend/scripts/verify_rag_workspace_routing_e2e.py

说明：
- in-process 起 agent（make_agent 真实模型 + 真实中间件栈 + **真实 RAG 工具链**——
  与既有 verify_* 脚本不同，本验证目标就是 RAG 链路，不得 mock）；
- 用户消息引导模型只做检索不进 Phase 流程，recursion_limit 兜底；
- 若停在 HITL interrupt 无碍断言（证据在消息流里）。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from app.agents.testcase import make_agent  # noqa: E402
from app.agents.testcase.agent import TestCaseGeneratorContext  # noqa: E402

PROJECT_ID = "PR-1"
THREAD_ID = "e2e-rag-ws-routing"

PROMPT = (
    "请直接用 rag_query_data 工具分别检索两个主题（各调一次，mode 用 mix）：\n"
    "1）登录流程\n"
    "2）支付流程\n"
    "然后原样概述两次检索各自返回了什么。本轮只做检索验证，不要生成测试用例、"
    "不要进入需求分析流程。"
)

# PR_1 库（登录流程测试文档）特征词：命中其一即视为检索到 PR_1 内容
PR1_MARKERS = ("锁定", "30 分钟", "30分钟", "登录按钮")
# PR_2 库（支付流程测试文档）特征词：PR-1 会话的支付查询结果中**不得**出现
PR2_MARKERS = ("购物车", "退款", "7个工作日", "7 个工作日")


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            c.get("text", "") for c in content if isinstance(c, dict)
        )
    return str(content or "")


async def main() -> int:
    ctx = TestCaseGeneratorContext(
        project_identifier=PROJECT_ID,
        folder_id="",
        template_type="test_case",
        enable_rag=True,                # 关键：真实 RAG 链路（区别于既有 verify 脚本）
        auto_approve_threshold=100.0,   # 关闭自动审批
    )
    # config.configurable 显式携带 project_identifier：模拟 LangGraph 平台
    # 把 run context 合并进 configurable 的行为（in-process ainvoke 不做此合并，
    # 而包装器 get_session_project() 优先读 config 键——平台原生键是唯一可靠
    # 通道，见 memory: langgraph-cross-node-context-loss）
    config = {
        "recursion_limit": 30,
        "configurable": {"thread_id": THREAD_ID, "project_identifier": PROJECT_ID},
    }

    print("\n=== 启动真实链路：PR-1 会话 + 真实 rag 工具（103 中间层）===")
    async with make_agent() as agent:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": PROMPT}]},
            config=config,
            context=ctx,
        )

    if isinstance(result, dict) and result.get("__interrupt__"):
        print("（流程停在 interrupt，证据已在消息流中，继续断言）")

    messages = result.get("messages", []) if isinstance(result, dict) else []

    # ── 收集证据：rag 工具调用 + 原始工具返回 ──
    rag_calls: list[tuple[str, dict]] = []
    rag_returns: list[tuple[str, str]] = []  # (tool_name, content)
    for msg in messages:
        for tc in getattr(msg, "tool_calls", None) or []:
            name = tc.get("name", "")
            if name.startswith("rag_"):
                rag_calls.append((name, tc.get("args") or {}))
        if getattr(msg, "type", "") == "tool" and (getattr(msg, "name", "") or "").startswith("rag_"):
            rag_returns.append((msg.name, _text_of(getattr(msg, "content", ""))))

    print(f"\n=== rag 工具调用 {len(rag_calls)} 次 ===")
    for name, args in rag_calls:
        print(f"  {name}: query={str(args.get('query'))[:40]!r} space_id={args.get('space_id')!r}")

    # 完整返回 dump 供事后分析
    dump_path = BACKEND_ROOT / "scripts" / "rag_routing_e2e_dump.json"
    import json as _json
    dump_path.write_text(_json.dumps(
        {"calls": [(n, a) for n, a in rag_calls], "returns": rag_returns},
        ensure_ascii=False, indent=2,
    ), encoding="utf-8")
    print(f"（完整返回已 dump: {dump_path}）")

    # ── 按查询主题把返回内容分组 ──
    # tool 消息与 tool_call 按顺序对应：登录查询的调用在前、支付在后（按 PROMPT 顺序）。
    login_blob, pay_blob = "", ""
    for (_name, args), (_tname, content) in zip(
        [c for c in rag_calls if "query" in c[1]], rag_returns
    ):
        q = str(args.get("query", ""))
        if "登录" in q:
            login_blob += content
        elif "支付" in q:
            pay_blob += content
    # 兜底：若分组失败（模型合并查询等），合并全部返回用于双向检查
    all_blob = "".join(c for _, c in rag_returns)

    failures = 0

    # H1: 至少一次 rag 查询调用
    h1 = any(n in ("rag_query_data", "rag_query") for n, _ in rag_calls)
    print(f"[{'PASS' if h1 else 'FAIL'}] H1: 发起了 rag_query_data/rag_query 调用")
    failures += 0 if h1 else 1

    # H2: 登录查询命中 PR_1 内容
    login_hit = any(m in login_blob for m in PR1_MARKERS)
    print(f"[{'PASS' if login_hit else 'FAIL'}] H2: 登录查询命中 PR_1 库特征内容"
          + ("" if login_hit else f"（登录返回前 200 字：{login_blob[:200]!r}）"))
    failures += 0 if login_hit else 1

    # H3: 支付查询不含 PR_2 内容（反向隔离）
    pay_leak_src = pay_blob if pay_blob else all_blob if not login_blob else ""
    h3_checked = bool(pay_blob)
    pay_leak = any(m in pay_blob for m in PR2_MARKERS) if h3_checked else None
    if not h3_checked:
        print("[SKIP] H3: 模型未发起独立的支付查询（检查合并返回中 PR_2 特征词）")
        merged_leak = any(m in all_blob for m in PR2_MARKERS)
        print(f"[{'PASS' if not merged_leak else 'FAIL'}] H3': 全量返回不含 PR_2 库特征内容")
        failures += 0 if not merged_leak else 1
    else:
        print(f"[{'PASS' if not pay_leak else 'FAIL'}] H3: 支付查询返回不含 PR_2 库特征内容"
              + ("" if not pay_leak else f"（支付返回前 200 字：{pay_blob[:200]!r}）"))
        failures += 0 if not pay_leak else 1

    print(f"\n=== {'全部通过' if failures == 0 else f'{failures} 项失败'} ===")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
