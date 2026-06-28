"""
API Agent 的 OpenAPI 解析工具

提供 OpenAPI 文件解析、文件夹结构生成、接口查询等功能。

主要工具：
- parse_openapi_and_create_structure: 解析 OpenAPI JSON 并创建文件夹结构
- list_api_endpoints: 列出项目的 API 端点（支持多种过滤方式）
- get_endpoint_details: 获取单个 API 端点的详细信息
- get_multiple_endpoints_details: 批量获取多个 API 端点的详细信息
- get_folder_structure: 获取项目的文件夹结构
"""

import json
from typing import Any
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.models.api_endpoint import APIEndpoint
from app.models.attachment import Attachment
from app.models.folder import Folder
from app.models.folder_type import FolderType
from app.models.project import Project
from app.services.openapi_parser import OpenAPIParser


# @tool
# async def parse_openapi_and_create_structure(
#     project_identifier: str,
#     openapi_json: dict[str, Any],
#     parent_folder_id: str | None = None
# ) -> str:
#     """
#     解析 OpenAPI JSON 并创建文件夹结构
#
#     此工具会解析 OpenAPI/Swagger 格式的 JSON 文档，并自动创建如下的文件夹结构：
#
#     父文件夹（如 "Activities"）
#         ├── 子文件夹 "GET-Activities"
#         ├── 子文件夹 "POST-Activities"
#         └── ...
#
#     Args:
#         project_identifier: 项目标识符（如 "PR-1234"）
#         openapi_json: OpenAPI 规范的 JSON 字典
#         parent_folder_id: 父文件夹 ID（可选，如果为空则在项目根目录创建）
#
#     Returns:
#         JSON 格式的创建结果，包含：
#         - schema_title: Schema 标题
#         - schema_version: Schema 版本
#         - total_endpoints: 端点总数
#         - tag_folders: 创建的标签文件夹列表
#         - endpoints: 创建的端点列表
#
#     Example:
#         >>> result = await parse_openapi_and_create_structure(
#         ...     project_identifier="PR-1234",
#         ...     openapi_json={"openapi": "3.0.0", "info": {...}, "paths": {...}},
#         ...     parent_folder_id=None
#         ... )
#     """
#     async for db in get_db():
#         try:
#             # 1. 查询项目
#             project_stmt = select(Project).where(
#                 Project.identifier == project_identifier
#             )
#             project_result = await db.execute(project_stmt)
#             project = project_result.scalar_one_or_none()
#
#             if not project:
#                 return json.dumps({
#                     "success": False,
#                     "error": f"项目 {project_identifier} 不存在"
#                 }, ensure_ascii=False, indent=2)
#
#             # 2. 转换 parent_folder_id
#             parent_id = UUID(parent_folder_id) if parent_folder_id else None
#
#             # 3. 创建解析器实例
#             parser = OpenAPIParser(db)
#
#             # 4. 解析并创建结构
#             result = await parser.parse_and_create_structure(
#                 project_id=project.id,
#                 parent_folder_id=parent_id,
#                 schema_file_id=None,  # 暂时不上传文件
#                 openapi_spec=openapi_json,
#                 user_id=project.created_by  # 使用项目创建者作为操作用户
#             )
#
#             # 5. 提交事务
#             await db.commit()
#
#             # 6. 返回结果
#             return json.dumps({
#                 "success": True,
#                 "message": f"成功解析并创建了 {result['total_endpoints']} 个 API 端点",
#                 "data": result
#             }, ensure_ascii=False, indent=2)
#
#         except Exception as e:
#             await db.rollback()
#             return json.dumps({
#                 "success": False,
#                 "error": f"解析 OpenAPI 文件失败: {str(e)}"
#             }, ensure_ascii=False, indent=2)


