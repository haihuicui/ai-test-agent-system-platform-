"""
API 场景测试工具单元测试

覆盖 create_test_scenario 周边缓存与会话 ID 解析逻辑，
重点验证：不同 AI 对话（conversation_id 不同）不会互相覆盖场景。
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.agents.tools.api.scenario_design_validator import _validate_scenario_design
from app.agents.tools.api.scenario_tools import (
    SCENARIO_CONVERSATION_CACHE_TTL_MINUTES,
    _cache_key,
    _clear_conversation_scenario_id,
    _fill_required_body_defaults,
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


class TestFillRequiredBodyDefaults:
    """测试 add_scenario_step 自动填充必填字段默认值"""

    def _make_endpoint(self, request_body=None):
        endpoint = MagicMock()
        endpoint.request_body = request_body
        return endpoint

    def test_no_fill_when_body_already_provided(self):
        endpoint = self._make_endpoint({
            "content": {
                "application/json": {
                    "schema": {"required": ["name"], "properties": {"name": {"type": "string"}}}
                }
            }
        })
        override = {"body": {"name": "manual"}}
        result, filled = _fill_required_body_defaults(endpoint, override)
        assert result["body"]["name"] == "manual"
        assert filled == []

    def test_fill_string_name_with_faker(self):
        endpoint = self._make_endpoint({
            "content": {
                "application/json": {
                    "schema": {
                        "required": ["name", "address"],
                        "properties": {
                            "name": {"type": "string"},
                            "address": {"type": "string"},
                        },
                    }
                }
            }
        })
        result, filled = _fill_required_body_defaults(endpoint, {})
        assert "name" in filled
        assert "address" in filled
        assert result["body"]["name"] == "{{$faker.name}}"
        assert result["body"]["address"] == "{{$faker.address}}"

    def test_fill_integer_count_with_one(self):
        endpoint = self._make_endpoint({
            "content": {
                "application/json": {
                    "schema": {
                        "required": ["pageSize"],
                        "properties": {"pageSize": {"type": "integer"}},
                    }
                }
            }
        })
        result, filled = _fill_required_body_defaults(endpoint, None)
        assert filled == ["pageSize"]
        assert result["body"]["pageSize"] == 1

    def test_no_fill_when_no_required(self):
        endpoint = self._make_endpoint({
            "content": {
                "application/json": {
                    "schema": {"type": "object", "properties": {"name": {"type": "string"}}}
                }
            }
        })
        result, filled = _fill_required_body_defaults(endpoint, {})
        assert "body" not in result
        assert filled == []


class TestValidateScenarioDesign:
    """测试场景设计静态预检"""

    def _make_step(self, step_id, step_order, name, endpoint_id, **kwargs):
        step = MagicMock()
        step.id = step_id
        step.step_order = step_order
        step.name = name
        step.endpoint_id = endpoint_id
        step.request_override = kwargs.get("request_override", {})
        step.assertions = kwargs.get("assertions", [])
        step.extractors = kwargs.get("extractors", [])
        step.continue_on_failure = kwargs.get("continue_on_failure", False)
        step.delay_ms = kwargs.get("delay_ms", 0)
        return step

    def _make_endpoint(self, endpoint_id, method="POST", path="/items", request_body=None, parameters=None):
        endpoint = MagicMock()
        endpoint.id = endpoint_id
        endpoint.method = method
        endpoint.path = path
        endpoint.request_body = request_body or {}
        endpoint.parameters = parameters or []
        return endpoint

    @pytest.mark.asyncio
    async def test_detects_missing_required_field(self):
        step_id = uuid4()
        endpoint_id = uuid4()
        scenario_id = uuid4()

        step = self._make_step(step_id, 1, "新增", endpoint_id)
        endpoint = self._make_endpoint(
            endpoint_id,
            request_body={
                "content": {
                    "application/json": {
                        "schema": {
                            "required": ["name"],
                            "properties": {"name": {"type": "string"}},
                        }
                    }
                }
            },
        )

        session = AsyncMock()
        session.get = AsyncMock(return_value=MagicMock(global_variables={}))
        session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))

        result = await _validate_scenario_design(
            session, scenario_id, [step], {endpoint_id: endpoint}, None
        )

        assert result["valid"] is False
        assert any(i["category"] == "missing_required_field" for i in result["errors"])

    @pytest.mark.asyncio
    async def test_detects_unmapped_path_param(self):
        step_id = uuid4()
        endpoint_id = uuid4()
        scenario_id = uuid4()

        step = self._make_step(
            step_id, 1, "编辑", endpoint_id,
            request_override={"path": "/items/{itemId}"},
        )
        endpoint = self._make_endpoint(endpoint_id, method="PUT", path="/items/{itemId}")

        session = AsyncMock()
        session.get = AsyncMock(return_value=MagicMock(global_variables={}))
        session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))

        result = await _validate_scenario_design(
            session, scenario_id, [step], {endpoint_id: endpoint}, None
        )

        assert result["valid"] is False
        assert any(i["category"] == "unmapped_path_param" for i in result["errors"])

    @pytest.mark.asyncio
    async def test_passes_when_path_param_extracted(self):
        step_id = uuid4()
        endpoint_id = uuid4()
        scenario_id = uuid4()

        step = self._make_step(
            step_id, 1, "编辑", endpoint_id,
            request_override={"path": "/items/{{itemId}}"},
            extractors=[{"name": "itemId", "path": "$.data.id", "type": "jsonpath"}],
        )
        endpoint = self._make_endpoint(endpoint_id, method="PUT", path="/items/{itemId}")

        session = AsyncMock()
        session.get = AsyncMock(return_value=MagicMock(global_variables={}))
        session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))

        result = await _validate_scenario_design(
            session, scenario_id, [step], {endpoint_id: endpoint}, None
        )

        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_warns_missing_teardown_for_create_step(self):
        step_id = uuid4()
        endpoint_id = uuid4()
        scenario_id = uuid4()

        step = self._make_step(
            step_id, 1, "新增客户", endpoint_id,
            assertions=[{"type": "status", "expected": 200}],
        )
        endpoint = self._make_endpoint(endpoint_id, method="POST", path="/customers")

        session = AsyncMock()
        session.get = AsyncMock(return_value=MagicMock(global_variables={}))
        session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))

        result = await _validate_scenario_design(
            session, scenario_id, [step], {endpoint_id: endpoint}, None
        )

        assert any(w["category"] == "missing_teardown" for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_warns_unverified_query_param(self):
        step_id = uuid4()
        endpoint_id = uuid4()
        scenario_id = uuid4()

        step = self._make_step(
            step_id, 1, "分页查询", endpoint_id,
            request_override={"params": {"orders": "created_at desc"}},
            assertions=[{"type": "status", "expected": 200}],
        )
        endpoint = self._make_endpoint(endpoint_id, method="GET", path="/customers")

        session = AsyncMock()
        session.get = AsyncMock(return_value=MagicMock(global_variables={}))
        session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))

        result = await _validate_scenario_design(
            session, scenario_id, [step], {endpoint_id: endpoint}, None
        )

        assert any(w["category"] == "unverified_param" for w in result["warnings"])
