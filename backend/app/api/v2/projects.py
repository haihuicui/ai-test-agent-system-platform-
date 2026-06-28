"""
项目管理 API

提供项目的 CRUD 操作接口
参考: https://www.browserstack.com/docs/test-management/api-reference/projects
"""

from fastapi import APIRouter, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    ProjectServiceDep,
    PaginationDep,
    CurrentUserIdDep,
    DbSessionDep,
)
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectInfo
from app.schemas.common import SuccessResponse, MessageResponse
from app.schemas.pagination import PaginatedResponse, PaginationInfo
from app.config.settings import settings
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1RnM2RnPT06OTg2YzliNjI=


router = APIRouter(prefix="/projects")


@router.get(
    "",
    response_model=PaginatedResponse[ProjectInfo],
    summary="获取项目列表",
    description="获取所有项目的列表，支持分页",
)
async def get_projects(
    service: ProjectServiceDep,
    pagination: PaginationDep,
) -> PaginatedResponse[ProjectInfo]:
    """
    获取项目列表
    
    - **p**: 页码，从 1 开始
    - **page_size**: 每页数量，默认 30，最大 300
    """
    offset = (pagination.page - 1) * pagination.page_size
    projects, total = await service.get_projects(offset, pagination.page_size)
    
    # 计算分页信息
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    base_url = f"{settings.api_prefix}/projects"
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1RnM2RnPT06OTg2YzliNjI=
    
    prev_url = None
    if pagination.page > 1:
        prev_url = f"{base_url}?p={pagination.page - 1}&page_size={pagination.page_size}"
    
    next_url = None
    if pagination.page < total_pages:
        next_url = f"{base_url}?p={pagination.page + 1}&page_size={pagination.page_size}"
    
    return PaginatedResponse(
        success=True,
        data=projects,
        info=PaginationInfo(
            page=pagination.page,
            page_size=pagination.page_size,
            count=len(projects),
            total=total,
            prev=prev_url,
            next=next_url,
        ),
    )

# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1RnM2RnPT06OTg2YzliNjI=

@router.get(
    "/{project_identifier}",
    response_model=SuccessResponse[ProjectInfo],
    summary="获取项目详情",
    description="根据项目标识符获取项目详细信息",
)
async def get_project(
    project_identifier: str,
    service: ProjectServiceDep,
) -> SuccessResponse[ProjectInfo]:
    """
    获取项目详情
    
    - **project_identifier**: 项目标识符，如 PR-1234
    """
    project = await service.get_project(project_identifier)
    return SuccessResponse(success=True, data=project)


@router.post(
    "",
    response_model=SuccessResponse[ProjectInfo],
    status_code=status.HTTP_201_CREATED,
    summary="创建项目",
    description="创建一个新项目",
)
async def create_project(
    data: ProjectCreate,
    service: ProjectServiceDep,
    current_user_id: CurrentUserIdDep,
    db: DbSessionDep,
) -> SuccessResponse[ProjectInfo]:
    """
    创建项目
    
    - **name**: 项目名称（必填）
    - **description**: 项目描述（可选）
    - **team_id**: 关联的团队 ID 列表（可选）
    """
    project = await service.create_project(data, current_user_id)
    await db.commit()
    return SuccessResponse(success=True, data=project)

# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1RnM2RnPT06OTg2YzliNjI=

@router.patch(
    "/{project_identifier}",
    response_model=SuccessResponse[ProjectInfo],
    summary="更新项目",
    description="更新指定项目的信息",
)
async def update_project(
    project_identifier: str,
    data: ProjectUpdate,
    service: ProjectServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[ProjectInfo]:
    """
    更新项目

    - **project_identifier**: 项目标识符，如 PR-1234
    - **name**: 项目名称（可选）
    - **description**: 项目描述（可选）

    只更新请求体中提供的字段
    """
    project = await service.update_project(project_identifier, data)
    await db.commit()
    return SuccessResponse(success=True, data=project)


@router.delete(
    "/{project_identifier}",
    response_model=MessageResponse,
    summary="删除项目",
    description="删除指定的项目及其所有关联数据",
)
async def delete_project(
    project_identifier: str,
    service: ProjectServiceDep,
    db: DbSessionDep,
) -> MessageResponse:
    """
    删除项目

    - **project_identifier**: 项目标识符，如 PR-1234

    注意: 删除项目将同时删除该项目下的所有文件夹和测试用例
    """
    message = await service.delete_project(project_identifier)
    await db.commit()
    return MessageResponse(success=True, message=message)

