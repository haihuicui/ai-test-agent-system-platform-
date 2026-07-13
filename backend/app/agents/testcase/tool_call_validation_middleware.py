"""Tool-call adjacency validator.

OpenAI / OpenAI-compatible providers enforce that every assistant message with
`tool_calls` must be immediately followed by `ToolMessage` responses for each
`tool_call_id`, with no other message type in between. DeepSeek is more lenient,
so invalid histories can be saved to checkpoint and only surface when the
image model (ChatOpenAI) is selected.

This middleware repairs such histories right before the model call by moving
matching tool results to immediately follow their assistant message and
back-filling dummy results for any dangling tool calls.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from langchain.agents.middleware import AgentMiddleware, AgentState, ModelRequest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite

logger = logging.getLogger("app.tool_call_validation")


def _msg_type(msg: Any) -> str:
    """Return the message type, handling both BaseMessage instances and dicts."""
    if isinstance(msg, dict):
        return msg.get("type", msg.get("role", "unknown"))
    return getattr(msg, "type", type(msg).__name__)


def _msg_id(msg: Any) -> str | None:
    if isinstance(msg, dict):
        return msg.get("id")
    return getattr(msg, "id", None)


def _is_ai_message(msg: Any) -> bool:
    return isinstance(msg, AIMessage) or (isinstance(msg, dict) and _msg_type(msg) in ("ai", "assistant"))


def _is_tool_message(msg: Any) -> bool:
    return isinstance(msg, ToolMessage) or (isinstance(msg, dict) and _msg_type(msg) in ("tool", "function"))


def _tool_calls(msg: Any) -> list[dict[str, Any]]:
    """Extract tool_calls from an AI message (instance or dict).

    兼容 LangChain OpenAI 转换器的 fallback：当 msg.tool_calls 为空但
    additional_kwargs['tool_calls'] 存在时，也把它当作 tool_calls 处理。
    """
    if isinstance(msg, dict):
        tcs = msg.get("tool_calls") or []
        if not tcs:
            tcs = (msg.get("additional_kwargs") or {}).get("tool_calls") or []
    else:
        tcs = getattr(msg, "tool_calls", None) or []
        if not tcs:
            ak = getattr(msg, "additional_kwargs", None) or {}
            tcs = ak.get("tool_calls") or []
    # 同时接受 dict 与 ToolCall TypedDict 实例
    result = []
    for tc in tcs:
        if isinstance(tc, dict):
            result.append(tc)
        elif hasattr(tc, "id") and hasattr(tc, "name"):
            result.append({
                "id": getattr(tc, "id", None),
                "name": getattr(tc, "name", None),
                "args": getattr(tc, "args", {}),
                "type": getattr(tc, "type", "tool_call"),
            })
    return result


def _tool_call_id(tc: dict[str, Any]) -> str | None:
    """Return the tool_call id, normalizing missing/empty values."""
    tid = tc.get("id")
    if tid:
        return str(tid)
    return None


def _tool_message_call_id(msg: Any) -> str | None:
    if isinstance(msg, dict):
        tid = msg.get("tool_call_id")
    else:
        tid = getattr(msg, "tool_call_id", None)
    return str(tid) if tid else None


def _tool_message_name(msg: Any) -> str | None:
    if isinstance(msg, dict):
        return msg.get("name")
    return getattr(msg, "name", None)


def _tool_message_content(msg: Any) -> Any:
    if isinstance(msg, dict):
        return msg.get("content", "")
    return getattr(msg, "content", "")


def _msg_summary(msg: Any, max_content_len: int = 120) -> str:
    """返回一条消息的安全摘要，用于诊断日志。"""
    name = _msg_type(msg)
    msg_id = _msg_id(msg)
    parts = [f"{name}(id={msg_id!r}"]
    if _is_ai_message(msg):
        tcs = _tool_calls(msg)
        tc_ids = [_tool_call_id(tc) for tc in tcs]
        parts.append(f" tool_calls(n={len(tcs)}, ids={tc_ids})")
    elif _is_tool_message(msg):
        parts.append(f" tool_call_id={_tool_message_call_id(msg)!r}")
        parts.append(f" name={_tool_message_name(msg)!r}")
    content = _tool_message_content(msg)
    if isinstance(content, str):
        preview = content.replace("\n", "\\n")[:max_content_len]
        if len(content) > max_content_len:
            preview += "..."
        parts.append(f" content={preview!r}")
    elif content is not None:
        parts.append(f" content=<{type(content).__name__}>")
    parts.append(")")
    return "".join(parts)


def _summarize_messages(messages: list[Any]) -> str:
    return "\n".join(f"  [{i}] {_msg_summary(m)}" for i, m in enumerate(messages))


def _message_to_dict(msg: Any) -> dict[str, Any]:
    """Best-effort convert a message to a serializable dict for debugging."""
    if isinstance(msg, dict):
        return msg
    d: dict[str, Any] = {"type": _msg_type(msg), "content": _tool_message_content(msg)}
    msg_id = _msg_id(msg)
    if msg_id:
        d["id"] = msg_id
    if _is_ai_message(msg):
        tcs = _tool_calls(msg)
        if tcs:
            d["tool_calls"] = tcs
    elif _is_tool_message(msg):
        d["tool_call_id"] = _tool_message_call_id(msg)
        d["name"] = _tool_message_name(msg)
    return d


def _dump_messages(messages: list[Any], label: str, exc: Exception | None = None) -> Path:
    """Dump messages to a JSON file for post-mortem analysis."""
    dump_dir = Path("tool_call_validation_dumps")
    dump_dir.mkdir(exist_ok=True)
    timestamp = "_".join(str(type(exc).__name__).split()) if exc else "dump"
    path = dump_dir / f"{label}_{timestamp}.json"
    payload = {
        "label": label,
        "count": len(messages),
        "exception": f"{type(exc).__name__}: {exc}" if exc else None,
        "messages": [_message_to_dict(m) for m in messages],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


class ToolCallAdjacencyMiddleware(AgentMiddleware):
    """确保 assistant tool_calls 与 tool 响应在发送给模型前严格相邻。"""

    async def abefore_agent(
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        """在 agent 启动前也修复一次 state，避免无效历史被 checkpoint 持久化。"""
        messages = state.get("messages") or []
        patched = _ensure_tool_call_adjacency(messages)
        if patched is messages:
            return None
        logger.info(
            "abefore_agent: repaired messages (%d -> %d):\n%s",
            len(messages),
            len(patched),
            _summarize_messages(patched),
        )
        return {"messages": Overwrite(value=patched)}

    async def abefore_model(
        self,
        state: AgentState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        """在每个 model node 执行前再修复一次，确保其它 middleware 改动后仍合法。"""
        messages = state.get("messages") or []
        patched = _ensure_tool_call_adjacency(messages)
        if patched is messages:
            return None
        logger.info(
            "abefore_model: repaired messages (%d -> %d):\n%s",
            len(messages),
            len(patched),
            _summarize_messages(patched),
        )
        return {"messages": Overwrite(value=patched)}

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Any],
    ) -> Any:
        original = list(request.messages or [])
        patched_messages = _ensure_tool_call_adjacency(original)
        if patched_messages is not original:
            request = request.override(messages=patched_messages)
            logger.info(
                "awrap_model_call: repaired messages (%d -> %d):\n%s",
                len(original),
                len(patched_messages),
                _summarize_messages(patched_messages),
            )

        validation_error = _validate_adjacency(patched_messages)
        if validation_error:
            path = _dump_messages(patched_messages, "awrap_model_call_invalid")
            logger.error(
                "awrap_model_call: adjacency still invalid after repair: %s\n"
                "input:\n%s\noutput:\n%s\ndump: %s",
                validation_error,
                _summarize_messages(original),
                _summarize_messages(patched_messages),
                path,
            )
        return await handler(request)


def _validate_adjacency(messages: list[Any]) -> str | None:
    """按 OpenAI 规则检查消息序列是否合法。返回错误描述或 None。"""
    pending_tool_calls: list[tuple[int, list[str]]] = []  # (ai_index, ids)
    for idx, msg in enumerate(messages):
        if _is_ai_message(msg) and _tool_calls(msg):
            ids = [_tool_call_id(tc) for tc in _tool_calls(msg) if _tool_call_id(tc)]
            if ids:
                pending_tool_calls.append((idx, ids))
        elif _is_tool_message(msg):
            tc_id = _tool_message_call_id(msg)
            if pending_tool_calls:
                ai_idx, ai_ids = pending_tool_calls[-1]
                if tc_id in ai_ids:
                    ai_ids.remove(tc_id)
                    if not ai_ids:
                        pending_tool_calls.pop()
                    continue
            return f"ToolMessage at index {idx} (tool_call_id={tc_id!r}) does not follow a matching assistant tool_call"
        else:
            if pending_tool_calls:
                ai_idx, ai_ids = pending_tool_calls[-1]
                return (
                    f"Non-tool message {type(msg).__name__} at index {idx} "
                    f"breaks adjacency after assistant at index {ai_idx} "
                    f"with pending tool_call_ids={ai_ids}"
                )
    if pending_tool_calls:
        ai_idx, ai_ids = pending_tool_calls[-1]
        return f"Assistant at index {ai_idx} has pending tool_call_ids without matching ToolMessages: {ai_ids}"
    return None


def _ensure_tool_call_adjacency(messages: list[Any]) -> list[Any]:
    """重建消息列表，保证每个 AIMessage(tool_calls) 后紧跟其 ToolMessage 响应。

    策略：
    1. 先深拷贝所有消息，避免与 checkpoint / state 共享引用导致中间件运行期间被
       其它任务或 LangChain 内部逻辑改写。
    2. 清理 AI 消息里的 tool_calls：去掉没有合法 id 的条目，避免 OpenAI 看到它们
       却找不到对应 ToolMessage。
    3. 收集所有 AIMessage 需要的 tool_call_id（保持 tool_calls 内顺序）。
    4. 按 tool_call_id 收集所有 ToolMessage；出现重复时保留最后一个（通常最接近
       其 assistant）。
    5. 将 ToolMessage 归属给拥有对应 tool_call_id 的最近一个 AIMessage。
    6. 顺序重建消息：遇到 AIMessage(tool_calls) 时，先输出 AI，再按 tool_calls
       顺序输出归属的 ToolMessage；缺失的用 dummy ToolMessage 补齐。未被归属的
       ToolMessage 直接丢弃（OpenAI 也不允许无对应 assistant 的 tool 消息）。
    """
    if not messages:
        return messages

    copied = [_copy_message(m) for m in messages]
    sanitized_messages, sanitized = _sanitize_ai_tool_calls(copied)

    # 若输入是 OpenAI dict 列表，dummy 输出也用 dict，保持类型一致
    output_as_dict = all(isinstance(m, dict) for m in messages)

    ai_tool_calls: list[tuple[int, list[dict[str, Any]]]] = []
    for idx, msg in enumerate(sanitized_messages):
        if _is_ai_message(msg):
            tcs = _tool_calls(msg)
            if tcs:
                ai_tool_calls.append((idx, tcs))

    if not ai_tool_calls:
        return sanitized_messages if sanitized else copied

    needed_ids = {_tool_call_id(tc) for _, tcs in ai_tool_calls for tc in tcs if _tool_call_id(tc)}

    tool_results: dict[str, Any] = {}
    for msg in sanitized_messages:
        if _is_tool_message(msg):
            tc_id = _tool_message_call_id(msg)
            if tc_id and tc_id in needed_ids:
                tool_results[tc_id] = msg

    ai_assignments: dict[int, dict[str, Any]] = {idx: {} for idx, _ in ai_tool_calls}
    ai_id_lists: dict[int, list[str]] = {
        idx: [_tool_call_id(tc) for tc in tcs if _tool_call_id(tc)] for idx, tcs in ai_tool_calls
    }
    for tc_id, tool_msg in tool_results.items():
        assigned_idx: int | None = None
        for idx, tcs in reversed(ai_tool_calls):
            if tc_id in {_tool_call_id(tc) for tc in tcs}:
                assigned_idx = idx
                break
        if assigned_idx is not None:
            ai_assignments[assigned_idx][tc_id] = tool_msg

    assigned_tool_call_ids: set[str] = set()
    for assignments in ai_assignments.values():
        assigned_tool_call_ids.update(assignments.keys())

    result: list[Any] = []
    patched = sanitized
    ai_indices = {idx for idx, _ in ai_tool_calls}

    for idx, msg in enumerate(sanitized_messages):
        if idx in ai_indices:
            ai_msg = msg
            result.append(ai_msg)
            assignments = ai_assignments[idx]
            for tc_id in ai_id_lists[idx]:
                tool_msg = assignments.pop(tc_id, None)
                if tool_msg is not None:
                    result.append(tool_msg)
                else:
                    result.append(_dummy_tool_message(ai_msg, tc_id, as_dict=output_as_dict))
                    patched = True
                    logger.warning(
                        "Back-filled dummy ToolMessage for tool_call %s",
                        tc_id,
                    )
        elif _is_tool_message(msg):
            tc_id = _tool_message_call_id(msg)
            if tc_id and tc_id in assigned_tool_call_ids:
                patched = True
                continue
            patched = True
            if tc_id:
                logger.warning(
                    "Dropping ToolMessage with tool_call_id %s (no matching assistant tool_call)",
                    tc_id,
                )
            else:
                logger.warning("Dropping ToolMessage without tool_call_id")
        else:
            result.append(msg)

    if not patched:
        return messages

    logger.info("Tool-call adjacency repaired before model call")
    return result


def _sanitize_ai_tool_calls(messages: list[Any]) -> tuple[list[Any], bool]:
    """清理 AI 消息中的无效 tool_calls（无 id 的条目）。"""
    sanitized = False
    result: list[Any] = []
    for msg in messages:
        if not _is_ai_message(msg):
            result.append(msg)
            continue

        tcs = _tool_calls(msg)
        valid_tcs = [tc for tc in tcs if _tool_call_id(tc)]
        if len(valid_tcs) == len(tcs):
            result.append(msg)
            continue

        sanitized = True
        if valid_tcs:
            new_msg = _copy_ai_message_with_tool_calls(msg, valid_tcs)
            logger.warning(
                "Sanitized AI message %s: dropped %d tool_call(s) without id",
                _msg_id(msg),
                len(tcs) - len(valid_tcs),
            )
            result.append(new_msg)
        else:
            new_msg = _copy_ai_message_with_tool_calls(msg, [])
            logger.warning(
                "Sanitized AI message %s: removed all tool_calls (no valid ids)",
                _msg_id(msg),
            )
            result.append(new_msg)
    return result, sanitized


def _copy_message(msg: Any) -> Any:
    """Deep-copy a message (BaseMessage instance or dict)."""
    if isinstance(msg, dict):
        return json.loads(json.dumps(msg, default=str))
    if hasattr(msg, "model_dump"):
        return type(msg)(**msg.model_dump())
    if hasattr(msg, "copy"):
        new_msg = msg.copy()
        for attr in ("content", "additional_kwargs", "response_metadata", "tool_calls", "invalid_tool_calls"):
            if hasattr(new_msg, attr):
                try:
                    val = getattr(new_msg, attr)
                    if val is not None:
                        setattr(new_msg, attr, json.loads(json.dumps(val, default=str)))
                except Exception:
                    pass
        return new_msg
    return msg


def _copy_ai_message_with_tool_calls(msg: Any, tool_calls: list[dict[str, Any]]) -> Any:
    """创建一份 AI 消息副本，使用新的 tool_calls 列表。"""
    if isinstance(msg, dict):
        new_msg = dict(msg)
        if tool_calls:
            new_msg["tool_calls"] = tool_calls
        else:
            new_msg.pop("tool_calls", None)
        if "additional_kwargs" in new_msg:
            new_msg["additional_kwargs"] = {
                k: v for k, v in new_msg["additional_kwargs"].items() if k != "tool_calls"
            }
        return new_msg

    new_msg = msg.copy()
    ak = dict(getattr(new_msg, "additional_kwargs", {}) or {})
    ak.pop("tool_calls", None)
    new_msg.additional_kwargs = ak  # type: ignore[misc]
    new_msg.tool_calls = tool_calls  # type: ignore[misc]
    return new_msg


def _dummy_tool_message(ai_msg: Any, tool_call_id: str, as_dict: bool = False) -> Any:
    """为缺失的 tool 响应生成一个占位 ToolMessage。"""
    name = "unknown"
    for tc in _tool_calls(ai_msg):
        if _tool_call_id(tc) == tool_call_id:
            name = tc.get("name") or tc.get("function", {}).get("name") or "unknown"
            break
    content = f"Tool call {name} (id: {tool_call_id}) had no recorded result; assuming completed."
    if as_dict:
        return {
            "role": "tool",
            "content": content,
            "tool_call_id": tool_call_id,
            "name": name,
        }
    return ToolMessage(
        content=content,
        name=name,
        tool_call_id=tool_call_id,
    )


# 用于防止对同一模型实例重复 patch
_PATCHED_MODELS: set[int] = set()


def patch_model_for_tool_call_adjacency(model: Any) -> None:
    """Monkey-patch 一个 ChatModel，在调用前最终修复 tool-call 邻接。

    create_deep_agent 会把若干内置 middleware 排在用户 middleware 之后，因此仅靠
    ToolCallAdjacencyMiddleware.awrap_model_call 仍可能在下层 middleware 改动后失效。
    这里直接在模型序列化消息前做最后一道修复，避开 middleware 顺序问题。
    """
    model_id = id(model)
    if model_id in _PATCHED_MODELS:
        logger.debug("Model %s already patched, skipping", type(model).__name__)
        return
    _PATCHED_MODELS.add(model_id)

    logger.info("Patching %s for tool-call adjacency", type(model).__name__)
    original_ainvoke = model.ainvoke
    original_invoke = model.invoke
    original_astream = getattr(model, "astream", None)
    original_stream = getattr(model, "stream", None)
    original_get_request_payload = getattr(model, "_get_request_payload", None)

    # 最后一道防线：在 LangChain 把消息序列化成 OpenAI dict 后，再修复一次。
    # 这能 catch 到在序列化阶段才从 additional_kwargs 暴露出来的 tool_calls。
    if original_get_request_payload is not None:
        def get_request_payload_patched(input_: Any, *, stop: Any = None, **kwargs: Any) -> Any:
            payload = original_get_request_payload(input_, stop=stop, **kwargs)
            messages = payload.get("messages")
            if messages:
                repaired = _ensure_tool_call_adjacency(messages)
                if repaired is not messages:
                    logger.info("_get_request_payload: repaired OpenAI message dicts (%d -> %d)", len(messages), len(repaired))
                validation_error = _validate_adjacency(repaired)
                if validation_error:
                    logger.error("_get_request_payload: adjacency still invalid: %s", validation_error)
                payload["messages"] = repaired
            return payload

        object.__setattr__(model, "_get_request_payload", get_request_payload_patched)

    async def ainvoke_patched(input: Any, config: Any = None, **kwargs: Any) -> Any:
        msg_list = _as_message_list(input)
        repaired = _ensure_tool_call_adjacency(msg_list)
        validation_error = _validate_adjacency(repaired)
        if validation_error:
            path = _dump_messages(repaired, "ainvoke_patched_invalid")
            logger.error(
                "ainvoke_patched: adjacency invalid after repair: %s; dump=%s",
                validation_error,
                path,
            )
        try:
            return await original_ainvoke(repaired, config=config, **kwargs)
        except Exception as exc:
            path = _dump_messages(repaired, "ainvoke_patched_failed", exc)
            logger.error(
                "ainvoke_patched: model call failed (%s); repaired messages dumped to %s",
                type(exc).__name__,
                path,
            )
            raise

    def invoke_patched(input: Any, config: Any = None, **kwargs: Any) -> Any:
        repaired = _ensure_tool_call_adjacency(_as_message_list(input))
        return original_invoke(repaired, config=config, **kwargs)

    object.__setattr__(model, "ainvoke", ainvoke_patched)
    object.__setattr__(model, "invoke", invoke_patched)

    if original_astream is not None:
        async def astream_patched(input: Any, config: Any = None, **kwargs: Any) -> Any:
            return await original_astream(_ensure_tool_call_adjacency(_as_message_list(input)), config=config, **kwargs)

        object.__setattr__(model, "astream", astream_patched)

    if original_stream is not None:
        def stream_patched(input: Any, config: Any = None, **kwargs: Any) -> Any:
            return original_stream(_ensure_tool_call_adjacency(_as_message_list(input)), config=config, **kwargs)

        object.__setattr__(model, "stream", stream_patched)


def _as_message_list(input: Any) -> list[Any]:
    """把模型输入统一成列表；保留非列表输入原样返回（让底层模型报错更真实）。"""
    if isinstance(input, list):
        return input
    if input is None:
        return []
    return [input]
