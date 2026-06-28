"""add android test tables

Revision ID: 0005_add_android_test_tables
Revises: 0004_add_pentest_tables
Create Date: 2026-06-10 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UTJkM2RRPT06NmYyYTI1Njg=


revision: str = "0006_add_android_test_tables"
down_revision: Union[str, None] = "0005_unified_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UTJkM2RRPT06NmYyYTI1Njg=


def upgrade() -> None:
    # 新增 Android 附件实体类型枚举值（使用 ALTER TYPE ADD VALUE）
    # PostgreSQL 枚举 ALTER 需在事务块内单独执行
    op.execute("ALTER TYPE attachmententitytype ADD VALUE IF NOT EXISTS 'android_test_plan'")
    op.execute("ALTER TYPE attachmententitytype ADD VALUE IF NOT EXISTS 'android_test_case'")
    op.execute("ALTER TYPE attachmententitytype ADD VALUE IF NOT EXISTS 'android_test_script'")
    op.execute("ALTER TYPE attachmententitytype ADD VALUE IF NOT EXISTS 'android_test_report'")

    op.create_table(
        "android_tests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "folder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("folders.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "test_case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("test_cases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("identifier", sa.String(length=50), nullable=False, unique=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("app_package", sa.String(length=500), nullable=True),
        sa.Column("app_activity", sa.String(length=500), nullable=True),
        sa.Column("device_udid", sa.String(length=500), nullable=True),
        sa.Column("script_path", sa.String(length=2048), nullable=False),
        sa.Column("script_format", sa.String(length=50), nullable=False, server_default="midscene"),
        sa.Column("script_language", sa.String(length=50), nullable=False, server_default="typescript"),
        sa.Column("test_config", postgresql.JSONB(), nullable=True),
        sa.Column("test_scenarios", postgresql.JSONB(), nullable=True),
        sa.Column("generated_by_agent", sa.String(length=100), nullable=False, server_default="android_agent"),
        sa.Column("generation_params", postgresql.JSONB(), nullable=True),
        sa.Column("total_scenarios", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_android_tests_folder_id", "android_tests", ["folder_id"])
    op.create_index("ix_android_tests_identifier", "android_tests", ["identifier"])
    op.create_index("ix_android_tests_project_id", "android_tests", ["project_id"])
    op.create_index("ix_android_tests_test_case_id", "android_tests", ["test_case_id"])

    op.create_table(
        "android_test_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "android_test_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("android_tests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("identifier", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("execution_config", postgresql.JSONB(), nullable=True),
        sa.Column("total_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_tests", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("report_path", sa.String(length=2048), nullable=True),
        sa.Column("screenshots_path", sa.String(length=2048), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_android_test_runs_android_test_id", "android_test_runs", ["android_test_id"])
    op.create_index("ix_android_test_runs_identifier", "android_test_runs", ["identifier"])
    op.create_index("ix_android_test_runs_project_id", "android_test_runs", ["project_id"])
    op.create_index("ix_android_test_runs_status", "android_test_runs", ["status"])

    op.create_table(
        "android_test_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "test_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("android_test_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "android_test_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("android_tests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scenario_name", sa.String(length=500), nullable=False),
        sa.Column("case_id", sa.String(length=100), nullable=False),
        sa.Column("test_type", sa.String(length=50), nullable=False),
        sa.Column("status", postgresql.ENUM("passed", "failed", "skipped", "blocked", name="testresultstatus", create_type=False), nullable=False),
        sa.Column("test_summary", postgresql.JSONB(), nullable=True),
        sa.Column("error_details", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("screenshot_path", sa.String(length=2048), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_android_test_results_android_test_id", "android_test_results", ["android_test_id"])
    op.create_index("ix_android_test_results_status", "android_test_results", ["status"])
    op.create_index("ix_android_test_results_test_run_id", "android_test_results", ["test_run_id"])
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UTJkM2RRPT06NmYyYTI1Njg=


def downgrade() -> None:
    op.drop_index("ix_android_test_results_test_run_id", table_name="android_test_results")
    op.drop_index("ix_android_test_results_status", table_name="android_test_results")
    op.drop_index("ix_android_test_results_android_test_id", table_name="android_test_results")
    op.drop_table("android_test_results")
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UTJkM2RRPT06NmYyYTI1Njg=

    op.drop_index("ix_android_test_runs_status", table_name="android_test_runs")
    op.drop_index("ix_android_test_runs_project_id", table_name="android_test_runs")
    op.drop_index("ix_android_test_runs_identifier", table_name="android_test_runs")
    op.drop_index("ix_android_test_runs_android_test_id", table_name="android_test_runs")
    op.drop_table("android_test_runs")

    op.drop_index("ix_android_tests_test_case_id", table_name="android_tests")
    op.drop_index("ix_android_tests_project_id", table_name="android_tests")
    op.drop_index("ix_android_tests_identifier", table_name="android_tests")
    op.drop_index("ix_android_tests_folder_id", table_name="android_tests")
    op.drop_table("android_tests")

    # 枚举值无法安全删除，保留新增的枚举值
