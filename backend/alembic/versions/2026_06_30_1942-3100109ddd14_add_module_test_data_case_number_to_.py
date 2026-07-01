"""add_module_test_data_case_number_to_test_cases

Revision ID: 3100109ddd14
Revises: 8b0da0e3e1b8
Create Date: 2026-06-30 19:42:24.822097+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3100109ddd14'
down_revision: Union[str, None] = '8b0da0e3e1b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 新增 module / test_data / case_number 列
    op.add_column(
        "test_cases",
        sa.Column("module", sa.String(length=255), nullable=True, comment="所属模块")
    )
    op.add_column(
        "test_cases",
        sa.Column("test_data", postgresql.JSONB(), nullable=True, comment="测试数据")
    )
    op.add_column(
        "test_cases",
        sa.Column("case_number", sa.String(length=50), nullable=True, comment="用例编号")
    )

    # module 索引
    op.create_index("ix_test_cases_module", "test_cases", ["module"])

    # 用 folder.name 回填已有记录的 module
    op.execute("""
        UPDATE test_cases
        SET module = folders.name
        FROM folders
        WHERE test_cases.folder_id = folders.id
          AND test_cases.module IS NULL
    """)


def downgrade() -> None:
    op.drop_index("ix_test_cases_module", table_name="test_cases")
    op.drop_column("test_cases", "case_number")
    op.drop_column("test_cases", "test_data")
    op.drop_column("test_cases", "module")
