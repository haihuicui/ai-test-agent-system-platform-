"""
场景设计校验工具注册与导出测试

validate_scenario_design 的核心逻辑（_validate_scenario_design）已在
backend/tests/tools/test_scenario_tools.py 中覆盖；本文件只验证工具被正确注册。
"""

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
