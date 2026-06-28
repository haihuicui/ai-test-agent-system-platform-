"""
Security Agent 工具模块

本目录包含所有渗透测试智能体的工具定义，按功能分类组织：
- 信息收集 (recon)
- 漏洞利用 (exploit)
- 报告生成 (report)
- 结果存储 (storage)
"""

from typing import List
from langchain_core.tools import BaseTool

from app.agents.tools.security.recon_tools import (
    recon_subdomains,
    recon_port_scan,
    recon_directory_scan,
    recon_fingerprint,
    recon_full_scan,
)

from app.agents.tools.security.exploit_tools import (
    exploit_sqli,
    exploit_xss,
    exploit_lfi,
    exploit_file_download,
    exploit_full_scan,
)

from app.agents.tools.security.report_tools import (
    generate_pentest_report,
    generate_executive_summary,
    generate_html_pentest_report,
)
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTJ4VmVnPT06MGNlYjVlOTk=

from app.agents.tools.security.storage_tools import (
    storage_create_project,
    storage_list_projects,
    storage_add_vulnerability,
    storage_list_vulnerabilities,
    storage_update_vulnerability_status,
    storage_save_scan_result,
    storage_get_scan_results,
    storage_save_report,
    storage_get_statistics,
)
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTJ4VmVnPT06MGNlYjVlOTk=

from app.agents.tools.security.pentest_mgmt_tools import (
    mgmt_create_pentest,
    mgmt_list_pentests,
    mgmt_save_pentest_report,
    mgmt_list_reports,
    mgmt_add_vulnerability,
    mgmt_list_vulnerabilities,
    mgmt_update_pentest_status,
)

# 按业务域分类的工具列表
RECON_TOOLS = [
    recon_subdomains,
    recon_port_scan,
    recon_directory_scan,
    recon_fingerprint,
    recon_full_scan,
]

EXPLOIT_TOOLS = [
    exploit_sqli,
    exploit_xss,
    exploit_lfi,
    exploit_file_download,
    exploit_full_scan,
]

REPORT_TOOLS = [
    generate_pentest_report,
    generate_executive_summary,
    generate_html_pentest_report,
]
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTJ4VmVnPT06MGNlYjVlOTk=

STORAGE_TOOLS = [
    storage_create_project,
    storage_list_projects,
    storage_add_vulnerability,
    storage_list_vulnerabilities,
    storage_update_vulnerability_status,
    storage_save_scan_result,
    storage_get_scan_results,
    storage_save_report,
    storage_get_statistics,
]

MGMT_TOOLS = [
    mgmt_create_pentest,
    mgmt_list_pentests,
    mgmt_save_pentest_report,
    mgmt_list_reports,
    mgmt_add_vulnerability,
    mgmt_list_vulnerabilities,
    mgmt_update_pentest_status,
]

ALL_SECURITY_TOOLS = (
    RECON_TOOLS
    + EXPLOIT_TOOLS
    + REPORT_TOOLS
    + STORAGE_TOOLS
    + MGMT_TOOLS
)


def get_local_tools() -> List[BaseTool]:
    """
    获取所有 Security 本地工具列表。

    MCP 工具（如 Chart MCP Server）在 agent.py 中异步加载，此处只返回本地工具。
    """
    return list(ALL_SECURITY_TOOLS)
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTJ4VmVnPT06MGNlYjVlOTk=


__all__ = [
    # 信息收集
    "recon_subdomains",
    "recon_port_scan",
    "recon_directory_scan",
    "recon_fingerprint",
    "recon_full_scan",
    # 漏洞利用
    "exploit_sqli",
    "exploit_xss",
    "exploit_lfi",
    "exploit_file_download",
    "exploit_full_scan",
    # 报告生成
    "generate_pentest_report",
    "generate_executive_summary",
    "generate_html_pentest_report",
    # 结果存储
    "storage_create_project",
    "storage_list_projects",
    "storage_add_vulnerability",
    "storage_list_vulnerabilities",
    "storage_update_vulnerability_status",
    "storage_save_scan_result",
    "storage_get_scan_results",
    "storage_save_report",
    "storage_get_statistics",
    # 管理接口
    "mgmt_create_pentest",
    "mgmt_list_pentests",
    "mgmt_save_pentest_report",
    "mgmt_list_reports",
    "mgmt_add_vulnerability",
    "mgmt_list_vulnerabilities",
    "mgmt_update_pentest_status",
    # 分类列表
    "RECON_TOOLS",
    "EXPLOIT_TOOLS",
    "REPORT_TOOLS",
    "STORAGE_TOOLS",
    "MGMT_TOOLS",
    "ALL_SECURITY_TOOLS",
    "get_local_tools",
]
