"""
Web 测试模型

定义 Web 测试脚本、运行和结果的表结构
"""

from sqlalchemy import ForeignKey, Integer, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.schemas.enums import TestResultStatus
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTNaSVZBPT06MDQ3ZjA1OTY=


# Web 测试运行状态枚举
class WebTestRunStatus(str):
    """Web 测试运行状态"""
    PENDING = "pending"           # 等待执行
    RUNNING = "running"           # 执行中
    COMPLETED = "completed"       # 执行完成
    FAILED = "failed"             # 执行失败
    CANCELLED = "cancelled"       # 已取消


# Web 测试脚本格式枚举
class WebScriptFormat(str):
    """Web 测试脚本格式"""
    PLAYWRIGHT = "playwright"     # Playwright 测试
    CYPRESS = "cypress"           # Cypress 测试
    SELENIUM = "selenium"         # Selenium 测试


class WebTest(Base, UUIDMixin, TimestampMixin):
    """
    Web 测试脚本表

    存储 web_agent 生成的 Web 测试脚本元数据
    """
    __tablename__ = "web_tests"
    __table_args__ = {"comment": "Web 测试脚本表"}

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
    function_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("web_functions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="所属功能 ID"
    )
    sub_function_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("web_sub_functions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="所属子功能 ID"
    )
    identifier: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Web 测试标识符,如 WT-1001"
    )
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Web 测试名称"
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="测试描述"
    )

    # Web 应用信息
    base_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="Web 应用基础 URL"
    )
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTNaSVZBPT06MDQ3ZjA1OTY=

    # 测试脚本内容 (存储在 MinIO, 这里存路径)
    script_path: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="测试脚本文件路径 (MinIO)"
    )
    script_format: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=WebScriptFormat.PLAYWRIGHT,
        comment="脚本格式: playwright, cypress, selenium"
    )
    script_language: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="typescript",
        comment="脚本语言: typescript, javascript, python"
    )

    # 测试配置 (JSONB)
    test_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="测试配置 {viewport, timeout, browser_options, headless, etc.}"
    )

    # 页面和流程信息 (JSONB)
    target_pages: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="目标页面列表 [{url, name, elements}]"
    )
    test_flows: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="测试流程定义 [{name, steps, assertions}]"
    )

    # 生成信息
    generated_by_agent: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="web_agent",
        comment="生成智能体标识"
    )
    generation_params: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="生成参数"
    )

    # 统计信息
    total_pages: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="测试的页面总数"
    )
    total_flows: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="测试流程总数"
    )

    # 关系
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="web_tests"
    )
    folder: Mapped["Folder | None"] = relationship(
        "Folder",
        back_populates="web_tests"
    )
    test_case: Mapped["TestCase | None"] = relationship(
        "TestCase",
        back_populates="web_tests"
    )
    function: Mapped["WebFunction | None"] = relationship(
        "WebFunction",
        back_populates="web_tests"
    )
    sub_function: Mapped["WebSubFunction | None"] = relationship(
        "WebSubFunction",
        back_populates="web_tests"
    )
    test_runs: Mapped[list["WebTestRun"]] = relationship(
        "WebTestRun",
        back_populates="web_test",
        cascade="all, delete-orphan",
        order_by="WebTestRun.created_at.desc()"
    )


class WebTestRun(Base, UUIDMixin, TimestampMixin):
    """
    Web 测试运行表

    记录 Web 测试的执行记录
    """
    __tablename__ = "web_test_runs"
    __table_args__ = {"comment": "Web 测试运行表"}

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    web_test_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("web_tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    identifier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="运行标识符,如 WTR-20250125-001"
    )

    # 执行状态
    status: Mapped[str] = mapped_column(
        String(50),
        default=WebTestRunStatus.PENDING,
        nullable=False,
        index=True,
        comment="运行状态: pending, running, completed, failed, cancelled"
    )

    # 执行配置 (JSONB)
    execution_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="执行配置 {browser, viewport, headless, timeout, etc.}"
    )
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTNaSVZBPT06MDQ3ZjA1OTY=

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

    # 执行日志
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

    # 关系
    project: Mapped["Project"] = relationship("Project")
    web_test: Mapped["WebTest"] = relationship(
        "WebTest",
        back_populates="test_runs"
    )
    test_results: Mapped[list["WebTestResult"]] = relationship(
        "WebTestResult",
        back_populates="test_run",
        cascade="all, delete-orphan",
        order_by="WebTestResult.created_at"
    )


class WebTestResult(Base, UUIDMixin, TimestampMixin):
    """
    Web 测试结果表

    存储单个测试场景的执行结果
    """
    __tablename__ = "web_test_results"
    __table_args__ = {"comment": "Web 测试结果表"}

    test_run_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("web_test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    web_test_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("web_tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # 测试场景信息
    scenario_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="测试场景名称"
    )
    page_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="页面 URL"
    )
    test_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="测试类型: navigation, interaction, form, assertion"
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
        comment="测试摘要 {steps, duration, screenshot, elements}"
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
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTNaSVZBPT06MDQ3ZjA1OTY=

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

    # 关系
    test_run: Mapped["WebTestRun"] = relationship(
        "WebTestRun",
        back_populates="test_results"
    )
    web_test: Mapped["WebTest"] = relationship("WebTest")
