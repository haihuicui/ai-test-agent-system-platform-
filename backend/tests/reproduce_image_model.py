"""Inject invalid tool-call adjacency checkpoint and trigger image model."""
from __future__ import annotations

import asyncio
import base64
import json
import sys
import uuid

import httpx

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 100x100 透明 PNG
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAYAAABw4pVUAAAABmJLR0QA/wD/AP+gvaeTAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH6QcTFAkYH6j0qQAAAB1pVFh0Q29tbWVudAAAAAAAQ3JlYXRlZCB3aXRoIEdJTVBkLmUHAAAAjUlEQVR42u3BAQ0AAADCoPdPbQ8HFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD8G7d4AAEpl2gzAAAAAElFTkSuQmCC"
)

BASE_URL = "http://localhost:2026"
GRAPH_ID = "testcase_generator_agent"


def make_image_content() -> dict:
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{base64.b64encode(TINY_PNG).decode()}"},
    }


async def create_thread() -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/threads",
            json={"metadata": {"test": "tool-call-adjacency"}},
        )
        r.raise_for_status()
        return r.json()["thread_id"]


async def update_state(thread_id: str, messages: list[dict]) -> None:
    """Directly inject messages into the checkpoint."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/threads/{thread_id}/state",
            json={
                "values": {"messages": messages},
            },
        )
        print("update_state response:", r.status_code, r.text[:500])
        r.raise_for_status()


async def run_agent(thread_id: str, messages: list[dict]) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/threads/{thread_id}/runs",
            json={
                "assistant_id": GRAPH_ID,
                "input": {"messages": messages},
                "stream_mode": ["values", "events"],
            },
        )
        print("run_agent response:", r.status_code, r.text[:300])
        r.raise_for_status()
        return r.json()


async def stream_run(thread_id: str, run_id: str):
    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream(
            "GET",
            f"{BASE_URL}/threads/{thread_id}/runs/{run_id}/stream",
            params={"stream_mode": ["values", "events"]},
        ) as response:
            response.raise_for_status()
            event_type = None
            async for line in response.aiter_lines():
                if not line:
                    event_type = None
                    continue
                if line.startswith("event:"):
                    event_type = line[len("event:"):].strip()
                    continue
                if line.startswith("data:"):
                    payload_str = line[len("data:"):].strip()
                    if not payload_str:
                        continue
                    try:
                        data = json.loads(payload_str)
                    except json.JSONDecodeError:
                        print("RAW:", payload_str[:200])
                        continue
                    if event_type == "error":
                        print("ERROR EVENT:", json.dumps(data, ensure_ascii=False, indent=2))
                    elif event_type in ("values", "event"):
                        event_name = data.get("event")
                        node = (data.get("metadata") or {}).get("langgraph_node")
                        print(f"  event={event_name} node={node}")
                        if event_name == "on_chain_end" and node == "model":
                            output = data.get("data", {}).get("output")
                            if output:
                                print("  model output keys:", list(output.keys()))
                    else:
                        print(f"  [{event_type}] {json.dumps(data, ensure_ascii=False, default=str)[:200]}")


async def wait_for_run(thread_id: str, run_id: str, timeout: float = 60):
    async with httpx.AsyncClient(timeout=30) as client:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            r = await client.get(f"{BASE_URL}/threads/{thread_id}/runs/{run_id}")
            r.raise_for_status()
            status = r.json().get("status")
            print(f"  run {run_id} status: {status}")
            if status in ("success", "error", "failed"):
                return r.json()
            await asyncio.sleep(2)
        raise TimeoutError("Run did not complete in time")


async def main():
    thread_id = await create_thread()
    print(f"Created thread: {thread_id}")

    # Step 1: run a simple text turn to bind graph id to thread
    print("Step 1: bind graph id with simple run")
    run1 = await run_agent(thread_id, [{"role": "human", "content": "hello"}])
    await wait_for_run(thread_id, run1["run_id"])

    # Step 2: inject invalid checkpoint
    print("Step 2: inject invalid checkpoint")
    invalid_messages = [
        {
            "type": "ai",
            "content": "",
            "tool_calls": [
                {"id": "call_invalid_1", "name": "rag_query_data", "args": {"query": "login"}}
            ],
        },
        {
            "type": "human",
            "content": "请继续",
        },
        {
            "type": "tool",
            "content": "rag result here",
            "tool_call_id": "call_invalid_1",
            "name": "rag_query_data",
        },
    ]
    await update_state(thread_id, invalid_messages)

    # Step 3: send an image message to force image model path
    print("Step 3: send image message")
    messages = [
        {
            "role": "human",
            "content": [
                {"type": "text", "text": "分析这张图片并生成登录功能的测试用例"},
                make_image_content(),
            ],
        }
    ]
    run2 = await run_agent(thread_id, messages)
    print("Run created:", run2.get("run_id"))
    run_id = run2["run_id"]
    await stream_run(thread_id, run_id)


if __name__ == "__main__":
    asyncio.run(main())
