"""Web Agent 意图确认端到端验证脚本。

通过 LangGraph SDK 直接调用 web_agent，验证：
1. 发送"为 SauceDemo 创建 Web 功能测试"消息后能否触发 web_intent_confirmation 中断。
2. 中断 payload 结构是否正确。
3. resume 后能否继续执行。
"""

from __future__ import annotations

import asyncio
import json
import sys

# 保证 Windows 控制台 UTF-8 输出
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from langgraph_sdk import get_client
from langgraph_sdk.schema import StreamPart


LANGGRAPH_API_URL = "http://127.0.0.1:2026"
ASSISTANT_ID = "web_agent"
PROJECT_ID = "PR-1"

USER_MESSAGE = "为 SauceDemo 网站创建完整的 Web 功能测试，覆盖登录、加购、购物车、结账流程。"


async def main():
    client = get_client(url=LANGGRAPH_API_URL)

    # 1. 创建 thread
    thread = await client.threads.create()
    thread_id = thread["thread_id"]
    print(f"创建 thread: {thread_id}")

    # 2. 首次运行，期望触发 interrupt
    print("\n=== 第一次运行：发送用户请求 ===")
    interrupt_value = None
    run_id = None

    def _extract_interrupt(data):
        """从 updates 数据中提取 interrupt payload。"""
        if isinstance(data, dict):
            raw = data.get("__interrupt__")
            if isinstance(raw, list) and raw:
                return raw[0].get("value") if isinstance(raw[0], dict) else raw[0]
            if isinstance(raw, dict):
                return raw.get("value") or raw
        return None

    async for event in client.runs.stream(
        thread_id,
        ASSISTANT_ID,
        input={
            "messages": [
                {"type": "human", "content": USER_MESSAGE}
            ]
        },
        config={
            "configurable": {
                "project_identifier": PROJECT_ID,
                "folder_id": "",
            }
        },
        stream_mode="updates",
    ):
        if event.event == "metadata":
            run_id = event.data.get("run_id")
            print(f"run_id: {run_id}")
            continue

        if event.event == "updates":
            inter = _extract_interrupt(event.data)
            if inter is not None:
                interrupt_value = inter
                print("\n>>> 收到 INTERRUPT <<<")
                print(json.dumps(interrupt_value, ensure_ascii=False, indent=2))
                continue

            # 只打印关键节点事件，避免日志过长
            data = event.data
            key = next((k for k in data if k not in ("PatchToolCallsMiddleware.before_agent", "SkillsMiddleware.before_agent")), None)
            if key:
                snippet = json.dumps({key: data[key]}, ensure_ascii=False, indent=2)[:400]
                print(f"事件: {event.event} -> {snippet}...")

    if interrupt_value is None:
        print("\n❌ 未触发意图确认中断")
        return False

    payload = interrupt_value if isinstance(interrupt_value, dict) else interrupt_value[0]
    if payload.get("type") != "web_intent_confirmation":
        print(f"\n❌ 中断类型错误: {payload.get('type')}")
        return False

    existing = payload.get("existing_function", {})

    print("\n=== 中断验证通过 ===")
    print(f"推荐方案: {payload.get('recommendation')}")
    print(f"原因: {payload.get('reason')}")
    print(f"已有功能: {existing.get('identifier')} - {existing.get('display_name')}")

    # 3. resume 选择扩展
    print("\n=== 第二次运行：resume 选择 expand ===")
    resumed = False
    async for event in client.runs.stream(
        thread_id,
        ASSISTANT_ID,
        command={"resume": {"decision": "expand"}},
        config={
            "configurable": {
                "project_identifier": PROJECT_ID,
                "folder_id": "",
            }
        },
        stream_mode="updates",
    ):
        print(f"事件: {event.event}")
        if event.event == "updates":
            data = event.data
            print(json.dumps(data, ensure_ascii=False, indent=2)[:500])
            resumed = True
        elif event.event == "interrupt":
            print("\n>>> 再次收到 INTERRUPT <<<")
            print(json.dumps(event.data, ensure_ascii=False, indent=2))

    if not resumed:
        print("\n❌ resume 后没有继续执行")
        return False

    print("\n✅ 端到端验证通过：触发中断 → resume 继续")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
