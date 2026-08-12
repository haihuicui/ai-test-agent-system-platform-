"""端到端验证脚本：驱动 web_agent 走完 生成→意图确认→执行邀约→执行→报告 全链路。

用法：PYTHONPATH=backend .venv/Scripts/python.exe scripts/_e2e_web_verify.py
观察点：
- langgraph_server.log 中 [WebMCPAgent] / [Web Script Execution] 关键行
- backend/workspace/web_mcp/playwright.config.ss-*.js 是否生成且含 storageState
- 执行命令是否携带 --config
"""

import asyncio
import json
import sys

# Windows 控制台默认 GBK，AI 消息含 emoji 时 print 会炸
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from langgraph_sdk import get_client

AGENT_URL = "http://localhost:2026"
PROJECT = "PR-1"
REQUIREMENT = (
    "执行 WF-1002 功能下 user-login 子功能的 Web 测试脚本，并保存测试报告。"
)

MAX_INTERRUPT_ROUNDS = 8


async def main() -> int:
    client = get_client(url=AGENT_URL)
    thread = await client.threads.create()
    tid = thread["thread_id"]
    print(f"[e2e] thread_id={tid}", flush=True)

    config = {
        "configurable": {
            "project_identifier": PROJECT,
            "folder_id": "",
            "template_type": "web_test",
        }
    }

    # 首轮提交需求
    try:
        await client.runs.wait(
            tid,
            "web_agent",
            input={"messages": [{"role": "user", "content": REQUIREMENT}]},
            config=config,
        )
    except Exception as exc:
        print(f"[e2e] FIRST RUN ERROR: {exc}", flush=True)
        return 1
    print("[e2e] first run reached a stop point", flush=True)

    # 逐轮处理 interrupt
    for round_no in range(1, MAX_INTERRUPT_ROUNDS + 1):
        state = await client.threads.get_state(tid)
        interrupts = []
        for task in state.get("tasks", []):
            interrupts.extend(task.get("interrupts", []))

        if not interrupts:
            print(f"[e2e] run completed (no pending interrupts) after {round_no - 1} resume(s)", flush=True)
            break

        value = interrupts[0].get("value", {})
        itype = value.get("type", "") if isinstance(value, dict) else ""
        print(f"[e2e] interrupt round {round_no}: type={itype}", flush=True)

        if itype == "web_intent_confirmation":
            resume = {"decision": "execute"}
        elif itype == "execution_invitation":
            resume = {"decision": "execute"}
        else:
            # 未知面板（如工具审批）：默认放行
            resume = {"decision": "execute"}
        print(f"[e2e] resume -> {resume}", flush=True)

        try:
            await client.runs.wait(tid, "web_agent", command={"resume": resume})
        except Exception as exc:
            print(f"[e2e] RESUME RUN ERROR (round {round_no}): {exc}", flush=True)
            return 1
        print(f"[e2e] resume round {round_no} reached a stop point", flush=True)
    else:
        print("[e2e] WARN: hit MAX_INTERRUPT_ROUNDS, stopping", flush=True)

    # 输出最终 AI 消息摘要
    state = await client.threads.get_state(tid)
    messages = (state.get("values") or {}).get("messages") or []
    ai_texts = []
    for m in messages:
        if m.get("type") in ("ai", "AIMessage"):
            content = m.get("content")
            if isinstance(content, list):
                content = "".join(
                    b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
                )
            if content:
                ai_texts.append(str(content))
    print("=== FINAL AI MESSAGE (last 2000 chars) ===", flush=True)
    print((ai_texts[-1] if ai_texts else "(none)")[-2000:], flush=True)
    print(f"[e2e] DONE thread_id={tid}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
