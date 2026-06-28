"""
测试用例模型

定义测试用例、测试步骤、标签等表结构
"""

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.schemas.enums import Priority, TestCaseState, TestCaseType, TestCaseTemplate, AutomationStatus


class TestCase(Base, UUIDMixin, TimestampMixin):
    """
    测试用例表

    存储测试用例信息，支持普通测试用例和 BDD 测试用例
    """
    __tablename__ = "test_cases"
    __table_args__ = {"comment": "测试用例表"}

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID"
    )
    folder_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="所属文件夹 ID"
    )
    identifier: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="测试用例标识符，如 TC-1234"
    )
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="测试用例名称"
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="测试用例描述"
    )
    preconditions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="前置条件"
    )
    priority: Mapped[Priority] = mapped_column(
        SQLEnum(Priority),
        default=Priority.MEDIUM,
        nullable=False,
        index=True,
        comment="优先级"
    )
    state: Mapped[TestCaseState] = mapped_column(
        SQLEnum(TestCaseState, values_callable=lambda x: [e.value for e in x]),
        default=TestCaseState.NEW,
        nullable=False,
        index=True,
        comment="状态"
    )
    test_case_type: Mapped[TestCaseType] = mapped_column(
        SQLEnum(TestCaseType),
        default=TestCaseType.FUNCTIONAL,
        nullable=False,
        index=True,
        comment="测试类型"
    )
    # BDD 测试用例模板字段
    template: Mapped[TestCaseTemplate] = mapped_column(
        SQLEnum(TestCaseTemplate),
        default=TestCaseTemplate.TEST_CASE,
        nullable=False,
        comment="测试用例模板类型"
    )
    feature: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="BDD Feature 描述"
    )
    scenario: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="BDD Scenario 描述"
    )
    background: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="BDD Background 描述"
    )
    # 自动化状态
    automation_status: Mapped[AutomationStatus] = mapped_column(
        SQLEnum(AutomationStatus),
        default=AutomationStatus.NOT_AUTOMATED,
        nullable=False,
        comment="自动化状态"
    )
    # 自定义字段（JSONB 存储）
    custom_fields: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="自定义字段"
    )
    # 关联的 Jira issues
    issues: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="关联的 Jira issues"
    )
    owner_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="负责人 ID"
    )
    created_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        comment="创建者 ID"
    )
    last_updated_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="最后更新者 ID"
    )
    dataset: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="数据驱动用例的数据集 [{variable, row}, ...]"
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="版本号"
    )
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WWtrMFJ3PT06N2QxNGQxZjI=
    
    # 关系
    project: Mapped["Project"] = relationship("Project", back_populates="test_cases")
    folder: Mapped["Folder | None"] = relationship("Folder", back_populates="test_cases")
    owner: Mapped["User | None"] = relationship(
        "User", back_populates="owned_test_cases", foreign_keys=[owner_id]
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    last_updater: Mapped["User | None"] = relationship(
        "User", foreign_keys=[last_updated_by]
    )
    steps: Mapped[list["TestStep"]] = relationship(
        "TestStep", back_populates="test_case", cascade="all, delete-orphan",
        order_by="TestStep.step_number"
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", secondary="test_case_tags", back_populates="test_cases"
    )
    test_run_cases: Mapped[list["TestRunTestCase"]] = relationship(
        "TestRunTestCase",
        back_populates="test_case",
        cascade="all, delete-orphan"
    )
    api_tests: Mapped[list["APITest"]] = relationship(
        "APITest",
        back_populates="test_case",
        cascade="all, delete-orphan"
    )
    web_tests: Mapped[list["WebTest"]] = relationship(
        "WebTest",
        back_populates="test_case",
        cascade="all, delete-orphan"
    )
    android_tests: Mapped[list["AndroidTest"]] = relationship(
        "AndroidTest",
        back_populates="test_case",
        cascade="all, delete-orphan"
    )
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WWtrMFJ3PT06N2QxNGQxZjI=

    def __repr__(self) -> str:
        return f"<TestCase(id={self.id}, identifier={self.identifier}, name={self.name})>"


class TestStep(Base, UUIDMixin):
    """
    测试步骤表

    存储测试用例的执行步骤
    """
    __tablename__ = "test_steps"
    __table_args__ = {"comment": "测试步骤表"}

    test_case_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属测试用例 ID"
    )
    step_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="步骤序号"
    )
    action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="操作步骤描述"
    )
    expected_result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="预期结果"
    )

    # 关系
    test_case: Mapped["TestCase"] = relationship(
        "TestCase",
        back_populates="steps"
    )

    def __repr__(self) -> str:
        return f"<TestStep(id={self.id}, step_number={self.step_number})>"
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WWtrMFJ3PT06N2QxNGQxZjI=


class Tag(Base, UUIDMixin, TimestampMixin):
    """
    标签表

    存储项目级别的标签
    """
    __tablename__ = "tags"
    __table_args__ = {"comment": "标签表"}

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID"
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="标签名称"
    )

    # 关系
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="tags"
    )
    test_cases: Mapped[list["TestCase"]] = relationship(
        "TestCase",
        secondary="test_case_tags",
        back_populates="tags"
    )

    def __repr__(self) -> str:
        return f"<Tag(id={self.id}, name={self.name})>"


class TestCaseTag(Base):
    """
    测试用例标签关联表

    多对多关系的中间表
    """
    __tablename__ = "test_case_tags"
    __table_args__ = {"comment": "测试用例标签关联表"}
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WWtrMFJ3PT06N2QxNGQxZjI=

    test_case_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        primary_key=True,
        comment="测试用例 ID"
    )
    tag_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
        comment="标签 ID"
    )

