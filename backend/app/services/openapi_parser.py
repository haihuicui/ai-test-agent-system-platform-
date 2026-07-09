"""
OpenAPI Schema 解析服务

负责解析 OpenAPI/Swagger 文档并生成对应的文件夹结构和端点定义
"""

import json
from typing import Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_endpoint import APIEndpoint
from app.models.attachment import Attachment
from app.models.folder import Folder
from app.models.project import Project
from app.models.folder_type import FolderType


class OpenAPIParser:
    """OpenAPI Schema 解析器"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def parse_and_create_structure(
        self,
        project_id: UUID,
        parent_folder_id: UUID | None,
        schema_file_id: UUID,
        openapi_spec: dict[str, Any],
        user_id: UUID
    ) -> dict[str, Any]:
        """
        解析 OpenAPI Spec 并创建文件夹结构

        Args:
            project_id: 项目 ID
            parent_folder_id: 父文件夹 ID（如果为空，则在项目根目录创建）
            schema_file_id: Schema 文件 ID
            openapi_spec: OpenAPI 规范字典
            user_id: 当前用户 ID

        Returns:
            包含创建的文件夹和端点信息的字典
        """
        # 提取基本信息
        info = openapi_spec.get("info", {})
        title = info.get("title", "API")
        version = info.get("version", "1.0.0")

        # 提取所有路径
        paths = openapi_spec.get("paths", {})
        top_servers = openapi_spec.get("servers", [])

        # 按标签分组端点
        endpoints_by_tag = self._group_endpoints_by_tag(paths, top_servers)
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0ZwV1p3PT06MDg1MGI4ODg=

        # 创建文件夹结构
        result = {
            "schema_title": title,
            "schema_version": version,
            "total_endpoints": sum(len(endpoints) for endpoints in endpoints_by_tag.values()),
            "total_tags": len(endpoints_by_tag),
            "tag_folders": [],
            "endpoints": [],
            "summary": {}  # 新增：汇总信息
        }

        # 为每个标签组创建文件夹
        for tag_name, endpoints in sorted(endpoints_by_tag.items()):
            # 创建标签文件夹（如 "Activities"）
            tag_folder = await self._create_tag_folder(
                project_id=project_id,
                parent_folder_id=parent_folder_id,
                tag_name=tag_name,
                schema_file_id=schema_file_id,
                user_id=user_id
            )
            result["tag_folders"].append({
                "folder_id": str(tag_folder.id),
                "folder_name": tag_name,
                "endpoint_count": len(endpoints)
            })

            # 为每个端点创建子文件夹（如 "GET /api/v1/Activities"）
            for endpoint_data in endpoints:
                endpoint = await self._create_endpoint_folder(
                    project_id=project_id,
                    parent_folder_id=tag_folder.id,
                    endpoint_data=endpoint_data,
                    schema_file_id=schema_file_id,
                    tag_name=tag_name
                )
                result["endpoints"].append({
                    "endpoint_id": str(endpoint.id),
                    "display_name": endpoint.display_name,
                    "folder_name": endpoint.custom_config.get("folder_name", ""),
                    "method": endpoint.method,
                    "path": endpoint.path,
                    "summary": endpoint.summary,
                    "folder_id": str(endpoint.folder_id),
                    "tag_group": tag_name
                })

        # 添加汇总信息
        result["summary"] = {
            "message": f"成功解析 OpenAPI 文档：{title} v{version}",
            "folders_created": len(result["tag_folders"]),
            "endpoints_created": result["total_endpoints"],
            "structure": "已创建按标签分组的文件夹结构，可以在左侧查看"
        }
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0ZwV1p3PT06MDg1MGI4ODg=

        return result

    def _group_endpoints_by_tag(
        self,
        paths: dict[str, Any],
        top_servers: list[dict[str, str]] | None = None
    ) -> dict[str, list[dict[str, Any]]]:
        """
        按标签分组端点

        Args:
            paths: OpenAPI paths 对象
            top_servers: 顶层 servers 配置

        Returns:
            {tag_name: [endpoint_data, ...]}
        """
        endpoints_by_tag: dict[str, list[dict[str, Any]]] = {}
        top_servers = top_servers or []

        for path, path_item in paths.items():
            # 路径级 servers
            path_servers = path_item.get("servers", []) if isinstance(path_item, dict) else []

            # 遍历该路径的所有 HTTP 方法
            for method, method_spec in path_item.items():
                if method.lower() not in ["get", "post", "put", "delete", "patch", "options", "head", "trace"]:
                    continue

                if not isinstance(method_spec, dict):
                    continue

                # 提取标签（如果没有标签，则使用 "Other"）
                tags = method_spec.get("tags", ["Other"])
                primary_tag = tags[0] if tags else "Other"

                # 方法级 servers 优先级最高，其次是路径级，最后是顶层
                operation_servers = method_spec.get("servers", [])
                servers = operation_servers or path_servers or top_servers

                # 构建端点数据
                endpoint_data = {
                    "path": path,
                    "method": method.upper(),
                    "summary": method_spec.get("summary"),
                    "description": method_spec.get("description"),
                    "parameters": method_spec.get("parameters", []),
                    "request_body": method_spec.get("requestBody"),
                    "responses": method_spec.get("responses", {}),
                    "security": method_spec.get("security"),
                    "tags": tags,
                    "deprecated": method_spec.get("deprecated", False),
                    "operation_id": method_spec.get("operationId"),
                    "servers": servers
                }

                # 添加到分组
                if primary_tag not in endpoints_by_tag:
                    endpoints_by_tag[primary_tag] = []
                endpoints_by_tag[primary_tag].append(endpoint_data)

        return endpoints_by_tag
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0ZwV1p3PT06MDg1MGI4ODg=

    async def _create_tag_folder(
        self,
        project_id: UUID,
        parent_folder_id: UUID | None,
        tag_name: str,
        schema_file_id: UUID,
        user_id: UUID
    ) -> Folder:
        """
        创建标签文件夹（如 "Activities"）

        Args:
            project_id: 项目 ID
            parent_folder_id: 父文件夹 ID
            tag_name: 标签名称
            schema_file_id: Schema 文件 ID
            user_id: 用户 ID

        Returns:
            创建的文件夹对象
        """
        # 检查是否已存在同名文件夹
        # 这里简化处理，实际应该查询数据库

        folder = Folder(
            project_id=project_id,
            parent_id=parent_folder_id,
            name=tag_name,
            description=f"API endpoints for {tag_name}",
            folder_type=FolderType.API_TEST
        )

        self.db.add(folder)
        await self.db.flush()

        return folder

    async def _create_endpoint_folder(
        self,
        project_id: UUID,
        parent_folder_id: UUID,
        endpoint_data: dict[str, Any],
        schema_file_id: UUID,
        tag_name: str
    ) -> APIEndpoint:
        """
        创建端点定义和对应的文件夹

        Args:
            project_id: 项目 ID
            parent_folder_id: 父文件夹 ID（标签文件夹）
            endpoint_data: 端点数据
            schema_file_id: Schema 文件 ID
            tag_name: 标签名称

        Returns:
            创建的端点对象
        """
        path = endpoint_data["path"]
        method = endpoint_data["method"]

        # 提取路径的最后一部分作为资源名称
        # 例如：/api/v1/Activities -> Activities
        #       /api/v1/Users/{id} -> Users
        path_parts = path.strip("/").split("/")
        resource_name = path_parts[-1].replace("{", "").replace("}", "") if path_parts else "Unknown"

        # 创建显示名称（保持原样：GET /api/v1/Activities）
        display_name = f"{method} {path}"

        # 创建文件夹名称（简化：GET-Activities）
        folder_name = f"{method}-{resource_name}"

        # 创建文件夹（如 "GET-Activities"）
        endpoint_folder = Folder(
            project_id=project_id,
            parent_id=parent_folder_id,
            name=folder_name,
            description=endpoint_data.get("summary") or endpoint_data.get("description", ""),
            folder_type=FolderType.API_TEST
        )
        self.db.add(endpoint_folder)
        await self.db.flush()

        # 创建端点定义
        endpoint = APIEndpoint(
            project_id=project_id,
            folder_id=endpoint_folder.id,
            display_name=display_name,
            path=path,
            method=method,
            summary=endpoint_data.get("summary"),
            description=endpoint_data.get("description"),
            schema_file_id=schema_file_id,
            parameters=endpoint_data.get("parameters"),
            request_body=endpoint_data.get("request_body"),
            responses=endpoint_data.get("responses"),
            security=endpoint_data.get("security"),
            tags=endpoint_data.get("tags"),
            tag_group=tag_name,
            custom_config={
                "deprecated": endpoint_data.get("deprecated", False),
                "operation_id": endpoint_data.get("operation_id"),
                "resource_name": resource_name,
                "folder_name": folder_name,
                "servers": endpoint_data.get("servers", [])
            },
            sort_order=self._get_method_sort_order(method)
        )
        self.db.add(endpoint)
        await self.db.flush()

        return endpoint

    def _get_method_sort_order(self, method: str) -> int:
        """
        获取 HTTP 方法的排序顺序

        顺序：GET -> POST -> PUT -> PATCH -> DELETE -> 其他
        """
        order = {
            "GET": 0,
            "POST": 1,
            "PUT": 2,
            "PATCH": 3,
            "DELETE": 4
        }
        return order.get(method.upper(), 99)
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0ZwV1p3PT06MDg1MGI4ODg=


async def parse_openapi_from_attachment(
    db: AsyncSession,
    attachment: Attachment
) -> dict[str, Any]:
    """
    从附件对象解析 OpenAPI Spec

    Args:
        db: 数据库会话
        attachment: 附件对象

    Returns:
        OpenAPI 规范字典
    """
    # 从 MinIO 或本地存储读取文件内容
    # 这里简化处理，假设已经有文件内容
    # 实际实现需要从 MinIO 读取

    # 临时方案：假设文件内容在 attachment.file_path
    import aiofiles
    async with aiofiles.open(attachment.file_path, "r", encoding="utf-8") as f:
        content = await f.read()

    return json.loads(content)
