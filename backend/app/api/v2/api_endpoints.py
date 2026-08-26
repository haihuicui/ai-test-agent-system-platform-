"""
API 端点管理路由

提供 OpenAPI 文档解析、端点查询、文件夹结构管理等功能
"""

import json
import logging
import httpx
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUserIdDep, DbSessionDep, APITestServiceDep
from app.models.api_endpoint import APIEndpoint
from app.models.attachment import Attachment, AttachmentEntityType
from app.models.folder import Folder
from app.models.folder_type import FolderType
from app.models.project import Project
from app.models.api_test import APITest, APITestRun
from app.schemas.api_endpoint import (
    APIEndpointResponse,
    APIEndpointCreate,
    APIEndpointUpdate,
    OpenAPIParseResult,
    OpenAPIUploadRequest
)
from app.services.openapi_parser import OpenAPIParser
from app.services.api_test_service import APITestService

logger = logging.getLogger(__name__)

router = APIRouter()


async def fetch_openapi_from_url(url: str) -> dict[str, Any]:
    """
    从远程 URL 获取 OpenAPI 文档

    Args:
        url: OpenAPI/Swagger 文档的 URL

    Returns:
        解析后的 JSON 字典
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()

            # 根据内容类型解析
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return response.json()
            else:
                # 尝试作为 JSON 解析
                return response.json()

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无法从 URL 获取文档: {e.response.status_code} {e.response.reason}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"获取远程文档失败: {str(e)}"
        )


@router.post("/upload-openapi", response_model=OpenAPIParseResult)
async def upload_openapi_schema(
    request: OpenAPIUploadRequest,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep
):
    """
    上传并解析 OpenAPI Schema 文件

    支持两种方式：
    1. 上传 JSON 文件内容
    2. 提供 OpenAPI 文档的 URL（自动获取）

    自动解析并创建对应的文件夹结构：
    - 按标签分组创建父文件夹（如 "Activities"）
    - 为每个端点创建子文件夹（如 "GET /api/v1/Activities"）
    - 提取完整的接口信息存储到数据库
    """
    # 1. 查询项目
    project_stmt = select(Project).where(
        Project.identifier == request.project_identifier
    )
    project_result = await db.execute(project_stmt)
    project = project_result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {request.project_identifier} 不存在"
        )

    # 2. 转换 parent_folder_id
    parent_id = request.parent_folder_id if request.parent_folder_id else None

    # 3. 获取 OpenAPI 内容
    openapi_spec = request.file_content
    spec_source = "upload"

    # 如果提供的是 URL，则从远程获取
    if isinstance(openapi_spec, dict) and "url" in openapi_spec:
        spec_source = "url"
        url = openapi_spec["url"]
        try:
            openapi_spec = await fetch_openapi_from_url(url)
        except HTTPException:
            raise
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UldVM2FnPT06YjI2NDVkYjk=

    # 4. 验证是否为有效的 OpenAPI 文档
    if not isinstance(openapi_spec, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件内容必须是有效的 JSON 对象"
        )

    # 检查必需字段
    if "paths" not in openapi_spec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAPI 文档必须包含 'paths' 字段"
        )

    # 5. 创建解析器并解析
    parser = OpenAPIParser(db)

    try:
        result = await parser.parse_and_create_structure(
            project_id=project.id,
            parent_folder_id=parent_id,
            schema_file_id=None,  # 完整 spec 以快照形式存 openapi_spec_snapshots 表
            openapi_spec=openapi_spec,
            user_id=current_user_id,
            source=spec_source
        )
        await db.commit()

        return OpenAPIParseResult(**result)

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解析 OpenAPI 文件失败: {str(e)}"
        )


@router.get("/projects/{project_identifier}/api-endpoints", response_model=list[APIEndpointResponse])
async def list_api_endpoints(
    project_identifier: str,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep,
    folder_id: UUID | None = None,
    tag_group: str | None = None
):
    """
    查询项目的 API 端点列表

    支持按文件夹或标签分组过滤
    """
    # 查询项目
    project_stmt = select(Project).where(
        Project.identifier == project_identifier
    )
    project_result = await db.execute(project_stmt)
    project = project_result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_identifier} 不存在"
        )

    # 构建查询
    endpoint_stmt = select(APIEndpoint).where(
        APIEndpoint.project_id == project.id
    )

    if folder_id:
        endpoint_stmt = endpoint_stmt.where(APIEndpoint.folder_id == folder_id)

    if tag_group:
        endpoint_stmt = endpoint_stmt.where(APIEndpoint.tag_group == tag_group)

    endpoint_stmt = endpoint_stmt.order_by(
        APIEndpoint.tag_group,
        APIEndpoint.sort_order,
        APIEndpoint.path
    )
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UldVM2FnPT06YjI2NDVkYjk=

    # 执行查询
    endpoint_result = await db.execute(endpoint_stmt)
    endpoints = endpoint_result.scalars().all()

    return endpoints


@router.get("/api-endpoints/{endpoint_id}", response_model=APIEndpointResponse)
async def get_api_endpoint(
    endpoint_id: UUID,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep
):
    """获取 API 端点的详细信息"""
    endpoint_stmt = select(APIEndpoint).where(APIEndpoint.id == endpoint_id)
    endpoint_result = await db.execute(endpoint_stmt)
    endpoint = endpoint_result.scalar_one_or_none()

    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"端点 {endpoint_id} 不存在"
        )

    return endpoint


@router.post("/api-endpoints", response_model=APIEndpointResponse)
async def create_api_endpoint(
    create_data: dict,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep
):
    """手工创建 API 端点"""
    # 获取项目
    project_identifier = create_data.get("project_identifier")
    project_stmt = select(Project).where(
        Project.identifier == project_identifier
    )
    project_result = await db.execute(project_stmt)
    project = project_result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_identifier} 不存在"
        )
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UldVM2FnPT06YjI2NDVkYjk=

    # 创建端点
    endpoint = APIEndpoint(
        project_id=project.id,
        folder_id=create_data.get("folder_id"),
        display_name=create_data.get("display_name"),
        path=create_data.get("path"),
        method=create_data.get("method"),
        summary=create_data.get("summary"),
        description=create_data.get("description"),
        tag_group=create_data.get("tag_group"),
        parameters=create_data.get("parameters"),
        request_body=create_data.get("request_body"),
        responses=create_data.get("responses"),
        sort_order=0,
        total_test_cases=0,
        total_test_runs=0,
        last_run_status=None,
        api_test_ids=[],
    )

    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)

    return endpoint


@router.get("/projects/{project_identifier}/folder-structure")
async def get_api_folder_structure(
    project_identifier: str,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep
):
    """
    获取项目的 API 文件夹结构

    返回树形结构的文件夹列表，包含端点统计信息
    """
    # 查询项目
    project_stmt = select(Project).where(
        Project.identifier == project_identifier
    )
    project_result = await db.execute(project_stmt)
    project = project_result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_identifier} 不存在"
        )

    # 查询根文件夹
    folder_stmt = select(Folder).where(
        Folder.project_id == project.id,
        Folder.folder_type == FolderType.API_TEST,
        Folder.parent_id.is_(None)
    ).order_by(Folder.name)

    folder_result = await db.execute(folder_stmt)
    root_folders = folder_result.scalars().all()

    # 递归构建文件夹树
    async def build_folder_tree(folder: Folder) -> dict[str, Any]:
        # 查询该文件夹下的端点数量
        endpoint_count_stmt = select(APIEndpoint).where(
            APIEndpoint.folder_id == folder.id
        )
        endpoint_count_result = await db.execute(endpoint_count_stmt)
        endpoint_count = len(endpoint_count_result.scalars().all())

        return {
            "id": str(folder.id),
            "name": folder.name,
            "description": folder.description,
            "folder_type": folder.folder_type.value,
            "endpoint_count": endpoint_count,
            "parent_id": str(folder.parent_id) if folder.parent_id else None,
            "children": [await build_folder_tree(child) for child in folder.children]
        }

    folder_tree = []
    for folder in root_folders:
        folder_tree.append(await build_folder_tree(folder))
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UldVM2FnPT06YjI2NDVkYjk=

    return {
        "project_identifier": project_identifier,
        "folder_type": "api_test",
        "folder_tree": folder_tree
    }


@router.patch("/api-endpoints/{endpoint_id}", response_model=APIEndpointResponse)
async def update_api_endpoint(
    endpoint_id: UUID,
    update_data: APIEndpointUpdate,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep
):
    """更新 API 端点信息"""
    endpoint_stmt = select(APIEndpoint).where(APIEndpoint.id == endpoint_id)
    endpoint_result = await db.execute(endpoint_stmt)
    endpoint = endpoint_result.scalar_one_or_none()

    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"端点 {endpoint_id} 不存在"
        )

    # 更新字段
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(endpoint, field, value)

    await db.commit()
    await db.refresh(endpoint)

    return endpoint


@router.delete("/api-endpoints/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_endpoint(
    endpoint_id: UUID,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep
):
    """删除 API 端点"""
    endpoint_stmt = select(APIEndpoint).where(APIEndpoint.id == endpoint_id)
    endpoint_result = await db.execute(endpoint_stmt)
    endpoint = endpoint_result.scalar_one_or_none()

    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"端点 {endpoint_id} 不存在"
        )

    await db.delete(endpoint)
    await db.commit()

    return None


@router.get("/api-endpoints/{endpoint_id}/test-scripts")
async def get_endpoint_test_scripts(
    endpoint_id: UUID,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep
):
    """
    获取 API 端点关联的测试脚本列表
    """
    # 查询端点
    endpoint_stmt = select(APIEndpoint).where(APIEndpoint.id == endpoint_id)
    endpoint_result = await db.execute(endpoint_stmt)
    endpoint = endpoint_result.scalar_one_or_none()

    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"端点 {endpoint_id} 不存在"
        )

    # 获取关联的测试脚本
    api_test_ids = endpoint.api_test_ids or []
    if not api_test_ids:
        return {
            "endpoint_id": str(endpoint_id),
            "test_scripts": []
        }

    # 查询测试脚本详情
    test_scripts_stmt = select(APITest).where(
        APITest.id.in_(api_test_ids)
    )
    test_scripts_result = await db.execute(test_scripts_stmt)
    test_scripts = test_scripts_result.scalars().all()

    return {
        "endpoint_id": str(endpoint_id),
        "test_scripts": [
            {
                "id": str(script.id),
                "name": script.name,
                "identifier": script.identifier,
                "script_format": script.script_format,
                "script_language": script.script_language,
                "total_endpoints": script.total_endpoints,
                "total_scenarios": script.total_scenarios,
                "created_at": script.created_at.isoformat() if script.created_at else None,
                "updated_at": script.updated_at.isoformat() if script.updated_at else None,
            }
            for script in test_scripts
        ]
    }


@router.get("/api-endpoints/{endpoint_id}/test-runs")
async def get_endpoint_test_runs(
    endpoint_id: UUID,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep,
    limit: int = 10
):
    """
    获取 API 端点的测试执行报告

    返回最近的测试运行记录
    """
    # 查询端点
    endpoint_stmt = select(APIEndpoint).where(APIEndpoint.id == endpoint_id)
    endpoint_result = await db.execute(endpoint_stmt)
    endpoint = endpoint_result.scalar_one_or_none()

    if not endpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"端点 {endpoint_id} 不存在"
        )

    # 获取关联的测试脚本
    api_test_ids = endpoint.api_test_ids or []
    if not api_test_ids:
        return {
            "endpoint_id": str(endpoint_id),
            "test_runs": [],
            "total_runs": 0,
            "last_run_status": endpoint.last_run_status
        }

    # 查询测试运行记录（按时间倒序）
    test_runs_stmt = select(APITestRun).where(
        APITestRun.api_test_id.in_(api_test_ids)
    ).order_by(APITestRun.created_at.desc()).limit(limit)

    test_runs_result = await db.execute(test_runs_stmt)
    test_runs = test_runs_result.scalars().all()

    # 统计总运行次数
    count_stmt = select(APITestRun).where(
        APITestRun.api_test_id.in_(api_test_ids)
    )
    count_result = await db.execute(count_stmt)
    total_runs = len(count_result.scalars().all())

    # 查询这些运行关联的 HTML 报告附件，按 report_path 映射
    report_paths = [run.report_path for run in test_runs if run.report_path]
    attachment_map: dict[str, str] = {}
    if report_paths:
        attachment_stmt = select(Attachment).where(
            Attachment.entity_id == endpoint_id,
            Attachment.entity_type == AttachmentEntityType.API_TEST_REPORT,
            Attachment.object_name.in_(report_paths),
        )
        attachment_result = await db.execute(attachment_stmt)
        for att in attachment_result.scalars().all():
            attachment_map[att.object_name] = str(att.id)

    return {
        "endpoint_id": str(endpoint_id),
        "test_runs": [
            {
                "id": str(run.id),
                "api_test_id": str(run.api_test_id),
                "status": run.status,
                "total_scenarios": run.total_tests,
                "passed_scenarios": run.passed_tests,
                "failed_scenarios": run.failed_tests,
                "skipped_scenarios": run.skipped_tests,
                "duration": (run.duration_ms / 1000) if run.duration_ms else None,
                "report_path": run.report_path,
                "report_attachment_id": attachment_map.get(run.report_path),
                "created_at": run.created_at.isoformat() if run.created_at else None,
            }
            for run in test_runs
        ],
        "total_runs": total_runs,
        "last_run_status": endpoint.last_run_status
    }


@router.get("/api-endpoints/{endpoint_id}/runs/{run_id}/results")
async def get_endpoint_run_results(
    endpoint_id: UUID,
    run_id: UUID,
    service: APITestServiceDep,
    api_test_id: UUID | None = None,
    page: int = 1,
    page_size: int = 50,
):
    """
    获取 API 端点某次测试运行的详细结果。

    返回每条用例的真实请求/响应/断言明细，供前端“执行结果”面板使用。
    """
    result = await service.get_endpoint_run_results(
        endpoint_id=str(endpoint_id),
        run_id=str(run_id),
        api_test_id=str(api_test_id) if api_test_id else None,
        page=page,
        page_size=page_size,
    )
    return result


@router.get("/api-endpoints/{endpoint_id}/artifacts")
async def get_endpoint_artifacts_api(
    endpoint_id: UUID,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep,
    artifact_type: str | None = None
):
    """
    获取 API 端点的测试成果物列表
    """
    try:
        # 查询端点
        endpoint_stmt = select(APIEndpoint).where(APIEndpoint.id == endpoint_id)
        endpoint_result = await db.execute(endpoint_stmt)
        endpoint = endpoint_result.scalar_one_or_none()

        if not endpoint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"端点 {endpoint_id} 不存在"
            )

        # 导入 Attachment 模型
        from app.models.attachment import Attachment, AttachmentEntityType

        # 只查询 API 测试相关的成果物类型
        api_test_artifact_types = [
            AttachmentEntityType.API_TEST_PLAN,
            AttachmentEntityType.API_TEST_CASE,
            AttachmentEntityType.API_TEST_SCRIPT,
            AttachmentEntityType.API_TEST_REPORT,
        ]

        # 构建查询 - 只查询 API 测试成果物
        stmt = select(Attachment).where(
            Attachment.entity_id == endpoint_id,
            Attachment.entity_type.in_(api_test_artifact_types)
        )

        # 按类型过滤（可选）
        if artifact_type:
            try:
                entity_type = AttachmentEntityType[artifact_type]
                stmt = stmt.where(Attachment.entity_type == entity_type)
            except KeyError:
                pass

        # 执行查询
        result = await db.execute(stmt)
        attachments = result.scalars().all()

        print(f"[API Endpoints] Found {len(attachments)} artifacts for endpoint {endpoint_id}")

        # 格式化返回
        artifacts = []
        for attachment in attachments:
            artifact_data = {
                "id": str(attachment.id),
                "type": attachment.entity_type.value.upper(),
                "file_name": attachment.file_name,
                "description": attachment.description,
                "file_size": attachment.file_size,
                "content_type": attachment.content_type,
                "object_name": attachment.object_name,
                "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
                "updated_at": attachment.updated_at.isoformat() if attachment.updated_at else None,
            }
            print(f"[API Endpoints] Artifact: {artifact_data['type']} - {artifact_data['file_name']}")
            artifacts.append(artifact_data)

        print(f"[API Endpoints] Returning {len(artifacts)} artifacts")

        return {
            "success": True,
            "endpoint_id": str(endpoint_id),
            "artifacts": artifacts,
            "total": len(artifacts)
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching artifacts for endpoint {endpoint_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取成果物失败: {str(e)}"
        )


@router.get("/attachments/{attachment_id}/content")
async def get_attachment_content_api(
    attachment_id: UUID,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep
):
    """
    获取附件内容（文本文件）
    """
    from app.models.attachment import Attachment
    from app.config.minio_client import MinIOClient

    # 查询附件
    stmt = select(Attachment).where(Attachment.id == attachment_id)
    result = await db.execute(stmt)
    attachment = result.scalar_one_or_none()

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"附件 {attachment_id} 不存在"
        )

    # 从 MinIO 下载文件
    try:
        from fastapi.responses import JSONResponse

        content_bytes = MinIOClient.download_file(attachment.object_name)
        content = content_bytes.decode('utf-8')

        return JSONResponse(
            content={
                "success": True,
                "attachment_id": str(attachment.id),
                "type": attachment.entity_type.value,
                "file_name": attachment.file_name,
                "content": content,
                "content_type": attachment.content_type,
                "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
                "updated_at": attachment.updated_at.isoformat() if attachment.updated_at else None,
            },
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载文件失败: {str(e)}"
        )


@router.get("/attachments/{attachment_id}/download")
async def download_attachment_api(
    attachment_id: UUID,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep
):
    """
    下载附件文件
    """
    from fastapi.responses import StreamingResponse
    from app.models.attachment import Attachment
    from app.config.minio_client import MinIOClient
    import io

    # 查询附件
    stmt = select(Attachment).where(Attachment.id == attachment_id)
    result = await db.execute(stmt)
    attachment = result.scalar_one_or_none()

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"附件 {attachment_id} 不存在"
        )

    # 从 MinIO 下载文件
    try:
        content_bytes = MinIOClient.download_file(attachment.object_name)

        return StreamingResponse(
            io.BytesIO(content_bytes),
            media_type=attachment.content_type or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{attachment.file_name}"',
                "Content-Length": str(len(content_bytes)),
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载文件失败: {str(e)}"
        )


@router.get("/attachments/{attachment_id}/report-viewer")
async def get_report_viewer_url(
    attachment_id: UUID,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep
):
    """
    获取测试报告查看器 URL

    对于 ZIP 格式的测试报告，解压并返回 index.html 的访问路径
    """
    from app.models.attachment import Attachment, AttachmentEntityType
    from app.config.minio_client import MinIOClient
    import zipfile
    import io
    import tempfile
    import shutil
    from pathlib import Path

    # 查询附件
    stmt = select(Attachment).where(Attachment.id == attachment_id)
    result = await db.execute(stmt)
    attachment = result.scalar_one_or_none()

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"附件 {attachment_id} 不存在"
        )

    # 只处理测试报告类型（支持 API 和 Web 测试报告）
    if attachment.entity_type not in [AttachmentEntityType.API_TEST_REPORT, AttachmentEntityType.WEB_TEST_REPORT]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持查看测试报告"
        )

    # 从 MinIO 下载报告文件
    try:
        report_bytes = MinIOClient.download_file(attachment.object_name)

        # 创建临时目录（先清空，避免不同报告结构差异导致旧文件干扰）
        temp_dir = Path(tempfile.gettempdir()) / "test-reports" / str(attachment_id)
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        # 判断是否为 ZIP：ZIP 文件以 PK 头开始
        is_zip = report_bytes.startswith(b"PK")

        if is_zip:
            # 解压 ZIP 文件
            with zipfile.ZipFile(io.BytesIO(report_bytes), 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # 查找 index.html（支持直接放在根目录或 html/ 等子目录下的报告包）
            index_html = temp_dir / "index.html"
            if not index_html.exists():
                for candidate in temp_dir.rglob("index.html"):
                    # 取找到的第一个 index.html（Playwright HTML 报告通常仅有一个）
                    index_html = candidate
                    break

            if not index_html.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="报告中未找到 index.html"
                )

            # 计算 index.html 相对于临时目录的路径，用于构造访问 URL
            try:
                rel_index_path = index_html.relative_to(temp_dir).as_posix()
            except ValueError:
                rel_index_path = "index.html"
        else:
            # 非 ZIP（如 save_web_test_report 保存的单个 HTML 摘要）：
            # 直接落到临时目录作为 index.html，后续 report-files 统一读取
            index_html = temp_dir / "index.html"
            index_html.write_bytes(report_bytes)
            rel_index_path = "index.html"

        # 返回临时目录路径和附件 ID
        return {
            "success": True,
            "attachment_id": str(attachment_id),
            "report_path": str(temp_dir),
            "index_url": f"/api/v2/attachments/{attachment_id}/report-files/{rel_index_path}"
        }
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的 ZIP 文件"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"处理报告失败: {str(e)}"
        )


def _inject_platform_favicon(html_content: str) -> str:
    """
    将 HTML 中的 favicon 统一替换为平台图标 /logo.svg。

    若已经存在 <link rel="icon">，则替换其 href；否则在 </head> 前注入。
    使用绝对路径 /logo.svg，可避免报告包内 <base> 标签的影响。
    """
    import re

    icon_link_pattern = re.compile(
        r'<link(?=[^>]*\brel=["\']icon["\'])[^>]*>',
        re.IGNORECASE,
    )
    if icon_link_pattern.search(html_content):
        return icon_link_pattern.sub(
            '<link rel="icon" type="image/svg+xml" href="/logo.svg">',
            html_content,
            count=1,
        )

    head_end_pattern = re.compile(r'</head>', re.IGNORECASE)
    return head_end_pattern.sub(
        '<link rel="icon" type="image/svg+xml" href="/logo.svg">\n</head>',
        html_content,
        count=1,
    )


async def _get_corrected_api_test_stats(
    attachment: "Attachment",
    db,
) -> dict | None:
    """
    获取 API 测试报告的修正后统计（优先使用描述解析，兜底查询 DB）。

    返回 {"passed": int, "failed": int, "skipped": int} 或 None。
    """
    from app.models.api_test import APITestRun, APITestResult

    # 1) 快速路径：从附件描述中解析（修复后的报告描述已包含修正统计）
    stats = _parse_corrected_stats_from_description(attachment.description)
    if stats and (stats["passed"] + stats["failed"] + stats["skipped"]) > 0:
        return stats

    # 2) 兜底：通过 report_path == object_name 查询 APITestRun
    try:
        stmt = select(APITestRun).where(
            APITestRun.report_path == attachment.object_name
        ).order_by(APITestRun.created_at.desc()).limit(1)
        result = await db.execute(stmt)
        test_run = result.scalar_one_or_none()

        if test_run:
            total = (test_run.passed_tests or 0) + (test_run.failed_tests or 0) + (test_run.skipped_tests or 0)
            if total > 0:
                return {
                    "passed": test_run.passed_tests or 0,
                    "failed": test_run.failed_tests or 0,
                    "skipped": test_run.skipped_tests or 0,
                }

            # test_run 存在但计数全为 0（旧数据），从 APITestResult 重新统计
            results_stmt = select(APITestResult).where(
                APITestResult.test_run_id == test_run.id
            )
            results_result = await db.execute(results_stmt)
            results = results_result.scalars().all()
            if results:
                corrected = {"passed": 0, "failed": 0, "skipped": 0}
                for r in results:
                    status_val = r.status.value if hasattr(r.status, 'value') else str(r.status)
                    if status_val == "passed":
                        corrected["passed"] += 1
                    elif status_val == "failed":
                        corrected["failed"] += 1
                    elif status_val == "skipped":
                        corrected["skipped"] += 1
                if sum(corrected.values()) > 0:
                    return corrected
    except Exception:
        pass

    # 3) 如果解析到了 stats 但计数为 0（描述解析出了零值），仍返回
    if stats:
        return stats

    return None


def _parse_corrected_stats_from_description(description: str | None) -> dict | None:
    """
    从附件描述中解析经过断言修正的测试统计。

    描述格式（由 _save_test_report / _save_html_report 生成）：
        API 测试报告 - {name}
        执行时间: {duration}秒
        通过: {n} | 失败: {n} | 跳过: {n}

    Returns:
        {"passed": int, "failed": int, "skipped": int} 或 None（解析失败时）
    """
    import re
    if not description:
        return None
    try:
        passed_m = re.search(r"通过:\s*(\d+)", description)
        failed_m = re.search(r"失败:\s*(\d+)", description)
        skipped_m = re.search(r"跳过:\s*(\d+)", description)
        if passed_m is None and failed_m is None:
            return None
        return {
            "passed": int(passed_m.group(1)) if passed_m else 0,
            "failed": int(failed_m.group(1)) if failed_m else 0,
            "skipped": int(skipped_m.group(1)) if skipped_m else 0,
        }
    except Exception:
        return None


def _inject_corrected_stats_banner(html_content: str, stats: dict) -> str:
    """
    向 Playwright HTML 报告中注入一个统计修正横幅。

    Playwright 原生 HTML 报告以脚本自身的断言结果为准（如 expect(401).toBe(401)
    视为通过），本平台在后处理阶段会根据真实 HTTP 状态码、业务码等自动生成
    额外断言并修正判定。此横幅用于展示修正后的统计，与附件描述保持一致。

    Args:
        html_content: 原始 HTML 内容
        stats: {"passed": int, "failed": int, "skipped": int}

    Returns:
        注入了横幅脚本的 HTML 内容
    """
    import re

    total = stats["passed"] + stats["failed"] + stats["skipped"]
    banner_html = f'''<style id="__corrected_stats_style">
.__ai_corrected_banner {{
  position: fixed; top: 0; left: 0; right: 0; z-index: 99999;
  background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
  color: #f1f5f9; font-family: system-ui, -apple-system, sans-serif;
  font-size: 13px; padding: 8px 16px;
  display: flex; align-items: center; justify-content: center; gap: 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.3); flex-wrap: wrap;
}}
.__ai_corrected_banner .__ai_label {{
  font-weight: 600; color: #94a3b8; font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.5px;
}}
.__ai_corrected_banner .__ai_stat {{
  display: flex; align-items: center; gap: 6px; font-weight: 600;
}}
.__ai_corrected_banner .__ai_passed {{ color: #4ade80; }}
.__ai_corrected_banner .__ai_failed {{ color: #f87171; }}
.__ai_corrected_banner .__ai_skipped {{ color: #fbbf24; }}
.__ai_corrected_banner .__ai_note {{
  font-size: 11px; color: #64748b; margin-left: 8px;
}}
.__ai_corrected_banner .__ai_dismiss {{
  cursor: pointer; background: none; border: 1px solid #475569;
  color: #94a3b8; border-radius: 4px; padding: 2px 8px; font-size: 11px;
  margin-left: 8px;
}}
.__ai_corrected_banner .__ai_dismiss:hover {{
  background: #475569; color: #e2e8f0;
}}
body {{ padding-top: 44px !important; }}
</style>
<div id="__ai_corrected_banner" class="__ai_corrected_banner">
  <span class="__ai_label">平台修正统计</span>
  <span class="__ai_stat"><span>通过</span><span class="__ai_passed">{stats["passed"]}</span></span>
  <span class="__ai_stat"><span>失败</span><span class="__ai_failed">{stats["failed"]}</span></span>
  <span class="__ai_stat"><span>跳过</span><span class="__ai_skipped">{stats["skipped"]}</span></span>
  <span class="__ai_stat"><span>总计</span><span>{total}</span></span>
  <span class="__ai_note">基于 HTTP 状态码 &amp; 业务码的自动断言修正</span>
  <button class="__ai_dismiss" onclick="
    var b=document.getElementById('__ai_corrected_banner');
    var s=document.getElementById('__corrected_stats_style');
    if(b) b.remove(); if(s) s.remove();
    document.body.style.paddingTop='';
  ">✕ 关闭</button>
</div>'''

    # 注入到 <body> 标签之后
    body_pattern = re.compile(r'<body[^>]*>', re.IGNORECASE)
    if body_pattern.search(html_content):
        html_content = body_pattern.sub(
            lambda m: m.group(0) + banner_html,
            html_content,
            count=1,
        )
    else:
        # 没有 <body> 标签，注入到文档开头
        html_content = banner_html + html_content

    return html_content


async def _get_test_run_for_attachment(
    attachment: "Attachment",
    db,
):
    """通过 attachment.object_name 匹配 APITestRun.report_path 找到对应运行。"""
    from app.models.api_test import APITestRun

    try:
        stmt = select(APITestRun).where(
            APITestRun.report_path == attachment.object_name
        ).order_by(APITestRun.created_at.desc()).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception:
        return None


def _truncate_for_embed(value, max_chars: int = 5000) -> str:
    """将任意值序列化为 JSON 字符串并按 max_chars 截断，用于安全嵌入 HTML。"""
    if value is None:
        return "null"
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... [truncated, {len(text)} total chars]"
    return text


async def _get_test_case_details(test_run_id, db) -> list[dict]:
    """
    查询 APITestResult 并返回可嵌入 HTML 的用例详情列表。

    返回每条用例的 scenario_name, endpoint, method, status, duration_ms,
    request (含 headers/body), response (含 status/headers/body),
    assertions, error_message。
    """
    from app.models.api_test import APITestResult

    stmt = (
        select(APITestResult)
        .where(APITestResult.test_run_id == test_run_id)
        .order_by(APITestResult.created_at.asc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    cases: list[dict] = []
    for r in rows:
        status_val = r.status.value if hasattr(r.status, "value") else str(r.status)

        # 请求数据
        req = dict(r.request_data) if r.request_data else {}
        req_body = req.get("body")
        req_body_str = _truncate_for_embed(req_body) if req_body is not None else None

        # 响应数据
        resp = dict(r.response_data) if r.response_data else {}
        resp_body = resp.get("body")
        resp_body_str = _truncate_for_embed(resp_body) if resp_body is not None else None

        # 断言结果
        assertions = list(r.assertion_results) if r.assertion_results else []

        cases.append({
            "name": r.scenario_name or "",
            "endpoint": r.endpoint or "",
            "method": (r.method or "GET").upper(),
            "status": status_val,
            "duration_ms": r.duration_ms,
            "error_message": r.error_message,
            "request": {
                "url": req.get("url", ""),
                "method": req.get("method", (r.method or "GET").upper()),
                "headers": req.get("headers") or {},
                "body": req_body_str,
                "body_truncated": (req.get("body_meta") or {}).get("truncated", False),
            },
            "response": {
                "status": resp.get("status"),
                "statusText": resp.get("statusText", ""),
                "headers": resp.get("headers") or {},
                "body": resp_body_str,
                "body_truncated": (resp.get("body_meta") or {}).get("truncated", False),
                "timing": resp.get("timing"),
            },
            "assertions": [
                {
                    "type": (a.get("assertion") or {}).get("type", "test"),
                    "passed": a.get("passed"),
                    "expected": a.get("expected"),
                    "actual": a.get("actual"),
                    "message": a.get("message", ""),
                }
                for a in assertions
            ],
        })

    return cases


def _inject_test_details_panel(html_content: str, test_cases_json: str) -> str:
    """
    向 Playwright HTML 报告中注入用例详情面板（CSS + JS + JSON 数据）。

    面板功能：
    - 右下角固定按钮打开
    - 右侧滑出面板（40%宽度）
    - 下拉框切换用例
    - 可折叠的 Request / Response / Assertions 区域
    """
    import re

    panel_code = f'''<script id="__ai_tc_data" type="application/json">{test_cases_json}</script>
<style id="__ai_panel_style">
/* ---- AI Test Details Panel ---- */
.__ai_panel_btn {{
  position: fixed; bottom: 24px; right: 24px; z-index: 99990;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; border: none; border-radius: 12px;
  padding: 10px 18px; font-size: 14px; font-weight: 600;
  cursor: pointer; box-shadow: 0 4px 16px rgba(99,102,241,0.4);
  display: flex; align-items: center; gap: 8px;
  font-family: system-ui, -apple-system, sans-serif;
  transition: transform 0.15s, box-shadow 0.15s;
}}
.__ai_panel_btn:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(99,102,241,0.5); }}
.__ai_panel_btn.__ai_hidden {{ display: none; }}

.__ai_overlay {{
  position: fixed; inset: 0; background: rgba(0,0,0,0.35);
  z-index: 99991; display: none;
}}
.__ai_overlay.__ai_open {{ display: block; }}

.__ai_drawer {{
  position: fixed; top: 0; right: 0; bottom: 0; width: min(520px, 90vw);
  background: #0f172a; z-index: 99992; color: #e2e8f0;
  font-family: system-ui, -apple-system, sans-serif;
  display: flex; flex-direction: column;
  box-shadow: -4px 0 24px rgba(0,0,0,0.5);
  transform: translateX(100%); transition: transform 0.25s ease;
}}
.__ai_drawer.__ai_open {{ transform: translateX(0); }}

.__ai_drawer_header {{
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px; border-bottom: 1px solid #1e293b;
  background: #1e293b; flex-shrink: 0;
}}
.__ai_drawer_header h3 {{ margin: 0; font-size: 15px; color: #f1f5f9; }}
.__ai_drawer_close {{
  background: none; border: none; color: #94a3b8; font-size: 20px;
  cursor: pointer; padding: 4px 8px; border-radius: 4px;
}}
.__ai_drawer_close:hover {{ background: #334155; color: #e2e8f0; }}

.__ai_case_selector {{
  padding: 10px 18px; border-bottom: 1px solid #1e293b; flex-shrink: 0;
}}
.__ai_case_selector select {{
  width: 100%; padding: 8px 12px; border-radius: 6px;
  background: #1e293b; color: #e2e8f0; border: 1px solid #334155;
  font-size: 13px; font-family: inherit; cursor: pointer;
}}

.__ai_drawer_body {{
  flex: 1; overflow-y: auto; padding: 16px 18px;
}}

/* ---- Status / Meta ---- */
.__ai_meta {{ display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 16px; }}
.__ai_badge {{
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px; border-radius: 6px; font-size: 12px; font-weight: 600;
}}
.__ai_badge_pass {{ background: #064e3b; color: #4ade80; }}
.__ai_badge_fail {{ background: #450a0a; color: #f87171; }}
.__ai_badge_skip {{ background: #422006; color: #fbbf24; }}
.__ai_method {{ font-weight: 700; font-size: 12px; }}
.__ai_url {{ font-size: 12px; color: #94a3b8; word-break: break-all; }}
.__ai_duration {{ font-size: 12px; color: #64748b; }}

/* ---- Collapsible Sections ---- */
.__ai_section {{
  border: 1px solid #1e293b; border-radius: 8px; margin-bottom: 12px; overflow: hidden;
}}
.__ai_section_toggle {{
  width: 100%; text-align: left; padding: 10px 14px;
  background: #1e293b; color: #cbd5e1; border: none;
  font-size: 13px; font-weight: 600; cursor: pointer;
  display: flex; align-items: center; justify-content: space-between;
  font-family: inherit;
}}
.__ai_section_toggle:hover {{ background: #273449; }}
.__ai_section_toggle .__ai_arrow {{ transition: transform 0.2s; }}
.__ai_section_toggle.__ai_collapsed .__ai_arrow {{ transform: rotate(-90deg); }}
.__ai_section_content {{ padding: 12px 14px; display: block; }}
.__ai_section_content.__ai_hidden {{ display: none; }}

/* ---- Tables ---- */
.__ai_table {{
  width: 100%; border-collapse: collapse; font-size: 11px;
}}
.__ai_table th {{
  text-align: left; padding: 6px 8px; background: #1e293b;
  color: #94a3b8; font-weight: 600; border-bottom: 1px solid #334155;
  white-space: nowrap;
}}
.__ai_table td {{
  padding: 6px 8px; border-bottom: 1px solid #1e293b;
  color: #cbd5e1; vertical-align: top;
}}
.__ai_table code {{
  font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 11px;
}}
.__ai_table .__ai_pass {{ color: #4ade80; }}
.__ai_table .__ai_fail {{ color: #f87171; }}

/* ---- Body Preview ---- */
.__ai_body_pre {{
  background: #0f172a; border: 1px solid #1e293b; border-radius: 6px;
  padding: 10px; font-size: 11px; line-height: 1.5;
  overflow: auto; max-height: 300px; white-space: pre-wrap;
  word-break: break-all; color: #cbd5e1;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  margin: 0;
}}
.__ai_truncated_note {{
  font-size: 11px; color: #fbbf24; margin-top: 6px;
  display: flex; align-items: center; gap: 4px;
}}
.__ai_empty {{ font-size: 12px; color: #64748b; padding: 8px 0; }}
</style>

<div id="__ai_panel_btn" class="__ai_panel_btn" onclick="__aiTogglePanel()">
  <span style="font-size:18px">📋</span> 用例详情
</div>

<div id="__ai_overlay" class="__ai_overlay" onclick="__aiClosePanel()"></div>
<div id="__ai_drawer" class="__ai_drawer">
  <div class="__ai_drawer_header">
    <h3>📋 用例请求/响应详情</h3>
    <button class="__ai_drawer_close" onclick="__aiClosePanel()">✕</button>
  </div>
  <div class="__ai_case_selector">
    <select id="__ai_case_select" onchange="__aiRenderCase()"></select>
  </div>
  <div id="__ai_drawer_body" class="__ai_drawer_body"></div>
</div>

<script>
(function() {{
  try {{
    var __aiData = JSON.parse(document.getElementById('__ai_tc_data').textContent);
  }} catch(e) {{ __aiData = []; }}
  var __aiOpen = false;

  window.__aiTogglePanel = function() {{
    __aiOpen = !__aiOpen;
    document.getElementById('__ai_overlay').className = '__ai_overlay' + (__aiOpen ? ' __ai_open' : '');
    document.getElementById('__ai_drawer').className = '__ai_drawer' + (__aiOpen ? ' __ai_open' : '');
    if (__aiOpen) __aiRenderCase();
  }};
  window.__aiClosePanel = function() {{
    __aiOpen = false;
    document.getElementById('__ai_overlay').className = '__ai_overlay';
    document.getElementById('__ai_drawer').className = '__ai_drawer';
  }};

  // Populate dropdown
  (function() {{
    var sel = document.getElementById('__ai_case_select');
    sel.innerHTML = '';
    for (var i = 0; i < __aiData.length; i++) {{
      var c = __aiData[i];
      var icon = c.status === 'passed' ? '✓' : c.status === 'failed' ? '✗' : '⊘';
      var opt = document.createElement('option');
      opt.value = i;
      opt.textContent = icon + ' ' + c.method + ' ' + (c.endpoint || c.name);
      sel.appendChild(opt);
    }}
  }})();

  window.__aiRenderCase = function() {{
    var idx = parseInt(document.getElementById('__ai_case_select').value);
    if (isNaN(idx) || idx < 0 || idx >= __aiData.length) return;
    var c = __aiData[idx];
    var statusLabel = c.status === 'passed' ? '通过' : c.status === 'failed' ? '失败' : c.status;
    var statusCls = c.status === 'passed' ? '__ai_badge_pass' : c.status === 'failed' ? '__ai_badge_fail' : '__ai_badge_skip';

    var html = '';
    // Meta row
    html += '<div class="__ai_meta">';
    html += '<span class="__ai_badge ' + statusCls + '">' + statusLabel + '</span>';
    html += '<span class="__ai_method">' + __aiEsc(c.method) + '</span>';
    html += '<span class="__ai_url">' + __aiEsc(c.endpoint) + '</span>';
    if (c.duration_ms) html += '<span class="__ai_duration">' + c.duration_ms + 'ms</span>';
    html += '</div>';

    // Error
    if (c.error_message) {{
      html += '<div style="background:#450a0a;color:#fca5a5;padding:8px 12px;border-radius:6px;margin-bottom:12px;font-size:12px;">' + __aiEsc(c.error_message) + '</div>';
    }}

    // Request section
    html += __aiSection('📤 Request', __aiRenderRequest(c));

    // Response section
    html += __aiSection('📥 Response', __aiRenderResponse(c));

    // Assertions section
    html += __aiSection('🔍 Assertions (' + c.assertions.length + ')', __aiRenderAssertions(c));

    document.getElementById('__ai_drawer_body').innerHTML = html;
  }};

  function __aiSection(title, content) {{
    var id = '__ai_sec_' + Math.random().toString(36).slice(2,8);
    return '<div class="__ai_section">' +
      '<button class="__ai_section_toggle" onclick="var c=this.nextElementSibling;var t=!c.classList.contains(\'__ai_hidden\');c.classList.toggle(\'__ai_hidden\',t);this.classList.toggle(\'__ai_collapsed\',t)">' +
        title + '<span class="__ai_arrow">▼</span>' +
      '</button>' +
      '<div class="__ai_section_content">' + content + '</div>' +
    '</div>';
  }}

  function __aiRenderRequest(c) {{
    var r = c.request;
    var html = '';
    html += '<div style="font-size:12px;color:#94a3b8;margin-bottom:6px;">' + __aiEsc(r.method) + ' ' + __aiEsc(r.url) + '</div>';
    html += __aiTable(Object.entries(r.headers || {{}}), 'Header', 'Value');
    if (r.body) {{
      html += '<div style="margin-top:8px;font-size:11px;font-weight:600;color:#94a3b8;">Body:</div>';
      html += '<pre class="__ai_body_pre">' + __aiPretty(r.body) + '</pre>';
      if (r.body_truncated) html += '<div class="__ai_truncated_note">⚠ 响应体已截断</div>';
    }} else {{
      html += '<div class="__ai_empty">(无请求体)</div>';
    }}
    return html;
  }}

  function __aiRenderResponse(c) {{
    var r = c.response;
    var html = '';
    var s = r.status || '?';
    var sc = (typeof s === 'number' && s >= 200 && s < 300) ? '#4ade80' : (typeof s === 'number' && s >= 400) ? '#f87171' : '#94a3b8';
    html += '<div style="font-size:12px;margin-bottom:6px;">Status: <span style="color:' + sc + ';font-weight:700">' + s + '</span> ' + __aiEsc(r.statusText || '') + '</div>';
    html += __aiTable(Object.entries(r.headers || {{}}), 'Header', 'Value');
    if (r.body) {{
      html += '<div style="margin-top:8px;font-size:11px;font-weight:600;color:#94a3b8;">Body:</div>';
      html += '<pre class="__ai_body_pre">' + __aiPretty(r.body) + '</pre>';
      if (r.body_truncated) html += '<div class="__ai_truncated_note">⚠ 响应体已截断</div>';
    }} else {{
      html += '<div class="__ai_empty">(无响应体)</div>';
    }}
    return html;
  }}

  function __aiRenderAssertions(c) {{
    if (!c.assertions.length) return '<div class="__ai_empty">(无断言记录)</div>';
    var rows = '';
    for (var i = 0; i < c.assertions.length; i++) {{
      var a = c.assertions[i];
      var cls = a.passed ? '__ai_pass' : '__ai_fail';
      var icon = a.passed ? '✓' : '✗';
      var exp = a.expected !== undefined ? String(a.expected) : '-';
      var act = a.actual !== undefined ? String(a.actual) : '-';
      rows += '<tr>' +
        '<td class="' + cls + '">' + icon + '</td>' +
        '<td>' + __aiEsc(a.type || '') + '</td>' +
        '<td><code>' + __aiEsc(exp.length > 60 ? exp.slice(0,60)+'...' : exp) + '</code></td>' +
        '<td><code>' + __aiEsc(act.length > 60 ? act.slice(0,60)+'...' : act) + '</code></td>' +
        '<td>' + __aiEsc((a.message || '').length > 120 ? a.message.slice(0,120)+'...' : (a.message || '')) + '</td>' +
      '</tr>';
    }}
    return '<table class="__ai_table"><thead><tr><th></th><th>类型</th><th>预期</th><th>实际</th><th>消息</th></tr></thead><tbody>' + rows + '</tbody></table>';
  }}

  function __aiTable(entries, labelH, labelV) {{
    if (!entries.length) return '<div class="__ai_empty">(无数据)</div>';
    var rows = '';
    for (var i = 0; i < entries.length; i++) {{
      rows += '<tr><td style="color:#94a3b8;white-space:nowrap">' + __aiEsc(String(entries[i][0])) + '</td><td><code>' + __aiEsc(String(entries[i][1])) + '</code></td></tr>';
    }}
    return '<table class="__ai_table"><thead><tr><th>' + labelH + '</th><th>' + labelV + '</th></tr></thead><tbody>' + rows + '</tbody></table>';
  }}

  function __aiPretty(raw) {{
    try {{
      var parsed = typeof raw === 'string' ? JSON.parse(raw) : raw;
      return __aiEsc(JSON.stringify(parsed, null, 2));
    }} catch(e) {{ return __aiEsc(String(raw)); }}
  }}

  function __aiEsc(s) {{
    if (!s) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }}
}})();
</script>'''

    # Inject before </body>
    body_end = re.compile(r'</body>', re.IGNORECASE)
    if body_end.search(html_content):
        html_content = body_end.sub(panel_code + '\n</body>', html_content, count=1)
    else:
        html_content += panel_code

    return html_content


@router.get("/attachments/{attachment_id}/report-files/{file_path:path}")
async def get_report_file(
    attachment_id: UUID,
    file_path: str,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep
):
    """
    获取测试报告中的文件

    从解压后的临时目录中读取文件并返回；如果临时文件已被清理，
    则从 MinIO 重新下载 ZIP 并解压。
    """
    from fastapi.responses import FileResponse, HTMLResponse
    from pathlib import Path
    import tempfile
    import mimetypes
    import zipfile
    import io
    from app.models.attachment import Attachment, AttachmentEntityType
    from app.config.minio_client import MinIOClient

    # 查询附件
    stmt = select(Attachment).where(Attachment.id == attachment_id)
    result = await db.execute(stmt)
    attachment = result.scalar_one_or_none()

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"附件 {attachment_id} 不存在"
        )

    if attachment.entity_type not in [AttachmentEntityType.API_TEST_REPORT, AttachmentEntityType.WEB_TEST_REPORT]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持查看测试报告"
        )

    # 构建文件路径
    temp_dir = Path(tempfile.gettempdir()) / "test-reports" / str(attachment_id)
    target_file = temp_dir / file_path

    # 安全检查：确保文件在临时目录内
    try:
        target_file = target_file.resolve()
        temp_dir_resolved = temp_dir.resolve()
        if not str(target_file).startswith(str(temp_dir_resolved)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="访问被拒绝"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="访问被拒绝"
        )

    # 如果文件不存在，从 MinIO 重新下载并准备
    if not target_file.exists() or not target_file.is_file():
        try:
            file_bytes = MinIOClient.download_file(attachment.object_name)
            temp_dir.mkdir(parents=True, exist_ok=True)

            # 判断是否为 ZIP：ZIP 文件以 PK 头开始
            if file_bytes.startswith(b"PK"):
                # ZIP 报告包：解压到临时目录
                with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
            else:
                # 非 ZIP（如单个 HTML 摘要文件）：直接落到目标路径
                target_file.parent.mkdir(parents=True, exist_ok=True)
                target_file.write_bytes(file_bytes)
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的 ZIP 文件"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"处理报告失败: {str(e)}"
            )

    # 再次检查文件是否存在
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文件不存在: {file_path}"
        )

    # 确定 MIME 类型
    mime_type, _ = mimetypes.guess_type(str(target_file))
    if mime_type is None:
        mime_type = "application/octet-stream"

    # 对于 HTML 文件，读取内容并统一平台 favicon，避免浏览器标签页图标与主站不一致
    if mime_type == "text/html":
        with open(target_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        html_content = _inject_platform_favicon(html_content)
        # 对 API 测试报告注入修正统计横幅 + 用例详情面板
        if (attachment.entity_type == AttachmentEntityType.API_TEST_REPORT
                and file_path.endswith("index.html")):
            corrected_stats = await _get_corrected_api_test_stats(
                attachment, db
            )
            if corrected_stats:
                html_content = _inject_corrected_stats_banner(
                    html_content, corrected_stats
                )
            # 注入用例详情面板（请求/响应/断言）
            try:
                test_run = await _get_test_run_for_attachment(attachment, db)
                if test_run:
                    test_cases = await _get_test_case_details(test_run.id, db)
                    if test_cases:
                        test_cases_json = json.dumps(
                            test_cases, ensure_ascii=False, default=str
                        )
                        html_content = _inject_test_details_panel(
                            html_content, test_cases_json
                        )
            except Exception as e:
                logger.warning(
                    "[get_report_file] 注入用例详情面板失败: %s", e
                )
        return HTMLResponse(content=html_content)

    # 对于其他文件，使用 FileResponse 但不设置 filename，让浏览器根据 MIME 类型处理
    return FileResponse(
        path=str(target_file),
        media_type=mime_type
    )


@router.put("/attachments/{attachment_id}/content")
async def update_attachment_content_api(
    attachment_id: UUID,
    content_data: dict,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep
):
    """
    更新附件内容
    """
    from app.models.attachment import Attachment
    from app.config.minio_client import MinIOClient

    # 查询附件
    stmt = select(Attachment).where(Attachment.id == attachment_id)
    result = await db.execute(stmt)
    attachment = result.scalar_one_or_none()

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"附件 {attachment_id} 不存在"
        )

    try:
        content = content_data.get("content", "")
        content_bytes = content.encode('utf-8')

        # 上传到 MinIO（覆盖原有文件）
        MinIOClient.upload_bytes(
            object_name=attachment.object_name,
            data=content_bytes,
            content_type=attachment.content_type
        )

        # 更新文件大小
        attachment.file_size = len(content_bytes)
        await db.commit()

        return {
            "success": True,
            "message": "附件内容已更新",
            "attachment_id": str(attachment.id),
            "file_size": len(content_bytes)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新附件失败: {str(e)}"
        )


@router.get("/api-test-results/{result_id}/response-body")
async def download_api_test_response_body(
    result_id: UUID,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep,
):
    """
    下载 API 测试执行结果的完整响应体。

    当响应体超过截断阈值时，完整内容会被上传到 MinIO，本接口用于下载该完整内容。
    """
    from fastapi.responses import StreamingResponse
    from app.models.api_test import APITestResult
    from app.config.minio_client import MinIOClient
    import io

    result = await db.get(APITestResult, result_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"测试结果 {result_id} 不存在"
        )

    response_data = result.response_data or {}
    body_meta = response_data.get("body_meta") or {}
    storage_path = body_meta.get("storage_path")

    if not storage_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该测试结果没有上传的完整响应体"
        )

    try:
        content_bytes = MinIOClient.download_file(storage_path)
        return StreamingResponse(
            io.BytesIO(content_bytes),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="response_body_{result_id}.json"',
                "Content-Length": str(len(content_bytes)),
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载响应体失败: {str(e)}"
        )

