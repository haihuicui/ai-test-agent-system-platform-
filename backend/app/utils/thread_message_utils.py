"""Message merging utilities for thread history.

This module is kept free of database/runtime dependencies so it can be imported
and unit-tested without a configured LangGraph database.
"""

from __future__ import annotations

import json
from typing import Any

from langgraph.types import StateSnapshot


def _message_content_length(msg: dict[str, Any]) -> int:
    """Approximate length of a message's content for tie-breaking merges."""
    content = msg.get("content")
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return len(json.dumps(content, ensure_ascii=False))
    return 0


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
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []

    for snapshot in reversed(snapshots):
        values = snapshot.values or {}
        messages = values.get("messages", []) if isinstance(values, dict) else []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            msg_id = msg.get("id")
            if not msg_id:
                # Messages without ids cannot be deduplicated; preserve them.
                merged.append(msg)
                continue

            if msg_id not in seen:
                seen.add(msg_id)
                merged.append(msg)
                continue

            existing_idx = next(
                (i for i, m in enumerate(merged) if m.get("id") == msg_id),
                None,
            )
            if existing_idx is not None and _message_content_length(
                msg
            ) > _message_content_length(merged[existing_idx]):
                merged[existing_idx] = msg

    return merged
