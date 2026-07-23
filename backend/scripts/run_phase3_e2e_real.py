"""Phase 3 真实 LLM 端到端验证脚本。

依赖：
- 后端服务已启动（python backend/start_fastapi_debug.py）
- LangGraph in-memory server 已启动（python start_server_inmem.py）
- 环境变量 DEEPSEEK_API_KEY 已设置
- 测试项目已创建（替换 PROJECT_ID）

运行：
    python backend/scripts/run_phase3_e2e_real.py
"""
from __future__ import annotations

import asyncio
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from langgraph_sdk import get_client

LANGGRAPH_URL = "http://127.0.0.1:2025"
ASSISTANT_ID = "testcase_generator_agent"
PROJECT_ID = "PR-1"  # 替换为真实项目 identifier
FOLDER_ID = ""
PROMPT = "请为‘用户登录功能’设计完整测试用例，覆盖正常、异常、边界和安全场景。"


def _extract_interrupt(event):
    data = event.data
    if isinstance(data, dict):
        raw = data.get("__interrupt__")
        if isinstance(raw, list) and raw:
            return raw[0].get("value") if isinstance(raw[0], dict) else raw[0]
        if isinstance(raw, dict):
            return raw.get("value") or raw
    return None


async def main():
    client = get_client(url=LANGGRAPH_URL)
    thread = await client.threads.create()
    print(f"创建 thread: {thread['thread_id']}")

    config = {
        "configurable": {
            "project_identifier": PROJECT_ID,
            "folder_id": FOLDER_ID,
            "template_type": "test_case",
            "enable_rag": False,
            "auto_approve_threshold": 75,
        }
    }

    first_input = {
        "messages": [
            {
                "type": "human",
                "content": PROMPT,
                "additional_kwargs": {"enable_rag": False},
            }
        ]
    }

    command = None
    round_count = 0

    while True:
        round_count += 1
        print(f"\n=== round {round_count} ===")

        kwargs = {"command": command} if command else {"input": first_input}
        interrupt_value = None

        async for event in client.runs.stream(
            thread["thread_id"],
            ASSISTANT_ID,
            config=config,
            stream_mode="updates",
            **kwargs,
        ):
            if event.event == "updates":
                inter = _extract_interrupt(event)
                if inter:
                    interrupt_value = inter
                    break

        if not interrupt_value:
            print("Run ended without further interrupts.")
            break

        print("Interrupt received:")
        print(json.dumps(interrupt_value, ensure_ascii=False, default=str)[:800])

        if isinstance(interrupt_value, dict) and interrupt_value.get("type") == "format_selection":
            resume_value = {"format": "excel"}
        else:
            resume_value = {"decision": "approve", "message": "", "checklist": {}}

        command = {"resume": resume_value}

    print("\n验证项：")
    print(f"  后端用例：GET http://localhost:8001/api/v2/projects/{PROJECT_ID}/test-cases")
    print(f"  JSONL 文件：检查 backend/workspace/testcase/")
    print(f"  Manifest：检查 backend/workspace/testcase/test_case_manifest.json")
    print(f"  Thread state：GET http://localhost:2025/threads/{thread['thread_id']}/state")


if __name__ == "__main__":
    asyncio.run(main())
