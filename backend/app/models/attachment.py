"""
附件模型

定义附件的表结构
参考: https://www.browserstack.com/docs/test-management/api-reference/attachments
"""

from enum import Enum as PyEnum
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzJ0WGVnPT06ZjlmMTBlMTA=

from sqlalchemy import ForeignKey, Integer, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class AttachmentEntityType(str, PyEnum):
    """附件关联的实体类型"""
    TEST_CASE = "test_case"
    TEST_CASE_STEP = "test_case_step"
    TEST_RESULT = "test_result"
    TEST_STEP_RESULT = "test_step_result"
    API_ENDPOINT = "api_endpoint"
    API_TEST_PLAN = "api_test_plan"
    API_TEST_CASE = "api_test_case"
    API_TEST_SCRIPT = "api_test_script"
    API_TEST_REPORT = "api_test_report"
    # Web 测试相关实体类型
    WEB_PAGE = "web_page"
    WEB_TEST_PLAN = "web_test_plan"
    WEB_TEST_CASE = "web_test_case"
    WEB_TEST_SCRIPT = "web_test_script"
    WEB_TEST_REPORT = "web_test_report"
    STORAGE_STATE = "storage_state"  # Playwright 全局登录态文件
    STORAGE_STATE_JOB = "storage_state_job"  # 登录态生成任务产物（失败截图等）
    # Android 测试相关实体类型
    ANDROID_TEST_PLAN = "android_test_plan"
    ANDROID_TEST_CASE = "android_test_case"
    ANDROID_TEST_SCRIPT = "android_test_script"
    ANDROID_TEST_REPORT = "android_test_report"
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzJ0WGVnPT06ZjlmMTBlMTA=


class Attachment(Base, UUIDMixin, TimestampMixin):
    """
    附件表

    存储上传的附件元数据，实际文件存储在 MinIO
    """
    __tablename__ = "attachments"
    __table_args__ = {"comment": "附件表"}

    # 关联实体类型和 ID
    entity_type: Mapped[AttachmentEntityType] = mapped_column(
        SQLEnum(AttachmentEntityType),
        nullable=False,
        index=True,
        comment="关联实体类型"
    )
    entity_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="关联实体 ID"
    )
    
    # 项目关联（用于权限控制）
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目 ID"
    )
    
    # 文件信息
    file_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="原始文件名"
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="文件大小（字节）"
    )
    content_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="MIME 类型"
    )
    
    # MinIO 存储信息
    object_name: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        unique=True,
        comment="MinIO 对象名称"
    )
    
    # 额外信息
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="附件描述"
    )
    created_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="上传人邮箱"
    )
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzJ0WGVnPT06ZjlmMTBlMTA=
    
    # 步骤相关（当 entity_type 为 test_case_step 或 test_step_result 时）
    step_index: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="步骤索引（从 1 开始）"
    )

    # 关系
    project: Mapped["Project"] = relationship(
        "Project",
        backref="attachments",
        passive_deletes=True
    )
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzJ0WGVnPT06ZjlmMTBlMTA=

    def __repr__(self) -> str:
        return f"<Attachment(id={self.id}, file_name={self.file_name})>"

