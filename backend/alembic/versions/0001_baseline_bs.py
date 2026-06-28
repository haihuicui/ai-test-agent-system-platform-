"""baseline: test_run/test_plan/test_case BrowserStack 字段对齐

Revision ID: 0001_baseline_bs
Revises:
Create Date: 2026-05-17 00:00:00

本迁移负责把 ``create_all`` 已经生成的 schema 升级到 BrowserStack 对齐的状态：

- TestResultStatus 枚举新增 ``untested`` / ``retest`` / ``in_progress``
- 新增枚举 FilterScope (global / within_folders)
- test_runs 新增 BS 规范要求的字段（sub_test_plan_id, configuration_map, folder_ids,
  include_all, filter_scope, filter_test_cases, issue_tracker, closed_at, test_case_assignee,
  untested/retest/in_progress/custom_status 计数）
- test_plans 新增自引用 parent_id（支持 sub_test_plan）
- test_cases 新增 dataset / last_updated_by

如果是全新部署，先在干净库上执行 ``python -c "import asyncio; from app.config.database
import init_db; asyncio.run(init_db())"`` 创建基础表，然后 ``alembic stamp head`` 标记基线，
之后所有变更通过 alembic 管理。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TjNSTFRBPT06NjZhODRmZDY=


revision: str = "0001_baseline_bs"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_enum_values_if_missing(enum_name: str, values: list[str]) -> None:
    """安全地往 PG 枚举里追加新值（不存在才追加）。"""
    for value in values:
        op.execute(
            sa.text(
                f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"
            )
        )


def upgrade() -> None:
    # 1) TestResultStatus 枚举扩展
    _add_enum_values_if_missing(
        "testresultstatus",
        ["untested", "retest", "in_progress"],
    )
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TjNSTFRBPT06NjZhODRmZDY=

    # 2) FilterScope 枚举（如果不存在则创建）
    #
    # 注意：先前 ``create_all`` 可能已经用 SQLAlchemy 默认（enum name，大写）
    # 创建过 filterscope = ('GLOBAL', 'WITHIN_FOLDERS')。本迁移要求小写值
    # ('global', 'within_folders') 与 BrowserStack 规范一致。filter_scope 列尚未
    # 添加，此时 filterscope 类型不会被任何列引用，直接 DROP 再 CREATE 即可。
    op.execute(sa.text("DROP TYPE IF EXISTS filterscope CASCADE"))
    op.execute(
        sa.text("CREATE TYPE filterscope AS ENUM ('global', 'within_folders')")
    )

    # 3) test_runs 字段扩展
    with op.batch_alter_table("test_runs") as batch:
        batch.add_column(sa.Column("test_case_assignee", sa.String(length=255), nullable=True))
        batch.add_column(
            sa.Column(
                "sub_test_plan_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("test_plans.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch.add_column(sa.Column("issue_tracker", postgresql.JSONB(), nullable=True))
        batch.add_column(sa.Column("configuration_map", postgresql.JSONB(), nullable=True))
        batch.add_column(sa.Column("folder_ids", postgresql.JSONB(), nullable=True))
        batch.add_column(
            sa.Column(
                "include_all",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch.add_column(
            sa.Column(
                "filter_scope",
                postgresql.ENUM(
                    "global", "within_folders", name="filterscope", create_type=False
                ),
                nullable=False,
                server_default="global",
            )
        )
        batch.add_column(sa.Column("filter_test_cases", postgresql.JSONB(), nullable=True))
        batch.add_column(
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("untested_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("retest_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("in_progress_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column(
                "custom_status_count", sa.Integer(), nullable=False, server_default="0"
            )
        )

    op.create_index(
        "ix_test_runs_sub_test_plan_id", "test_runs", ["sub_test_plan_id"]
    )

    # 把已有 not_executed_count 同步到 untested_count
    op.execute(
        sa.text(
            "UPDATE test_runs SET untested_count = not_executed_count "
            "WHERE not_executed_count IS NOT NULL AND not_executed_count > 0"
        )
    )

    # 4) test_plans 自引用
    op.add_column(
        "test_plans",
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("test_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_test_plans_parent_id", "test_plans", ["parent_id"])

    # 5) test_cases 新字段
    op.add_column(
        "test_cases",
        sa.Column("dataset", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "test_cases",
        sa.Column(
            "last_updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TjNSTFRBPT06NjZhODRmZDY=


def downgrade() -> None:
    # 5) test_cases
    op.drop_column("test_cases", "last_updated_by")
    op.drop_column("test_cases", "dataset")
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TjNSTFRBPT06NjZhODRmZDY=

    # 4) test_plans
    op.drop_index("ix_test_plans_parent_id", table_name="test_plans")
    op.drop_column("test_plans", "parent_id")

    # 3) test_runs
    op.drop_index("ix_test_runs_sub_test_plan_id", table_name="test_runs")
    with op.batch_alter_table("test_runs") as batch:
        batch.drop_column("custom_status_count")
        batch.drop_column("in_progress_count")
        batch.drop_column("retest_count")
        batch.drop_column("untested_count")
        batch.drop_column("closed_at")
        batch.drop_column("filter_test_cases")
        batch.drop_column("filter_scope")
        batch.drop_column("include_all")
        batch.drop_column("folder_ids")
        batch.drop_column("configuration_map")
        batch.drop_column("issue_tracker")
        batch.drop_column("sub_test_plan_id")
        batch.drop_column("test_case_assignee")

    # 2) FilterScope 枚举
    op.execute(sa.text("DROP TYPE IF EXISTS filterscope"))

    # 1) TestResultStatus 枚举（PG 不支持 enum 值移除，需 recreate type；此处略，
    #    生产环境通常不向下兼容这种破坏性变更）
