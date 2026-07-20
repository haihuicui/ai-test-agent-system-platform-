"""Message merging utilities for thread history.

This module is kept free of database/runtime dependencies so it can be imported
and unit-tested without a configured LangGraph database.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import BaseMessage
from langgraph.types import StateSnapshot


def _message_content_length(msg: dict[str, Any]) -> int:
    """Approximate length of a message's content for tie-breaking merges."""
    content = msg.get("content")
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return len(json.dumps(content, ensure_ascii=False))
    return 0


def _message_to_dict(msg: Any) -> dict[str, Any] | None:
    """Convert a message object or dict to a plain dict.

    LangGraph checkpoints may store messages as BaseMessage instances (e.g.
    AIMessage, ToolMessage) instead of plain dicts. The UI and merge logic
    expect the flat dict representation used by /history, so normalize them
    here.
    """
    if isinstance(msg, dict):
        return msg
    if isinstance(msg, BaseMessage):
        return msg.model_dump()
    return None


def merge_messages_from_snapshots(
    snapshots: list[StateSnapshot],
) -> list[dict[str, Any]]:
    """Merge messages from multiple checkpoints into a chronological list.

    Checkpoints are returned newest-first by LangGraph. We iterate from oldest
    to newest so that later versions of the same message id overwrite earlier
    ones, matching the behavior of the messages delta reducer.

    For the same message id across checkpoints (e.g. due to summarization or
    compaction rewriting an old tool result), keep the version with the longest
    content so the UI shows the most complete payload.
    """
    # dict preserves insertion order in Python 3.7+ and gives O(1) lookup/updates
    # for deduplication, avoiding the previous O(n^2) list scan.
    merged: dict[str, dict[str, Any]] = {}
    tail: list[dict[str, Any]] = []

    for snapshot in reversed(snapshots):
        values = snapshot.values or {}
        messages = (
            (values.get("messages") or []) if isinstance(values, dict) else []
        )
        for msg in messages:
            msg_dict = _message_to_dict(msg)
            if msg_dict is None:
                continue
            msg_id = msg_dict.get("id")
            if not msg_id:
                # Messages without ids cannot be deduplicated; preserve them.
                tail.append(msg_dict)
                continue

            existing = merged.get(msg_id)
            if existing is None:
                merged[msg_id] = msg_dict
            elif _message_content_length(msg_dict) > _message_content_length(
                existing
            ):
                merged[msg_id] = msg_dict

    return list(merged.values()) + tail
