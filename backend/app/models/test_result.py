"""
测试结果模型

定义测试结果及其步骤结果的表结构
参考: https://www.browserstack.com/docs/test-management/api-reference/test-results
"""

from sqlalchemy import ForeignKey, Integer, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.schemas.enums import TestResultStatus

# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZWtKeVNBPT06M2I2ZWE0ODg=

class TestResult(Base, UUIDMixin, TimestampMixin):
    """
    测试结果表

    存储测试用例在测试运行中的执行结果
    """
    __tablename__ = "test_results"
    __table_args__ = {"comment": "测试结果表"}
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZWtKeVNBPT06M2I2ZWE0ODg=

    test_run_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="测试运行 ID"
    )
    test_case_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="测试用例 ID"
    )
    test_run_test_case_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_run_test_cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="测试运行测试用例关联 ID"
    )
    configuration_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="配置 ID"
    )
    status: Mapped[TestResultStatus] = mapped_column(
        SQLEnum(TestResultStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="测试结果状态"
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="测试结果描述/备注"
    )
    created_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="创建人邮箱"
    )
    assignee: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="执行人邮箱"
    )
    issues: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="关联的问题列表"
    )
    issue_tracker: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="问题跟踪器配置 {name, host}"
    )
    custom_fields: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="自定义字段"
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="执行时长(毫秒)"
    )

    # 关系
    test_run: Mapped["TestRun"] = relationship(
        "TestRun",
        backref="test_results"
    )
    test_case: Mapped["TestCase"] = relationship(
        "TestCase",
        backref="test_results"
    )
    step_results: Mapped[list["TestStepResult"]] = relationship(
        "TestStepResult",
        back_populates="test_result",
        cascade="all, delete-orphan",
        order_by="TestStepResult.step_index"
    )

    def __repr__(self) -> str:
        return f"<TestResult(id={self.id}, status={self.status})>"

# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZWtKeVNBPT06M2I2ZWE0ODg=

class TestStepResult(Base, UUIDMixin, TimestampMixin):
    """
    测试步骤结果表

    存储测试用例中每个步骤的执行结果
    """
    __tablename__ = "test_step_results"
    __table_args__ = {"comment": "测试步骤结果表"}

    test_result_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="测试结果 ID"
    )
    step_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="步骤 ID (永久标识符)"
    )
    step_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="步骤索引 (从 1 开始)"
    )
    status: Mapped[TestResultStatus] = mapped_column(
        SQLEnum(TestResultStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="步骤执行状态"
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="步骤结果描述/备注"
    )
    issues: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="关联的问题列表"
    )

    # 关系
    test_result: Mapped["TestResult"] = relationship(
        "TestResult",
        back_populates="step_results"
    )
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZWtKeVNBPT06M2I2ZWE0ODg=

    def __repr__(self) -> str:
        return f"<TestStepResult(id={self.id}, step_index={self.step_index}, status={self.status})>"

