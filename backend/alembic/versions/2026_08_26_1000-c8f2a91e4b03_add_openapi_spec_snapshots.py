"""add openapi spec snapshots table

新增 OpenAPI 原始文档快照表：每次导入留存完整 spec 原文（JSONB），
解决「端点只存解析片段、完整 spec 未持久化」的根因，支持审计、
重解析与 $ref 解引用排障。

Revision ID: c8f2a91e4b03
Revises: 7d515442481c
Create Date: 2026-08-26 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c8f2a91e4b03'
down_revision: Union[str, None] = '7d515442481c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'openapi_spec_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'project_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('projects.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('title', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('version', sa.String(length=100), nullable=False, server_default=''),
        sa.Column('source', sa.String(length=50), nullable=False, server_default='upload'),
        sa.Column('endpoint_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('spec', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        comment='OpenAPI 原始文档快照：每次导入留存完整 spec 原文',
    )
    op.create_index(
        'ix_openapi_spec_snapshots_project_id',
        'openapi_spec_snapshots',
        ['project_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_openapi_spec_snapshots_project_id', table_name='openapi_spec_snapshots')
    op.drop_table('openapi_spec_snapshots')
