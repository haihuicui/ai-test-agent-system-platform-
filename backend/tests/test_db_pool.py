"""database.py 连接池模式（DB_POOL）单元测试。

运行方式（backend 容器内）：
  默认模式:  python -m pytest /tmp/test_db_pool.py -v
  池化模式:  DB_POOL=queue python -m pytest /tmp/test_db_pool.py -v -k queue
"""
import asyncio
import os

import pytest

from app.config import database


def test_default_mode_uses_global_nullpool_factory():
    """未设 DB_POOL 时：get_session_factory 返回全局 NullPool 工厂。"""
    if os.environ.get("DB_POOL", "null").lower() == "queue":
        pytest.skip("仅在默认模式（NullPool）下断言")
    factory = database.get_session_factory()
    assert factory is database.async_session_factory
    from sqlalchemy.pool import NullPool
    assert factory.kw["bind"].pool.__class__ is NullPool or \
        isinstance(factory.kw.get("bind", database.engine).pool, NullPool.__class__)


@pytest.mark.asyncio
async def test_queue_mode_same_loop_reuses_factory():
    """DB_POOL=queue：同一事件循环内返回同一个池化工厂（连接复用的前提）。"""
    if os.environ.get("DB_POOL", "null").lower() != "queue":
        pytest.skip("仅在 DB_POOL=queue 下断言")
    f1 = database.get_session_factory()
    f2 = database.get_session_factory()
    assert f1 is f2, "同一事件循环应复用同一个池化工厂"


@pytest.mark.asyncio
async def test_queue_mode_pooled_engine_config():
    """DB_POOL=queue：分桶引擎使用 QueuePool 而非 NullPool。"""
    if os.environ.get("DB_POOL", "null").lower() != "queue":
        pytest.skip("仅在 DB_POOL=queue 下断言")
    database.get_session_factory()
    loop = asyncio.get_running_loop()
    eng = database._loop_engines[loop]
    from sqlalchemy.pool import AsyncAdaptedQueuePool
    assert isinstance(eng.pool, AsyncAdaptedQueuePool)


def test_queue_mode_distinct_loops_get_distinct_factories():
    """DB_POOL=queue：不同事件循环各持独立工厂（跨循环不复用，LangGraph 安全）。"""
    if os.environ.get("DB_POOL", "null").lower() != "queue":
        pytest.skip("仅在 DB_POOL=queue 下断言")
    results = []

    async def grab():
        results.append(database.get_session_factory())

    asyncio.run(grab())
    asyncio.run(grab())  # asyncio.run 每次新建事件循环
    assert len(results) == 2
    assert results[0] is not results[1], "不同事件循环必须使用不同的池"


@pytest.mark.asyncio
async def test_get_db_yields_working_session():
    """get_db 依赖注入路径：能产生会话并执行查询（真实连库）。"""
    agen = database.get_db()
    session = await agen.__anext__()
    try:
        from sqlalchemy import text
        row = (await session.execute(text("SELECT 1"))).scalar()
        assert row == 1
    finally:
        await agen.aclose()
