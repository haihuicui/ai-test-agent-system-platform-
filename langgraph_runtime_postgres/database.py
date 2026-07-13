
import asyncio
import os
import re
import threading
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any, TypeAlias

import langgraph_api.config as config
import structlog
from langgraph_api.feature_flags import FF_USE_CORE_API
from langgraph_api.serde import fragment_loads, json_dumpb
from psycopg import AsyncConnection
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import DictRow, dict_row
from psycopg.types.json import set_json_dumps, set_json_loads
from psycopg_pool import AsyncConnectionPool
from redis.exceptions import LockError, LockNotOwnedError

from langgraph_runtime_postgres import redis
from langgraph_runtime_postgres.redis import LOCK_MIGRATION

Row: TypeAlias = dict[str, Any]


logger = structlog.stdlib.get_logger(__name__)
_pg_pool: AsyncConnectionPool[AsyncConnection[DictRow]] | None = None
_stats_task: asyncio.Task | None = None

# Thread-local storage for per-thread connection pools
_thread_local = threading.local()


async def healthcheck() -> None:
    # check postgres
    async with connect() as conn, conn.cursor() as cur:
        await cur.execute("SELECT 1")
    # check redis
    await redis.get_redis().ping()  # type: ignore[invalid-await]
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WmsxSVJ3PT06NDg2YjZiNzE=


@asynccontextmanager
async def connect(
    *, supports_core_api: bool = False, __test__: bool = False
) -> AsyncIterator[AsyncConnection[DictRow]]:
    if supports_core_api and FF_USE_CORE_API:
        # No need to connect to Postgres if we're using the gRPC server.
        yield
        return

    if __test__:
        async with await create_conn(__test__) as conn:
            yield conn
    elif threading.current_thread() is not threading.main_thread():
        # Use thread-local connection pool
        if not hasattr(_thread_local, "pg_pool"):
            # Create a new pool for this thread on first use
            _thread_local.pg_pool = create_pool(__test__=__test__, thread_local=True)
            await _thread_local.pg_pool.open(wait=True)
            logger.info(
                "Created new thread-local Postgres connection pool",
                thread_name=threading.current_thread().name,
            )

        # Use the thread-local pool
        async with _thread_local.pg_pool.connection() as conn:
            yield conn
    else:
        if _pg_pool is None:
            raise RuntimeError("Postgres pool not initialized")
        async with _pg_pool.connection() as conn:
            yield conn


# Define an configure function that sets JSON adapters for each new connection
async def _configure_connection(conn: AsyncConnection[DictRow]):
    # Register custom JSON dumps/loads on this connection
    set_json_dumps(json_dumpb, conn)
    set_json_loads(fragment_loads, conn)


async def _reset_connection(conn: AsyncConnection[DictRow]) -> None:
    # Always rollback to clear any open transaction or lock
    with suppress(Exception):
        await conn.rollback()


def _connection_params(*, __test__: bool = False) -> dict[str, Any]:
    """Parse DATABASE_URI and add statement timeouts + TCP keepalive settings.

    TCP keepalive is especially important when the PostgreSQL server is remote
    (e.g. 192.168.60.103): firewalls and NAT gateways often drop idle TCP
    sessions, and PostgreSQL may also close idle connections depending on its
    own ``tcp_keepalives_*`` configuration. Without keepalive, a connection
    returned from the pool can be silently closed by the server, causing
    ``OperationalError: server closed the connection unexpectedly`` on the
    first query.
    """
    params = conninfo_to_dict(config.DATABASE_URI)
    params.setdefault("options", "")
    if not __test__:
        params["options"] += " -c lock_timeout=1000"  # ms
        params["options"] += " -c statement_timeout=900s"
        params["options"] += " -c idle_in_transaction_session_timeout=900s"

    # TCP keepalive: start probing after 30s idle, every 10s, up to 5 times.
    params.setdefault("keepalives", 1)
    params.setdefault("keepalives_idle", 30)
    params.setdefault("keepalives_interval", 10)
    params.setdefault("keepalives_count", 5)
    return params


