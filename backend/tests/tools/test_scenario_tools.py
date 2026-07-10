"""
API 场景测试工具单元测试

覆盖 create_test_scenario 周边缓存与会话 ID 解析逻辑，
重点验证：不同 AI 对话（conversation_id 不同）不会互相覆盖场景。
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.agents.tools.api.scenario_tools import (
    SCENARIO_CONVERSATION_CACHE_TTL_MINUTES,
    _cache_key,
    _clear_conversation_scenario_id,
    _get_conversation_scenario_id,
    _get_current_conversation_id,
    _replace_conversation_scenario,
    _scenario_conversation_cache,
    _set_conversation_scenario_id,
)


class TestGetCurrentConversationId:
    def test_reads_from_config(self):
        config = {"configurable": {"conversation_id": "conv-123"}}
        assert _get_current_conversation_id(config) == "conv-123"

    def test_returns_none_when_config_missing(self):
        assert _get_current_conversation_id(None) is None

    def test_returns_none_when_configurable_missing(self):
        assert _get_current_conversation_id({}) is None

    def test_returns_none_when_conversation_id_empty(self):
        config = {"configurable": {"conversation_id": ""}}
        assert _get_current_conversation_id(config) is None


class TestConversationCache:
    def setup_method(self):
        _scenario_conversation_cache.clear()

    def teardown_method(self):
        _scenario_conversation_cache.clear()

    def test_cache_key_uses_conversation_and_project(self):
        project_id = uuid4()
        assert _cache_key("conv-1", project_id) == ("conv-1", project_id)

    def test_set_and_get_round_trip(self):
        project_id = uuid4()
        scenario_id = uuid4()
        _set_conversation_scenario_id("conv-1", project_id, scenario_id)
        assert _get_conversation_scenario_id("conv-1", project_id) == scenario_id

    def test_different_conversations_are_isolated(self):
        project_id = uuid4()
        scenario_a = uuid4()
        scenario_b = uuid4()
        _set_conversation_scenario_id("conv-a", project_id, scenario_a)
        _set_conversation_scenario_id("conv-b", project_id, scenario_b)
        assert _get_conversation_scenario_id("conv-a", project_id) == scenario_a
        assert _get_conversation_scenario_id("conv-b", project_id) == scenario_b

    def test_expired_entry_is_removed(self):
        project_id = uuid4()
        scenario_id = uuid4()
        # 手动写入一个已经过期的条目
        expired_at = datetime.now(timezone.utc) - timedelta(
            minutes=SCENARIO_CONVERSATION_CACHE_TTL_MINUTES + 1
        )
        key = _cache_key("conv-expired", project_id)
        _scenario_conversation_cache[key] = (scenario_id, expired_at)
        assert _get_conversation_scenario_id("conv-expired", project_id) is None
        assert key not in _scenario_conversation_cache

    def test_clear_removes_entry(self):
        project_id = uuid4()
        scenario_id = uuid4()
        _set_conversation_scenario_id("conv-1", project_id, scenario_id)
        _clear_conversation_scenario_id("conv-1", project_id)
        assert _get_conversation_scenario_id("conv-1", project_id) is None


class TestReplaceConversationScenario:
    def setup_method(self):
        _scenario_conversation_cache.clear()

    def teardown_method(self):
        _scenario_conversation_cache.clear()

    @pytest.mark.asyncio
    async def test_skips_replacement_when_conversation_id_is_none(self):
        session = AsyncMock()
        await _replace_conversation_scenario(session, None, uuid4())
        session.get.assert_not_awaited()
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_replacement_when_no_cached_scenario(self):
        session = AsyncMock()
        await _replace_conversation_scenario(session, "conv-no-cache", uuid4())
        session.get.assert_not_awaited()
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_deletes_cached_scenario_and_clears_cache(self):
        project_id = uuid4()
        scenario_id = uuid4()
        conversation_id = "conv-to-replace"

        scenario = MagicMock()
        session = AsyncMock()
        session.get = AsyncMock(return_value=scenario)
        session.commit = AsyncMock()
        session.delete = AsyncMock()

        _set_conversation_scenario_id(conversation_id, project_id, scenario_id)

        await _replace_conversation_scenario(session, conversation_id, project_id)

        session.get.assert_awaited_once_with(
            _get_test_scenario_class(), scenario_id
        )
        session.delete.assert_awaited_once_with(scenario)
        session.commit.assert_awaited_once()
        assert _get_conversation_scenario_id(conversation_id, project_id) is None

    @pytest.mark.asyncio
    async def test_only_replaces_scenario_for_same_conversation(self):
        project_id = uuid4()
        scenario_a = uuid4()
        _set_conversation_scenario_id("conv-a", project_id, scenario_a)

        session = AsyncMock()
        session.get = AsyncMock(return_value=MagicMock())

        # conv-b 不应该删除 conv-a 的场景
        await _replace_conversation_scenario(session, "conv-b", project_id)
        session.get.assert_not_awaited()
        assert _get_conversation_scenario_id("conv-a", project_id) == scenario_a


def _get_test_scenario_class():
    """延迟导入，避免在模块导入时触发 SQLAlchemy 反射等副作用。"""
    from app.models.test_scenario import TestScenario

    return TestScenario
