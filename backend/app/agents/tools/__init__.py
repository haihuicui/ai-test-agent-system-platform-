"""
Agent 工具包

包含 Web/API/Testcase 测试相关的本地工具、通用错误处理及工具注册表。
"""

from app.agents.tools.error_handler import (
    wrap_tool_with_error_handling,
    wrap_tools_with_error_handling,
)
from app.agents.tools.web import (
    FUNCTION_TOOLS as WEB_FUNCTION_TOOLS,
    ARTIFACT_TOOLS as WEB_ARTIFACT_TOOLS,
    SCRIPT_TOOLS as WEB_SCRIPT_TOOLS,
    EXECUTION_TOOLS as WEB_EXECUTION_TOOLS,
    ALL_WEB_TOOLS,
    get_local_tools as get_web_local_tools,
)
from app.agents.tools.api import (
    OPENAPI_TOOLS,
    ARTIFACT_TOOLS as API_ARTIFACT_TOOLS,
    SCRIPT_TOOLS as API_SCRIPT_TOOLS,
    EXECUTION_TOOLS as API_EXECUTION_TOOLS,
    RUNNER_TOOLS,
    BATCH_TOOLS,
    SCENARIO_TOOLS,
    ALL_API_TOOLS,
    get_local_tools as get_api_local_tools,
)
from app.agents.tools.testcase import (
    TESTCASE_TOOLS,
    DOCUMENT_TOOLS,
    EXCEL_TOOLS,
    ALL_LOCAL_TOOLS as ALL_TESTCASE_LOCAL_TOOLS,
    get_local_tools as get_testcase_local_tools,
    get_all_tools as get_testcase_all_tools,
)
# pylint: disable  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2UjFWR1VBPT06MTM1ZGVhZjA=

__all__ = [
    # Web
    "get_web_local_tools",
    "WEB_FUNCTION_TOOLS",
    "WEB_ARTIFACT_TOOLS",
    "WEB_SCRIPT_TOOLS",
    "WEB_EXECUTION_TOOLS",
    "ALL_WEB_TOOLS",
    # API
    "get_api_local_tools",
    "OPENAPI_TOOLS",
    "API_ARTIFACT_TOOLS",
    "API_SCRIPT_TOOLS",
    "API_EXECUTION_TOOLS",
    "RUNNER_TOOLS",
    "BATCH_TOOLS",
    "SCENARIO_TOOLS",
    "ALL_API_TOOLS",
    # Testcase
    "get_testcase_local_tools",
    "get_testcase_all_tools",
    "TESTCASE_TOOLS",
    "DOCUMENT_TOOLS",
    "EXCEL_TOOLS",
    "ALL_TESTCASE_LOCAL_TOOLS",
    # 通用
    "wrap_tool_with_error_handling",
    "wrap_tools_with_error_handling",
]
# type: ignore  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2UjFWR1VBPT06MTM1ZGVhZjA=
