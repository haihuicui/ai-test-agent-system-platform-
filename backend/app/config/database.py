"""
数据库连接配置

管理 PostgreSQL 和 MongoDB 的连接
"""

from typing import AsyncGenerator
import asyncio

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config.settings import settings, PROJECT_ROOT

# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzNBMGJBPT06M2NmMGZmN2E=

# ==================== PostgreSQL 配置 ====================

# 创建异步引擎
# 必须使用 NullPool：LangGraph worker 会在不同的事件循环中执行工具调用，
# 池化连接绑定在创建它的事件循环上，跨循环复用会触发
# "Future attached to a different loop"（asyncpg）。
# NullPool 每次检出都在当前循环新建连接，规避该问题。
engine = create_async_engine(
    settings.postgres_url,
    echo=settings.debug,
    poolclass=NullPool,
)

# 创建异步会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzNBMGJBPT06M2NmMGZmN2E=

from app.models.base import Base


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的依赖注入函数
    
    Yields:
        AsyncSession: 异步数据库会话
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """初始化数据库表（开发态使用）。

    生产环境一律走 ``alembic upgrade head``。这里的 ``create_all`` 只在
    ``settings.debug`` 模式下被 [app/main.py](app/main.py) 调用，方便
    快速搭建本地或测试环境。
    """
    import app.models  # noqa: F401 注册所有模型表到 Base.metadata
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def run_migrations() -> None:
    """应用 Alembic 迁移到最新版本（head）。

    生产/开发环境启动时统一调用，确保 SQLAlchemy 模型与数据库 schema 保持一致。
    该操作是幂等的：若数据库已处于最新 alembic 版本，则不会重复执行任何迁移。
    """
    from alembic.config import Config
    from alembic import command

    alembic_ini = PROJECT_ROOT / "backend" / "alembic.ini"
    if not alembic_ini.exists():
        raise RuntimeError(f"Alembic 配置文件不存在: {alembic_ini}")

    def _upgrade() -> None:
        alembic_cfg = Config(str(alembic_ini))
        # alembic.ini 里的 script_location 是相对路径，必须解析为绝对路径，
        # 否则在非 backend 目录启动时会报 "Path doesn't exist: alembic"。
        alembic_cfg.set_main_option(
            "script_location", str(PROJECT_ROOT / "backend" / "alembic")
        )
        command.upgrade(alembic_cfg, "head")

    await asyncio.to_thread(_upgrade)
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzNBMGJBPT06M2NmMGZmN2E=

# ==================== MongoDB 配置 ====================

class MongoDB:
    """MongoDB 连接管理器"""
    
    client: AsyncIOMotorClient = None
    database: AsyncIOMotorDatabase = None
    
    @classmethod
    async def connect(cls) -> None:
        """建立 MongoDB 连接"""
        cls.client = AsyncIOMotorClient(settings.mongodb_url)
        cls.database = cls.client[settings.mongodb_db]
    
    @classmethod
    async def disconnect(cls) -> None:
        """关闭 MongoDB 连接"""
        if cls.client:
            cls.client.close()
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzNBMGJBPT06M2NmMGZmN2E=
    
    @classmethod
    def get_database(cls) -> AsyncIOMotorDatabase:
        """获取数据库实例"""
        return cls.database


async def get_mongodb() -> AsyncIOMotorDatabase:
    """
    获取 MongoDB 数据库的依赖注入函数
    
    Returns:
        AsyncIOMotorDatabase: MongoDB 数据库实例
    """
    return MongoDB.get_database()

