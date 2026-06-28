"""
测试计划模型

定义测试计划的表结构
参考: https://www.browserstack.com/docs/test-management/api-reference/test-plans
"""

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.schemas.enums import TestPlanStatus, TestPlanActiveState
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VlZKMU1RPT06MjIxOTZiNWU=


class TestPlan(Base, UUIDMixin, TimestampMixin):
    """
    测试计划表

    存储测试计划的基本信息，用于组织和跟踪多个测试运行
    """
    __tablename__ = "test_plans"
    __table_args__ = {"comment": "测试计划表"}

    # 所属项目
    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID"
    )

    # 父测试计划（自引用，支持 sub_test_plan，identifier 形如 STP-x）
    parent_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="父测试计划 ID，根计划为空"
    )
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VlZKMU1RPT06MjIxOTZiNWU=

    # 标识符
    identifier: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="测试计划标识符，如 TP-123"
    )
    
    # 基本信息
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="测试计划名称"
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="测试计划描述"
    )
    
    # 状态
    plan_status: Mapped[TestPlanStatus] = mapped_column(
        SQLEnum(TestPlanStatus),
        default=TestPlanStatus.DRAFT,
        nullable=False,
        comment="计划状态"
    )
    active_state: Mapped[TestPlanActiveState] = mapped_column(
        SQLEnum(TestPlanActiveState),
        default=TestPlanActiveState.ACTIVE,
        nullable=False,
        comment="活跃状态"
    )
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VlZKMU1RPT06MjIxOTZiNWU=
    
    # 时间范围
    start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="开始日期"
    )
    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="结束日期"
    )
    
    # 负责人
    owner: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="负责人邮箱"
    )
    
    # 统计信息
    test_runs_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="关联的测试运行数量"
    )
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VlZKMU1RPT06MjIxOTZiNWU=
    
    # 标签和自定义字段
    tags: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="标签列表"
    )
    custom_fields: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="自定义字段"
    )

    # 关系
    project: Mapped["Project"] = relationship("Project", back_populates="test_plans")
    test_runs: Mapped[list["TestRun"]] = relationship(
        "TestRun",
        back_populates="test_plan",
        foreign_keys="TestRun.test_plan_id"
    )
    parent: Mapped["TestPlan | None"] = relationship(
        "TestPlan",
        remote_side="TestPlan.id",
        back_populates="children",
    )
    children: Mapped[list["TestPlan"]] = relationship(
        "TestPlan",
        back_populates="parent",
        cascade="all",
    )

    def __repr__(self) -> str:
        return f"<TestPlan(id={self.id}, identifier={self.identifier}, name={self.name})>"

