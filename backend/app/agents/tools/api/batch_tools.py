"""
API 测试批量操作工具

提供批量生成和执行测试的准备功能。
这些工具用于查询和准备批量操作所需的端点信息，
实际的生成和执行由 MCP 工具和执行工具完成。
"""

import json
from typing import Optional, List
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2U0ZKS09RPT06MmRiZGMwMmI=

from langchain_core.tools import tool
from sqlalchemy import select

from app.config.database import async_session_factory
from app.models.api_endpoint import APIEndpoint
from app.models.project import Project


@tool
async def batch_generate_tests(
    project_identifier: str,
    endpoint_ids: Optional[List[str]] = None,
    tag_group: Optional[str] = None,
    framework: str = "playwright",
    language: str = "typescript"
) -> str:
    """
    准备批量测试生成 - 查询端点并返回生成配置

    此工具用于准备批量生成测试的端点列表和配置。
    返回的端点信息可用于后续调用 api_generator 逐个生成测试。

    Args:
        project_identifier: 项目标识符
        endpoint_ids: 指定的端点 ID 列表（可选）
        tag_group: 按标签过滤（可选，与 endpoint_ids 二选一）
        framework: 测试框架 (playwright/jest/pytest)
        language: 编程语言 (typescript/javascript/python)

    Returns:
        JSON 格式的端点列表和生成配置
    """
    async with async_session_factory() as session:
        try:
            # 查询项目
            project_stmt = select(Project).where(
                Project.identifier == project_identifier
            )
            project_result = await session.execute(project_stmt)
            project = project_result.scalar_one_or_none()

            if not project:
                return json.dumps({
                    "success": False,
                    "error": f"项目 {project_identifier} 不存在"
                }, ensure_ascii=False, indent=2)

            # 构建端点查询
            endpoint_stmt = select(APIEndpoint).where(
                APIEndpoint.project_id == project.id
            )

            if endpoint_ids:
                endpoint_stmt = endpoint_stmt.where(
                    APIEndpoint.id.in_(endpoint_ids)
                )
            elif tag_group:
                endpoint_stmt = endpoint_stmt.where(
                    APIEndpoint.tag_group == tag_group
                )
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2U0ZKS09RPT06MmRiZGMwMmI=

            endpoint_result = await session.execute(endpoint_stmt)
            endpoints = endpoint_result.scalars().all()

            if not endpoints:
                return json.dumps({
                    "success": False,
                    "error": "未找到匹配的端点"
                }, ensure_ascii=False, indent=2)

            # 返回端点列表和配置
            endpoints_info = [
                {
                    "id": str(endpoint.id),
                    "display_name": endpoint.display_name,
                    "path": endpoint.path,
                    "method": endpoint.method,
                    "tag_group": endpoint.tag_group
                }
                for endpoint in endpoints
            ]

            return json.dumps({
                "success": True,
                "message": f"找到 {len(endpoints)} 个端点待生成测试",
                "project_identifier": project_identifier,
                "endpoints": endpoints_info,
                "config": {
                    "framework": framework,
                    "language": language
                },
                "workflow": [
                    "1. 对每个端点调用 get_endpoint_details 获取详情",
                    "2. 调用 api_planner 生成测试计划",
                    "3. 调用 api_generator 生成测试代码",
                    "4. 调用 save_test_plan/save_test_script 保存成果物"
                ]
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"批量生成准备失败: {str(e)}"
            }, ensure_ascii=False, indent=2)
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2U0ZKS09RPT06MmRiZGMwMmI=


@tool
async def batch_run_tests(
    project_identifier: str,
    endpoint_ids: Optional[List[str]] = None,
    tag_group: Optional[str] = None,
    framework: str = "playwright",
    parallel: bool = False
) -> str:
    """
    准备批量测试执行 - 查询端点并返回执行计划

    此工具用于准备批量执行测试的端点列表和执行配置。
    返回的执行计划可用于后续调用 run_test_suite 执行测试。

    Args:
        project_identifier: 项目标识符
        endpoint_ids: 指定的端点 ID 列表（可选）
        tag_group: 按标签过滤（可选）
        framework: 测试框架 (playwright/jest/pytest)
        parallel: 是否并行执行

    Returns:
        JSON 格式的执行计划
    """
    async with async_session_factory() as session:
        try:
            # 查询项目
            project_stmt = select(Project).where(
                Project.identifier == project_identifier
            )
            project_result = await session.execute(project_stmt)
            project = project_result.scalar_one_or_none()

            if not project:
                return json.dumps({
                    "success": False,
                    "error": f"项目 {project_identifier} 不存在"
                }, ensure_ascii=False, indent=2)

            # 构建端点查询
            endpoint_stmt = select(APIEndpoint).where(
                APIEndpoint.project_id == project.id
            )

            if endpoint_ids:
                endpoint_stmt = endpoint_stmt.where(
                    APIEndpoint.id.in_(endpoint_ids)
                )
            elif tag_group:
                endpoint_stmt = endpoint_stmt.where(
                    APIEndpoint.tag_group == tag_group
                )

            endpoint_result = await session.execute(endpoint_stmt)
            endpoints = endpoint_result.scalars().all()

            if not endpoints:
                return json.dumps({
                    "success": False,
                    "error": "未找到匹配的端点"
                }, ensure_ascii=False, indent=2)

            # 构建执行计划
            execution_plan = [
                {
                    "endpoint_id": str(endpoint.id),
                    "display_name": endpoint.display_name,
                    "path": endpoint.path,
                    "method": endpoint.method,
                    "test_path": f"./api-tests/{project_identifier}/endpoints/{endpoint.id}",
                }
                for endpoint in endpoints
            ]

            return json.dumps({
                "success": True,
                "message": f"准备运行 {len(execution_plan)} 个端点的测试",
                "project_identifier": project_identifier,
                "execution_plan": execution_plan,
                "config": {
                    "framework": framework,
                    "parallel": parallel
                },
                "workflow": [
                    "1. 调用 run_test_suite 执行所有测试",
                    "2. 分析测试结果",
                    "3. 对失败的测试调用 api_healer 修复"
                ]
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"批量执行准备失败: {str(e)}"
            }, ensure_ascii=False, indent=2)
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2U0ZKS09RPT06MmRiZGMwMmI=
