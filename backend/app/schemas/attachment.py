"""
附件相关的 Pydantic 模型

基于 BrowserStack Test Management API 的附件接口设计
参考: https://www.browserstack.com/docs/test-management/api-reference/attachments
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.attachment import AttachmentEntityType


class AttachmentUploadResponse(BaseModel):
    """
    附件上传响应

    用于返回上传成功后的附件信息
    符合 BrowserStack API 格式:
    - id: 附件 ID
    - name: 文件名
    - size: 文件大小
    - created_at: 创建时间
    - url: 下载 URL
    """
    id: UUID = Field(..., description="附件 ID")
    name: str = Field(..., description="原始文件名")
    size: int = Field(..., description="文件大小（字节）")
    content_type: Optional[str] = Field(default=None, description="MIME 类型")
    created_by: Optional[str] = Field(default=None, description="上传人邮箱")
    created_at: datetime = Field(..., description="上传时间")
    url: Optional[str] = Field(default=None, description="下载 URL")
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TldOdFJ3PT06ODk0ZjNlYWQ=


class AttachmentInfo(BaseModel):
    """
    附件信息模型

    用于返回附件详细信息
    符合 BrowserStack API 格式，同时保留内部扩展字段
    """
    id: UUID = Field(..., description="附件 ID")
    entity_type: AttachmentEntityType = Field(..., description="关联实体类型")
    entity_id: UUID = Field(..., description="关联实体 ID")
    name: str = Field(..., description="原始文件名")
    size: int = Field(..., description="文件大小（字节）")
    content_type: Optional[str] = Field(default=None, description="MIME 类型")
    description: Optional[str] = Field(default=None, description="附件描述")
    step_index: Optional[int] = Field(default=None, description="步骤索引")
    created_by: Optional[str] = Field(default=None, description="上传人邮箱")
    created_at: datetime = Field(..., description="上传时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")
    url: Optional[str] = Field(default=None, description="下载 URL")


class AttachmentListInfo(BaseModel):
    """
    附件列表项模型

    用于列表返回的简化信息
    符合 BrowserStack API 格式:
    - id: 附件 ID
    - name: 文件名
    - size: 文件大小
    - created_at: 创建时间
    - url: 下载 URL
    """
    id: UUID = Field(..., description="附件 ID")
    name: str = Field(..., description="原始文件名")
    size: int = Field(..., description="文件大小（字节）")
    content_type: Optional[str] = Field(default=None, description="MIME 类型")
    step_index: Optional[int] = Field(default=None, description="步骤索引")
    created_by: Optional[str] = Field(default=None, description="上传人邮箱")
    created_at: datetime = Field(..., description="上传时间")
    url: Optional[str] = Field(default=None, description="下载 URL")


class AttachmentDownloadResponse(BaseModel):
    """
    附件下载响应

    返回预签名 URL 用于下载
    """
    id: UUID = Field(..., description="附件 ID")
    name: str = Field(..., description="原始文件名")
    download_url: str = Field(..., description="预签名下载 URL")
    expires_in: int = Field(default=3600, description="URL 过期时间（秒）")


class AttachmentBulkDeleteRequest(BaseModel):
    """
    批量删除附件请求
    """
    attachment_ids: list[UUID] = Field(..., description="要删除的附件 ID 列表")
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TldOdFJ3PT06ODk0ZjNlYWQ=


class TestCaseAttachmentsResponse(BaseModel):
    """
    测试用例附件响应 (符合 BrowserStack API 格式)
    """
    test_case_id: str = Field(..., description="测试用例标识符")
    attachments: list[AttachmentListInfo] = Field(default=[], description="附件列表")


class StepAttachment(BaseModel):
    """步骤附件信息"""
    step_index: int = Field(..., description="步骤索引")
    attachments: list[AttachmentListInfo] = Field(default=[], description="该步骤的附件列表")
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TldOdFJ3PT06ODk0ZjNlYWQ=


class TestCaseStepAttachmentsResponse(BaseModel):
    """
    测试用例步骤附件响应 (符合 BrowserStack API 格式)
    """
    test_case_id: str = Field(..., description="测试用例标识符")
    step_attachments: list[StepAttachment] = Field(default=[], description="步骤附件列表")

# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TldOdFJ3PT06ODk0ZjNlYWQ=

class TestResultAttachmentsResponse(BaseModel):
    """
    测试结果附件响应 (符合 BrowserStack API 格式)
    """
    test_result_id: UUID = Field(..., description="测试结果 ID")
    test_case_id: str = Field(..., description="测试用例标识符")
    attachments: list[AttachmentListInfo] = Field(default=[], description="附件列表")


class TestResultStepAttachment(BaseModel):
    """测试结果步骤附件信息"""
    step_index: int = Field(..., description="步骤索引")
    attachments: list[AttachmentListInfo] = Field(default=[], description="该步骤的附件列表")


class TestResultStepAttachmentsResponse(BaseModel):
    """
    测试结果步骤附件响应 (符合 BrowserStack API 格式)
    """
    test_result_id: UUID = Field(..., description="测试结果 ID")
    test_case_id: str = Field(..., description="测试用例标识符")
    step_attachments: list[TestResultStepAttachment] = Field(default=[], description="步骤附件列表")

