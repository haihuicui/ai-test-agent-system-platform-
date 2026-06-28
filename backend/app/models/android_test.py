"""
Android 测试模型

定义 Android 测试脚本、运行和结果的表结构
"""

from sqlalchemy import ForeignKey, Integer, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTNCQlF3PT06M2FlMDAyYjA=

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.schemas.enums import TestResultStatus


# Android 测试运行状态枚举
class AndroidTestRunStatus(str):
    """Android 测试运行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Android 测试脚本格式枚举
class AndroidScriptFormat(str):
    """Android 测试脚本格式"""
    MIDSCENE = "midscene"       # Midscene.js 测试
    APPIUM = "appium"           # Appium 测试
    ESPRESSO = "espresso"       # Espresso 测试


class AndroidTest(Base, UUIDMixin, TimestampMixin):
    """
    Android 测试脚本表

    存储 android_agent 生成的 Android 测试脚本元数据
    """
    __tablename__ = "android_tests"
    __table_args__ = {"comment": "Android 测试脚本表"}

    # 基本信息
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
        comment="所属文件夹 ID (可选)"
    )
    test_case_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="关联的测试用例 ID (可选)"
    )
    identifier: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Android 测试标识符,如 ANT-1001"
    )
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Android 测试名称"
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="测试描述"
    )

    # Android 应用信息
    app_package: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="被测应用包名"
    )
    app_activity: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="被测应用启动 Activity"
    )
    device_udid: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="目标设备 UDID"
    )

    # 测试脚本内容 (存储在 MinIO, 这里存路径)
    script_path: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="测试脚本文件路径 (MinIO)"
    )
    script_format: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AndroidScriptFormat.MIDSCENE,
        comment="脚本格式: midscene, appium, espresso"
    )
    script_language: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="typescript",
        comment="脚本语言: typescript, javascript, python, java"
    )

    # 测试配置 (JSONB)
    test_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="测试配置 {device, ai_model, timeout, etc.}"
    )

    # 场景信息 (JSONB)
    test_scenarios: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="测试场景列表 [{name, steps, assertions}]"
    )

    # 生成信息
    generated_by_agent: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="android_agent",
        comment="生成智能体标识"
    )
    generation_params: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="生成参数"
    )

    # 统计信息
    total_scenarios: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="测试场景总数"
    )
    total_cases: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="测试用例总数"
    )

    # 关系
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="android_tests"
    )
    folder: Mapped["Folder | None"] = relationship(
        "Folder",
        back_populates="android_tests"
    )
    test_case: Mapped["TestCase | None"] = relationship(
        "TestCase",
        back_populates="android_tests"
    )
    test_runs: Mapped[list["AndroidTestRun"]] = relationship(
        "AndroidTestRun",
        back_populates="android_test",
        cascade="all, delete-orphan",
        order_by="AndroidTestRun.created_at.desc()"
    )


class AndroidTestRun(Base, UUIDMixin, TimestampMixin):
    """
    Android 测试运行表

    记录 Android 测试的执行记录
    """
    __tablename__ = "android_test_runs"
    __table_args__ = {"comment": "Android 测试运行表"}
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTNCQlF3PT06M2FlMDAyYjA=

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    android_test_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("android_tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    identifier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="运行标识符,如 ANTR-20250125-001"
    )

    # 执行状态
    status: Mapped[str] = mapped_column(
        String(50),
        default=AndroidTestRunStatus.PENDING,
        nullable=False,
        index=True,
        comment="运行状态: pending, running, completed, failed, cancelled"
    )

    # 执行配置 (JSONB)
    execution_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="执行配置 {device, env, timeout, etc.}"
    )

    # 执行结果统计
    total_tests: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="总测试数"
    )
    passed_tests: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="通过数"
    )
    failed_tests: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="失败数"
    )
    skipped_tests: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="跳过数"
    )

    # 执行时长
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="执行时长(毫秒)"
    )

    # 报告和截图文件路径
    report_path: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="测试报告文件路径 (MinIO)"
    )
    screenshots_path: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="截图文件夹路径 (MinIO)"
    )

    # 错误信息
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息"
    )

    # 关系
    project: Mapped["Project"] = relationship("Project")
    android_test: Mapped["AndroidTest"] = relationship(
        "AndroidTest",
        back_populates="test_runs"
    )
    test_results: Mapped[list["AndroidTestResult"]] = relationship(
        "AndroidTestResult",
        back_populates="test_run",
        cascade="all, delete-orphan",
        order_by="AndroidTestResult.created_at"
    )
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTNCQlF3PT06M2FlMDAyYjA=


class AndroidTestResult(Base, UUIDMixin, TimestampMixin):
    """
    Android 测试结果表

    存储单个测试场景的执行结果
    """
    __tablename__ = "android_test_results"
    __table_args__ = {"comment": "Android 测试结果表"}

    test_run_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("android_test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    android_test_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("android_tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # 测试场景信息
    scenario_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="测试场景名称"
    )
    case_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="测试用例 ID"
    )
    test_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="测试类型: launch, interaction, assertion, navigation"
    )

    # 执行结果
    status: Mapped[TestResultStatus] = mapped_column(
        SQLEnum(TestResultStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
        comment="测试状态: passed, failed, skipped, blocked"
    )

    # 测试摘要 (JSONB)
    test_summary: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="测试摘要 {steps, duration, screenshot, assertions}"
    )
    error_details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="错误详情 {error_message, stack_trace, element}"
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息"
    )

    # 截图路径
    screenshot_path: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="截图文件路径 (MinIO)"
    )

    # 执行时长
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="执行时长(毫秒)"
    )

    # 重试信息
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="重试次数"
    )
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTNCQlF3PT06M2FlMDAyYjA=

    # 关系
    test_run: Mapped["AndroidTestRun"] = relationship(
        "AndroidTestRun",
        back_populates="test_results"
    )
    android_test: Mapped["AndroidTest"] = relationship("AndroidTest")
