"""轨迹采集器：从 LangGraph Server 拉取 thread 消息，落为审计样本。

把「修完一个线上 bug 顺手收编翻车现场」的动作一键化——从 Langfuse/
日志里拿到 thread_id 后：

    ./.venv/Scripts/python.exe -m tests.eval.traj_harvest <thread_id> --agent web
    ./.venv/Scripts/python.exe -m tests.eval.traj_harvest <thread_id> --agent testcase --golden

产出文件写入 tests/eval/dataset/trajectories/（{agent}_{thread前8位}.json），
格式与 traj_audit 消费的消息转储同构（HumanMessage/AIMessage/ToolMessage 数组）。

注意：
- langgraph_sdk 为可选依赖（生产 root/.venv 有，测试 backend/.venv 未必有），
  缺失时给出安装提示而不是炸栈；
- --golden 仅用于人工确认过流程合规的标杆轨迹（门禁范围），翻车样本不要加；
- 样本只增不减（与回归集同纪律），翻车样本修复后依然保留。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "dataset" / "trajectories"
DEFAULT_URL = os.environ.get("LANGGRAPH_URL", "http://localhost:2026")


def _normalize_message(msg: dict, idx: int) -> dict | None:
    """把 SDK 返回的消息（可能是 LangChain 序列化格式）规整为转储格式。"""
    # LangChain 序列化格式：{"lc":1,"type":"constructor","id":[...,"AIMessage"],"kwargs":{...}}
    if "kwargs" in msg and isinstance(msg.get("id"), list):
        mtype = msg["id"][-1]
        msg = msg.get("kwargs") or {}
        msg["type"] = mtype
    mtype = msg.get("type") or msg.get("role") or ""
    type_map = {"human": "HumanMessage", "user": "HumanMessage", "ai": "AIMessage",
                "assistant": "AIMessage", "tool": "ToolMessage"}
    if mtype not in type_map.values():
        mtype = type_map.get(str(mtype).lower())
    if mtype is None:
        return None
    out: dict = {"i": idx, "type": mtype, "content": msg.get("content", "")}
    tool_calls = msg.get("tool_calls") or []
    if tool_calls:
        out["tool_calls"] = [
            {"name": tc.get("name", ""), "args": tc.get("args", {})}
            for tc in tool_calls if isinstance(tc, dict)
        ]
    if msg.get("name"):
        out["name"] = msg["name"]
    return out


async def harvest(thread_id: str, url: str) -> list[dict]:
    try:
        from langgraph_sdk import get_client
    except ImportError:
        print("缺 langgraph_sdk：请在 backend/.venv 安装 langgraph-sdk 后重试", file=sys.stderr)
        sys.exit(2)

    client = get_client(url=url)
    state = await client.threads.get_state(thread_id)
    values = state.get("values") or {}
    messages = values.get("messages") or []
    out = []
    for idx, msg in enumerate(messages):
        if isinstance(msg, dict):
            normalized = _normalize_message(msg, idx)
            if normalized:
                out.append(normalized)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="从 LangGraph Server 采集 thread 轨迹样本")
    parser.add_argument("thread_id", help="LangGraph thread_id")
    parser.add_argument("--agent", default="unknown", choices=["testcase", "web", "api", "unknown"])
    parser.add_argument("--url", default=DEFAULT_URL, help="LangGraph Server 地址")
    parser.add_argument("--golden", action="store_true",
                        help="标记为 golden 标杆样本（进入 pre-push 门禁范围，仅人工确认合规后使用）")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    messages = asyncio.run(harvest(args.thread_id, args.url))
    if not messages:
        print(f"thread {args.thread_id} 未取到消息（thread 不存在或 graph 无 messages 状态）", file=sys.stderr)
        sys.exit(2)

    prefix = {"testcase": "tc", "web": "web", "api": "api"}.get(args.agent, "unknown")
    suffix = ".golden.json" if args.golden else ".json"
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"{prefix}_{args.thread_id[:8]}{suffix}"
    path.write_text(json.dumps(messages, ensure_ascii=False, indent=1), encoding="utf-8")
    n_calls = sum(len(m.get("tool_calls", [])) for m in messages)
    print(f"已采集 {path.name}：{len(messages)} 条消息 / {n_calls} 次工具调用")
    print("下一步：./.venv/Scripts/python.exe -m tests.eval.traj_audit " + str(path))


if __name__ == "__main__":
    main()
