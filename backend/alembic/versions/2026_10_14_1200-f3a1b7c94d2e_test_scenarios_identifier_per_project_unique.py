"""test_scenarios identifier 改为项目内唯一

identifier 由创建逻辑按「项目内 MAX + 1」生成（TS-0001 起），但原
ix_test_scenarios_identifier 是全局唯一索引，导致新项目与已有项目的
TS-0001 冲突、无法创建任何场景（UniqueViolationError）。

本迁移将全局唯一索引替换为 (project_id, identifier) 复合唯一索引。
现有数据本来就全局唯一，迁移无数据冲突。

注意：downgrade 时若各项目间已出现同名 identifier 将无法恢复全局唯一索引。

Revision ID: f3a1b7c94d2e
Revises: c8f2a91e4b03
Create Date: 2026-10-14 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f3a1b7c94d2e'
down_revision: Union[str, None] = 'c8f2a91e4b03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_test_scenarios_identifier', table_name='test_scenarios')
    op.create_index(
        'uq_test_scenarios_project_identifier',
        'test_scenarios',
        ['project_id', 'identifier'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('uq_test_scenarios_project_identifier', table_name='test_scenarios')
    op.create_index(
        'ix_test_scenarios_identifier',
        'test_scenarios',
        ['identifier'],
        unique=True,
    )
