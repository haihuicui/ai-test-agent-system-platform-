"""API Agent 会话标识三通道读取测试。

覆盖 get_conversation_id 的优先级：config conversation_id（直调图路径）
→ config thread_id（平台注入，前端聊天路径唯一可靠通道）→ contextvar。
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.agents.api import runtime_context
from app.agents.api.runtime_context import conversation_id_ctx, get_conversation_id


@pytest.fixture(autouse=True)
def _clean_ctx():
    token = conversation_id_ctx.set(None)
    yield
    conversation_id_ctx.reset(token)


def _config_with(configurable: dict):
    return {"configurable": configurable}


class TestGetConversationId:
    def test_no_context_returns_none(self):
        with patch.object(runtime_context, "get_config", side_effect=RuntimeError("no config")):
            assert get_conversation_id() is None

    def test_contextvar_fallback(self):
        conversation_id_ctx.set("ctx-conv")
        with patch.object(runtime_context, "get_config", side_effect=RuntimeError("no config")):
            assert get_conversation_id() == "ctx-conv"

    def test_config_conversation_id_wins(self):
        with patch.object(
            runtime_context, "get_config",
            return_value=_config_with({"conversation_id": "explicit-conv", "thread_id": "tid-1"}),
        ):
            assert get_conversation_id() == "explicit-conv"

    def test_thread_id_fallback_when_no_conversation_id(self):
        """前端 SDK 直连路径：无显式 conversation_id 时用平台原生 thread_id。"""
        with patch.object(
            runtime_context, "get_config",
            return_value=_config_with({"thread_id": "tid-1"}),
        ):
            assert get_conversation_id() == "tid-1"

    def test_config_beats_contextvar(self):
        conversation_id_ctx.set("ctx-conv")
        with patch.object(
            runtime_context, "get_config",
            return_value=_config_with({"thread_id": "tid-1"}),
        ):
            assert get_conversation_id() == "tid-1"

    def test_empty_configurable_falls_back_to_contextvar(self):
        conversation_id_ctx.set("ctx-conv")
        with patch.object(runtime_context, "get_config", return_value=_config_with({})):
            assert get_conversation_id() == "ctx-conv"
