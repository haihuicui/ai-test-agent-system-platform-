"""
Web 功能和子功能管理 API

提供 Web 功能和子功能的 CRUD 操作接口
"""

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import (
    WebFunctionServiceDep,
    PaginationDep,
)
from app.schemas.common import SuccessResponse


# ============ 请求模型 ============

class CreateWebFunctionRequest(BaseModel):
    """创建 Web 功能请求"""
    display_name: str
    name: str
    folder_id: Optional[str] = None
    description: Optional[str] = None
    base_url: Optional[str] = None
    business_module: Optional[str] = None
    navigation: Optional[dict] = None
    pages: Optional[list] = None
    tags: Optional[list] = None
    custom_config: Optional[dict] = None
    sort_order: int = 0


class UpdateWebFunctionRequest(BaseModel):
    """更新 Web 功能请求"""
    display_name: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    base_url: Optional[str] = None
    business_module: Optional[str] = None
    navigation: Optional[dict] = None
    pages: Optional[list] = None
    tags: Optional[list] = None
    custom_config: Optional[dict] = None
    sort_order: Optional[int] = None

# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TlRRMFNnPT06NmFkNmU1NWI=

class CreateWebSubFunctionRequest(BaseModel):
    """创建 Web 子功能请求"""
    function_id: str
    display_name: str
    name: str
    folder_id: Optional[str] = None
    description: Optional[str] = None
    test_type: str = "functional"
    target_pages: Optional[list] = None
    test_scenario: Optional[str] = None
    test_data: Optional[dict] = None
    expected_results: Optional[list] = None
    priority: str = "medium"
    tags: Optional[list] = None
    custom_config: Optional[dict] = None
    sort_order: int = 0


class UpdateWebSubFunctionRequest(BaseModel):
    """更新 Web 子功能请求"""
    display_name: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    test_type: Optional[str] = None
    target_pages: Optional[list] = None
    test_scenario: Optional[str] = None
    test_data: Optional[dict] = None
    expected_results: Optional[list] = None
    priority: Optional[str] = None
    tags: Optional[list] = None
    custom_config: Optional[dict] = None
    sort_order: Optional[int] = None

# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TlRRMFNnPT06NmFkNmU1NWI=

# ============ 路由定义 ============

router = APIRouter(prefix="/projects/{project_identifier}/web-functions")


# ============ Web 功能管理接口 ============

@router.post(
    "",
    response_model=SuccessResponse,
    summary="创建 Web 功能",
    description="创建新的 Web 功能定义",
)
async def create_web_function(
    project_identifier: str,
    request: CreateWebFunctionRequest,
    service: WebFunctionServiceDep,
):
    """创建 Web 功能"""
    result = await service.create_web_function(
        project_identifier=project_identifier,
        **request.model_dump(),
    )

    return SuccessResponse(data=result, message="Web 功能创建成功")


@router.get(
    "",
    response_model=SuccessResponse,
    summary="获取 Web 功能列表",
    description="获取项目下的所有 Web 功能列表，支持搜索和过滤",
)
async def list_web_functions(
    project_identifier: str,
    service: WebFunctionServiceDep,
    pagination: PaginationDep,
    folder_id: Optional[str] = Query(None, description="文件夹 ID 过滤"),
    search: Optional[str] = Query(None, description="搜索关键词"),
):
    """获取 Web 功能列表"""
    result = await service.list_web_functions(
        project_identifier=project_identifier,
        folder_id=folder_id,
        offset=(pagination.p - 1) * pagination.page_size,
        limit=pagination.page_size,
        search=search,
    )

    return SuccessResponse(data=result)


# ============ Web 子功能管理接口 ============

@router.get(
    "/sub-functions",
    response_model=SuccessResponse,
    summary="获取 Web 子功能列表",
    description="获取项目下的所有 Web 子功能列表，支持搜索和过滤",
)
async def list_web_sub_functions(
    project_identifier: str,
    service: WebFunctionServiceDep,
    pagination: PaginationDep,
    function_id: Optional[str] = Query(None, description="功能 ID 过滤"),
    folder_id: Optional[str] = Query(None, description="文件夹 ID 过滤"),
    search: Optional[str] = Query(None, description="搜索关键词"),
):
    """获取 Web 子功能列表"""
    result = await service.list_web_sub_functions(
        project_identifier=project_identifier,
        function_id=function_id,
        folder_id=folder_id,
        offset=(pagination.p - 1) * pagination.page_size,
        limit=pagination.page_size,
        search=search,
    )

    return SuccessResponse(data=result)


