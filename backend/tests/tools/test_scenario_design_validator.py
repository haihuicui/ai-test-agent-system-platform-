"""
场景设计校验工具注册与导出测试

validate_scenario_design 的核心逻辑（_validate_scenario_design）已在
backend/tests/tools/test_scenario_tools.py 中覆盖；本文件只验证工具被正确注册。
"""

import json
from uuid import uuid4

from app.agents.tools.api import SCENARIO_TOOLS
from app.agents.tools.api.scenario_design_validator import (
    _validate_scenario_design,
    validate_scenario_design,
)


class TestValidateScenarioDesignRegistration:
    """测试 validate_scenario_design 工具的注册与导出"""

    def test_tool_is_in_scenario_tools_list(self):
        assert validate_scenario_design in SCENARIO_TOOLS

    def test_tool_has_expected_name(self):
        assert validate_scenario_design.name == "validate_scenario_design"

    def test_tool_exposes_underlying_validator(self):
        """工具包装器应暴露同名的底层校验函数，供测试和中间件复用"""
        assert callable(_validate_scenario_design)

    def test_tool_wrapper_accepts_variables(self):
        """工具包装器应接受 variables 参数并透传给底层校验器"""
        import inspect
        sig = inspect.signature(validate_scenario_design.coroutine)
        assert "variables" in sig.parameters
        param = sig.parameters["variables"]
        assert param.default is None

    def test_tool_wrapper_returns_json_string(self):
        """工具包装器返回 JSON 字符串"""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        scenario_id = uuid4()

        with patch(
            "app.agents.tools.api.scenario_design_validator.async_session_factory"
        ) as mock_factory:
            session = AsyncMock()
            session.execute = AsyncMock(return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            ))
            session.get = AsyncMock(return_value=MagicMock(global_variables={"env": "test"}))

            class _AsyncCtx:
                async def __aenter__(self):
                    return session
                async def __aexit__(self, exc_type, exc, tb):
                    return False

            mock_factory.return_value = _AsyncCtx()

            result = asyncio.run(validate_scenario_design.coroutine(
                scenario_id=str(scenario_id),
                variables={"siteName": "demo"},
            ))

        data = json.loads(result)
        assert data["success"] is True
        assert "valid" in data
        assert "summary" in data
