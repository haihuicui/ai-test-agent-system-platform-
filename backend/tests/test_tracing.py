"""Langfuse 打标（CallbackHandler 子类派生）测试。

背景：中间件写回 config.metadata 传播不到回调（patch_config 语义），
trace 维度由 SessionEnrichedCallbackHandler 从平台注入的 metadata
（thread_id/project_identifier）派生。本测试锁定该派生逻辑。
"""
from __future__ import annotations

import pytest

langfuse = pytest.importorskip("langfuse", reason="langfuse 未安装时跳过")

from app.core.tracing import _make_session_enriched_handler_class  # noqa: E402


@pytest.fixture()
def handler():
    cls = _make_session_enriched_handler_class()
    # 不触发 Langfuse 客户端初始化：裸实例仅用于元数据解析方法
    return cls.__new__(cls)


class TestTraceAttributeDerivation:
    def test_session_derived_from_thread_id(self, handler):
        attrs = handler._parse_langfuse_trace_attributes_from_metadata(
            {"thread_id": "thread-abc", "project_identifier": "PR-1"}
        )
        assert attrs["session_id"] == "thread-abc"
        assert "project:PR-1" in attrs["tags"]

    def test_explicit_session_id_wins(self, handler):
        """调用方显式 langfuse_session_id 优先于 thread_id 派生。"""
        attrs = handler._parse_langfuse_trace_attributes_from_metadata(
            {"langfuse_session_id": "explicit-sess", "thread_id": "thread-abc"}
        )
        assert attrs["session_id"] == "explicit-sess"

    def test_graph_level_tags_preserved(self, handler):
        """图级 agent:<name> 标签保留，project 标签追加而非覆盖。"""
        attrs = handler._parse_langfuse_trace_attributes_from_metadata(
            {
                "thread_id": "t1",
                "project_identifier": "PR-1",
                "langfuse_tags": ["agent:web"],
            }
        )
        assert attrs["tags"] == ["agent:web", "project:PR-1"]

    def test_empty_metadata(self, handler):
        assert handler._parse_langfuse_trace_attributes_from_metadata(None) == {}
        assert handler._parse_langfuse_trace_attributes_from_metadata({}) == {}

    def test_no_project_no_tag(self, handler):
        attrs = handler._parse_langfuse_trace_attributes_from_metadata(
            {"thread_id": "t1"}
        )
        assert attrs["session_id"] == "t1"
        assert "tags" not in attrs
