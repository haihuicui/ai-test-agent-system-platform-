"""test_run_script_jobs: add TestRunScriptJob, TestRunSchedule, and TestRun execution fields

Revision ID: 0002_test_run_script_jobs
Revises: 0001_baseline_bs
Create Date: 2026-05-19 00:00:00

本迁移新增企业级测试调度平台所需的核心表和字段：

- 新增枚举: scripttype, executionmode, triggertype, scheduletriggertype, jobstatus
- test_runs 新增执行配置字段: execution_mode, max_concurrency, trigger_type, scheduled_by
- 新增表: test_run_script_jobs（统一脚本作业表）
- 新增表: test_run_schedules（定时调度表）
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y21RMFZ3PT06ZTY0MzRkNjg=

revision: str = "0002_test_run_script_jobs"
down_revision: Union[str, None] = "0001_baseline_bs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 创建新枚举类型
    op.execute(
        sa.text("CREATE TYPE scripttype AS ENUM ('api_test', 'scenario', 'web_test', 'test_case')")
    )
    op.execute(
        sa.text("CREATE TYPE executionmode AS ENUM ('sequential', 'parallel')")
    )
    op.execute(
        sa.text("CREATE TYPE triggertype AS ENUM ('manual', 'scheduled', 'api')")
    )
    op.execute(
        sa.text("CREATE TYPE scheduletriggertype AS ENUM ('cron', 'interval', 'date')")
    )
    op.execute(
        sa.text("CREATE TYPE jobstatus AS ENUM ('pending', 'running', 'completed', 'failed', 'skipped', 'cancelled')")
    )
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y21RMFZ3PT06ZTY0MzRkNjg=

    # 2) test_runs 新增字段（不含 scheduled_by 外键，因为目标表尚未创建）
    with op.batch_alter_table("test_runs") as batch:
        batch.add_column(
            sa.Column(
                "execution_mode",
                postgresql.ENUM("sequential", "parallel", name="executionmode", create_type=False),
                nullable=False,
                server_default="sequential",
            )
        )
        batch.add_column(
            sa.Column(
                "max_concurrency",
                sa.Integer(),
                nullable=False,
                server_default="5",
            )
        )
        batch.add_column(
            sa.Column(
                "trigger_type",
                postgresql.ENUM("manual", "scheduled", "api", name="triggertype", create_type=False),
                nullable=False,
                server_default="manual",
            )
        )
        batch.add_column(
            sa.Column(
                "scheduled_by",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            )
        )

    # 3) 创建 test_run_schedules 表（先于外键创建）
    op.create_table(
        "test_run_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("test_run_template", postgresql.JSONB(), nullable=False),
        sa.Column(
            "trigger_type",
            postgresql.ENUM("cron", "interval", "date", name="scheduletriggertype", create_type=False),
            nullable=False,
        ),
        sa.Column("trigger_config", postgresql.JSONB(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("apscheduler_job_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_test_run_schedules_project_id", "test_run_schedules", ["project_id"])

    # 4) 为 test_runs.scheduled_by 添加外键约束（现在目标表已存在）
    op.create_foreign_key(
        "fk_test_runs_scheduled_by",
        "test_runs",
        "test_run_schedules",
        ["scheduled_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_test_runs_scheduled_by", "test_runs", ["scheduled_by"])

    # 5) 创建 test_run_script_jobs 表
    op.create_table(
        "test_run_script_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("test_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "script_type",
            postgresql.ENUM("api_test", "scenario", "web_test", "test_case", name="scripttype", create_type=False),
            nullable=False,
        ),
        sa.Column("script_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("script_identifier", sa.String(length=50), nullable=False),
        sa.Column("script_name", sa.String(length=500), nullable=True),
        sa.Column("execution_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "execution_mode",
            postgresql.ENUM("sequential", "parallel", name="executionmode", create_type=False),
            nullable=False,
            server_default="sequential",
        ),
        sa.Column(
            "status",
            postgresql.ENUM("pending", "running", "completed", "failed", "skipped", "cancelled", name="jobstatus", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("result_summary", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("report_path", sa.String(length=2048), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_config", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["test_run_id"], ["test_runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_test_run_script_jobs_test_run_id", "test_run_script_jobs", ["test_run_id"])
    op.create_index("ix_test_run_script_jobs_script_type", "test_run_script_jobs", ["script_type"])
    op.create_index("ix_test_run_script_jobs_script_id", "test_run_script_jobs", ["script_id"])
    op.create_index("ix_test_run_script_jobs_status", "test_run_script_jobs", ["status"])
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y21RMFZ3PT06ZTY0MzRkNjg=


def downgrade() -> None:
    # 5) 删除 test_run_script_jobs
    op.drop_index("ix_test_run_script_jobs_status", table_name="test_run_script_jobs")
    op.drop_index("ix_test_run_script_jobs_script_id", table_name="test_run_script_jobs")
    op.drop_index("ix_test_run_script_jobs_script_type", table_name="test_run_script_jobs")
    op.drop_index("ix_test_run_script_jobs_test_run_id", table_name="test_run_script_jobs")
    op.drop_table("test_run_script_jobs")

    # 4) 删除 test_run_schedules 及关联外键
    op.drop_index("ix_test_run_schedules_project_id", table_name="test_run_schedules")
    op.drop_table("test_run_schedules")

    # 3) 删除 test_runs 的外键和字段
    op.drop_index("ix_test_runs_scheduled_by", table_name="test_runs")
    op.drop_constraint("fk_test_runs_scheduled_by", "test_runs", type_="foreignkey")
    with op.batch_alter_table("test_runs") as batch:
        batch.drop_column("scheduled_by")
        batch.drop_column("trigger_type")
        batch.drop_column("max_concurrency")
        batch.drop_column("execution_mode")

    # 1) 删除枚举类型
    op.execute(sa.text("DROP TYPE IF EXISTS jobstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS scheduletriggertype"))
    op.execute(sa.text("DROP TYPE IF EXISTS triggertype"))
    op.execute(sa.text("DROP TYPE IF EXISTS executionmode"))
    op.execute(sa.text("DROP TYPE IF EXISTS scripttype"))
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y21RMFZ3PT06ZTY0MzRkNjg=
