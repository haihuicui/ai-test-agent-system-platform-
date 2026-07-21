"""add_storage_state_failure_screenshot

Revision ID: 9de27089e91f
Revises: f8e7d6c5b4a3
Create Date: 2026-07-20 12:27:51.802401+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "9de27089e91f"
down_revision: Union[str, None] = "f8e7d6c5b4a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 向附件实体类型 enum 追加登录态生成任务产物类型
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'attachmententitytype') THEN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = 'attachmententitytype'
                      AND e.enumlabel = 'storage_state_job'
                ) THEN
                    ALTER TYPE attachmententitytype ADD VALUE 'STORAGE_STATE_JOB';
                END IF;
            END IF;
        END $$;
        """
    )

    # 登录态生成任务增加失败截图附件 ID
    op.add_column(
        "storage_state_jobs",
        sa.Column(
            "failure_screenshot_attachment_id",
            sa.UUID(),
            nullable=True,
            comment="失败时页面截图附件 ID",
        ),
    )
    op.create_index(
        "ix_storage_state_jobs_failure_screenshot_attachment_id",
        "storage_state_jobs",
        ["failure_screenshot_attachment_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_storage_state_jobs_failure_screenshot_attachment",
        "storage_state_jobs",
        "attachments",
        ["failure_screenshot_attachment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_storage_state_jobs_failure_screenshot_attachment",
        "storage_state_jobs",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_storage_state_jobs_failure_screenshot_attachment_id",
        table_name="storage_state_jobs",
    )
    op.drop_column("storage_state_jobs", "failure_screenshot_attachment_id")
    # PostgreSQL enum 值不支持删除，保留即可
