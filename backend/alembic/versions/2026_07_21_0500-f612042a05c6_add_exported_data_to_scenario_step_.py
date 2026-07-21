"""add exported_data to scenario_step_results

Revision ID: f612042a05c6
Revises: 27a86ed6d63e
Create Date: 2026-07-21 05:00:18.761729+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f612042a05c6'
down_revision: Union[str, None] = '27a86ed6d63e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为步骤执行结果表增加 exported_data 列，用于持久化 variable_exports 的实际导出值。"""
    op.add_column(
        'scenario_step_results',
        sa.Column(
            'exported_data',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default='{}',
            nullable=False,
            comment='步骤执行时 variable_exports 的实际导出值快照，供后续步骤引用及结果展示',
        ),
    )


def downgrade() -> None:
    """移除 scenario_step_results 表的 exported_data 列。"""
    op.drop_column('scenario_step_results', 'exported_data')
