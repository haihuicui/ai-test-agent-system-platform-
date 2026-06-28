"""
Web 测试管理 API

提供 Web 测试的 CRUD 操作接口
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query, UploadFile, File, Form, Depends
from fastapi.responses import Response, StreamingResponse

from app.api.deps import (
    PaginationDep,
)
from app.schemas.common import SuccessResponse
from app.services.web_test_service import WebTestService
from app.config.database import async_session_factory
from motor.motor_asyncio import AsyncIOMotorClient


router = APIRouter(prefix="/projects/{project_identifier}/web-tests")

# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTA1MGN3PT06MjcxZTc3MzM=

async def get_web_test_service():
    """获取 Web 测试服务实例"""
    async with async_session_factory() as session:
        # mongodb = None  # 简化版本，不需要mongodb
        yield WebTestService(session, None)


# ============ Web 测试管理接口 ============

@router.post(
    "",
    response_model=SuccessResponse,
    summary="创建 Web 测试",
    description="创建新的 Web 测试",
)
async def create_web_test(
    project_identifier: str,
    service: WebTestService = Depends(get_web_test_service),
    name: str = Form(..., description="Web 测试名称"),
    base_url: str = Form(..., description="Web 应用基础 URL"),
    script_path: str = Form(..., description="脚本文件路径 (MinIO)"),
    script_format: str = Form(default="playwright", description="脚本格式"),
    script_language: str = Form(default="typescript", description="脚本语言"),
    description: Optional[str] = Form(None, description="描述"),
    test_config: Optional[str] = Form(None, description="测试配置 (JSON)"),
    folder_id: Optional[str] = Form(None, description="文件夹 ID"),
    target_pages: Optional[str] = Form(None, description="目标页面 (JSON)"),
    test_flows: Optional[str] = Form(None, description="测试流程 (JSON)"),
):
    """创建 Web 测试"""
    import json
    config = json.loads(test_config) if test_config else None
    pages = json.loads(target_pages) if target_pages else None
    flows = json.loads(test_flows) if test_flows else None

    result = await service.create_web_test(
        project_identifier=project_identifier,
        name=name,
        base_url=base_url,
        script_path=script_path,
        script_format=script_format,
        script_language=script_language,
        description=description,
        test_config=config,
        folder_id=folder_id,
        target_pages=pages,
        test_flows=flows,
    )

    return SuccessResponse(data=result, message="Web 测试创建成功")


@router.get(
    "",
    response_model=SuccessResponse,
    summary="获取 Web 测试列表",
    description="获取项目下的所有 Web 测试列表，支持搜索和过滤",
)
async def list_web_tests(
    project_identifier: str,
    service: WebTestService = Depends(get_web_test_service),
    pagination: PaginationDep = None,  # type: ignore
    search: Optional[str] = Query(None, description="搜索关键词"),
    script_format: Optional[str] = Query(None, description="脚本格式过滤"),
):
    """获取 Web 测试列表"""
    result = await service.list_web_tests(
        project_identifier=project_identifier,
        page=pagination.p,
        page_size=pagination.page_size,
        search=search,
        script_format=script_format,
    )

    return SuccessResponse(data=result)


@router.get(
    "/{web_test_id}",
    response_model=SuccessResponse,
    summary="获取 Web 测试详情",
    description="获取指定 Web 测试的详细信息",
)
async def get_web_test(
    project_identifier: str,
    web_test_id: str,
    service: WebTestService = Depends(get_web_test_service),
):
    """获取 Web 测试详情"""
    result = await service.get_web_test(
        project_identifier=project_identifier,
        web_test_id=web_test_id,
    )

    return SuccessResponse(data=result)


@router.patch(
    "/{web_test_id}",
    response_model=SuccessResponse,
    summary="更新 Web 测试",
    description="更新 Web 测试配置",
)
async def update_web_test(
    project_identifier: str,
    web_test_id: str,
    service: WebTestService = Depends(get_web_test_service),
    name: Optional[str] = None,
    description: Optional[str] = None,
    test_config: Optional[dict] = None,
):
    """更新 Web 测试"""
    result = await service.update_web_test(
        project_identifier=project_identifier,
        web_test_id=web_test_id,
        name=name,
        description=description,
        test_config=test_config,
    )
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTA1MGN3PT06MjcxZTc3MzM=

    return SuccessResponse(data=result, message="Web 测试更新成功")


@router.delete(
    "/{web_test_id}",
    response_model=SuccessResponse,
    summary="删除 Web 测试",
    description="删除指定的 Web 测试",
)
async def delete_web_test(
    project_identifier: str,
    web_test_id: str,
    service: WebTestService = Depends(get_web_test_service),
):
    """删除 Web 测试"""
    await service.delete_web_test(
        project_identifier=project_identifier,
        web_test_id=web_test_id,
    )

    return SuccessResponse(message="Web 测试删除成功")


# ============ 测试脚本管理接口 ============

@router.get(
    "/{web_test_id}/script",
    response_class=Response,
    summary="获取测试脚本",
    description="获取 Web 测试的脚本内容",
)
async def get_test_script(
    project_identifier: str,
    web_test_id: str,
    service: WebTestService = Depends(get_web_test_service),
):
    """获取测试脚本"""
    content = await service.get_test_script(
        project_identifier=project_identifier,
        web_test_id=web_test_id,
    )

    return Response(content=content, media_type="text/plain")
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTA1MGN3PT06MjcxZTc3MzM=


@router.put(
    "/{web_test_id}/script",
    response_model=SuccessResponse,
    summary="更新测试脚本",
    description="更新 Web 测试的脚本内容",
)
async def update_test_script(
    project_identifier: str,
    web_test_id: str,
    service: WebTestService = Depends(get_web_test_service),
    script_content: str = Form(..., description="脚本内容"),
):
    """更新测试脚本"""
    await service.update_test_script(
        project_identifier=project_identifier,
        web_test_id=web_test_id,
        script_content=script_content,
    )

    return SuccessResponse(message="测试脚本更新成功")


# ============ 测试执行接口 ============

@router.post(
    "/{web_test_id}/run",
    response_model=SuccessResponse,
    summary="执行 Web 测试",
    description="执行指定的 Web 测试",
)
async def run_web_test(
    project_identifier: str,
    web_test_id: str,
    service: WebTestService = Depends(get_web_test_service),
    execution_config: Optional[dict] = None,
):
    """执行 Web 测试"""
    result = await service.run_web_test(
        project_identifier=project_identifier,
        web_test_id=web_test_id,
        execution_config=execution_config,
    )

    return SuccessResponse(data=result, message="Web 测试已开始执行")


@router.get(
    "/{web_test_id}/runs",
    response_model=SuccessResponse,
    summary="获取测试运行历史",
    description="获取 Web 测试的运行历史记录",
)
async def list_test_runs(
    project_identifier: str,
    web_test_id: str,
    service: WebTestService = Depends(get_web_test_service),
    pagination: PaginationDep = None,  # type: ignore
):
    """获取测试运行历史"""
    result = await service.get_test_runs(
        project_identifier=project_identifier,
        web_test_id=web_test_id,
        page=pagination.p,
        page_size=pagination.page_size,
    )

    return SuccessResponse(data=result)
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTA1MGN3PT06MjcxZTc3MzM=


# ============ 文件夹操作接口 ============

@router.get(
    "/folder/{folder_id}",
    response_model=SuccessResponse,
    summary="获取文件夹下的 Web 测试",
    description="获取指定文件夹下的所有 Web 测试",
)
async def get_folder_web_tests(
    project_identifier: str,
    folder_id: str,
    service: WebTestService = Depends(get_web_test_service),
    pagination: PaginationDep = None,  # type: ignore
):
    """获取文件夹下的 Web 测试"""
    result = await service.get_folder_web_tests(
        project_identifier=project_identifier,
        folder_id=folder_id,
        page=pagination.p,
        page_size=pagination.page_size,
    )

    return SuccessResponse(data=result)
