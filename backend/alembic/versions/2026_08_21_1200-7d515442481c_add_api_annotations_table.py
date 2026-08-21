"""add api annotations table

新增 API 业务语义标注库，用于沉淀从 trace、探测、文档、RAG 或人工录入中
获取的业务语义：

- 业务成功/错误码
- 字段级校验规则
- 枚举含义
- 接口依赖与状态约束

供 API agent 在生成单接口测试与场景测试时直接消费，把负向用例从
"期望 400" 提升到 "期望 code=4009, msg=xxx"。

Revision ID: 7d515442481c
Revises: a4d0508718bc
Create Date: 2026-08-21 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7d515442481c'
down_revision: Union[str, None] = 'a4d0508718bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'api_annotations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'project_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('projects.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'endpoint_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('api_endpoints.id', ondelete='CASCADE'),
            nullable=True,
        ),
        sa.Column('annotation_type', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('http_status', sa.Integer(), nullable=True),
        sa.Column('business_code', sa.String(length=100), nullable=True),
        sa.Column('field_path', sa.String(length=500), nullable=True),
        sa.Column('condition', sa.String(length=100), nullable=True),
        sa.Column('message_pattern', sa.Text(), nullable=True),
        sa.Column(
            'expected_value',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('hit_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column(
            'first_seen_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column(
            'last_seen_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'source_metadata',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'endpoint_id',
            'annotation_type',
            'http_status',
            'business_code',
            'field_path',
            'condition',
            name='uq_api_annotations_natural_key',
            deferrable=True,
            initially='DEFERRED',
        ),
        comment='API 业务语义标注库：错误码、字段约束、枚举含义、依赖关系等',
    )

    # 索引
    op.create_index(
        'ix_api_annotations_project_id_endpoint_id',
        'api_annotations',
        ['project_id', 'endpoint_id'],
    )
    op.create_index(
        'ix_api_annotations_endpoint_id_type',
        'api_annotations',
        ['endpoint_id', 'annotation_type'],
    )
    op.create_index(
        'ix_api_annotations_business_code',
        'api_annotations',
        ['business_code'],
    )
    op.create_index(
        'ix_api_annotations_field_path',
        'api_annotations',
        ['field_path'],
    )
    op.create_index(
        'ix_api_annotations_last_seen_at',
        'api_annotations',
        ['last_seen_at'],
    )
    # project_id / endpoint_id 本身在 create_table 时没建 index，补建
    op.create_index(
        'ix_api_annotations_project_id',
        'api_annotations',
        ['project_id'],
    )
    op.create_index(
        'ix_api_annotations_endpoint_id',
        'api_annotations',
        ['endpoint_id'],
    )


def downgrade() -> None:
    op.drop_table('api_annotations')
