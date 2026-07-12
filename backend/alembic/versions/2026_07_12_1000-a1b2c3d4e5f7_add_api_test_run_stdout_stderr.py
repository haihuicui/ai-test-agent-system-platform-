"""add api_test_run stdout/stderr columns

Revision ID: a1b2c3d4e5f7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-12 10:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "api_test_runs",
        sa.Column("stdout", sa.Text(), nullable=True, comment="Playwright 标准输出日志"),
    )
    op.add_column(
        "api_test_runs",
        sa.Column("stderr", sa.Text(), nullable=True, comment="Playwright 标准错误日志"),
    )


def downgrade() -> None:
    op.drop_column("api_test_runs", "stderr")
    op.drop_column("api_test_runs", "stdout")
