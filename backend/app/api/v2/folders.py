"""
文件夹管理 API

提供文件夹的 CRUD 操作接口
参考: https://www.browserstack.com/docs/test-management/api-reference/folders
"""

from typing import Optional
from uuid import UUID
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZHpKYWR3PT06Mzc4ZjIxMDg=

from fastapi import APIRouter, Query, status

from app.api.deps import (
    FolderServiceDep,
    PaginationDep,
    DbSessionDep,
)
from app.schemas.folder import FolderCreate, FolderUpdate, FolderMove, FolderInfo
from app.schemas.common import SuccessResponse, MessageResponse
from app.schemas.pagination import PaginatedResponse, PaginationInfo
from app.config.settings import settings


router = APIRouter(prefix="/projects/{project_identifier}/folders")


@router.get(
    "",
    response_model=PaginatedResponse[FolderInfo],
    summary="获取根文件夹列表",
    description="获取项目下的根文件夹列表（不包含子文件夹）",
)
async def get_folders(
    project_identifier: str,
    service: FolderServiceDep,
    pagination: PaginationDep,
    folder_type: Optional[str] = Query(None, description="文件夹类型过滤 (test_case 或 api_test)"),
) -> PaginatedResponse[FolderInfo]:
    """
    获取根文件夹列表

    - **project_identifier**: 项目标识符
    - **p**: 页码
    - **page_size**: 每页数量
    - **folder_type**: 文件夹类型过滤 (可选)
    """
    offset = (pagination.page - 1) * pagination.page_size
    folders, total = await service.get_root_folders(
        project_identifier, offset, pagination.page_size, folder_type
    )

    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    base_url = f"{settings.api_prefix}/projects/{project_identifier}/folders"

    # 构建 URL 参数
    params = []
    if folder_type:
        params.append(f"folder_type={folder_type}")

    prev_url = None
    if pagination.page > 1:
        prev_params = params.copy()
        prev_params.append(f"p={pagination.page - 1}&page_size={pagination.page_size}")
        prev_url = f"{base_url}?{'&'.join(prev_params)}"

    next_url = None
    if pagination.page < total_pages:
        next_params = params.copy()
        next_params.append(f"p={pagination.page + 1}&page_size={pagination.page_size}")
        next_url = f"{base_url}?{'&'.join(next_params)}"

    return PaginatedResponse(
        success=True,
        data=folders,
        info=PaginationInfo(
            page=pagination.page,
            page_size=pagination.page_size,
            count=len(folders),
            total=total,
            prev=prev_url,
            next=next_url,
        ),
    )


@router.get(
    "/{folder_id}",
    response_model=SuccessResponse[FolderInfo],
    summary="获取文件夹详情",
    description="获取指定文件夹的详细信息",
)
async def get_folder(
    project_identifier: str,
    folder_id: UUID,
    service: FolderServiceDep,
) -> SuccessResponse[FolderInfo]:
    """获取文件夹详情"""
    folder = await service.get_folder(project_identifier, folder_id)
    return SuccessResponse(success=True, data=folder)
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZHpKYWR3PT06Mzc4ZjIxMDg=


@router.get(
    "/{folder_id}/sub-folders",
    response_model=PaginatedResponse[FolderInfo],
    summary="获取子文件夹列表",
    description="获取指定文件夹下的子文件夹列表",
)
async def get_sub_folders(
    project_identifier: str,
    folder_id: UUID,
    service: FolderServiceDep,
    pagination: PaginationDep,
    folder_type: Optional[str] = Query(None, description="文件夹类型过滤 (test_case 或 api_test)"),
) -> PaginatedResponse[FolderInfo]:
    """获取子文件夹列表"""
    offset = (pagination.page - 1) * pagination.page_size
    folders, total = await service.get_sub_folders(
        project_identifier, folder_id, offset, pagination.page_size, folder_type
    )

    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    base_url = f"{settings.api_prefix}/projects/{project_identifier}/folders/{folder_id}/sub-folders"
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZHpKYWR3PT06Mzc4ZjIxMDg=

    # 构建 URL 参数
    params = []
    if folder_type:
        params.append(f"folder_type={folder_type}")

    prev_url = None
    if pagination.page > 1:
        prev_params = params.copy()
        prev_params.append(f"p={pagination.page - 1}&page_size={pagination.page_size}")
        prev_url = f"{base_url}?{'&'.join(prev_params)}"

    next_url = None
    if pagination.page < total_pages:
        next_params = params.copy()
        next_params.append(f"p={pagination.page + 1}&page_size={pagination.page_size}")
        next_url = f"{base_url}?{'&'.join(next_params)}"

    return PaginatedResponse(
        success=True,
        data=folders,
        info=PaginationInfo(
            page=pagination.page,
            page_size=pagination.page_size,
            count=len(folders),
            total=total,
            prev=prev_url,
            next=next_url,
        ),
    )


@router.post(
    "",
    response_model=SuccessResponse[FolderInfo],
    status_code=status.HTTP_201_CREATED,
    summary="创建文件夹",
    description="在项目下创建新文件夹",
)
async def create_folder(
    project_identifier: str,
    data: FolderCreate,
    service: FolderServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[FolderInfo]:
    """创建文件夹"""
    folder = await service.create_folder(project_identifier, data)
    await db.commit()
    return SuccessResponse(success=True, data=folder)


@router.patch(
    "/{folder_id}",
    response_model=SuccessResponse[FolderInfo],
    summary="更新文件夹",
    description="更新指定文件夹的信息",
)
async def update_folder(
    project_identifier: str,
    folder_id: UUID,
    data: FolderUpdate,
    service: FolderServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[FolderInfo]:
    """更新文件夹"""
    folder = await service.update_folder(project_identifier, folder_id, data)
    await db.commit()
    return SuccessResponse(success=True, data=folder)


@router.delete(
    "/{folder_id}",
    response_model=MessageResponse,
    summary="删除文件夹",
    description="删除指定的文件夹及其所有子文件夹和测试用例",
)
async def delete_folder(
    project_identifier: str,
    folder_id: UUID,
    service: FolderServiceDep,
    db: DbSessionDep,
) -> MessageResponse:
    """删除文件夹"""
    message = await service.delete_folder(project_identifier, folder_id)
    await db.commit()
    return MessageResponse(success=True, message=message)
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZHpKYWR3PT06Mzc4ZjIxMDg=


@router.post(
    "/{folder_id}/move",
    response_model=SuccessResponse[FolderInfo],
    summary="移动文件夹",
    description="将文件夹移动到新的父文件夹下",
)
async def move_folder(
    project_identifier: str,
    folder_id: UUID,
    data: FolderMove,
    service: FolderServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[FolderInfo]:
    """
    移动文件夹

    参考: https://www.browserstack.com/docs/test-management/api-reference/folders#move-a-folder

    - **parent_id**: 目标父文件夹 ID，为 null 则移动到根目录
    """
    folder = await service.move_folder(project_identifier, folder_id, data)
    await db.commit()
    return SuccessResponse(success=True, data=folder)


@router.post(
    "/{folder_id}/copy",
    response_model=SuccessResponse[FolderInfo],
    status_code=status.HTTP_201_CREATED,
    summary="复制文件夹",
    description="复制文件夹及其所有子文件夹和测试用例",
)
async def copy_folder(
    project_identifier: str,
    folder_id: UUID,
    service: FolderServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[FolderInfo]:
    """
    复制文件夹

    复制文件夹及其所有子文件夹和测试用例到同级目录
    """
    folder = await service.copy_folder(project_identifier, folder_id)
    await db.commit()
    return SuccessResponse(success=True, data=folder)
