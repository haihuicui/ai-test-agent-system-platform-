"""add web_healing_knowledge table

修复 healer 工具（search_healing_knowledge / record_healing_result）因
web_healing_knowledge 表缺失而报错的问题。模型早已存在于
app/models/web_test.py，但从未生成过迁移。

Revision ID: b3c9a1e24f07
Revises: 6d23fdf78e8f
Create Date: 2026-08-04 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c9a1e24f07'
down_revision: Union[str, None] = '6d23fdf78e8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'web_healing_knowledge',
        sa.Column('id', sa.UUID(), nullable=False, comment='主键 ID'),
        sa.Column(
            'error_signature',
            sa.String(length=500),
            nullable=False,
            comment='规范化错误指纹（去除动态值）',
        ),
        sa.Column(
            'error_category',
            sa.String(length=50),
            nullable=False,
            comment='错误类别: selector/timing/assertion/environment/application',
        ),
        sa.Column(
            'fix_strategy',
            sa.Text(),
            nullable=False,
            comment='修复策略描述（给 Agent 看的自然语言指引）',
        ),
        sa.Column(
            'fix_code_template',
            sa.Text(),
            nullable=True,
            comment='可自动应用的代码模板',
        ),
        sa.Column(
            'confidence',
            sa.Float(),
            server_default='0.5',
            nullable=False,
            comment='修复成功率 (0-1)，每次成功 +0.05，失败 -0.1',
        ),
        sa.Column(
            'apply_count',
            sa.Integer(),
            server_default='0',
            nullable=False,
            comment='应用次数',
        ),
        sa.Column(
            'success_count',
            sa.Integer(),
            server_default='0',
            nullable=False,
            comment='成功次数',
        ),
        sa.Column(
            'project_id',
            sa.UUID(),
            nullable=True,
            comment='所属项目 ID（NULL 表示全局通用）',
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='创建时间',
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='更新时间',
        ),
        sa.ForeignKeyConstraint(
            ['project_id'], ['projects.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
        comment='Web 测试修复知识图谱表',
    )
    op.create_index(
        'ix_web_healing_knowledge_error_signature',
        'web_healing_knowledge',
        ['error_signature'],
    )
    op.create_index(
        'ix_web_healing_knowledge_error_category',
        'web_healing_knowledge',
        ['error_category'],
    )
    op.create_index(
        'ix_web_healing_knowledge_project_id',
        'web_healing_knowledge',
        ['project_id'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_web_healing_knowledge_project_id',
        table_name='web_healing_knowledge',
    )
    op.drop_index(
        'ix_web_healing_knowledge_error_category',
        table_name='web_healing_knowledge',
    )
    op.drop_index(
        'ix_web_healing_knowledge_error_signature',
        table_name='web_healing_knowledge',
    )
    op.drop_table('web_healing_knowledge')
