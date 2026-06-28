"""Local `DeltaChannel` reducer for the messages key.

Adapted from langgraph's `_messages_delta_reducer` (PR #7729). The upstream
version coerces `BaseMessageChunk` writes to full messages for parity with
`add_messages`. Deepagents never writes chunks to the messages channel —
`langchain.agents.create_agent` appends full `AIMessage` objects, and
streaming via `astream_events` operates on the output side, not the state
side — so we skip the per-message coercion.

PATCH: messages_reducer_sanitized_v1
This file has been patched to:
1. Guard against `state=None` during checkpoint/history replay.
2. Sanitize leaked `{'value': [...]}` interrupt / snapshot blobs that would
   otherwise make `convert_to_messages()` raise `KeyError: 'role'` / `'type'`.
"""

from __future__ import annotations

from typing import Any, cast

from langchain_core.messages import (
    AnyMessage,
    BaseMessage,
    RemoveMessage,
    convert_to_messages,
)
from langgraph.graph.message import REMOVE_ALL_MESSAGES


def _unwrap_value(obj: Any) -> Any:
    """Unwrap leaked interrupt / `_DeltaSnapshot` blobs shaped `{'value': [...]}`.

    These payloads occasionally leak into the messages channel's pending writes
    and are not message-like, so `convert_to_messages` chokes on them with
    `KeyError: 'role'` / `'type'`. Peel the wrapper(s) to recover the inner value.
    """
    while isinstance(obj, dict) and set(obj) == {"value"}:
        obj = obj["value"]
    return obj


def _is_message_like(item: Any) -> bool:
    if isinstance(item, BaseMessage):
        return True
    try:
        convert_to_messages([item])
        return True
    except Exception:
        return False


def _sanitize(seq: list[Any]) -> list[Any]:
    """Drop / unwrap non-message-like items so `convert_to_messages` succeeds.

    Only invoked on the slow path, after a plain `convert_to_messages` has
    already failed — so the common case pays nothing.
    """
    out: list[Any] = []
    for it in seq:
        it = _unwrap_value(it)
        if isinstance(it, list):
            out.extend(x for x in it if _is_message_like(x))
        elif _is_message_like(it):
            out.append(it)
    return out


def _messages_delta_reducer(  # noqa: C901
    state: list[AnyMessage], writes: list[list[AnyMessage]]
) -> list[AnyMessage]:
    """Batch reducer for use with `DeltaChannel` on the messages key.

    Dedups by ID, tombstones via `RemoveMessage`, resets on
    `REMOVE_ALL_MESSAGES`. ID-less messages are appended without ID
    assignment — checkpointers serialize pending writes before
    `update()` runs, so IDs assigned inside the reducer never reach
    stored writes and would differ on replay, defeating deduplication.

    Raw dict / string / tuple inputs are coerced to typed `BaseMessage` so
    HTTP-driven graphs work without a separate coercion step.
    """
    # Each write is either a list of message-likes or a single message-like
    # (BaseMessage / dict / str / tuple). Only lists flatten; everything
    # else is one message.
    flat: list[Any] = []
    for w in writes:
        if isinstance(w, list):
            flat.extend(w)
        else:
            flat.append(w)
    # Steady state: the reducer's own output is already typed BaseMessages,
    # so skip convert_to_messages on the fast path. Only raw input (initial
    # dicts, deserialized blobs) hits the slow path.
    # NOTE: `state` may be None during checkpoint/history replay when the
    # messages channel has no base value yet; convert_to_messages(None) would
    # raise "TypeError: 'NoneType' object is not iterable", so coerce to [].
    if state is None:
        state = []
    # Fast path: the reducer's own output is already typed BaseMessages, and
    # writes are usually well-formed, so attempt a plain conversion first. Only
    # if a leaked non-message blob (e.g. `{'value': [...]}`) trips
    # convert_to_messages do we pay for sanitization on the slow path.
    try:
        state_msgs = state if state and isinstance(state[0], BaseMessage) else cast("list[AnyMessage]", convert_to_messages(state))
        msgs = cast("list[AnyMessage]", convert_to_messages(flat))
    except Exception:
        state_msgs = state if state and isinstance(state[0], BaseMessage) else cast("list[AnyMessage]", convert_to_messages(_sanitize(state)))
        msgs = cast("list[AnyMessage]", convert_to_messages(_sanitize(flat)))

    # REMOVE_ALL_MESSAGES resets everything; find the last sentinel and
    # discard all state plus all writes before it.
    remove_all_idx = None
    for idx, m in enumerate(msgs):
        if isinstance(m, RemoveMessage) and m.id == REMOVE_ALL_MESSAGES:
            remove_all_idx = idx
    if remove_all_idx is not None:
        state_msgs = []
        msgs = msgs[remove_all_idx + 1 :]

    index: dict[str, int] = {m.id: i for i, m in enumerate(state_msgs) if m.id is not None}
    result: list[AnyMessage | None] = list(state_msgs)
    for msg in msgs:
        mid = msg.id
        if mid is None:
            result.append(msg)
        elif isinstance(msg, RemoveMessage):
            if mid in index:
                result[index[mid]] = None
                del index[mid]
        elif mid in index:
            result[index[mid]] = msg
        else:
            index[mid] = len(result)
            result.append(msg)
    return [m for m in result if m is not None]