@tool
async def list_api_endpoints(
    project_identifier: str,
    folder_id: str | None = None,
    tag_group: str | None = None,
    method: str | None = None,
    endpoint_ids: list[str] | None = None
) -> str:
    """
    列出项目的 API 端点

    Args:
        project_identifier: 项目标识符
        folder_id: 文件夹 ID（可选，过滤特定文件夹的端点）
        tag_group: 标签分组（可选，过滤特定标签的端点）
        method: HTTP 方法（可选，过滤特定方法，如 "GET", "POST" 等）
        endpoint_ids: 端点 ID 列表（可选，只获取指定的端点）

    Returns:
        JSON 格式的端点列表

    Example:
        >>> result = await list_api_endpoints(
        ...     project_identifier="PR-1234",
        ...     tag_group="Activities",
        ...     method="GET"
        ... )
        >>> # 获取特定端点的信息
        >>> result = await list_api_endpoints(
        ...     project_identifier="PR-1234",
        ...     endpoint_ids=["uuid-1", "uuid-2"]
        ... )
    """
    async for db in get_db():
        try:
            # 查询项目
            project_stmt = select(Project).where(
                Project.identifier == project_identifier
            )
            project_result = await db.execute(project_stmt)
            project = project_result.scalar_one_or_none()

            if not project:
                return json.dumps({
                    "success": False,
                    "error": f"项目 {project_identifier} 不存在"
                }, ensure_ascii=False, indent=2)

            # 构建查询
            endpoint_stmt = select(APIEndpoint).where(
                APIEndpoint.project_id == project.id
            )

            # 如果提供了 endpoint_ids，只查询指定的端点
            if endpoint_ids:
                try:
                    endpoint_uuids = [UUID(eid) for eid in endpoint_ids]
                    endpoint_stmt = endpoint_stmt.where(
                        APIEndpoint.id.in_(endpoint_uuids)
                    )
                except ValueError:
                    return json.dumps({
                        "success": False,
                        "error": "无效的端点 ID 格式"
                    }, ensure_ascii=False, indent=2)
            else:
                # 否则应用其他过滤条件
                if folder_id:
                    endpoint_stmt = endpoint_stmt.where(
                        APIEndpoint.folder_id == UUID(folder_id)
                    )
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1c0MFZBPT06MzgxZDc5MDY=

                if tag_group:
                    endpoint_stmt = endpoint_stmt.where(
                        APIEndpoint.tag_group == tag_group
                    )

                if method:
                    endpoint_stmt = endpoint_stmt.where(
                        APIEndpoint.method == method.upper()
                    )
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1c0MFZBPT06MzgxZDc5MDY=

            endpoint_stmt = endpoint_stmt.order_by(
                APIEndpoint.tag_group,
                APIEndpoint.sort_order,
                APIEndpoint.path
            )

            # 执行查询
            endpoint_result = await db.execute(endpoint_stmt)
            endpoints = endpoint_result.scalars().all()

            # 转换为字典列表
            endpoints_data = []
            for endpoint in endpoints:
                endpoints_data.append({
                    "id": str(endpoint.id),
                    "display_name": endpoint.display_name,
                    "path": endpoint.path,
                    "method": endpoint.method,
                    "summary": endpoint.summary,
                    "description": endpoint.description,
                    "tag_group": endpoint.tag_group,
                    "folder_id": str(endpoint.folder_id) if endpoint.folder_id else None,
                    "total_test_cases": endpoint.total_test_cases,
                    "total_test_runs": endpoint.total_test_runs,
                    "last_run_status": endpoint.last_run_status
                })

            return json.dumps({
                "success": True,
                "total": len(endpoints_data),
                "endpoints": endpoints_data
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"查询 API 端点失败: {str(e)}"
            }, ensure_ascii=False, indent=2)


@tool
async def get_endpoint_details(
    endpoint_id: str
) -> str:
    """
    获取 API 端点的详细信息

    Args:
        endpoint_id: 端点 ID

    Returns:
        JSON 格式的端点详细信息，包括参数、请求体、响应等

    Example:
        >>> result = await get_endpoint_details(endpoint_id="123e4567-e89b-12d3-a456-426614174000")
    """
    async for db in get_db():
        try:
            # 查询端点
            endpoint_stmt = select(APIEndpoint).where(
                APIEndpoint.id == UUID(endpoint_id)
            )
            endpoint_result = await db.execute(endpoint_stmt)
            endpoint = endpoint_result.scalar_one_or_none()

            if not endpoint:
                return json.dumps({
                    "success": False,
                    "error": f"端点 {endpoint_id} 不存在"
                }, ensure_ascii=False, indent=2)

            # 构建详细信息
            endpoint_data = {
                "id": str(endpoint.id),
                "display_name": endpoint.display_name,
                "path": endpoint.path,
                "method": endpoint.method,
                "summary": endpoint.summary,
                "description": endpoint.description,
                "tag_group": endpoint.tag_group,
                "folder_id": str(endpoint.folder_id) if endpoint.folder_id else None,
                "parameters": endpoint.parameters,
                "request_body": endpoint.request_body,
                "responses": endpoint.responses,
                "security": endpoint.security,
                "tags": endpoint.tags,
                "custom_config": endpoint.custom_config,
                "statistics": {
                    "total_test_cases": endpoint.total_test_cases,
                    "total_test_runs": endpoint.total_test_runs,
                    "last_run_status": endpoint.last_run_status
                },
                "created_at": endpoint.created_at.isoformat(),
                "updated_at": endpoint.updated_at.isoformat() if endpoint.updated_at else None
            }

            return json.dumps({
                "success": True,
                "endpoint": endpoint_data
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"获取端点详情失败: {str(e)}"
            }, ensure_ascii=False, indent=2)


