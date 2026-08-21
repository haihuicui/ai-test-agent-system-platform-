"""
API 业务语义标注模型

存储从 trace、探测、文档、RAG 或人工录入中沉淀的业务语义：
- 业务成功/错误码
- 字段级校验规则
- 枚举含义
- 接口依赖与状态约束
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class APIAnnotation(Base, UUIDMixin, TimestampMixin):
    """API 业务语义标注"""

    __tablename__ = "api_annotations"
    __table_args__ = (
        Index("ix_api_annotations_project_id_endpoint_id", "project_id", "endpoint_id"),
        Index("ix_api_annotations_endpoint_id_type", "endpoint_id", "annotation_type"),
        Index("ix_api_annotations_business_code", "business_code"),
        Index("ix_api_annotations_field_path", "field_path"),
        Index("ix_api_annotations_last_seen_at", "last_seen_at"),
        UniqueConstraint(
            "endpoint_id",
            "annotation_type",
            "http_status",
            "business_code",
            "field_path",
            "condition",
            name="uq_api_annotations_natural_key",
            deferrable=True,
            initially="DEFERRED",
        ),
        {"comment": "API 业务语义标注库：错误码、字段约束、枚举含义、依赖关系等"},
    )

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID",
    )
    endpoint_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("api_endpoints.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="关联 API 端点 ID（可为空，表示项目级或按 path+method 兜底）",
    )

    annotation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="标注类型：business_success_code / business_error_code / field_validation / enum_meaning / dependency / state_constraint",
    )
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="来源：trace / openapi / probe / rag / manual",
    )

    http_status: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="触发该标注的 HTTP 状态码",
    )
    business_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="业务状态码，如 4009、2000",
    )
    field_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        index=True,
        comment="字段路径，如 body.email、query.page",
    )
    condition: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="约束条件，如 required_missing、invalid_enum、type_error、out_of_range",
    )
    message_pattern: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误提示样例或子串，用于断言",
    )
    expected_value: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="期望取值（成功码、合法枚举值等）",
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        comment="置信度 0-1，manual=1.0",
    )
    hit_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="命中次数",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否生效",
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="首次发现时间",
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="最近一次命中时间",
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最近一次主动验证时间（探测时更新）",
    )

    source_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="来源元数据：trace_id / run_id / scenario_id / 探测参数等",
    )
