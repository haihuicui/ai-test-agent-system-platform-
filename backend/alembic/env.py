"""Alembic 环境配置

负责把 SQLAlchemy 的 metadata 与运行时数据库 URL 注入到 Alembic。
URL 从 ``app.config.settings.settings.postgres_sync_url`` 读取（同步 psycopg2）。
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# 让 alembic 能 import 到 app 包
import os
import sys

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
# pylint: disable  MC8zOmFIVnBZMlhsdEpUbXRiZm92b2s2VTNVMVJRPT06MzE2ZDJkZDA=

from app.config.settings import settings  # noqa: E402
from app.models import Base  # noqa: E402,F401 — 触发所有 model 注册到 Base.metadata
from app import models  # noqa: F401,E402 — 确保子模块都被加载

config = context.config
# pylint: disable  MS8zOmFIVnBZMlhsdEpUbXRiZm92b2s2VTNVMVJRPT06MzE2ZDJkZDA=

# 用真实 DSN 覆盖 alembic.ini 中的占位符
config.set_main_option("sqlalchemy.url", settings.postgres_sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：把迁移以 SQL 字符串形式输出。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：直接连库执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
# noqa  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b2s2VTNVMVJRPT06MzE2ZDJkZDA=
