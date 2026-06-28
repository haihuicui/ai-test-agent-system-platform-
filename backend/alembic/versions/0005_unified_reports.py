"""unified reports (stub)

Revision ID: 0005_unified_reports
Revises: 0004_add_pentest_tables
Create Date: 2026-06-10 00:00:00

说明：该迁移已在其他分支/环境中创建过 `reports` 表，但当前工作区未保留其原文件。
为保持 alembic 版本链可定位，本 stub 文件仅提供 revision 标识；upgrade 保持空操作，
downgrade 删除 `reports` 表（与原始迁移的降级行为一致）。
"""

from typing import Sequence, Union

from alembic import op

# noqa  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2TW5wbWVRPT06ZWEyMTQ4ODA=

revision: str = "0005_unified_reports"
down_revision: Union[str, None] = "0004_add_pentest_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 数据库中已经存在该迁移创建的内容，无需重复执行
    pass


def downgrade() -> None:
    # 删除该迁移创建的 reports 表
    op.drop_table("reports")
# fmt: off  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2TW5wbWVRPT06ZWEyMTQ4ODA=
