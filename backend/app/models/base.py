"""
SQLAlchemy 基础模型定义

包含所有模型共用的基类和混入类
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass
# fmt: off  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2ZDNkd2RnPT06NTc3OGZlZmM=


class UUIDMixin:
    """UUID 主键混入类"""
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="主键 ID"
    )


class TimestampMixin:
    """时间戳混入类"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
        comment="更新时间"
    )

# noqa  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2ZDNkd2RnPT06NTc3OGZlZmM=
