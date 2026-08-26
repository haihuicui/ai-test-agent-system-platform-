"""
OpenAPI 原始文档快照模型

每次导入 OpenAPI 文档时留存完整 spec 原文（JSONB），解决
「端点只存解析片段、完整 spec 未持久化」的根因问题：

- 审计：可追溯端点定义来源于哪一版文档
- 重解析：resolver/推断规则升级后可基于原文重新解析，无需用户重新上传
- 排障：$ref 解引用结果异常时可对照原文
"""

from uuid import UUID

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class OpenAPISpecSnapshot(Base, UUIDMixin, TimestampMixin):
    """OpenAPI 原始文档快照（每次导入追加一条）"""

    __tablename__ = "openapi_spec_snapshots"
    __table_args__ = {"comment": "OpenAPI 原始文档快照：每次导入留存完整 spec 原文"}

    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID",
    )
    title: Mapped[str] = mapped_column(
        String(500), nullable=False, default="", comment="文档标题（info.title）"
    )
    version: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", comment="文档版本（info.version）"
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="upload", comment="来源：upload / url"
    )
    endpoint_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="该版本解析出的端点数"
    )
    spec: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment="完整 OpenAPI 文档原文"
    )
