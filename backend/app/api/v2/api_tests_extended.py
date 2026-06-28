"""
API 测试扩展 API

提供基于文件夹的 API 测试查询接口
"""

from typing import Optional
from uuid import UUID
# fmt: off  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2WkROdlJ3PT06MTBlN2Q0ZTc=

from fastapi import APIRouter, Query

from app.api.deps import (
    APITestServiceDep,
    PaginationDep,
)
from app.schemas.common import SuccessResponse


router = APIRouter(prefix="/projects/{project_identifier}/folders")


@router.get(
    "/{folder_id}/api-tests",
    response_model=SuccessResponse,
    summary="获取文件夹下的 API 测试列表",
    description="获取指定文件夹下的所有 API 测试列表，支持搜索和分页",
)
async def list_api_tests_by_folder(
    project_identifier: str,
    folder_id: UUID,
    service: APITestServiceDep,
    pagination: PaginationDep,
    search: Optional[str] = Query(None, description="搜索关键词（名称、标识符、描述）"),
):
    """
    获取文件夹下的 API 测试列表

    - **project_identifier**: 项目标识符
    - **folder_id**: 文件夹 ID
    - **p**: 页码
    - **page_size**: 每页数量
    - **search**: 搜索关键词（可选）
    """
    result = await service.list_api_tests_by_folder(
        project_identifier=project_identifier,
        folder_id=str(folder_id),
        page=pagination.p,
        page_size=pagination.page_size,
        search=search,
    )
# fmt: off  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2WkROdlJ3PT06MTBlN2Q0ZTc=

    return SuccessResponse(data=result)
