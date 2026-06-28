"""
测试运行模型

定义测试运行及其关联测试用例的表结构
参考: https://www.browserstack.com/docs/test-management/api-reference/test-runs
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.schemas.enums import (
    TestRunState,
    TestRunActiveState,
    TestResultStatus,
    FilterScope,
    ExecutionMode,
    TriggerType,
    ScriptType,
    JobStatus,
    ScheduleTriggerType,
)


class TestRun(Base, UUIDMixin, TimestampMixin):
    """
    测试运行表

    存储测试运行的基本信息，字段映射 BrowserStack Test Run。
    """
    __tablename__ = "test_runs"
    __table_args__ = {"comment": "测试运行表"}

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID"
    )
    identifier: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="测试运行标识符，如 TR-123"
    )
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="测试运行名称"
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="测试运行描述"
    )
    run_state: Mapped[TestRunState] = mapped_column(
        SQLEnum(TestRunState),
        default=TestRunState.NEW_RUN,
        nullable=False,
        comment="运行状态"
    )
    active_state: Mapped[TestRunActiveState] = mapped_column(
        SQLEnum(TestRunActiveState),
        default=TestRunActiveState.ACTIVE,
        nullable=False,
        comment="活跃状态"
    )
    assignee: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="负责人邮箱"
    )
    test_case_assignee: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="测试用例默认负责人邮箱（用于新加入用例）"
    )
    test_plan_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联的测试计划 ID"
    )
    sub_test_plan_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联的子测试计划 ID（与 test_plan_id 互斥）"
    )
    tags: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="标签列表"
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
    configurations: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="配置 ID 列表"
    )
    configuration_map: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="测试用例与配置的映射 [{test_case_id, configuration_ids}]"
    )
    folder_ids: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="创建时引用的文件夹 ID 列表"
    )
    include_all: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否纳入项目下全部测试用例"
    )
    filter_scope: Mapped[FilterScope] = mapped_column(
        SQLEnum(FilterScope, values_callable=lambda x: [e.value for e in x]),
        default=FilterScope.GLOBAL,
        nullable=False,
        comment="测试用例过滤作用域"
    )
    filter_test_cases: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="测试用例过滤条件（创建/更新时使用，便于审计与重算）"
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="关闭时间，用于 closed_before/closed_after 过滤"
    )
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUZJM2F3PT06ZjA3ODJmMDY=

    # 执行配置字段（企业级测试调度平台）
    execution_mode: Mapped[ExecutionMode] = mapped_column(
        SQLEnum(ExecutionMode, values_callable=lambda obj: [e.value for e in obj]),
        default=ExecutionMode.SEQUENTIAL,
        nullable=False,
        comment="执行模式: sequential / parallel"
    )
    max_concurrency: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
        comment="最大并发数"
    )
    trigger_type: Mapped[TriggerType] = mapped_column(
        SQLEnum(TriggerType, values_callable=lambda obj: [e.value for e in obj]),
        default=TriggerType.MANUAL,
        nullable=False,
        comment="触发方式: manual / scheduled / api"
    )
    scheduled_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_run_schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联的定时调度任务 ID"
    )

    # 统计字段 - 冗余存储以提高查询性能
    test_cases_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="测试用例总数"
    )
    untested_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="未执行数量"
    )
    passed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="通过数量"
    )
    retest_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="需重测数量"
    )
    failed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="失败数量"
    )
    blocked_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="阻塞数量"
    )
    skipped_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="跳过数量"
    )
    in_progress_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="测试中数量"
    )
    custom_status_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="自定义状态数量"
    )
    # 兼容旧字段：等价于 untested_count；待数据迁移完成后下线
    not_executed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="(deprecated) 历史 not_executed 计数，等价于 untested_count"
    )

    # 关系
    project: Mapped["Project"] = relationship("Project", back_populates="test_runs")
    test_plan: Mapped["TestPlan"] = relationship(
        "TestPlan",
        back_populates="test_runs",
        foreign_keys=[test_plan_id]
    )
    sub_test_plan: Mapped["TestPlan"] = relationship(
        "TestPlan",
        foreign_keys=[sub_test_plan_id]
    )
    test_run_cases: Mapped[list["TestRunTestCase"]] = relationship(
        "TestRunTestCase",
        back_populates="test_run",
        cascade="all, delete-orphan"
    )
    script_jobs: Mapped[list["TestRunScriptJob"]] = relationship(
        "TestRunScriptJob",
        back_populates="test_run",
        cascade="all, delete-orphan",
        order_by="TestRunScriptJob.execution_order"
    )

    def __repr__(self) -> str:
        return f"<TestRun(id={self.id}, identifier={self.identifier}, name={self.name})>"
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUZJM2F3PT06ZjA3ODJmMDY=


class TestRunTestCase(Base, UUIDMixin, TimestampMixin):
    """
    测试运行与测试用例关联表

    存储测试运行中包含的测试用例及其执行状态
    """
    __tablename__ = "test_run_test_cases"
    __table_args__ = {"comment": "测试运行测试用例关联表"}

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
    configuration_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="配置 ID"
    )
    assignee: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="负责人邮箱"
    )
    latest_status: Mapped[TestResultStatus] = mapped_column(
        SQLEnum(TestResultStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=TestResultStatus.UNTESTED,
        nullable=False,
        comment="最新测试结果状态"
    )
    latest_result_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="最新测试结果 ID"
    )
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUZJM2F3PT06ZjA3ODJmMDY=

    # 关系
    test_run: Mapped["TestRun"] = relationship(
        "TestRun",
        back_populates="test_run_cases"
    )
    test_case: Mapped["TestCase"] = relationship(
        "TestCase",
        back_populates="test_run_cases"
    )

    def __repr__(self) -> str:
        return f"<TestRunTestCase(test_run_id={self.test_run_id}, test_case_id={self.test_case_id})>"


class TestRunScriptJob(Base, UUIDMixin, TimestampMixin):
    """
    测试运行脚本作业表

    统一关联测试运行与各类测试脚本（API测试、场景测试、Web测试）
    支持多态关联：通过 script_type + script_id 指向不同脚本表
    """
    __tablename__ = "test_run_script_jobs"
    __table_args__ = {"comment": "测试运行脚本作业表"}

    test_run_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="测试运行 ID"
    )
    script_type: Mapped[ScriptType] = mapped_column(
        SQLEnum(ScriptType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
        comment="脚本类型: api_test / scenario / web_test / test_case"
    )
    script_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="脚本 ID（逻辑外键，按 script_type 解析指向的表）"
    )
    script_identifier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="脚本标识符冗余（AT-x / TS-x / WT-x / TC-x）"
    )
    script_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="脚本名称冗余"
    )
    execution_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="执行顺序"
    )
    execution_mode: Mapped[ExecutionMode] = mapped_column(
        SQLEnum(ExecutionMode, values_callable=lambda obj: [e.value for e in obj]),
        default=ExecutionMode.SEQUENTIAL,
        nullable=False,
        comment="执行模式: sequential / parallel"
    )
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=JobStatus.PENDING,
        nullable=False,
        index=True,
        comment="作业状态: pending / running / completed / failed / skipped / cancelled"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="开始时间"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="完成时间"
    )
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="执行时长(毫秒)"
    )
    result_summary: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="结果摘要 {passed, failed, skipped, total}"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息"
    )
    stdout: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="标准输出日志"
    )
    stderr: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="标准错误日志"
    )
    report_path: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="报告 MinIO 路径"
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="已重试次数"
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="最大重试次数"
    )
    execution_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="执行配置（覆盖 TestRun 级别的配置）"
    )

    # 关系
    test_run: Mapped["TestRun"] = relationship(
        "TestRun",
        back_populates="script_jobs"
    )

    def __repr__(self) -> str:
        return (
            f"<TestRunScriptJob(test_run_id={self.test_run_id}, "
            f"script_type={self.script_type.value}, script_id={self.script_id})>"
        )

# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZUZJM2F3PT06ZjA3ODJmMDY=

class TestRunSchedule(Base, UUIDMixin, TimestampMixin):
    """
    测试运行定时调度表

    使用 APScheduler 实现定时触发测试运行执行
    """
    __tablename__ = "test_run_schedules"
    __table_args__ = {"comment": "测试运行定时调度表"}

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属项目 ID"
    )
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="调度名称"
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="调度描述"
    )
    test_run_template: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="测试运行创建模板（脚本列表、配置等）"
    )
    trigger_type: Mapped[ScheduleTriggerType] = mapped_column(
        SQLEnum(ScheduleTriggerType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        comment="触发器类型: cron / interval / date"
    )
    trigger_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="触发器配置"
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否启用"
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="下次执行时间"
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="上次执行时间"
    )
    apscheduler_job_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="APScheduler 内部 job ID"
    )

    def __repr__(self) -> str:
        return f"<TestRunSchedule(id={self.id}, name={self.name}, trigger_type={self.trigger_type.value})>"