@router.post(
    "/sub-functions",
    response_model=SuccessResponse,
    summary="创建 Web 子功能",
    description="创建新的 Web 子功能定义",
)
async def create_web_sub_function(
    project_identifier: str,
    request: CreateWebSubFunctionRequest,
    service: WebFunctionServiceDep,
):
    """创建 Web 子功能"""
    result = await service.create_web_sub_function(
        project_identifier=project_identifier,
        **request.model_dump(),
    )

    return SuccessResponse(data=result, message="Web 子功能创建成功")
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TlRRMFNnPT06NmFkNmU1NWI=


@router.get(
    "/sub-functions/{sub_function_id}",
    response_model=SuccessResponse,
    summary="获取 Web 子功能详情",
    description="获取指定 Web 子功能的详细信息",
)
async def get_web_sub_function(
    sub_function_id: str,
    service: WebFunctionServiceDep,
):
    """获取 Web 子功能详情"""
    result = await service.get_web_sub_function(sub_function_id=sub_function_id)
    return SuccessResponse(data=result)


@router.patch(
    "/sub-functions/{sub_function_id}",
    response_model=SuccessResponse,
    summary="更新 Web 子功能",
    description="更新指定 Web 子功能的信息",
)
async def update_web_sub_function(
    sub_function_id: str,
    request: UpdateWebSubFunctionRequest,
    service: WebFunctionServiceDep,
):
    """更新 Web 子功能"""
    result = await service.update_web_sub_function(
        sub_function_id=sub_function_id,
        **request.model_dump(exclude_none=True),
    )

    return SuccessResponse(data=result, message="Web 子功能更新成功")


@router.delete(
    "/sub-functions/{sub_function_id}",
    response_model=SuccessResponse,
    summary="删除 Web 子功能",
    description="删除指定的 Web 子功能",
)
async def delete_web_sub_function(
    sub_function_id: str,
    service: WebFunctionServiceDep,
):
    """删除 Web 子功能"""
    result = await service.delete_web_sub_function(sub_function_id=sub_function_id)
    return SuccessResponse(data=result)
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TlRRMFNnPT06NmFkNmU1NWI=


@router.get(
    "/sub-functions/{sub_function_id}/artifacts",
    response_model=SuccessResponse,
    summary="获取 Web 子功能测试成果物",
    description="获取指定 Web 子功能的所有测试成果物（测试计划、测试用例、测试脚本、测试报告）",
)
async def get_web_sub_function_artifacts(
    sub_function_id: str,
    service: WebFunctionServiceDep,
):
    """获取 Web 子功能测试成果物"""
    result = await service.get_sub_function_artifacts(sub_function_id=sub_function_id)
    return SuccessResponse(data=result)


@router.get(
    "/{function_id}",
    response_model=SuccessResponse,
    summary="获取 Web 功能详情",
    description="获取指定 Web 功能的详细信息",
)
async def get_web_function(
    function_id: str,
    service: WebFunctionServiceDep,
):
    """获取 Web 功能详情"""
    result = await service.get_web_function(function_id=function_id)
    return SuccessResponse(data=result)


@router.patch(
    "/{function_id}",
    response_model=SuccessResponse,
    summary="更新 Web 功能",
    description="更新指定 Web 功能的信息",
)
async def update_web_function(
    function_id: str,
    request: UpdateWebFunctionRequest,
    service: WebFunctionServiceDep,
):
    """更新 Web 功能"""
    result = await service.update_web_function(
        function_id=function_id,
        **request.model_dump(exclude_none=True),
    )

    return SuccessResponse(data=result, message="Web 功能更新成功")


@router.delete(
    "/{function_id}",
    response_model=SuccessResponse,
    summary="删除 Web 功能",
    description="删除指定的 Web 功能",
)
async def delete_web_function(
    function_id: str,
    service: WebFunctionServiceDep,
):
    """删除 Web 功能"""
    result = await service.delete_web_function(function_id=function_id)
    return SuccessResponse(data=result)
