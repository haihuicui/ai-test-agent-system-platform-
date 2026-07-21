"""add_test_run_id_and_max_retries_to_snapshot_jobs

Revision ID: fdb7f7eb4aec
Revises: c6a79f4290f4
Create Date: 2026-07-21 01:08:53.865925+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'fdb7f7eb4aec'
down_revision: Union[str, None] = 'c6a79f4290f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'test_run_execution_snapshot_jobs',
        sa.Column('test_run_id', sa.UUID(), nullable=False, comment='测试运行 ID（冗余，便于与 TestRunScriptJob 对齐）')
    )
    op.add_column(
        'test_run_execution_snapshot_jobs',
        sa.Column('max_retries', sa.Integer(), nullable=False, comment='最大重试次数')
    )


def downgrade() -> None:
    op.drop_column('test_run_execution_snapshot_jobs', 'max_retries')
    op.drop_column('test_run_execution_snapshot_jobs', 'test_run_id')
