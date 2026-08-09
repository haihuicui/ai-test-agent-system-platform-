"""
数据库连接配置

管理 PostgreSQL 和 MongoDB 的连接
"""

from typing import AsyncGenerator
import asyncio
import os

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config.settings import settings, PROJECT_ROOT

# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzNBMGJBPT06M2NmMGZmN2E=

# ==================== PostgreSQL 配置 ====================

# 连接池模式：DB_POOL=queue 启用按事件循环分组的连接池；默认 NullPool。
#
# 背景：NullPool 每次检出都新建连接（TCP + SSL + SCRAM-SHA-256 纯 Python HMAC
# 约 0.5-1s，且在事件循环上阻塞计算），导致 backend 每个 API 请求都支付一次
# 建连成本，接口延迟 1.5-4s。但池化连接绑定创建它的事件循环，LangGraph worker
# 在多个隔离事件循环中复用会触发 "Future attached to a different loop"。
#
# 折中：DB_POOL=queue 时按「当前运行中的事件循环」分桶建池——单循环进程
# （backend FastAPI）天然只会有一个池，多循环场景（LangGraph worker、
# 线程内 asyncio.run）各自持有独立池，互不跨循环复用。
_USE_LOOP_POOL = os.environ.get("DB_POOL", "null").lower() == "queue"

# 创建异步引擎（默认 NullPool，保持 LangGraph worker 多事件循环安全）
engine = create_async_engine(
    settings.postgres_url,
    echo=settings.debug,
    poolclass=NullPool,
)

# NullPool 会话工厂（原始实现）；模块级公开名 async_session_factory 是池化代理（见下文）
_nullpool_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 按事件循环分桶的连接池/会话工厂注册表（仅 DB_POOL=queue 时使用）
_loop_engines: "dict[asyncio.AbstractEventLoop, object]" = {}
_loop_session_factories: "dict[asyncio.AbstractEventLoop, async_sessionmaker]" = {}


def _pooled_session_factory() -> async_sessionmaker:
    """返回当前事件循环专属的池化会话工厂（惰性创建）。"""
    loop = asyncio.get_running_loop()
    factory = _loop_session_factories.get(loop)
    if factory is None:
        loop_engine = create_async_engine(
            settings.postgres_url,
            echo=settings.debug,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        factory = async_sessionmaker(
            loop_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        _loop_engines[loop] = loop_engine
        _loop_session_factories[loop] = factory
    return factory


def get_session_factory() -> async_sessionmaker:
    """按池化模式返回会话工厂：queue 模式按事件循环分桶，否则全局 NullPool。"""
    if _USE_LOOP_POOL:
        return _pooled_session_factory()
    return _nullpool_session_factory


class _SessionFactoryProxy:
    """async_session_factory() 调用点的池化代理。

    全仓库 20+ 处直接 `async_session_factory()`（各 agent 工具、storageState 解析等），
    若直连 NullPool 工厂，DB_POOL=queue 对它们不生效。代理后所有调用点零改动：
    queue 模式按事件循环分桶复用连接（省每次 ~0.5-1s SCRAM 建连），默认模式行为不变。
    """

    def __call__(self) -> AsyncSession:
        return get_session_factory()()


# 公开会话工厂：保持原有用法 `async_session_factory()` 不变
async_session_factory = _SessionFactoryProxy()

# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzNBMGJBPT06M2NmMGZmN2E=

from app.models.base import Base


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的依赖注入函数
    
    Yields:
        AsyncSession: 异步数据库会话
    """
    async with get_session_factory()() as session:
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

