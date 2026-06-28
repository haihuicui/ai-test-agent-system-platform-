"""
Android 测试管理 API

提供 Android 测试的 CRUD 操作接口
"""

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import (
    PaginationDep,
)
from app.schemas.common import SuccessResponse
from app.services.android_test_service import AndroidTestService
from app.config.database import get_db
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession


# ============ 请求模型 ============

class CreateAndroidFunctionRequest(BaseModel):
    """创建 Android 功能请求"""
    display_name: str
    name: str
    folder_id: Optional[str] = None
    description: Optional[str] = None
    app_package: Optional[str] = None
    app_activity: Optional[str] = None
    device_udid: Optional[str] = None
    business_module: Optional[str] = None
    script_format: str = "midscene"
    script_language: str = "typescript"
    test_config: Optional[dict] = None
    pages: Optional[list] = None
    tags: Optional[list] = None
    custom_config: Optional[dict] = None
    sort_order: int = 0
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlVZNVNRPT06YzM2MjA1YTA=


class UpdateAndroidFunctionRequest(BaseModel):
    """更新 Android 功能请求"""
    display_name: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    app_package: Optional[str] = None
    app_activity: Optional[str] = None
    device_udid: Optional[str] = None
    business_module: Optional[str] = None
    script_format: Optional[str] = None
    script_language: Optional[str] = None
    test_config: Optional[dict] = None
    pages: Optional[list] = None
    tags: Optional[list] = None
    custom_config: Optional[dict] = None
    sort_order: Optional[int] = None


# ============ 依赖注入 ============

async def get_android_test_service(
    db: AsyncSession = Depends(get_db),
) -> AndroidTestService:
    """获取 Android 测试服务实例"""
    return AndroidTestService(db)

# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlVZNVNRPT06YzM2MjA1YTA=

AndroidTestServiceDep = AndroidTestService


# ============ 路由定义 ============

router = APIRouter(prefix="/projects/{project_identifier}/android-functions")


# ============ Android 功能管理接口 ============

@router.post(
    "",
    response_model=SuccessResponse,
    summary="创建 Android 功能",
    description="创建新的 Android 功能定义",
)
async def create_android_function(
    project_identifier: str,
    request: CreateAndroidFunctionRequest,
    service: AndroidTestService = Depends(get_android_test_service),
):
    """创建 Android 功能"""
    result = await service.create_android_function(
        project_identifier=project_identifier,
        **request.model_dump(),
    )

    return SuccessResponse(data=result, message="Android 功能创建成功")


@router.get(
    "",
    response_model=SuccessResponse,
    summary="获取 Android 功能列表",
    description="获取项目下的所有 Android 功能列表，支持搜索和过滤",
)
async def list_android_functions(
    project_identifier: str,
    pagination: PaginationDep,
    service: AndroidTestService = Depends(get_android_test_service),
    folder_id: Optional[str] = Query(None, description="文件夹 ID 过滤"),
    search: Optional[str] = Query(None, description="搜索关键词"),
):
    """获取 Android 功能列表"""
    result = await service.list_android_functions(
        project_identifier=project_identifier,
        folder_id=folder_id,
        offset=(pagination.p - 1) * pagination.page_size,
        limit=pagination.page_size,
        search=search,
    )

    return SuccessResponse(data=result)


# ============ Android 子功能管理接口 ============
# 注意：静态路由必须定义在动态路由 /{function_id} 之前，否则 FastAPI 会错误匹配

@router.get(
    "/sub-functions",
    response_model=SuccessResponse,
    summary="获取 Android 子功能列表",
    description="获取项目下的所有 Android 子功能列表，支持搜索和过滤",
)
async def list_android_sub_functions(
    project_identifier: str,
    pagination: PaginationDep,
    service: AndroidTestService = Depends(get_android_test_service),
    function_id: Optional[str] = Query(None, description="功能 ID 过滤"),
    folder_id: Optional[str] = Query(None, description="文件夹 ID 过滤"),
    search: Optional[str] = Query(None, description="搜索关键词"),
):
    """获取 Android 子功能列表"""
    result = await service.list_android_sub_functions(
        project_identifier=project_identifier,
        function_id=function_id,
        folder_id=folder_id,
        offset=(pagination.p - 1) * pagination.page_size,
        limit=pagination.page_size,
        search=search,
    )
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlVZNVNRPT06YzM2MjA1YTA=

    return SuccessResponse(data=result)


@router.get(
    "/sub-functions/{sub_function_id}",
    response_model=SuccessResponse,
    summary="获取 Android 子功能详情",
    description="获取指定 Android 子功能的详细信息",
)
async def get_android_sub_function(
    sub_function_id: str,
    service: AndroidTestService = Depends(get_android_test_service),
):
    """获取 Android 子功能详情"""
    result = await service.get_android_sub_function(sub_function_id=sub_function_id)
    return SuccessResponse(data=result)


@router.get(
    "/{function_id}",
    response_model=SuccessResponse,
    summary="获取 Android 功能详情",
    description="获取指定 Android 功能的详细信息",
)
async def get_android_function(
    function_id: str,
    service: AndroidTestService = Depends(get_android_test_service),
):
    """获取 Android 功能详情"""
    result = await service.get_android_function(function_id=function_id)
    return SuccessResponse(data=result)


@router.patch(
    "/{function_id}",
    response_model=SuccessResponse,
    summary="更新 Android 功能",
    description="更新指定 Android 功能的信息",
)
async def update_android_function(
    function_id: str,
    request: UpdateAndroidFunctionRequest,
    service: AndroidTestService = Depends(get_android_test_service),
):
    """更新 Android 功能"""
    result = await service.update_android_function(
        function_id=function_id,
        **request.model_dump(exclude_none=True),
    )

    return SuccessResponse(data=result, message="Android 功能更新成功")


@router.delete(
    "/{function_id}",
    response_model=SuccessResponse,
    summary="删除 Android 功能",
    description="删除指定的 Android 功能",
)
async def delete_android_function(
    function_id: str,
    service: AndroidTestService = Depends(get_android_test_service),
):
    """删除 Android 功能"""
    result = await service.delete_android_function(function_id=function_id)
    return SuccessResponse(data=result)


# ============ 设备管理接口 ============

devices_router = APIRouter(prefix="/projects/{project_identifier}/android-devices")


@devices_router.get(
    "",
    response_model=SuccessResponse,
    summary="获取 Android 设备列表",
    description="获取已连接的 Android 设备列表",
)
async def list_android_devices(
    project_identifier: str,
    service: AndroidTestService = Depends(get_android_test_service),
):
    """获取 Android 设备列表"""
    result = await service.list_android_devices(project_identifier=project_identifier)
    return SuccessResponse(data=result)

# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YlVZNVNRPT06YzM2MjA1YTA=

@devices_router.post(
    "/refresh",
    response_model=SuccessResponse,
    summary="刷新 Android 设备列表",
    description="重新扫描并获取已连接的 Android 设备列表",
)
async def refresh_android_devices(
    project_identifier: str,
    service: AndroidTestService = Depends(get_android_test_service),
):
    """刷新 Android 设备列表"""
    result = await service.refresh_android_devices(project_identifier=project_identifier)
    return SuccessResponse(data=result)
