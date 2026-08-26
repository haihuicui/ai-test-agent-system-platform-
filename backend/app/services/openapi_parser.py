"""
OpenAPI Schema 解析服务

负责解析 OpenAPI/Swagger 文档并生成对应的文件夹结构和端点定义
"""

import json
from typing import Any
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_endpoint import APIEndpoint
from app.models.attachment import Attachment
from app.models.folder import Folder
from app.models.project import Project
from app.models.folder_type import FolderType
from app.models.openapi_spec_snapshot import OpenAPISpecSnapshot
from app.services.dependency_inference import (
    infer_endpoint_dependencies,
    upsert_inferred_dependencies,
)
from app.services.openapi_resolver import resolve_refs


def _resolve_linked_endpoints(
    links_by_status: dict[str, Any] | None,
    operation_targets: dict[str, str]
) -> list[dict[str, Any]]:
    """
    将 OpenAPI links 解析为可读的接口依赖清单

    OpenAPI 3.0 中 links 定义在 response 对象上，通过 operationId / operationRef
    引用目标接口。此函数把引用解析为 "METHOD path"，供场景设计直接消费
    （link.parameters 保留了「目标接口参数 ← 本接口响应字段」的映射表达式，
    如 {orderId: "$response.body#/id"}，即场景步骤间数据提取/映射的依据）。

    Args:
        links_by_status: {响应状态: {link 名: link 对象}}
        operation_targets: {operationId: "METHOD path"} 全量映射

    Returns:
        [{status, link_name, operation_id, operation_ref, target, description, parameters}]
        target 解析失败（引用了文档外的 operation）时为 None
    """
    resolved = []
    for status, links in (links_by_status or {}).items():
        if not isinstance(links, dict):
            continue
        for name, link in links.items():
            if not isinstance(link, dict):
                continue
            operation_id = link.get("operationId")
            operation_ref = link.get("operationRef")
            target = operation_targets.get(operation_id) if operation_id else None
            resolved.append({
                "status": status,
                "link_name": name,
                "operation_id": operation_id,
                "operation_ref": operation_ref,
                "target": target,
                "description": link.get("description"),
                "parameters": link.get("parameters"),
            })
    return resolved


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
        user_id: UUID,
        source: str = "upload"
    ) -> dict[str, Any]:
        """
        解析 OpenAPI Spec 并创建文件夹结构

        重复导入是幂等的：按 (project_id, method, path) 匹配已有端点做更新，
        文件夹按名复用，不产生重复结构；每次导入留存完整 spec 快照。

        Args:
            project_id: 项目 ID
            parent_folder_id: 父文件夹 ID（如果为空，则在项目根目录创建）
            schema_file_id: Schema 文件 ID
            openapi_spec: OpenAPI 规范字典
            user_id: 当前用户 ID
            source: 文档来源（upload / url），用于快照记录

        Returns:
            包含创建的文件夹和端点信息的字典
        """
        # 提取基本信息
        info = openapi_spec.get("info", {})
        title = info.get("title", "API")
        version = info.get("version", "1.0.0")

        # 提取所有路径，并就地展开本地 $ref（#/components/schemas/、#/definitions/ 等）
        # 循环引用/外部引用/超深保留 $ref 原样，由下游降级处理
        raw_paths = openapi_spec.get("paths", {})
        ref_resolution = "ok"
        try:
            paths = resolve_refs(raw_paths, openapi_spec)
        except Exception:  # pylint: disable=broad-except
            paths = raw_paths
            ref_resolution = "failed_fallback_raw"
        top_servers = openapi_spec.get("servers", [])

        # 留存完整 spec 快照（审计/重解析/排障用）
        self.db.add(OpenAPISpecSnapshot(
            project_id=project_id,
            title=title,
            version=version,
            source=source,
            endpoint_count=len(raw_paths),
            spec=openapi_spec,
        ))

        # 按标签分组端点
        endpoints_by_tag = self._group_endpoints_by_tag(paths, top_servers)

        # 构建 operationId -> "METHOD path" 全量映射，把 links 中的接口引用
        # 解析为可读依赖清单（写入 custom_config.linked_endpoints）
        operation_targets: dict[str, str] = {}
        for endpoints in endpoints_by_tag.values():
            for endpoint_data in endpoints:
                if endpoint_data.get("operation_id"):
                    operation_targets.setdefault(
                        endpoint_data["operation_id"],
                        f"{endpoint_data['method']} {endpoint_data['path']}"
                    )
        for endpoints in endpoints_by_tag.values():
            for endpoint_data in endpoints:
                endpoint_data["linked_endpoints"] = (
                    _resolve_linked_endpoints(endpoint_data.get("links"), operation_targets) or None
                )
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
        created_endpoints: list[dict[str, Any]] = []  # (端点 + 原始数据)，供依赖推断使用
        endpoints_created = 0
        endpoints_updated = 0
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
                endpoint, was_created = await self._create_endpoint_folder(
                    project_id=project_id,
                    parent_folder_id=tag_folder.id,
                    endpoint_data=endpoint_data,
                    schema_file_id=schema_file_id,
                    tag_name=tag_name
                )
                if was_created:
                    endpoints_created += 1
                else:
                    endpoints_updated += 1
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
                created_endpoints.append({
                    "endpoint_id": str(endpoint.id),
                    "method": endpoint.method,
                    "path": endpoint.path,
                    "parameters": endpoint_data.get("parameters"),
                    "request_body": endpoint_data.get("request_body"),
                    "responses": endpoint_data.get("responses"),
                    "linked_endpoints": endpoint_data.get("linked_endpoints"),
                })

        # 导入期依赖推断（RESTler 风格 producer-consumer 匹配）：
        # 把 {xxxId} 路径参数 / 请求体 ID 引用与创建接口静态配对，写入 api_annotations
        # （annotation_type='dependency', source='openapi_inferred'）。
        # 推断失败不阻塞导入，仅在 summary 中记录。
        try:
            dep_candidates = infer_endpoint_dependencies(created_endpoints)
            dep_result = await upsert_inferred_dependencies(self.db, project_id, dep_candidates)
            dep_result["total"] = len(dep_candidates)
        except Exception as dep_err:  # pylint: disable=broad-except
            dep_result = {"error": str(dep_err), "total": 0}

        # 添加汇总信息
        result["summary"] = {
            "message": f"成功解析 OpenAPI 文档：{title} v{version}",
            "folders_created": len(result["tag_folders"]),
            "endpoints_created": endpoints_created,
            "endpoints_updated": endpoints_updated,
            "ref_resolution": ref_resolution,
            "dependencies_inferred": dep_result,
            "structure": "已创建按标签分组的文件夹结构，可以在左侧查看；重复导入按 (method, path) 更新已有端点"
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

                # OpenAPI links 定义在 response 对象上（非 operation 级），
                # 按响应状态分组收集，如 {"201": {"GetOrder": {...}}}
                links_by_status: dict[str, Any] = {}
                for status, resp in (method_spec.get("responses") or {}).items():
                    if isinstance(resp, dict) and resp.get("links"):
                        links_by_status[str(status)] = resp["links"]

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
                    "servers": servers,
                    "links": links_by_status or None,
                    "callbacks": method_spec.get("callbacks")
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
        # 幂等：同项目 + 同父目录 + 同名的 API_TEST 标签文件夹直接复用（重复导入不产生重复结构）
        existing_stmt = select(Folder).where(
            Folder.project_id == project_id,
            Folder.parent_id == parent_folder_id,
            Folder.name == tag_name,
            Folder.folder_type == FolderType.API_TEST,
        )
        existing_result = await self.db.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()
        if existing:
            return existing

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
    ) -> tuple[APIEndpoint, bool]:
        """
        创建或更新端点定义（幂等）及对应的文件夹

        按 (project_id, method, path) 匹配已有端点：
        - 已存在 → 就地更新契约字段（参数/请求体/响应/security/links 等），
          复用原文件夹，返回 (endpoint, False)
        - 不存在 → 新建端点与子文件夹，返回 (endpoint, True)

        Args:
            project_id: 项目 ID
            parent_folder_id: 父文件夹 ID（标签文件夹）
            endpoint_data: 端点数据
            schema_file_id: Schema 文件 ID
            tag_name: 标签名称

        Returns:
            (端点对象, 是否新建)
        """
        path = endpoint_data["path"]
        method = endpoint_data["method"]

        # 幂等：同项目同方法同路径的端点就地更新（重复导入不产生重复端点）
        existing_stmt = select(APIEndpoint).where(
            APIEndpoint.project_id == project_id,
            APIEndpoint.method == method,
            APIEndpoint.path == path,
        )
        existing_result = await self.db.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()
        if existing:
            existing.summary = endpoint_data.get("summary")
            existing.description = endpoint_data.get("description")
            existing.schema_file_id = schema_file_id
            existing.parameters = endpoint_data.get("parameters")
            existing.request_body = endpoint_data.get("request_body")
            existing.responses = endpoint_data.get("responses")
            existing.security = endpoint_data.get("security")
            existing.links = endpoint_data.get("links")
            existing.callbacks = endpoint_data.get("callbacks")
            existing.tags = endpoint_data.get("tags")
            existing.tag_group = tag_name
            existing.sort_order = self._get_method_sort_order(method)
            existing.custom_config = {
                "deprecated": endpoint_data.get("deprecated", False),
                "operation_id": endpoint_data.get("operation_id"),
                "resource_name": (existing.custom_config or {}).get("resource_name"),
                "folder_name": (existing.custom_config or {}).get("folder_name"),
                "servers": endpoint_data.get("servers", []),
                "linked_endpoints": endpoint_data.get("linked_endpoints")
            }
            await self.db.flush()
            return existing, False

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
            links=endpoint_data.get("links"),
            callbacks=endpoint_data.get("callbacks"),
            tags=endpoint_data.get("tags"),
            tag_group=tag_name,
            custom_config={
                "deprecated": endpoint_data.get("deprecated", False),
                "operation_id": endpoint_data.get("operation_id"),
                "resource_name": resource_name,
                "folder_name": folder_name,
                "servers": endpoint_data.get("servers", []),
                "linked_endpoints": endpoint_data.get("linked_endpoints")
            },
            sort_order=self._get_method_sort_order(method)
        )
        self.db.add(endpoint)
        await self.db.flush()

        return endpoint, True

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
