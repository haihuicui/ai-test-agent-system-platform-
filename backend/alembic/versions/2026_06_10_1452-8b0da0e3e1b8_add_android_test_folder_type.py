"""add_android_test_folder_type

Revision ID: 8b0da0e3e1b8
Revises: 0006_add_android_test_tables
Create Date: 2026-06-10 14:52:27.653009+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# noqa  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2T1VFeE9RPT06MmRjYjhkZTk=

# revision identifiers, used by Alembic.
revision: str = '8b0da0e3e1b8'
down_revision: Union[str, None] = '0006_add_android_test_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 向 foldertype 枚举添加 android_test 值
    # PostgreSQL ALTER TYPE ADD VALUE 不能在事务块内执行
    # 使用 execute 直接执行，Alembic 会自动处理
    op.execute("ALTER TYPE foldertype ADD VALUE IF NOT EXISTS 'android_test'")
# pragma: no cover  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2T1VFeE9RPT06MmRjYjhkZTk=


def downgrade() -> None:
    # PostgreSQL 不支持删除枚举值，保留新增的值
    pass
