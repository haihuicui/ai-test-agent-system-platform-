"""
API Agent 工具模块

本目录包含所有 API 测试智能体的工具定义，按功能分类组织。
"""

from typing import List
from langchain_core.tools import BaseTool

from app.agents.tools.api.openapi_tools import (
    list_api_endpoints,
    get_endpoint_details,
    get_multiple_endpoints_details,
    get_folder_structure,
)

from app.agents.tools.api.environment_tools import (
    get_project_environments,
    get_environment_details,
)

from app.agents.tools.api.artifacts_tools import (
    save_test_plan,
    save_test_cases,
    save_test_script,
    get_endpoint_artifacts,
    get_artifact_content,
)

from app.agents.tools.api.script_tools import (
    get_api_script_info,
    download_api_script,
    delete_api_script,
)
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVZkTVF3PT06MjJlNmJjMTM=

from app.agents.tools.api.execution_tools import (
    execute_api_script,
    execute_api_script_by_artifact_id,
    get_test_execution_status,
)

from app.agents.tools.api.runner_tools import (
    run_tests,
    run_test_suite,
    parse_test_results,
)

from app.agents.tools.api.batch_tools import (
    batch_generate_tests,
    batch_run_tests,
)

from app.agents.tools.api.scenario_tools import (
    create_test_scenario,
    update_test_scenario,
    add_scenario_step,
    update_scenario_step,
    add_data_mapping,
    add_step_extractor,
    add_step_assertion,
    get_scenario_details,
    list_test_scenarios,
    execute_scenario,
)
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVZkTVF3PT06MjJlNmJjMTM=

# 按业务域分类的工具列表
OPENAPI_TOOLS = [
    list_api_endpoints,
    get_endpoint_details,
    get_multiple_endpoints_details,
    get_folder_structure,
]

ENVIRONMENT_TOOLS = [
    get_project_environments,
    get_environment_details,
]

ARTIFACT_TOOLS = [
    save_test_plan,
    save_test_cases,
    save_test_script,
    get_endpoint_artifacts,
    get_artifact_content,
]

SCRIPT_TOOLS = [
    get_api_script_info,
    download_api_script,
    delete_api_script,
]

EXECUTION_TOOLS = [
    execute_api_script,
    execute_api_script_by_artifact_id,
    get_test_execution_status,
]
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVZkTVF3PT06MjJlNmJjMTM=

RUNNER_TOOLS = [
    run_tests,
    run_test_suite,
    parse_test_results,
]

BATCH_TOOLS = [
    batch_generate_tests,
    batch_run_tests,
]

SCENARIO_TOOLS = [
    create_test_scenario,
    update_test_scenario,
    add_scenario_step,
    update_scenario_step,
    add_data_mapping,
    add_step_extractor,
    add_step_assertion,
    get_scenario_details,
    list_test_scenarios,
    execute_scenario,
]

ALL_API_TOOLS = (
    OPENAPI_TOOLS
    + ENVIRONMENT_TOOLS
    + ARTIFACT_TOOLS
    + SCRIPT_TOOLS
    + EXECUTION_TOOLS
    + RUNNER_TOOLS
    + BATCH_TOOLS
    + SCENARIO_TOOLS
)


def get_local_tools() -> List[BaseTool]:
    """
    获取所有 API 本地工具列表。

    MCP 工具在 agent.py 中异步加载，此处只返回本地工具。
    """
    return list(ALL_API_TOOLS)
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVZkTVF3PT06MjJlNmJjMTM=


__all__ = [
    # OpenAPI
    "list_api_endpoints",
    "get_endpoint_details",
    "get_multiple_endpoints_details",
    "get_folder_structure",
    # Environment
    "get_project_environments",
    "get_environment_details",
    # 成果物
    "save_test_plan",
    "save_test_cases",
    "save_test_script",
    "get_endpoint_artifacts",
    "get_artifact_content",
    # 脚本
    "get_api_script_info",
    "download_api_script",
    "delete_api_script",
    # 执行
    "execute_api_script",
    "execute_api_script_by_artifact_id",
    "get_test_execution_status",
    # 运行器
    "run_tests",
    "run_test_suite",
    "parse_test_results",
    # 批量
    "batch_generate_tests",
    "batch_run_tests",
    # 场景
    "create_test_scenario",
    "update_test_scenario",
    "add_scenario_step",
    "update_scenario_step",
    "add_data_mapping",
    "add_step_extractor",
    "add_step_assertion",
    "get_scenario_details",
    "list_test_scenarios",
    "execute_scenario",
    # 分类列表
    "OPENAPI_TOOLS",
    "ARTIFACT_TOOLS",
    "SCRIPT_TOOLS",
    "EXECUTION_TOOLS",
    "RUNNER_TOOLS",
    "BATCH_TOOLS",
    "SCENARIO_TOOLS",
    "ALL_API_TOOLS",
    "get_local_tools",
]
