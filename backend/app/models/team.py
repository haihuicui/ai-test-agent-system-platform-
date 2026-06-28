"""
团队模型

定义团队和项目团队关联表结构
"""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
# noqa  MC8zOmFIVnBZMlhsdEpUbXRiZm92b2s2VHpGRlRBPT06ZTJkMTA3NmI=

from app.models.base import Base, TimestampMixin


class Team(Base, TimestampMixin):
    """
    团队表
    
    存储团队信息
    """
    __tablename__ = "teams"
    __table_args__ = {"comment": "团队表"}
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="团队 ID"
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="团队名称"
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="团队描述"
    )
# type: ignore  MS8zOmFIVnBZMlhsdEpUbXRiZm92b2s2VHpGRlRBPT06ZTJkMTA3NmI=
    
    # 关系
    projects: Mapped[list["Project"]] = relationship(
        "Project",
        secondary="project_teams",
        back_populates="teams"
    )
    
    def __repr__(self) -> str:
        return f"<Team(id={self.id}, name={self.name})>"

# pylint: disable  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b2s2VHpGRlRBPT06ZTJkMTA3NmI=

class ProjectTeam(Base):
    """
    项目团队关联表
    
    多对多关系的中间表
    """
    __tablename__ = "project_teams"
    __table_args__ = {"comment": "项目团队关联表"}
    
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
        comment="项目 ID"
    )
    team_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
        comment="团队 ID"
    )