def create_pool(
    *, __test__: bool = False, thread_local: bool = False
) -> AsyncConnectionPool[AsyncConnection[DictRow]]:
    # parse connection string and add keepalive/timeouts
    params = _connection_params(__test__=__test__)

    # For thread-local pools, use smaller pool sizes
    if thread_local:
        pool_min_size = 1
        # Default to 150 / 10 = 15 to let each worker have equal access to the pool
        pool_max_size = config.POSTGRES_POOL_MAX_SIZE // config.N_JOBS_PER_WORKER
        pool_max_idle = 30
    else:
        pool_min_size = 1
        pool_max_size = config.POSTGRES_POOL_MAX_SIZE
        pool_max_idle = 60

    # create connection pool
    return AsyncConnectionPool(
        connection_class=AsyncConnection[DictRow],
        min_size=pool_min_size,
        max_size=pool_max_size,
        max_idle=pool_max_idle,  # seconds
        max_lifetime=600,  # seconds; force rotation to avoid stale remote conns
        timeout=15,
        kwargs={
            **params,
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        configure=_configure_connection,
        reset=_reset_connection,
        open=False,
    )


async def create_conn(__test__: bool = False) -> AsyncConnection[DictRow]:
    params = _connection_params(__test__=__test__)

    conn = await AsyncConnection.connect(
        config.DATABASE_URI,
        row_factory=dict_row,
        autocommit=True,
        prepare_threshold=0,
        **params,
    )
    await _configure_connection(conn)
    return conn


def _split_sql_statements(sql: str) -> list[str]:
    """Split a SQL script into individual statements.

    Respects single-quoted strings and dollar-quoted bodies ($$ ... $$ /
    $tag$ ... $tag$) so that semicolons inside function/DO blocks do not split a
    statement. Each returned statement is executed on its own so that
    ``CREATE INDEX CONCURRENTLY`` never ends up inside an implicit transaction
    block (Postgres forbids that).
    """
    statements: list[str] = []
    buf: list[str] = []
    i, n = 0, len(sql)
    dollar_tag: str | None = None
    in_squote = False
    while i < n:
        ch = sql[i]
        if dollar_tag is not None:
            if sql.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
            else:
                buf.append(ch)
                i += 1
            continue
        if in_squote:
            buf.append(ch)
            if ch == "'":
                if sql[i + 1 : i + 2] == "'":  # escaped quote ''
                    buf.append("'")
                    i += 2
                    continue
                in_squote = False
            i += 1
            continue
        two = sql[i : i + 2]
        if two == "--":  # line comment
            j = sql.find("\n", i)
            j = n if j == -1 else j
            buf.append(sql[i:j])
            i = j
            continue
        if two == "/*":  # block comment
            j = sql.find("*/", i)
            j = n if j == -1 else j + 2
            buf.append(sql[i:j])
            i = j
            continue
        if ch == "'":
            in_squote = True
            buf.append(ch)
            i += 1
            continue
        if ch == "$":
            m = re.match(r"\$[A-Za-z0-9_]*\$", sql[i:])
            if m:
                dollar_tag = m.group(0)
                buf.append(dollar_tag)
                i += len(dollar_tag)
                continue
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _is_executable_statement(stmt: str) -> bool:
    """True if the statement contains SQL beyond comments/whitespace."""
    cleaned = re.sub(r"--[^\n]*", "", stmt)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    return bool(cleaned.strip())


async def migrate() -> None:
    # 如果 migrations 路径不存在，跳过迁移（适用于本地开发连接已有数据库）
    if not os.path.exists(config.MIGRATIONS_PATH):
        logger.info("Migrations path not found, skipping migrations", path=config.MIGRATIONS_PATH)
        return
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WmsxSVJ3PT06NDg2YjZiNzE=

    async with connect() as conn, conn.cursor() as cur:
        await cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version BIGINT PRIMARY KEY,
                dirty   BOOLEAN NOT NULL
            )
        """)
        await cur.execute(
            "SELECT COALESCE(MAX(version), -1) AS v FROM schema_migrations"
        )
        current_version = (await cur.fetchone())["v"]
        migration_paths = defaultdict(dict)
        for migration_path in sorted(os.listdir(config.MIGRATIONS_PATH)):
            version = int(migration_path.split("_")[0])
            which = migration_path.split(".")[-2]
            if which == "up":
                migration_paths[version]["standard"] = migration_path
            elif which == "lite":
                migration_paths[version]["lite"] = migration_path
            else:
                raise ValueError(f"Unknown migration file: {migration_path}")

        # A couple of the migrations have a "lite" fallback for those
        # whose deployments don't support certain extensions.
        postgres_extensions = config.LANGGRAPH_POSTGRES_EXTENSIONS
        for version, step_options in migration_paths.items():
            if postgres_extensions not in step_options:
                migration = step_options["standard"]
            else:
                migration = step_options[postgres_extensions]
            if version <= current_version:
                continue
            with open(os.path.join(config.MIGRATIONS_PATH, migration), encoding="utf-8") as f:
                sql = f.read().strip()
            # Execute each statement on its own so that CREATE INDEX CONCURRENTLY
            # is never bundled with other statements into an implicit transaction
            # block (which Postgres forbids). autocommit is enabled on connect().
            for stmt in _split_sql_statements(sql):
                if not _is_executable_statement(stmt):
                    continue
                try:
                    await cur.execute(stmt, prepare=False)
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to apply database migration {version}\n\nStatement: {stmt}"
                    ) from e
            await cur.execute(
                "INSERT INTO schema_migrations (version, dirty) VALUES (%s, %s)",
                (version, False),
            )
            logger.info("Applied database migration", version=version)


async def migrate_vector_index():
    from langgraph_runtime_postgres import store as lg_store

    if not config.STORE_CONFIG:
        return

    config_ = config.STORE_CONFIG
    lg_store.set_store_config(config_)
    logger.info(
        "Setting up vector index",
        store_config=config_,
    )
    await lg_store.setup_vector_index(lg_store.Store())


async def start_pool() -> None:
    global _pg_pool, _stats_task
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WmsxSVJ3PT06NDg2YjZiNzE=

    # start redis
    # Do this first so we can use redis for locking during migrations
    await redis.start_redis()

    _pg_pool = create_pool()
    # confirm connectivity
    await _pg_pool.open(wait=True)

    # Use redis lock to ensure only one server can run migrations at a time
    # We don't use PG advisory locks cause they result in deadlocks with some of the DDL statements run in migrations
    logger.info("Attempting to acquire migration lock")
    try:
        async with redis.get_redis().lock(
            name=LOCK_MIGRATION,
            timeout=60.0,
            blocking_timeout=30.0,
        ):
            await logger.ainfo("Migration lock acquired")
            # Actually run the migrations
            await migrate()
            await migrate_vector_index()
    except LockError:
        await logger.awarning(
            "Failed to acquire migration lock - another server is already running migrations. Continuing."
        )
    except LockNotOwnedError as e:
        await logger.awarning(
            "Error releasing migration lock. %s Continuing.",
            e,
        )
    except Exception as e:
        await logger.aexception("Migration failed", exc_info=e)
        raise
    finally:
        await logger.ainfo("Migration lock released")

    # start stats loop
    _stats_task = asyncio.create_task(stats_loop())


async def stats_loop() -> None:
    if config.IS_EXECUTOR_ENTRYPOINT:
        return
    _pool = _pg_pool
    if _pool is None:
        raise RuntimeError("Postgres pool not initialized")
    while True:
        logger.info("Postgres pool stats", **_pool.pop_stats())
        await asyncio.sleep(config.STATS_INTERVAL_SECS)


async def stop_pool() -> None:
    global _pg_pool, _stats_task

    if threading.current_thread() is not threading.main_thread():
        # Close thread-local connection pools
        if hasattr(_thread_local, "pg_pool"):
            await _thread_local.pg_pool.close()
            del _thread_local.pg_pool
            logger.info(
                "Closed thread-local Postgres connection pool",
                thread_name=threading.current_thread().name,
            )
        return

    # stop stats loop
    if _stats_task is not None:
        _stats_task.cancel("Stopping pool")
        try:
            await _stats_task
        except asyncio.CancelledError:
            pass
        finally:
            _stats_task = None
    # close main pool (thread-local pools are closed when the thread exits)
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None
    # stop redis
    await redis.stop_redis()
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WmsxSVJ3PT06NDg2YjZiNzE=


def pool_stats(
    project_id: str | None,
    revision_id: str | None,
    format: str = "prometheus",
) -> dict[str, dict[str, int]] | list[str]:
    """Get stats for the main Postgres and Redis pool"""

    # will get exception if start_pool hasn't been called yet
    try:
        stats = {
            "postgres": _get_pool().get_stats(),
            "redis": redis.redis_stats(),
        }
    except Exception:
        return {} if format == "json" else []

    if format == "json":
        return stats

    return [
        "# HELP lg_api_pg_pool_max The maximum size of the postgres connection pool.",
        "# TYPE lg_api_pg_pool_max gauge",
        f'lg_api_pg_pool_max{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["postgres"]["pool_max"]}',
        "# HELP lg_api_pg_pool_size Number of connections currently managed by the postgres connection pool (in the pool, given to clients, being prepared)",
        "# TYPE lg_api_pg_pool_size gauge",
        f'lg_api_pg_pool_size{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["postgres"]["pool_size"]}',
        "# HELP lg_api_pg_pool_available Number of connections currently idle in the postgres connection pool",
        "# TYPE lg_api_pg_pool_available gauge",
        f'lg_api_pg_pool_available{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["postgres"]["pool_available"]}',
        "# HELP lg_api_pg_pool_requests_queued Number of postgres connection requests queued because a postgres connection wasn't immediately available in the pool",
        "# TYPE lg_api_pg_pool_requests_queued counter",
        f'lg_api_pg_pool_requests_queued{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["postgres"].get("requests_queued", 0)}',
        "# HELP lg_api_pg_pool_requests_errors Number of postgres connection requests resulting in an error (timeouts, queue full...)",
        "# TYPE lg_api_pg_pool_requests_errors counter",
        f'lg_api_pg_pool_requests_errors{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["postgres"].get("requests_errors", 0)}',
        "# HELP lg_api_redis_pool_available Number of connections currently idle in the redis connection pool",
        "# TYPE lg_api_redis_pool_available gauge",
        f'lg_api_redis_pool_available{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["redis"]["idle_connections"]}',
        "# HELP lg_api_redis_pool_size Number of connections currently in use in the redis connection pool",
        "# TYPE lg_api_redis_pool_size gauge",
        f'lg_api_redis_pool_size{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["redis"]["in_use_connections"]}',
        "# HELP lg_api_redis_pool_max The maximum size of the redis connection pool.",
        "# TYPE lg_api_redis_pool_max gauge",
        f'lg_api_redis_pool_max{{project_id="{project_id}", revision_id="{revision_id}"}} {stats["redis"]["max_connections"]}',
    ]


def _get_pool() -> AsyncConnectionPool[AsyncConnection[DictRow]]:
    if threading.current_thread() is not threading.main_thread():
        return _thread_local.pg_pool
    elif _pg_pool is None:
        raise RuntimeError("Postgres pool not initialized")
    else:
        return _pg_pool


__all__ = [
    "start_pool",
    "stop_pool",
    "connect",
    "pool_stats",
]
