"""
附件服务

处理附件相关的业务逻辑，集成 MinIO 存储
参考: https://www.browserstack.com/docs/test-management/api-reference/attachments
"""

import uuid
from typing import Optional, BinaryIO
from datetime import timedelta

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment, AttachmentEntityType
from app.repositories.attachment_repo import AttachmentRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.test_case_repo import TestCaseRepository
from app.repositories.test_result_repo import TestResultRepository
from app.config.minio_client import MinIOClient
from app.config.settings import settings
from app.schemas.attachment import (
    AttachmentUploadResponse,
    AttachmentInfo,
    AttachmentListInfo,
    AttachmentDownloadResponse,
    TestCaseAttachmentsResponse,
    TestCaseStepAttachmentsResponse,
    StepAttachment,
    TestResultAttachmentsResponse,
    TestResultStepAttachmentsResponse,
    TestResultStepAttachment,
)
from app.utils.exceptions import NotFoundException, BadRequestException


class AttachmentService:
    """附件服务类"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AttachmentRepository(session)
        self.project_repo = ProjectRepository(session)
        self.tc_repo = TestCaseRepository(session)
        self.result_repo = TestResultRepository(session)
    
    async def _get_project_by_identifier(self, project_identifier: str):
        """根据标识符获取项目"""
        project = await self.project_repo.get_by_identifier(project_identifier)
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=project_identifier)
        return project
    
    async def _get_test_case(self, project_id, test_case_identifier: str):
        """获取测试用例"""
        test_case = await self.tc_repo.get_by_identifier(test_case_identifier)
        if not test_case or test_case.project_id != project_id:
            raise NotFoundException(resource_type="测试用例", resource_id=test_case_identifier)
        return test_case
    
    def _validate_file(self, file: UploadFile) -> None:
        """验证上传文件"""
        if file.size and file.size > settings.attachment_max_size:
            raise BadRequestException(
                f"文件大小超过限制，最大允许 {settings.attachment_max_size // 1024 // 1024} MB"
            )
        
        if file.content_type and file.content_type not in settings.attachment_allowed_types:
            raise BadRequestException(f"不支持的文件类型: {file.content_type}")
    
    def _generate_object_name(
        self,
        project_id: str,
        entity_type: AttachmentEntityType,
        entity_id: str,
        file_name: str,
    ) -> str:
        """生成 MinIO 对象名称"""
        unique_id = str(uuid.uuid4())[:8]
        return f"{project_id}/{entity_type.value}/{entity_id}/{unique_id}_{file_name}"
    
    def _to_list_info(self, attachment: Attachment) -> AttachmentListInfo:
        """转换为列表信息（符合 BrowserStack API 格式）"""
        # 生成预签名下载 URL
        try:
            url = MinIOClient.get_presigned_url(
                object_name=attachment.object_name,
                expires=timedelta(hours=1),
            )
        except Exception:
            url = None
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y1hORWJBPT06MTUwMjJhYzg=

        return AttachmentListInfo(
            id=attachment.id,
            name=attachment.file_name,
            size=attachment.file_size,
            content_type=attachment.content_type,
            step_index=attachment.step_index,
            created_by=attachment.created_by,
            created_at=attachment.created_at,
            url=url,
        )
    
    def _to_info(self, attachment: Attachment) -> AttachmentInfo:
        """转换为详细信息（符合 BrowserStack API 格式）"""
        # 生成预签名下载 URL
        try:
            url = MinIOClient.get_presigned_url(
                object_name=attachment.object_name,
                expires=timedelta(hours=1),
            )
        except Exception:
            url = None

        return AttachmentInfo(
            id=attachment.id,
            entity_type=attachment.entity_type,
            entity_id=attachment.entity_id,
            name=attachment.file_name,
            size=attachment.file_size,
            content_type=attachment.content_type,
            description=attachment.description,
            step_index=attachment.step_index,
            created_by=attachment.created_by,
            created_at=attachment.created_at,
            updated_at=attachment.updated_at,
            url=url,
        )
    
    async def upload_test_case_attachment(
        self,
        project_identifier: str,
        test_case_identifier: str,
        file: UploadFile,
        created_by: Optional[str] = None,
    ) -> AttachmentUploadResponse:
        """上传测试用例附件"""
        self._validate_file(file)
        
        project = await self._get_project_by_identifier(project_identifier)
        test_case = await self._get_test_case(project.id, test_case_identifier)
        
        # 生成对象名并上传到 MinIO
        object_name = self._generate_object_name(
            str(project.id),
            AttachmentEntityType.TEST_CASE,
            str(test_case.id),
            file.filename or "unnamed",
        )
        
        content = await file.read()
        MinIOClient.upload_bytes(
            object_name=object_name,
            data=content,
            content_type=file.content_type or "application/octet-stream",
        )
        
        # 创建附件记录
        attachment = Attachment(
            entity_type=AttachmentEntityType.TEST_CASE,
            entity_id=test_case.id,
            project_id=project.id,
            file_name=file.filename or "unnamed",
            file_size=len(content),
            content_type=file.content_type or "application/octet-stream",
            object_name=object_name,
            created_by=created_by,
        )
        attachment = await self.repo.create(attachment)
        
        # 生成预签名下载 URL
        try:
            url = MinIOClient.get_presigned_url(
                object_name=attachment.object_name,
                expires=timedelta(hours=1),
            )
        except Exception:
            url = None

        return AttachmentUploadResponse(
            id=attachment.id,
            name=attachment.file_name,
            size=attachment.file_size,
            content_type=attachment.content_type,
            created_by=attachment.created_by,
            created_at=attachment.created_at,
            url=url,
        )

    async def upload_test_result_attachment(
        self,
        project_identifier: str,
        test_result_id: str,
        file: UploadFile,
        created_by: Optional[str] = None,
    ) -> AttachmentUploadResponse:
        """上传测试结果附件"""
        from uuid import UUID as PyUUID

        self._validate_file(file)
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y1hORWJBPT06MTUwMjJhYzg=

        project = await self._get_project_by_identifier(project_identifier)

        # 获取测试结果
        try:
            result_uuid = PyUUID(test_result_id)
        except ValueError:
            raise BadRequestException(f"无效的测试结果 ID: {test_result_id}")

        test_result = await self.result_repo.get_by_id(result_uuid)
        if not test_result:
            raise NotFoundException(resource_type="测试结果", resource_id=test_result_id)

        # 生成对象名并上传到 MinIO
        object_name = self._generate_object_name(
            str(project.id),
            AttachmentEntityType.TEST_RESULT,
            str(test_result.id),
            file.filename or "unnamed",
        )

        content = await file.read()
        MinIOClient.upload_bytes(
            object_name=object_name,
            data=content,
            content_type=file.content_type or "application/octet-stream",
        )

        # 创建附件记录
        attachment = Attachment(
            entity_type=AttachmentEntityType.TEST_RESULT,
            entity_id=test_result.id,
            project_id=project.id,
            file_name=file.filename or "unnamed",
            file_size=len(content),
            content_type=file.content_type or "application/octet-stream",
            object_name=object_name,
            created_by=created_by,
        )
        attachment = await self.repo.create(attachment)

        # 生成预签名下载 URL
        try:
            url = MinIOClient.get_presigned_url(
                object_name=attachment.object_name,
                expires=timedelta(hours=1),
            )
        except Exception:
            url = None

        return AttachmentUploadResponse(
            id=attachment.id,
            name=attachment.file_name,
            size=attachment.file_size,
            content_type=attachment.content_type,
            created_by=attachment.created_by,
            created_at=attachment.created_at,
            url=url,
        )

    async def get_test_case_attachments(
        self,
        project_identifier: str,
        test_case_identifier: str,
    ) -> TestCaseAttachmentsResponse:
        """获取测试用例附件列表"""
        project = await self._get_project_by_identifier(project_identifier)
        test_case = await self._get_test_case(project.id, test_case_identifier)

        attachments = await self.repo.get_by_entity(
            AttachmentEntityType.TEST_CASE,
            test_case.id,
        )

        return TestCaseAttachmentsResponse(
            test_case_id=test_case.identifier,
            attachments=[self._to_list_info(a) for a in attachments],
        )

    async def get_test_result_attachments(
        self,
        project_identifier: str,
        test_result_id: str,
    ) -> TestResultAttachmentsResponse:
        """获取测试结果附件列表"""
        from uuid import UUID as PyUUID

        project = await self._get_project_by_identifier(project_identifier)

        try:
            result_uuid = PyUUID(test_result_id)
        except ValueError:
            raise BadRequestException(f"无效的测试结果 ID: {test_result_id}")

        test_result = await self.result_repo.get_by_id(result_uuid)
        if not test_result:
            raise NotFoundException(resource_type="测试结果", resource_id=test_result_id)

        attachments = await self.repo.get_by_entity(
            AttachmentEntityType.TEST_RESULT,
            test_result.id,
        )

        test_case = test_result.test_case

        return TestResultAttachmentsResponse(
            test_result_id=test_result.id,
            test_case_id=test_case.identifier if test_case else "",
            attachments=[self._to_list_info(a) for a in attachments],
        )

    async def get_attachment_download_url(
        self,
        project_identifier: str,
        attachment_id: str,
    ) -> AttachmentDownloadResponse:
        """获取附件下载 URL"""
        from uuid import UUID as PyUUID

        project = await self._get_project_by_identifier(project_identifier)
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y1hORWJBPT06MTUwMjJhYzg=

        try:
            att_uuid = PyUUID(attachment_id)
        except ValueError:
            raise BadRequestException(f"无效的附件 ID: {attachment_id}")

        attachment = await self.repo.get_by_id(att_uuid)
        if not attachment or attachment.project_id != project.id:
            raise NotFoundException(resource_type="附件", resource_id=attachment_id)

        # 生成预签名 URL
        download_url = MinIOClient.get_presigned_url(
            object_name=attachment.object_name,
            expires=timedelta(hours=1),
        )

        return AttachmentDownloadResponse(
            id=attachment.id,
            name=attachment.file_name,
            download_url=download_url,
            expires_in=3600,
        )

    async def delete_test_case_attachment(
        self,
        project_identifier: str,
        test_case_identifier: str,
        attachment_id: str,
    ) -> None:
        """删除测试用例附件"""
        from uuid import UUID as PyUUID

        project = await self._get_project_by_identifier(project_identifier)
        test_case = await self._get_test_case(project.id, test_case_identifier)

        try:
            att_uuid = PyUUID(attachment_id)
        except ValueError:
            raise BadRequestException(f"无效的附件 ID: {attachment_id}")

        attachment = await self.repo.get_by_id(att_uuid)
        if not attachment:
            raise NotFoundException(resource_type="附件", resource_id=attachment_id)

        # 验证附件属于该测试用例
        if (attachment.entity_type != AttachmentEntityType.TEST_CASE or
            attachment.entity_id != test_case.id):
            raise NotFoundException(resource_type="附件", resource_id=attachment_id)

        # 从 MinIO 删除文件
        try:
            MinIOClient.delete_file(attachment.object_name)
        except Exception:
            pass  # 忽略 MinIO 删除错误

        # 删除数据库记录
        await self.repo.delete(attachment)

    async def delete_test_result_attachment(
        self,
        project_identifier: str,
        test_result_id: str,
        attachment_id: str,
    ) -> None:
        """删除测试结果附件"""
        from uuid import UUID as PyUUID

        project = await self._get_project_by_identifier(project_identifier)
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y1hORWJBPT06MTUwMjJhYzg=

        try:
            result_uuid = PyUUID(test_result_id)
            att_uuid = PyUUID(attachment_id)
        except ValueError:
            raise BadRequestException("无效的 ID 格式")

        test_result = await self.result_repo.get_by_id(result_uuid)
        if not test_result:
            raise NotFoundException(resource_type="测试结果", resource_id=test_result_id)

        attachment = await self.repo.get_by_id(att_uuid)
        if not attachment:
            raise NotFoundException(resource_type="附件", resource_id=attachment_id)

        # 验证附件属于该测试结果
        if (attachment.entity_type != AttachmentEntityType.TEST_RESULT or
            attachment.entity_id != test_result.id):
            raise NotFoundException(resource_type="附件", resource_id=attachment_id)

        # 从 MinIO 删除文件
        try:
            MinIOClient.delete_file(attachment.object_name)
        except Exception:
            pass  # 忽略 MinIO 删除错误

        # 删除数据库记录
        await self.repo.delete(attachment)

    async def download_attachment(
        self,
        project_identifier: str,
        attachment_id: str,
    ) -> tuple[bytes, str, str]:
        """
        下载附件文件

        Returns:
            Tuple[bytes, str, str]: (文件内容, 文件名, 内容类型)
        """
        from uuid import UUID as PyUUID

        project = await self._get_project_by_identifier(project_identifier)

        try:
            att_uuid = PyUUID(attachment_id)
        except ValueError:
            raise BadRequestException(f"无效的附件 ID: {attachment_id}")

        attachment = await self.repo.get_by_id(att_uuid)
        if not attachment or attachment.project_id != project.id:
            raise NotFoundException(resource_type="附件", resource_id=attachment_id)

        # 从 MinIO 下载文件
        content = MinIOClient.download_file(attachment.object_name)

        return content, attachment.file_name, attachment.content_type

