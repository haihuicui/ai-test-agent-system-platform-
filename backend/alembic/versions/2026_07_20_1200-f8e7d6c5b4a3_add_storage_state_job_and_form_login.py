"""add_storage_state_job_and_form_login

Revision ID: f8e7d6c5b4a3
Revises: 07cf36d34e86
Create Date: 2026-07-20 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8e7d6c5b4a3'
down_revision: Union[str, None] = '07cf36d34e86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL enum 值追加（幂等：已存在则跳过）
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'attachmententitytype') THEN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = 'attachmententitytype'
                      AND e.enumlabel = 'storage_state'
                ) THEN
                    ALTER TYPE attachmententitytype ADD VALUE 'STORAGE_STATE';
                END IF;
            END IF;
        END $$;
        """
    )

    # 为已运行过低ercase 值的开发/测试库补加大写值（SQLAlchemy Enum 默认存 name）
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'attachmententitytype') THEN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = 'attachmententitytype'
                      AND e.enumlabel = 'STORAGE_STATE'
                ) THEN
                    ALTER TYPE attachmententitytype ADD VALUE 'STORAGE_STATE';
                END IF;
            END IF;
        END $$;
        """
    )

    op.create_table(
        'storage_state_jobs',
        sa.Column('project_id', sa.UUID(), nullable=False, comment='所属项目 ID'),
        sa.Column('environment_id', sa.UUID(), nullable=True, comment='使用的项目环境配置 ID'),
        sa.Column('status', sa.String(length=20), nullable=False, comment='任务状态: pending/running/completed/failed'),
        sa.Column('output_path', sa.String(length=2048), nullable=True, comment='生成的 storageState.json 本地路径'),
        sa.Column('attachment_id', sa.UUID(), nullable=True, comment='归档到 MinIO 的附件 ID'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='错误信息'),
        sa.Column('stdout', sa.Text(), nullable=True, comment='Playwright 标准输出'),
        sa.Column('stderr', sa.Text(), nullable=True, comment='Playwright 标准错误'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='开始执行时间'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='执行完成时间'),
        sa.Column('id', sa.UUID(), nullable=False, comment='主键 ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['environment_id'], ['project_environments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['attachment_id'], ['attachments.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        comment='Web 登录态生成任务'
    )
    op.create_index(op.f('ix_storage_state_jobs_project_id'), 'storage_state_jobs', ['project_id'], unique=False)
    op.create_index(op.f('ix_storage_state_jobs_environment_id'), 'storage_state_jobs', ['environment_id'], unique=False)
    op.create_index(op.f('ix_storage_state_jobs_status'), 'storage_state_jobs', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_storage_state_jobs_status'), table_name='storage_state_jobs')
    op.drop_index(op.f('ix_storage_state_jobs_environment_id'), table_name='storage_state_jobs')
    op.drop_index(op.f('ix_storage_state_jobs_project_id'), table_name='storage_state_jobs')
    op.drop_table('storage_state_jobs')
    # PostgreSQL 不支持删除 enum 值，此处不回滚 attachmententitytype
