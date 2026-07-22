"""
API 端点管理路由

提供 OpenAPI 文档解析、端点查询、文件夹结构管理等功能
"""

import json
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

    # 如果提供的是 URL，则从远程获取
    if isinstance(openapi_spec, dict) and "url" in openapi_spec:
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
            schema_file_id=None,  # 暂时不上传文件
            openapi_spec=openapi_spec,
            user_id=current_user_id
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

