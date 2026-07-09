"""
项目环境配置模型

用于管理每个项目的多环境配置（dev/test/prod 等），
包括 base_url、认证方式、凭据等。
"""

from enum import Enum as PyEnum

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class AuthType(str, PyEnum):
    """认证类型"""
    NONE = "none"
    BEARER = "bearer"
    DYNAMIC_BEARER = "dynamic_bearer"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"


class ProjectEnvironment(Base, UUIDMixin, TimestampMixin):
    """
    项目环境配置表

    存储项目的多环境配置，支持开发、测试、预发、生产等环境。
    按业务要求，认证凭据（auth_secret）明文存储。
    """
    __tablename__ = "project_environments"
    __table_args__ = {"comment": "项目环境配置表"}

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="项目 ID"
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="环境名称，如 dev/test/prod"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否为项目默认环境"
    )
    base_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="API Base URL"
    )
    auth_type: Mapped[AuthType] = mapped_column(
        String(20),
        default=AuthType.NONE.value,
        nullable=False,
        comment="认证类型"
    )
    # token / api_key / access_token / api_key 等认证凭据，按用户要求明文存储
    auth_secret: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="认证凭据（明文存储，如 bearer token、api_key、access_token、client_secret）"
    )
    auth_config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="非敏感认证配置，如 OAuth2 client_id、api_key 字段名、动态 token 接口配置"
    )
    timeout_ms: Mapped[int] = mapped_column(
        Integer,
        default=30000,
        nullable=False,
        comment="默认请求超时（毫秒）"
    )

    project: Mapped["Project"] = relationship("Project", back_populates="environments")

    def __repr__(self) -> str:
        return f"<ProjectEnvironment(id={self.id}, project_id={self.project_id}, name={self.name}, is_default={self.is_default})>"
