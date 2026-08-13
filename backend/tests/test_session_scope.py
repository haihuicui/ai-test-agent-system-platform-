"""统一会话作用域（session_scope）测试。

覆盖：
- 三通道读取优先级：平台原生 config 键 → 中间件写回键 → contextvar；
- set_session_scope 的 config 写回与 Langfuse metadata 注入；
- 各 Agent 中间件接入后的行为一致性（经公共模块，无需逐 agent 重复测）。
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

import app.utils.session_scope as scope
from app.utils.session_scope import (
    get_session_project,
    get_session_thread_id,
    session_project_ctx,
    session_thread_ctx,
    set_session_scope,
)


@pytest.fixture(autouse=True)
def _clean_ctx():
    t1 = session_project_ctx.set(None)
    t2 = session_thread_ctx.set(None)
    yield
    session_project_ctx.reset(t1)
    session_thread_ctx.reset(t2)


def _config_with(configurable: dict | None = None, metadata: dict | None = None):
    config: dict = {}
    if configurable is not None:
        config["configurable"] = configurable
    if metadata is not None:
        config["metadata"] = metadata
    return config


class TestReadPriority:
    def test_no_context_returns_none(self):
        with patch.object(scope, "get_config", side_effect=RuntimeError("no config")):
            assert get_session_project() is None
            assert get_session_thread_id() is None

    def test_platform_native_keys_win(self):
        """平台原生键（project_identifier/thread_id）优先于写回键与 contextvar。"""
        set_session_scope("proj-ctx", "thread-ctx")
        config = _config_with({"project_identifier": "proj-native", "thread_id": "thread-native"})
        with patch.object(scope, "get_config", return_value=config):
            assert get_session_project() == "proj-native"
            assert get_session_thread_id() == "thread-native"

    def test_writeback_keys_fallback(self):
        """原生键缺失时回退中间件写回键。"""
        config = _config_with({"session_project": "proj-wb", "session_thread_id": "thread-wb"})
        with patch.object(scope, "get_config", return_value=config):
            assert get_session_project() == "proj-wb"
            assert get_session_thread_id() == "thread-wb"

    def test_contextvar_last_resort(self):
        set_session_scope("proj-var", "thread-var")
        with patch.object(scope, "get_config", side_effect=RuntimeError("no config")):
            assert get_session_project() == "proj-var"
            assert get_session_thread_id() == "thread-var"


class TestSetSessionScope:
    def test_config_writeback(self):
        config = _config_with(configurable={})
        set_session_scope("proj-a", "thread-1", config)
        assert config["configurable"]["session_project"] == "proj-a"
        assert config["configurable"]["session_thread_id"] == "thread-1"

    def test_config_none_tolerated(self):
        """config=None（非平台环境）不抛异常。"""
        set_session_scope("proj-a", "thread-1", None)

    def test_config_without_configurable(self):
        config: dict = {}
        set_session_scope("proj-a", "thread-1", config)
        assert config["configurable"]["session_project"] == "proj-a"


class TestTraceMetadataInjection:
    def test_langfuse_session_and_project_injected(self):
        config = _config_with(configurable={})
        set_session_scope("proj-a", "thread-1", config)
        metadata = config["metadata"]
        assert metadata["langfuse_session_id"] == "thread-1"
        assert metadata["project_id"] == "proj-a"

    def test_existing_metadata_preserved(self):
        """已有 metadata（如图级 langfuse_tags）不被覆盖。"""
        config = _config_with(metadata={"langfuse_tags": ["agent:api"]})
        set_session_scope("proj-a", "thread-1", config)
        assert config["metadata"]["langfuse_tags"] == ["agent:api"]
        assert config["metadata"]["project_id"] == "proj-a"

    def test_empty_values_skip_injection(self):
        config = _config_with(metadata={})
        set_session_scope("", "", config)
        assert "langfuse_session_id" not in config["metadata"]
        assert "project_id" not in config["metadata"]
