"""Monitoring logic for detecting and recording long-running PostgreSQL queries."""


import asyncio
import typing

import redis.exceptions
import structlog

from langgraph_runtime_postgres.database import connect
from langgraph_runtime_postgres.redis import (
    LOCK_LONG_QUERY_MONITOR,
    STRING_LONG_QUERY_LAST_SCAN,
    get_redis,
)
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YmpCblp3PT06MzJmYmFmOWU=

logger = structlog.stdlib.get_logger(__name__)


async def long_query_monitor_loop():
    """Periodically scan for and record long-running PostgreSQL queries.

    This monitoring loop helps detect hanging queries and connection issues
    by scanning pg_stat_activity for queries running longer than the configured threshold.
    """

    threshold_minutes = 5
    scan_interval_seconds = 600

    await logger.ainfo(
        f"Starting long query monitor with {threshold_minutes}min threshold, scanning every {scan_interval_seconds}s",
        threshold_minutes=threshold_minutes,
        scan_interval_seconds=scan_interval_seconds,
    )

    loop = asyncio.get_running_loop()
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YmpCblp3PT06MzJmYmFmOWU=

    while True:
        await asyncio.sleep(scan_interval_seconds)
        try:
            # Check if a scan was recently performed by another replica (before acquiring lock)
            recent_threshold_seconds = scan_interval_seconds // 2
            last_scan = await get_redis().get(STRING_LONG_QUERY_LAST_SCAN)
            if last_scan:
                await logger.adebug(
                    "Long query scan recently performed by another replica, skipping",
                    last_scan=last_scan.decode() if last_scan else None,
                )
                continue

            # Acquire lock to coordinate between replicas
            try:
                redis_client = get_redis()
                async with redis_client.lock(
                    name=LOCK_LONG_QUERY_MONITOR,
                    timeout=30.0,  # Hold lock for max 30s
                    blocking_timeout=1.0,  # Give up if can't acquire in 1s
                ):
                    # Double-check pattern after acquiring lock
                    last_scan = await redis_client.get(STRING_LONG_QUERY_LAST_SCAN)
                    if last_scan:
                        await logger.adebug(
                            "Long query scan recently performed by another replica (after lock), skipping",
                            last_scan=last_scan.decode() if last_scan else None,
                        )
                        continue

                    # Perform the scan
                    async with connect() as conn:
                        scan_start = loop.time()
                        long_queries = await _get_long_running_queries(
                            conn, threshold_minutes
                        )

                        # Mark that we performed a scan
                        await redis_client.set(
                            STRING_LONG_QUERY_LAST_SCAN,
                            "1",
                            ex=recent_threshold_seconds,
                        )

                        if long_queries:
                            # Log all long queries
                            await logger.ainfo(
                                f"Found {len(long_queries)} long-running queries",
                                count=len(long_queries),
                                threshold_minutes=threshold_minutes,
                                queries=[
                                    {
                                        "pid": q["pid"],
                                        "duration_minutes": round(
                                            q["duration_minutes"], 2
                                        ),
                                        "state": q["state"],
                                        "query_preview": q["query"][:100] + "..."
                                        if len(q["query"]) > 100
                                        else q["query"],
                                        "wait_event": f"{q['wait_event_type']}/{q['wait_event']}"
                                        if q["wait_event_type"]
                                        else None,
                                    }
                                    for q in long_queries
                                ],
                                scan_duration=loop.time() - scan_start,
                            )
                        else:
                            await logger.adebug("No long-running queries found")

            except redis.exceptions.LockError:
                await logger.adebug("Skipping long query scan; lock not available.")
                continue
            except redis.exceptions.LockNotOwnedError as e:
                await logger.adebug("Failed to release lock: %s", e)
                continue

        except Exception as exc:
            await logger.awarning(
                "Long query monitor iteration failed. Continuing...", exc_info=exc
            )


async def _get_long_running_queries(
    conn, threshold_minutes: int
) -> list[dict[str, typing.Any]]:
    """Query PostgreSQL for long-running queries."""
    query = """
    SELECT
        pid,
        now() - pg_stat_activity.query_start AS duration,
        query_start,
        state,
        query,
        application_name,
        client_addr,
        client_port,
        usename,
        datname,
        wait_event_type,
        wait_event,
        backend_type,
        -- Additional context for debugging
        xact_start,
        state_change,
        backend_start
    FROM pg_stat_activity
    WHERE
        state != 'idle'
        AND query_start IS NOT NULL
        AND now() - pg_stat_activity.query_start > interval '%s minutes'
        AND pid != pg_backend_pid()  -- Exclude this monitoring query
        AND query NOT LIKE '%%pg_stat_activity%%'  -- Exclude monitoring queries
        AND query NOT LIKE '%%pg_reload_conf%%'  -- Exclude config reloads
        AND backend_type != 'autovacuum launcher'  -- Exclude autovacuum launcher
        AND backend_type != 'autovacuum worker'  -- Exclude autovacuum workers
        AND query NOT LIKE 'autovacuum%%'  -- Exclude any autovacuum queries
    ORDER BY query_start ASC;
    """

    try:
        async with await conn.execute(query, [threshold_minutes]) as cur:
            rows = await cur.fetchall()
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YmpCblp3PT06MzJmYmFmOWU=

        results = []
        for row in rows:
            # Convert to dict and handle datetime serialization
            result = dict(row)
            result["duration_seconds"] = result["duration"].total_seconds()
            result["duration_minutes"] = result["duration_seconds"] / 60

            # Convert datetime objects to ISO strings for logging
            for key in ["query_start", "xact_start", "state_change", "backend_start"]:
                if result[key]:
                    result[key] = result[key].isoformat()

            # Remove the timedelta object since we have duration_seconds
            del result["duration"]
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YmpCblp3PT06MzJmYmFmOWU=

            results.append(result)

        return results

    except Exception as e:
        await logger.aexception("Failed to query long-running queries", exc_info=e)
        return []
