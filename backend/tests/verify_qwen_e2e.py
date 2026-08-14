"""千问接入 testcase Agent 的真实 E2E 冒烟：建线程 → 发消息 → 等运行结束 → 看回复。

验证点：
1. 完整中间件链 + qwen 模型调用不炸（流式、tool-call 邻接修复、context overflow patch 等）
2. run 状态为 success 且 AI 有实际回复内容
"""
import asyncio
import sys

from langgraph_sdk import get_client


async def main() -> int:
    client = get_client(url="http://localhost:2026")
    thread = await client.threads.create()
    tid = thread["thread_id"]
    print(f"thread_id: {tid}")

    try:
        result = await asyncio.wait_for(
            client.runs.wait(
                tid,
                "testcase_generator_agent",
                input={"messages": [{"role": "user", "content": "你好，用一句话介绍你自己"}]},
            ),
            timeout=300,
        )
    except asyncio.TimeoutError:
        print("FAIL: run 300s 超时")
        return 1

    # runs.wait 返回最终 state（含 messages）
    messages = (result or {}).get("messages", [])
    ai_msgs = [m for m in messages if m.get("type") == "ai" and m.get("content")]
    if not ai_msgs:
        print(f"FAIL: 无 AI 回复。state keys={list((result or {}).keys())}")
        return 1
    last = ai_msgs[-1]["content"]
    if isinstance(last, list):
        last = "".join(b.get("text", "") for b in last if isinstance(b, dict))
    print(f"AI 回复（{len(last)} 字符）: {last[:200]}")

    # 确认 run 状态
    runs = await client.runs.list(tid)
    for r in runs:
        print(f"run status: {r['status']}")
        if r["status"] != "success":
            print(f"FAIL: error={r.get('error')}")
            return 1
    print("E2E PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
