"""
TestCase Agent 工具注册表

工具分类：
1. 测试用例管理工具：测试用例的创建、更新和批量操作（HTTP 接口调用）
2. 文档解析工具：从 URL 下载并解析文档内容（PDF/TXT/图片）
3. RAG 工具：知识库检索工具（异步加载）

注意：RAG MCP 工具在 agent.py 的 make_agent() 中异步加载，不在此处定义。
"""

import asyncio
from typing import List

# =============================================================================
# 测试用例管理工具
# =============================================================================

from app.agents.testcase.tools.testcase_tools import (
    create_test_case_tool,
    update_test_case_tool,
    batch_create_test_cases_tool,
)

# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFVsNmJBPT06ODRkMWVkYjA=

# =============================================================================
# 文档解析工具
# =============================================================================

from app.agents.testcase.tools.document_tools import (
    parse_document_from_url,
    get_rag_tools,
)

# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFVsNmJBPT06ODRkMWVkYjA=

# =============================================================================
# 工具集合
# =============================================================================

async def get_local_tools() -> List:
    """
    获取所有本地工具列表。

    MCP 工具在 agent.py 中异步加载，此处只返回本地工具。
    """
    return [
        # 测试用例管理
        create_test_case_tool,
        update_test_case_tool,
        batch_create_test_cases_tool,

        # 文档解析
        parse_document_from_url,
    ]


async def get_all_tools() -> List:
    """
    获取所有工具（包括 RAG MCP 工具）

    Returns:
        所有工具的列表
    """
    local_tools = await get_local_tools()
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFVsNmJBPT06ODRkMWVkYjA=

    # 加载 RAG MCP 工具
    try:
        rag_tools = await get_rag_tools()
        return local_tools + rag_tools
    except Exception as e:
        print(f"Warning: Failed to load RAG MCP tools66666: {e}")
        return local_tools


# =============================================================================
# 工具分类导出（供其他模块使用）
# =============================================================================

TESTCASE_TOOLS = [
    create_test_case_tool,
    update_test_case_tool,
    batch_create_test_cases_tool,
]
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFVsNmJBPT06ODRkMWVkYjA=

DOCUMENT_TOOLS = [
    parse_document_from_url,
]
