# -*- coding: utf-8 -*-
"""api agent conversation_id 跨节点传播验证（路径 A：前端 SDK 直连）。

创建 thread 并让 api_agent 调用 cached_read 包装的工具（get_project_environments），
通过 langgraph_server.log 中的 [conv-id] 诊断日志确认工具侧实际拿到的会话标识。
"""
import asyncio
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

from langgraph_sdk import get_client

ASSISTANT = "api_agent"
TIMEOUT_S = 300


async def main():
    client = get_client(url="http://localhost:2026")
    thread = await client.threads.create()
    tid = thread["thread_id"]
    print(f"thread: {tid}", flush=True)

    run = await client.runs.create(
        tid,
        ASSISTANT,
        input={"messages": [{"role": "user", "content": (
            "【联调验证】请调用 get_project_environments 工具查询当前项目的环境列表；"
            "拿到结果后，请再调用一次同样的 get_project_environments 确认结果一致，"
            "然后简单回复即可。不要执行其他工具。"
        )}]},
        context={
            "project_identifier": "PR-VERIFY",
            "folder_id": "",
            "environment_id": "",
            "template_type": "api_test",
        },
    )
    print(f"run: {run['run_id']}", flush=True)

    deadline = time.time() + TIMEOUT_S
    while time.time() < deadline:
        run = await client.runs.get(tid, run["run_id"])
        if run["status"] in ("success", "error", "interrupted", "timeout"):
            break
        await asyncio.sleep(4)
    print(f"run 终态: {run['status']}", flush=True)
    print("请检查 langgraph_server.log 中的 [conv-id] 诊断日志")


asyncio.run(main())
