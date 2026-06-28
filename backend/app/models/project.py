"""
项目模型

定义项目表结构
"""

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUVsRVFnPT06MTgwZWNlZmE=

from app.models.base import Base, TimestampMixin, UUIDMixin

# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUVsRVFnPT06MTgwZWNlZmE=

class Project(Base, UUIDMixin, TimestampMixin):
    """
    项目表
    
    存储测试项目信息
    """
    __tablename__ = "projects"
    __table_args__ = {"comment": "项目表"}
    
    identifier: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="项目标识符，如 PR-1234"
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="项目名称"
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="项目描述"
    )
    created_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        comment="创建者 ID"
    )
    
    # 关系
    creator: Mapped["User"] = relationship(
        "User",
        back_populates="created_projects",
        foreign_keys=[created_by]
    )
    teams: Mapped[list["Team"]] = relationship(
        "Team",
        secondary="project_teams",
        back_populates="projects"
    )
    folders: Mapped[list["Folder"]] = relationship(
        "Folder",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    test_cases: Mapped[list["TestCase"]] = relationship(
        "TestCase",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    test_runs: Mapped[list["TestRun"]] = relationship(
        "TestRun",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    test_plans: Mapped[list["TestPlan"]] = relationship(
        "TestPlan",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    api_tests: Mapped[list["APITest"]] = relationship(
        "APITest",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    api_endpoints: Mapped[list["APIEndpoint"]] = relationship(
        "APIEndpoint",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    web_tests: Mapped[list["WebTest"]] = relationship(
        "WebTest",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    android_tests: Mapped[list["AndroidTest"]] = relationship(
        "AndroidTest",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    web_functions: Mapped[list["WebFunction"]] = relationship(
        "WebFunction",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    web_sub_functions: Mapped[list["WebSubFunction"]] = relationship(
        "WebSubFunction",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    pentests: Mapped[list["Pentest"]] = relationship(
        "Pentest",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    pentest_reports: Mapped[list["PentestReport"]] = relationship(
        "PentestReport",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    pentest_vulnerabilities: Mapped[list["PentestVulnerability"]] = relationship(
        "PentestVulnerability",
        back_populates="project",
        cascade="all, delete-orphan"
    )
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUVsRVFnPT06MTgwZWNlZmE=

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, identifier={self.identifier}, name={self.name})>"
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUVsRVFnPT06MTgwZWNlZmE=

