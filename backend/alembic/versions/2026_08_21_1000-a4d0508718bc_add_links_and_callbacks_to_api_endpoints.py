"""add links and callbacks columns to api_endpoints

OpenAPI 3.0 的 links（response 级，接口间依赖）与 callbacks（operation 级，
异步回调）此前在导入时被整体丢弃。本迁移新增两个 JSONB 列落库：

- links:     {响应状态: {link 名: link 对象}}，link 内 parameters 描述
             「目标接口参数 ← 本接口响应字段」的映射表达式
- callbacks: {expression: callback 对象}

供 API agent 场景设计（步骤顺序 / 提取器 / 数据映射）直接消费。
存量行保持 NULL，重新导入 OpenAPI 文档后新端点即带数据。

Revision ID: a4d0508718bc
Revises: b3c9a1e24f07
Create Date: 2026-08-21 10:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a4d0508718bc'
down_revision: Union[str, None] = 'b3c9a1e24f07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'api_endpoints',
        sa.Column(
            'links',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "接口间依赖（OpenAPI links，按响应状态分组）"
                "{status: {link_name: link_object}}；link 内 parameters "
                "描述目标接口参数 ← 本接口响应字段的映射"
            ),
        ),
    )
    op.add_column(
        'api_endpoints',
        sa.Column(
            'callbacks',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "回调定义（OpenAPI callbacks，operation 级）"
                "{expression: callback_object}，描述本接口触发的异步通知"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column('api_endpoints', 'callbacks')
    op.drop_column('api_endpoints', 'links')
