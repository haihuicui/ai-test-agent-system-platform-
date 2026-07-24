"""add storage_state validation fields

Revision ID: 6d23fdf78e8f
Revises: f612042a05c6
Create Date: 2026-07-24 06:28:13.310138+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d23fdf78e8f'
down_revision: Union[str, None] = 'f612042a05c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 为 storage_state_jobs 增加登录态静态校验相关字段，全部可空以保持历史数据兼容。
    op.add_column(
        'storage_state_jobs',
        sa.Column(
            'expires_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='storageState 中最早过期时间',
        ),
    )
    op.add_column(
        'storage_state_jobs',
        sa.Column(
            'is_valid',
            sa.Boolean(),
            nullable=True,
            comment='最近一次静态校验结果：True 有效 / False 过期或损坏',
        ),
    )
    op.add_column(
        'storage_state_jobs',
        sa.Column(
            'validation_reason',
            sa.String(length=500),
            nullable=True,
            comment='校验结果说明',
        ),
    )
    op.add_column(
        'storage_state_jobs',
        sa.Column(
            'probe_status',
            sa.String(length=50),
            nullable=True,
            comment='运行时探针状态（预留）：pending/success/failed/skipped',
        ),
    )


def downgrade() -> None:
    op.drop_column('storage_state_jobs', 'probe_status')
    op.drop_column('storage_state_jobs', 'validation_reason')
    op.drop_column('storage_state_jobs', 'is_valid')
    op.drop_column('storage_state_jobs', 'expires_at')
