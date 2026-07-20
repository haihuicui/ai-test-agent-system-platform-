"""
场景测试质量中间件 ScenarioQualityGateMiddleware 单元测试
"""

from langchain_core.messages import ToolMessage
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agents.api.scenario_quality_middleware import ScenarioQualityGateMiddleware


class TestScenarioQualityGateMiddleware:
    """测试场景质量中间件对 execute_scenario 的拦截与放行"""

    def _make_request(self, name="execute_scenario", args=None):
        request = MagicMock()
        request.tool_call = {
            "id": "call-123",
            "name": name,
            "args": args or {"scenario_id": str(uuid4())},
        }
        return request

    @pytest.mark.asyncio
    async def test_passes_when_validation_succeeds(self):
        request = self._make_request()
        handler = AsyncMock(return_value=MagicMock())

        with patch(
            "app.agents.tools.api.scenario_design_validator.validate_scenario_design"
        ) as mock_validator:
            mock_validator.ainvoke = AsyncMock(
                return_value='{"success": true, "data": {"valid": true}}'
            )
            result = await ScenarioQualityGateMiddleware().awrap_tool_call(request, handler)

        handler.assert_awaited_once_with(request)
        assert result is handler.return_value

    @pytest.mark.asyncio
    async def test_blocks_when_validation_fails(self):
        request = self._make_request()
        handler = AsyncMock(return_value=MagicMock())

        with patch(
            "app.agents.tools.api.scenario_design_validator.validate_scenario_design"
        ) as mock_validator:
            mock_validator.ainvoke = AsyncMock(
                return_value=(
                    '{"success": true, "data": {"valid": false, '
                    '"issues": [{"category": "missing_required_field", '
                    '"message": "缺少必填字段"}]}}'
                )
            )
            result = await ScenarioQualityGateMiddleware().awrap_tool_call(request, handler)

        handler.assert_not_awaited()
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert "场景质量中间件拦截" in result.content

    @pytest.mark.asyncio
    async def test_passes_when_skip_design_gate_set(self):
        request = self._make_request(args={"scenario_id": str(uuid4()), "skip_design_gate": True})
        handler = AsyncMock(return_value=MagicMock())

        with patch(
            "app.agents.tools.api.scenario_design_validator.validate_scenario_design"
        ) as mock_validator:
            result = await ScenarioQualityGateMiddleware().awrap_tool_call(request, handler)

        mock_validator.ainvoke.assert_not_called()
        handler.assert_awaited_once_with(request)
        assert result is handler.return_value

    @pytest.mark.asyncio
    async def test_passes_non_scenario_tools_without_validation(self):
        request = self._make_request(name="create_test_scenario")
        handler = AsyncMock(return_value=MagicMock())

        with patch(
            "app.agents.tools.api.scenario_design_validator.validate_scenario_design"
        ) as mock_validator:
            result = await ScenarioQualityGateMiddleware().awrap_tool_call(request, handler)

        mock_validator.ainvoke.assert_not_called()
        handler.assert_awaited_once_with(request)
        assert result is handler.return_value

    def test_sync_path_passes_without_validation(self):
        request = self._make_request()
        handler = MagicMock(return_value=MagicMock())

        with patch(
            "app.agents.tools.api.scenario_design_validator.validate_scenario_design"
        ) as mock_validator:
            result = ScenarioQualityGateMiddleware().wrap_tool_call(request, handler)

        mock_validator.ainvoke.assert_not_called()
        handler.assert_called_once_with(request)
        assert result is handler.return_value
