"""add_test_run_execution_snapshots

Revision ID: c6a79f4290f4
Revises: 9de27089e91f
Create Date: 2026-07-21 00:58:38.360447+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c6a79f4290f4'
down_revision: Union[str, None] = '9de27089e91f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'test_run_execution_snapshots',
        sa.Column('test_run_id', sa.UUID(), nullable=False, comment='测试运行 ID'),
        sa.Column('execution_number', sa.Integer(), nullable=False, comment='该 TestRun 的第几次执行（从 1 开始自增）'),
        sa.Column('triggered_by', sa.String(length=50), nullable=False, comment='触发方式: manual / scheduled / retry'),
        sa.Column('run_state', sa.String(length=50), nullable=False, comment='最终运行状态'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='执行开始时间'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='执行结束时间'),
        sa.Column('overall_progress', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='执行结束时 overall_progress 快照'),
        sa.Column('id', sa.UUID(), nullable=False, comment='主键 ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['test_run_id'], ['test_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('test_run_id', 'execution_number', name='uix_snapshot_run_number'),
        comment='测试运行执行快照表'
    )
    op.create_index(op.f('ix_test_run_execution_snapshots_test_run_id'), 'test_run_execution_snapshots', ['test_run_id'], unique=False)

    op.create_table(
        'test_run_execution_snapshot_jobs',
        sa.Column('snapshot_id', sa.UUID(), nullable=False, comment='所属快照 ID'),
        sa.Column('test_run_id', sa.UUID(), nullable=False, comment='测试运行 ID'),
        sa.Column('script_job_id', sa.UUID(), nullable=False, comment='对应原始 TestRunScriptJob.id（软引用）'),
        sa.Column('script_type', postgresql.ENUM('api_test', 'scenario', 'web_test', 'test_case', name='scripttype', create_type=False), nullable=False, comment='脚本类型'),
        sa.Column('script_id', sa.UUID(), nullable=False, comment='脚本 ID'),
        sa.Column('script_identifier', sa.String(length=50), nullable=False, comment='脚本标识符冗余'),
        sa.Column('script_name', sa.String(length=500), nullable=True, comment='脚本名称冗余'),
        sa.Column('execution_order', sa.Integer(), nullable=False, comment='执行顺序'),
        sa.Column('execution_mode', postgresql.ENUM('sequential', 'parallel', name='executionmode', create_type=False), nullable=False, comment='执行模式'),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'completed', 'failed', 'skipped', 'blocked', 'cancelled', name='jobstatus', create_type=False), nullable=False, comment='作业状态'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='开始时间'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='完成时间'),
        sa.Column('duration_ms', sa.Integer(), nullable=True, comment='执行时长(毫秒)'),
        sa.Column('result_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='结果摘要'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='错误信息'),
        sa.Column('stdout', sa.Text(), nullable=True, comment='标准输出日志'),
        sa.Column('stderr', sa.Text(), nullable=True, comment='标准错误日志'),
        sa.Column('report_path', sa.String(length=2048), nullable=True, comment='报告 MinIO 路径'),
        sa.Column('retry_count', sa.Integer(), nullable=False, comment='已重试次数'),
        sa.Column('max_retries', sa.Integer(), nullable=False, comment='最大重试次数'),
        sa.Column('id', sa.UUID(), nullable=False, comment='主键 ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['snapshot_id'], ['test_run_execution_snapshots.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        comment='测试运行执行快照作业表'
    )
    op.create_index(op.f('ix_test_run_execution_snapshot_jobs_snapshot_id'), 'test_run_execution_snapshot_jobs', ['snapshot_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_test_run_execution_snapshot_jobs_snapshot_id'), table_name='test_run_execution_snapshot_jobs')
    op.drop_table('test_run_execution_snapshot_jobs')
    op.drop_index(op.f('ix_test_run_execution_snapshots_test_run_id'), table_name='test_run_execution_snapshots')
    op.drop_table('test_run_execution_snapshots')
