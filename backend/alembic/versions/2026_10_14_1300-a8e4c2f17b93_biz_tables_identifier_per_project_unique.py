"""6 张业务表 identifier 改为项目内唯一

与 test_scenarios 同款问题（见 f3a1b7c94d2e）：以下表的 identifier 均按
「项目内 MAX + 1」编号，但唯一索引是全局的，新项目与已有项目撞号即
UniqueViolationError：

- api_tests         AT-1001   （api_test_repo.get_next_identifier 项目内编号）
- android_tests     ANT-1001  （android_test_repo 同上）
- web_functions     WF-1001   （web_function_repo 同上）
- web_sub_functions WSF-1001  （web_function_repo 同上）
- pentests          PT-1001   （pentest_repo 同上）
- pentest_reports   PR-1001   （pentest_repo 同上）

统一替换为 (project_id, identifier) 复合唯一索引。已排查：这些表的
get_by_identifier 全局查询方法均无外部调用者，改动安全。
现有数据在全局唯一约束下本就无重复，迁移零冲突。

注意：downgrade 时若各项目间已出现同名 identifier 将无法恢复全局唯一索引。

Revision ID: a8e4c2f17b93
Revises: f3a1b7c94d2e
Create Date: 2026-10-14 13:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a8e4c2f17b93'
down_revision: Union[str, None] = 'f3a1b7c94d2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = [
    'api_tests',
    'android_tests',
    'web_functions',
    'web_sub_functions',
    'pentests',
    'pentest_reports',
]


def upgrade() -> None:
    for table in TABLES:
        op.drop_index(f'ix_{table}_identifier', table_name=table)
        op.create_index(
            f'uq_{table}_project_identifier',
            table,
            ['project_id', 'identifier'],
            unique=True,
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f'uq_{table}_project_identifier', table_name=table)
        op.create_index(
            f'ix_{table}_identifier',
            table,
            ['identifier'],
            unique=True,
        )
