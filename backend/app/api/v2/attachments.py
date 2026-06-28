"""
附件管理 API

提供附件的上传、下载和删除操作
参考: https://www.browserstack.com/docs/test-management/api-reference/attachments
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, status, UploadFile, File, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.api.deps import DbSessionDep
from app.services.attachment_service import AttachmentService
from app.schemas.attachment import (
    AttachmentUploadResponse,
    TestCaseAttachmentsResponse,
    TestResultAttachmentsResponse,
)
from app.schemas.common import SuccessResponse, MessageResponse
from app.config.database import get_db


# ============ 测试用例附件路由 ============
test_case_attachments_router = APIRouter(
    prefix="/projects/{project_identifier}/test-cases/{test_case_identifier}/attachments"
)


def get_attachment_service(session: AsyncSession = Depends(get_db)) -> AttachmentService:
    """获取附件服务"""
    return AttachmentService(session)
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UlZSeWRRPT06MTNkZDY1MjQ=


AttachmentServiceDep = Annotated[AttachmentService, Depends(get_attachment_service)]


@test_case_attachments_router.get(
    "",
    response_model=SuccessResponse[TestCaseAttachmentsResponse],
    summary="获取测试用例附件列表",
    description="获取指定测试用例的所有附件",
)
async def get_test_case_attachments(
    project_identifier: str,
    test_case_identifier: str,
    service: AttachmentServiceDep,
) -> SuccessResponse[TestCaseAttachmentsResponse]:
    """获取测试用例附件列表"""
    result = await service.get_test_case_attachments(
        project_identifier, test_case_identifier
    )
    return SuccessResponse(success=True, data=result)

# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UlZSeWRRPT06MTNkZDY1MjQ=

@test_case_attachments_router.post(
    "",
    response_model=SuccessResponse[AttachmentUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="上传测试用例附件",
    description="为测试用例上传附件文件，最大支持 50MB",
)
async def upload_test_case_attachment(
    project_identifier: str,
    test_case_identifier: str,
    file: UploadFile = File(..., description="要上传的文件"),
    service: AttachmentServiceDep = None,
    db: DbSessionDep = None,
) -> SuccessResponse[AttachmentUploadResponse]:
    """上传测试用例附件"""
    result = await service.upload_test_case_attachment(
        project_identifier, test_case_identifier, file
    )
    await db.commit()
    return SuccessResponse(success=True, data=result)


@test_case_attachments_router.delete(
    "/{attachment_id}",
    response_model=MessageResponse,
    summary="删除测试用例附件",
    description="删除指定的测试用例附件，此操作不可撤销",
)
async def delete_test_case_attachment(
    project_identifier: str,
    test_case_identifier: str,
    attachment_id: UUID,
    service: AttachmentServiceDep,
    db: DbSessionDep,
) -> MessageResponse:
    """删除测试用例附件"""
    await service.delete_test_case_attachment(
        project_identifier, test_case_identifier, str(attachment_id)
    )
    await db.commit()
    return MessageResponse(success=True, message="附件删除成功")


# ============ 测试结果附件路由 ============
test_result_attachments_router = APIRouter(
    prefix="/projects/{project_identifier}/test-results/{test_result_id}/attachments"
)
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UlZSeWRRPT06MTNkZDY1MjQ=


@test_result_attachments_router.get(
    "",
    response_model=SuccessResponse[TestResultAttachmentsResponse],
    summary="获取测试结果附件列表",
    description="获取指定测试结果的所有附件",
)
async def get_test_result_attachments(
    project_identifier: str,
    test_result_id: UUID,
    service: AttachmentServiceDep,
) -> SuccessResponse[TestResultAttachmentsResponse]:
    """获取测试结果附件列表"""
    result = await service.get_test_result_attachments(
        project_identifier, str(test_result_id)
    )
    return SuccessResponse(success=True, data=result)


@test_result_attachments_router.post(
    "",
    response_model=SuccessResponse[AttachmentUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="上传测试结果附件",
    description="为测试结果上传附件文件，最大支持 50MB",
)
async def upload_test_result_attachment(
    project_identifier: str,
    test_result_id: UUID,
    file: UploadFile = File(..., description="要上传的文件"),
    service: AttachmentServiceDep = None,
    db: DbSessionDep = None,
) -> SuccessResponse[AttachmentUploadResponse]:
    """上传测试结果附件"""
    result = await service.upload_test_result_attachment(
        project_identifier, str(test_result_id), file
    )
    await db.commit()
    return SuccessResponse(success=True, data=result)


@test_result_attachments_router.delete(
    "/{attachment_id}",
    response_model=MessageResponse,
    summary="删除测试结果附件",
    description="删除指定的测试结果附件，此操作不可撤销",
)
async def delete_test_result_attachment(
    project_identifier: str,
    test_result_id: UUID,
    attachment_id: UUID,
    service: AttachmentServiceDep,
    db: DbSessionDep,
) -> MessageResponse:
    """删除测试结果附件"""
    await service.delete_test_result_attachment(
        project_identifier, str(test_result_id), str(attachment_id)
    )
    await db.commit()
    return MessageResponse(success=True, message="附件删除成功")


# ============ 通用附件路由 ============
attachments_router = APIRouter(
    prefix="/projects/{project_identifier}/attachments"
)


@attachments_router.get(
    "/{attachment_id}",
    summary="获取附件下载链接",
    description="获取附件的预签名下载 URL",
)
async def get_attachment_download_url(
    project_identifier: str,
    attachment_id: UUID,
    service: AttachmentServiceDep,
):
    """获取附件下载链接"""
    result = await service.get_attachment_download_url(
        project_identifier, str(attachment_id)
    )
    return SuccessResponse(success=True, data=result)


@attachments_router.get(
    "/{attachment_id}/download",
    summary="下载附件",
    description="直接下载附件文件",
    responses={
        200: {
            "content": {"application/octet-stream": {}},
            "description": "附件文件内容",
        }
    },
)
async def download_attachment(
    project_identifier: str,
    attachment_id: UUID,
    service: AttachmentServiceDep,
) -> StreamingResponse:
    """下载附件"""
    content, filename, content_type = await service.download_attachment(
        project_identifier, str(attachment_id)
    )

    return StreamingResponse(
        io.BytesIO(content),
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
        }
    )

# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UlZSeWRRPT06MTNkZDY1MjQ=
