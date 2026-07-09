"""
测试场景模型

支持多接口业务流场景测试
"""

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.project import Project


class TestScenario(Base):
    """测试场景主表"""

    __tablename__ = "test_scenarios"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    folder_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("folders.id", ondelete="SET NULL"))

    # 标识信息
    identifier: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVZWM1dBPT06MjEwZjE3ZTk=

    # 全局配置
    global_variables: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    setup_config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    teardown_config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # 执行配置
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)
    parallel_execution: Mapped[bool] = mapped_column(Boolean, default=False)

    # 状态
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)  # draft, active, archived

    # 统计
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    last_run_status: Mapped[Optional[str]] = mapped_column(String(50))
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))

    # 关系
    steps: Mapped[list["ScenarioStep"]] = relationship("ScenarioStep", back_populates="scenario", cascade="all, delete-orphan", order_by="ScenarioStep.step_order")
    variables: Mapped[list["ScenarioVariable"]] = relationship("ScenarioVariable", back_populates="scenario", cascade="all, delete-orphan")
    runs: Mapped[list["ScenarioRun"]] = relationship("ScenarioRun", back_populates="scenario", cascade="all, delete-orphan")


class ScenarioStep(Base):
    """场景步骤表"""

    __tablename__ = "scenario_steps"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    scenario_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("test_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("api_endpoints.id", ondelete="SET NULL"), index=True)

    # 步骤信息
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # 请求覆盖配置
    request_override: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    headers_override: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # 数据提取器
    extractors: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    # 断言配置
    assertions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    # 条件执行
    condition_expression: Mapped[Optional[str]] = mapped_column(String(1000))
    continue_on_failure: Mapped[bool] = mapped_column(Boolean, default=False)
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVZWM1dBPT06MjEwZjE3ZTk=

    # 延迟和重试
    delay_ms: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    scenario: Mapped["TestScenario"] = relationship("TestScenario", back_populates="steps")
    data_mappings: Mapped[list["StepDataMapping"]] = relationship(
        "StepDataMapping",
        back_populates="step",
        cascade="all, delete-orphan",
        foreign_keys="[StepDataMapping.step_id]"
    )
    step_results: Mapped[list["ScenarioStepResult"]] = relationship("ScenarioStepResult", back_populates="step")


class StepDataMapping(Base):
    """步骤间数据映射表"""

    __tablename__ = "step_data_mappings"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    step_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scenario_steps.id", ondelete="CASCADE"), nullable=False, index=True)

    # 数据源
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # previous_response, variable, function, static
    source_step_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scenario_steps.id"), index=True)
    source_path: Mapped[Optional[str]] = mapped_column(String(500))

    # 目标位置
    target_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # 转换
    transform_expression: Mapped[Optional[str]] = mapped_column(String(1000))

    # 元数据
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    step: Mapped["ScenarioStep"] = relationship("ScenarioStep", back_populates="data_mappings", foreign_keys=[step_id])
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVZWM1dBPT06MjEwZjE3ZTk=


class ScenarioVariable(Base):
    """场景变量定义表"""

    __tablename__ = "scenario_variables"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    scenario_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("test_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # string, number, boolean, object, array
    default_value: Mapped[Optional[dict]] = mapped_column(JSONB)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # 作用域
    scope: Mapped[str] = mapped_column(String(50), default="scenario")  # scenario, step, global
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    scenario: Mapped["TestScenario"] = relationship("TestScenario", back_populates="variables")


class ScenarioRun(Base):
    """场景执行记录表"""

    __tablename__ = "scenario_runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    scenario_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("test_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)

    # 标识
    identifier: Mapped[str] = mapped_column(String(50), nullable=False)

    # 执行状态
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)  # pending, running, completed, failed, cancelled

    # 运行时数据
    runtime_variables: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    execution_config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # 统计
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    passed_steps: Mapped[int] = mapped_column(Integer, default=0)
    failed_steps: Mapped[int] = mapped_column(Integer, default=0)
    skipped_steps: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # 报告
    report_path: Mapped[Optional[str]] = mapped_column(String(2048))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # 时间
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UVZWM1dBPT06MjEwZjE3ZTk=

    # 执行者
    executed_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))

    # 关系
    scenario: Mapped["TestScenario"] = relationship("TestScenario", back_populates="runs")
    step_results: Mapped[list["ScenarioStepResult"]] = relationship("ScenarioStepResult", back_populates="run", cascade="all, delete-orphan")


class ScenarioStepResult(Base):
    """步骤执行结果表"""

    __tablename__ = "scenario_step_results"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scenario_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scenario_steps.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("api_endpoints.id", ondelete="SET NULL"))

    # 执行信息
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # passed, failed, skipped, error

    # 请求/响应数据
    full_url: Mapped[Optional[str]] = mapped_column(Text)
    request_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    response_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # 提取的数据
    extracted_data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # 断言结果
    assertion_results: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    # 性能
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # 错误
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_stack: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 关系
    run: Mapped["ScenarioRun"] = relationship("ScenarioRun", back_populates="step_results")
    step: Mapped["ScenarioStep"] = relationship("ScenarioStep", back_populates="step_results")

