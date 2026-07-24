"""
Web 登录态生成任务模型

记录 Playwright storageState.json 的生成过程与结果。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class StorageStateJob(Base, UUIDMixin, TimestampMixin):
    """
    Web 登录态生成任务表

    跟踪一次 storageState.json 生成任务的执行状态、产物路径与错误信息。
    """

    __tablename__ = "storage_state_jobs"
    __table_args__ = {"comment": "Web 登录态生成任务"}

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID",
    )

    environment_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_environments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="使用的项目环境配置 ID",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
        comment="任务状态: pending/running/completed/failed",
    )

    output_path: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="生成的 storageState.json 本地路径",
    )

    attachment_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attachments.id", ondelete="SET NULL"),
        nullable=True,
        comment="归档到 MinIO 的附件 ID",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息",
    )

    stdout: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Playwright 标准输出",
    )

    stderr: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Playwright 标准错误",
    )

    failure_screenshot_attachment_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attachments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="失败时页面截图附件 ID",
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="storageState 中最早过期时间",
    )

    is_valid: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="最近一次静态校验结果：True 有效 / False 过期或损坏",
    )

    validation_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="校验结果说明",
    )

    probe_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="运行时探针状态（预留）：pending/success/failed/skipped",
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="开始执行时间",
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="执行完成时间",
    )
