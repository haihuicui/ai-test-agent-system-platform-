"""Tests for thread message merging utilities."""

from __future__ import annotations

import pytest
from langgraph.types import StateSnapshot

from app.utils.thread_message_utils import (
    _message_content_length,
    merge_messages_from_snapshots,
)


def _snapshot(messages: list[dict], checkpoint_id: str = "ckpt") -> StateSnapshot:
    """Build a minimal StateSnapshot for testing message merging."""
    return StateSnapshot(
        values={"messages": messages},
        next=(),
        config={"configurable": {"checkpoint_id": checkpoint_id}},
        metadata=None,
        created_at=None,
        parent_config=None,
        tasks=(),
        interrupts=(),
    )


class TestMessageContentLength:
    def test_string_content(self):
        assert _message_content_length({"content": "hello"}) == 5

    def test_list_content(self):
        content = [{"type": "text", "text": "hi"}]
        assert _message_content_length({"content": content}) > 0

    def test_empty_content(self):
        assert _message_content_length({}) == 0


class TestMergeMessagesFromSnapshots:
    def test_empty_snapshots(self):
        assert merge_messages_from_snapshots([]) == []

    def test_single_checkpoint(self):
        msgs = [
            {"id": "m1", "type": "human", "content": "hello"},
            {"id": "m2", "type": "ai", "content": "hi"},
        ]
        result = merge_messages_from_snapshots([_snapshot(msgs)])
        assert [m["id"] for m in result] == ["m1", "m2"]

    def test_deduplicates_across_checkpoints(self):
        # Newest-first order as returned by LangGraph.
        snapshots = [
            _snapshot(
                [
                    {"id": "m1", "type": "human", "content": "hello"},
                    {"id": "m2", "type": "ai", "content": "hi"},
                ],
                checkpoint_id="latest",
            ),
            _snapshot(
                [
                    {"id": "m1", "type": "human", "content": "hello"},
                ],
                checkpoint_id="older",
            ),
        ]
        result = merge_messages_from_snapshots(snapshots)
        assert [m["id"] for m in result] == ["m1", "m2"]

    def test_keeps_longer_version_of_same_id(self):
        snapshots = [
            _snapshot(
                [
                    # Latest checkpoint has the compressed/pointer version
                    {"id": "m1", "type": "tool", "content": "[offloaded]"},
                ],
                checkpoint_id="latest",
            ),
            _snapshot(
                [
                    # Older checkpoint has the full content
                    {"id": "m1", "type": "tool", "content": "full content here"},
                ],
                checkpoint_id="older",
            ),
        ]
        result = merge_messages_from_snapshots(snapshots)
        assert len(result) == 1
        assert result[0]["content"] == "full content here"

    def test_preserves_messages_without_id(self):
        snapshots = [
            _snapshot(
                [
                    {"id": "m1", "type": "human", "content": "hello"},
                    {"type": "system", "content": "sys"},
                ]
            )
        ]
        result = merge_messages_from_snapshots(snapshots)
        assert len(result) == 2
        assert result[0]["id"] == "m1"
        assert result[1]["content"] == "sys"

    def test_chronological_order(self):
        snapshots = [
            _snapshot(
                [{"id": "m3", "type": "ai", "content": "third"}],
                checkpoint_id="ckpt-3",
            ),
            _snapshot(
                [{"id": "m2", "type": "ai", "content": "second"}],
                checkpoint_id="ckpt-2",
            ),
            _snapshot(
                [{"id": "m1", "type": "human", "content": "first"}],
                checkpoint_id="ckpt-1",
            ),
        ]
        result = merge_messages_from_snapshots(snapshots)
        assert [m["id"] for m in result] == ["m1", "m2", "m3"]

    def test_ignores_non_dict_messages(self):
        snapshots = [
            _snapshot(
                [
                    {"id": "m1", "type": "human", "content": "hello"},
                    "not-a-dict",
                    123,
                ]
            )
        ]
        result = merge_messages_from_snapshots(snapshots)
        assert [m["id"] for m in result] == ["m1"]

    def test_no_values_field(self):
        snapshot = StateSnapshot(
            values=None,
            next=(),
            config={"configurable": {"checkpoint_id": "empty"}},
            metadata=None,
            created_at=None,
            parent_config=None,
            tasks=(),
            interrupts=(),
        )
        assert merge_messages_from_snapshots([snapshot]) == []