@tool
async def get_multiple_endpoints_details(
    endpoint_ids: list[str]
) -> str:
    """
    批量获取多个 API 端点的详细信息

    此工具用于一次性获取多个端点的详细信息，比单独调用 get_endpoint_details 更高效。

    Args:
        endpoint_ids: 端点 ID 列表

    Returns:
        JSON 格式的端点详细信息列表

    Example:
        >>> result = await get_multiple_endpoints_details(
        ...     endpoint_ids=["uuid-1", "uuid-2", "uuid-3"]
        ... )
    """
    async for db in get_db():
        try:
            if not endpoint_ids:
                return json.dumps({
                    "success": False,
                    "error": "端点 ID 列表不能为空"
                }, ensure_ascii=False, indent=2)

            # 转换 ID 列表
            try:
                endpoint_uuids = [UUID(eid) for eid in endpoint_ids]
            except ValueError as e:
                return json.dumps({
                    "success": False,
                    "error": f"无效的端点 ID 格式: {str(e)}"
                }, ensure_ascii=False, indent=2)

            # 批量查询端点
            endpoint_stmt = select(APIEndpoint).where(
                APIEndpoint.id.in_(endpoint_uuids)
            )
            endpoint_result = await db.execute(endpoint_stmt)
            endpoints = endpoint_result.scalars().all()
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1c0MFZBPT06MzgxZDc5MDY=

            if not endpoints:
                return json.dumps({
                    "success": False,
                    "error": "未找到任何端点"
                }, ensure_ascii=False, indent=2)

            # 构建端点信息列表
            endpoints_data = []
            for endpoint in endpoints:
                endpoint_data = {
                    "id": str(endpoint.id),
                    "display_name": endpoint.display_name,
                    "path": endpoint.path,
                    "method": endpoint.method,
                    "summary": endpoint.summary,
                    "description": endpoint.description,
                    "tag_group": endpoint.tag_group,
                    "folder_id": str(endpoint.folder_id) if endpoint.folder_id else None,
                    "parameters": endpoint.parameters,
                    "request_body": endpoint.request_body,
                    "responses": endpoint.responses,
                    "security": endpoint.security,
                    "tags": endpoint.tags,
                    "custom_config": endpoint.custom_config,
                    "statistics": {
                        "total_test_cases": endpoint.total_test_cases,
                        "total_test_runs": endpoint.total_test_runs,
                        "last_run_status": endpoint.last_run_status
                    }
                }
                endpoints_data.append(endpoint_data)

            return json.dumps({
                "success": True,
                "total": len(endpoints_data),
                "endpoints": endpoints_data
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"批量获取端点详情失败: {str(e)}"
            }, ensure_ascii=False, indent=2)
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2U1c0MFZBPT06MzgxZDc5MDY=


@tool
async def get_folder_structure(
    project_identifier: str,
    folder_type: str = "api_test"
) -> str:
    """
    获取项目的文件夹结构

    Args:
        project_identifier: 项目标识符
        folder_type: 文件夹类型（"test_case" 或 "api_test"）

    Returns:
        JSON 格式的文件夹树结构

    Example:
        >>> result = await get_folder_structure(
        ...     project_identifier="PR-1234",
        ...     folder_type="api_test"
        ... )
    """
    async for db in get_db():
        try:
            # 查询项目
            project_stmt = select(Project).where(
                Project.identifier == project_identifier
            )
            project_result = await db.execute(project_stmt)
            project = project_result.scalar_one_or_none()

            if not project:
                return json.dumps({
                    "success": False,
                    "error": f"项目 {project_identifier} 不存在"
                }, ensure_ascii=False, indent=2)

            # 查询根文件夹
            folder_stmt = select(Folder).where(
                Folder.project_id == project.id,
                Folder.folder_type == FolderType.API_TEST,
                Folder.parent_id.is_(None)
            ).order_by(Folder.name)

            folder_result = await db.execute(folder_stmt)
            root_folders = folder_result.scalars().all()

            # 递归构建文件夹树
            def build_folder_tree(folder: Folder) -> dict:
                return {
                    "id": str(folder.id),
                    "name": folder.name,
                    "description": folder.description,
                    "folder_type": folder.folder_type.value,
                    "children": [build_folder_tree(child) for child in folder.children]
                }

            folder_tree = [build_folder_tree(folder) for folder in root_folders]

            return json.dumps({
                "success": True,
                "project_identifier": project_identifier,
                "folder_type": folder_type,
                "folder_tree": folder_tree
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"获取文件夹结构失败: {str(e)}"
            }, ensure_ascii=False, indent=2)
