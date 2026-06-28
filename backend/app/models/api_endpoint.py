"""
API 端点定义模型

用于存储从 OpenAPI/Swagger 文档解析出的 API 端点信息
支持按文件夹组织，每个端点可关联测试用例和测试脚本
"""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWxkWWJ3PT06ZDQzNTc1NmM=

class APIEndpoint(Base, UUIDMixin, TimestampMixin):
    """
    API 端点定义表

    存储从 OpenAPI/Swagger 文档解析出的单个 API 端点信息
    支持与文件夹、测试用例、测试脚本的多重关联
    """
    __tablename__ = "api_endpoints"
    __table_args__ = {"comment": "API 端点定义表"}

    # ========== 基本信息 ==========
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID"
    )

    folder_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="所属文件夹 ID (可选，用于组织端点结构)"
    )

    # ========== API 端点标识 ==========
    # 用于显示为文件夹名称，如 "GET /api/v1/Activities"
    display_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="显示名称：方法 + 路径，如 'GET /api/v1/Activities'"
    )

    # ========== API 详细信息 ==========
    path: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        index=True,
        comment="API 路径，如 /api/v1/Activities"
    )

    method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="HTTP 方法: GET, POST, PUT, DELETE, PATCH, etc."
    )
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWxkWWJ3PT06ZDQzNTc1NmM=

    summary: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="端点摘要（简短描述）"
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="端点详细描述"
    )

    # ========== OpenAPI Schema 引用 ==========
    schema_file_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attachments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联的 OpenAPI Schema 文件 ID"
    )

    # ========== 端点配置 (JSONB 存储) ==========
    parameters: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="参数定义 [{name, in, required, schema, description}]"
    )

    request_body: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="请求体定义 {content_type, schema, required}"
    )

    responses: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="响应定义 {200: {schema, description}, 400: {...}}"
    )

    security: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="安全配置 [{type, scheme, scopes}]"
    )

    tags: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="标签列表 [tag1, tag2, ...]"
    )

    # ========== 分组信息 ==========
    # 用于将同一模块的端点组织在一起
    # 例如：所有 /api/v1/Activities/* 的端点都属于 "Activities" 组
    tag_group: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        index=True,
        comment="标签分组（如 'Activities', 'Users'），用于组织端点"
    )

    # ========== 关联信息 ==========
    # 关联的测试用例（一个端点可以对应多个测试用例）
    test_case_ids: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="关联的测试用例 ID 列表"
    )
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWxkWWJ3PT06ZDQzNTc1NmM=

    # 关联的 API 测试脚本
    api_test_ids: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="关联的 API 测试脚本 ID 列表"
    )

    # ========== 扩展配置 ==========
    custom_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="自定义配置 {deprecated, servers, extensions}"
    )

    # ========== 统计信息 ==========
    total_test_cases: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="关联的测试用例总数"
    )

    total_test_runs: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="测试运行总次数"
    )

    last_run_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="最后一次测试运行状态"
    )

    # ========== 排序信息 ==========
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="排序顺序"
    )

    # ========== 关系 ==========
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="api_endpoints"
    )
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VWxkWWJ3PT06ZDQzNTc1NmM=

    folder: Mapped["Folder | None"] = relationship(
        "Folder",
        back_populates="api_endpoints"
    )

    schema_file: Mapped["Attachment | None"] = relationship(
        "Attachment",
        foreign_keys=[schema_file_id]
    )
