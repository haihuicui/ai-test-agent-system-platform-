"""
API 测试模型

定义 API 测试脚本、运行和结果的表结构
"""

from sqlalchemy import ForeignKey, Integer, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.schemas.enums import TestResultStatus


# API 测试运行状态枚举
class APITestRunStatus(str):
    """API 测试运行状态"""
    PENDING = "pending"           # 等待执行
    RUNNING = "running"           # 执行中
    COMPLETED = "completed"       # 执行完成
    FAILED = "failed"             # 执行失败
    CANCELLED = "cancelled"       # 已取消


# API 测试脚本格式枚举
class APIScriptFormat(str):
    """API 测试脚本格式"""
    PLAYWRIGHT = "playwright"     # Playwright 测试
    JEST = "jest"                 # Jest 测试
    POSTMAN = "postman"           # Postman Collection

# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0RWc1FRPT06ZTkyNzRiNGI=

# API Schema 类型枚举
class APISchemaType(str):
    """API Schema 类型"""
    OPENAPI = "openapi"           # OpenAPI 3.x
    SWAGGER = "swagger"           # Swagger 2.0
    GRAPHQL = "graphql"           # GraphQL


class APITest(Base, UUIDMixin, TimestampMixin):
    """
    API 测试脚本表

    存储 api_agent 生成的 API 测试脚本元数据
    """
    __tablename__ = "api_tests"
    __table_args__ = {"comment": "API 测试脚本表"}

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
        comment="API 测试标识符,如 AT-1001"
    )
    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="API 测试名称"
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="测试描述"
    )

    # API schema 信息
    schema_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="OpenAPI/Swagger schema URL"
    )
    schema_path: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="本地 schema 文件路径 (MinIO)"
    )
    schema_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=APISchemaType.OPENAPI,
        comment="Schema 类型: openapi, swagger, graphql"
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
        default=APIScriptFormat.PLAYWRIGHT,
        comment="脚本格式: playwright, jest, postman"
    )
    script_language: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="typescript",
        comment="脚本语言: typescript, javascript"
    )
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0RWc1FRPT06ZTkyNzRiNGI=

    # 测试配置 (JSONB)
    test_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
        default=dict,
        comment="测试配置 {baseUrl, headers, auth, etc.}"
    )

    # 生成信息
    generated_by_agent: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="api_agent",
        comment="生成智能体标识"
    )
    generation_params: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="生成参数"
    )

    # 统计信息
    total_endpoints: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="测试的端点总数"
    )
    total_scenarios: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="测试场景总数"
    )

    # 关系
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="api_tests"
    )
    folder: Mapped["Folder | None"] = relationship(
        "Folder",
        back_populates="api_tests"
    )
    test_case: Mapped["TestCase | None"] = relationship(
        "TestCase",
        back_populates="api_tests"
    )
    test_runs: Mapped[list["APITestRun"]] = relationship(
        "APITestRun",
        back_populates="api_test",
        cascade="all, delete-orphan",
        order_by="APITestRun.created_at.desc()"
    )


class APITestRun(Base, UUIDMixin, TimestampMixin):
    """
    API 测试运行表

    记录 API 测试的执行记录
    """
    __tablename__ = "api_test_runs"
    __table_args__ = {"comment": "API 测试运行表"}

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    api_test_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    identifier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="运行标识符,如 ATR-20250125-001"
    )

    # 执行状态
    status: Mapped[str] = mapped_column(
        String(50),
        default=APITestRunStatus.PENDING,
        nullable=False,
        index=True,
        comment="运行状态: pending, running, completed, failed, cancelled"
    )

    # 执行配置 (JSONB)
    execution_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="执行配置 {environment, timeout, retry, etc.}"
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
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0RWc1FRPT06ZTkyNzRiNGI=

    # 报告文件路径
    report_path: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment="测试报告文件路径 (MinIO)"
    )

    # 原始执行输出（Playwright stdout/stderr）
    stdout: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Playwright 标准输出日志"
    )
    stderr: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Playwright 标准错误日志"
    )

    # 错误信息
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息"
    )

    # 关系
    project: Mapped["Project"] = relationship("Project")
    api_test: Mapped["APITest"] = relationship(
        "APITest",
        back_populates="test_runs"
    )
    test_results: Mapped[list["APITestResult"]] = relationship(
        "APITestResult",
        back_populates="test_run",
        cascade="all, delete-orphan",
        order_by="APITestResult.created_at"
    )


class APITestResult(Base, UUIDMixin, TimestampMixin):
    """
    API 测试结果表

    存储单个测试场景的执行结果
    """
    __tablename__ = "api_test_results"
    __table_args__ = {"comment": "API 测试结果表"}

    test_run_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_test_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    api_test_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # 测试场景信息
    scenario_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="测试场景名称"
    )
    endpoint: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="API 端点"
    )
    method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="HTTP 方法: GET, POST, PUT, DELETE, etc."
    )

    # 执行结果
    status: Mapped[TestResultStatus] = mapped_column(
        SQLEnum(TestResultStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
        comment="测试状态: passed, failed, skipped, blocked"
    )

    # 请求/响应摘要 (JSONB) - 保留向后兼容
    request_summary: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="请求摘要 {url, method, headers, body_summary}"
    )
    response_summary: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="响应摘要 {status_code, duration_ms, size}"
    )

    # 完整请求/响应明细 (JSONB) - 新增
    request_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="完整请求数据 {method, url, headers, params, body}"
    )
    response_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="完整响应数据 {status, statusText, headers, body, timing}"
    )
    assertion_results: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="断言结果列表 [{assertion, passed, actual, expected, message}]"
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息"
    )

    # MongoDB 详细日志 ID
    detail_log_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="详细日志 ID (MongoDB)"
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

    # 关系
    test_run: Mapped["APITestRun"] = relationship(
        "APITestRun",
        back_populates="test_results"
    )
    api_test: Mapped["APITest"] = relationship("APITest")
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0RWc1FRPT06ZTkyNzRiNGI=
