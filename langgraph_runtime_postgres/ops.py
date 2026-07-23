
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime
from typing import (  # noqa: UP035
    TYPE_CHECKING,
    Any,
    AsyncContextManager,
    Literal,
    NamedTuple,
    cast,
)
from uuid import UUID, uuid4

import orjson
import psycopg.errors
import redis.exceptions
import structlog
from croniter import croniter
from langgraph.checkpoint.serde.jsonplus import _msgpack_ext_hook_to_json
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.pregel.debug import CheckpointPayload
from langgraph.types import StateSnapshot
from langgraph_api import store as api_store
from langgraph_api.asyncio import SimpleTaskGroup, ValueEvent, create_task
from langgraph_api.auth.custom import handle_event
from langgraph_api.command import map_cmd
from langgraph_api.config import (
    BG_JOB_HEARTBEAT,
    BG_JOB_INTERVAL,
    BG_JOB_TIMEOUT_SECS,
    FF_LOG_DROPPED_EVENTS,
    FF_LOG_QUERY_AND_PARAMS,
    MAX_STREAM_CHUNK_SIZE_BYTES,
    REDIS_CLUSTER,
    RESUMABLE_STREAM_TTL_SECONDS,
    RUN_STATS_CACHE_SECONDS,
    THREAD_TTL,
    ThreadTTLConfig,
)
from langgraph_api.errors import UserInterrupt, UserRollback
from langgraph_api.graph import (
    GRAPHS,
    assert_graph_exists,
    get_assistant_id,
    get_graph,
    graph_exists,
)
from langgraph_api.logging import LOG_LEVEL_DEBUG
from langgraph_api.schema import (
    Assistant,
    AssistantSelectField,
    Checkpoint,
    Config,
    Context,
    Cron,
    CronSelectField,
    IfNotExists,
    MetadataInput,
    MetadataValue,
    MultitaskStrategy,
    OnConflictBehavior,
    QueueStats,
    Run,
    RunSelectField,
    RunStatus,
    StreamMode,
    Thread,
    ThreadMessagesResponse,
    ThreadSelectField,
    ThreadStatus,
    ThreadStreamMode,
    ThreadUpdateResponse,
)
from langgraph_api.serde import json_dumpb, json_loads
from langgraph_api.state import patch_interrupt, state_snapshot_to_thread_state
from langgraph_api.utils import fetchone, get_auth_ctx, next_cron_date, uuid7
from langgraph_api.utils.stream_codec import (
    STREAM_CODEC,
    decode_stream_message,
)
from langgraph_sdk import Auth
from psycopg import AsyncConnection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb
from redis.asyncio.client import PubSub
from starlette.exceptions import HTTPException
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzAwNFF3PT06ZGEwODJkZTg=

from langgraph_runtime_postgres.checkpoint import Checkpointer
from langgraph_runtime_postgres.database import connect
from app.utils.thread_message_utils import merge_messages_from_snapshots
from langgraph_runtime_postgres.redis import (
    CHANNEL_RUN_CONTROL,
    CHANNEL_RUN_CONTROL_OLD,
    CHANNEL_RUN_STREAM,
    CHANNEL_RUN_STREAM_OLD,
    LIST_RUN_QUEUE,
    LOCK_RUN_STATS,
    LOCK_RUN_SWEEP,
    LOCK_THREAD_SWEEP,
    RUN_STATUS_STRING,
    STREAM_THREAD_CACHE,
    STRING_RUN_ATTEMPT,
    STRING_RUN_RUNNING,
    STRING_RUN_STATS_CACHE,
    STRING_THREAD_LAST_SWEEP,
    get_pubsub,
    get_redis,
)
from langgraph_runtime_postgres.retry import RETRIABLE_EXCEPTIONS, RetryableException

logger = structlog.stdlib.get_logger(__name__)

StreamHandler = PubSub

WAIT_TIMEOUT = 5  # seconds, set to DRAIN_TIMEOUT when switching to "drain" state
WAIT_LESS_TIMEOUT = 0.1  # seconds, shorter wait after receiving interrupt/rollback
DRAIN_TIMEOUT = 0.01  # drain queue, but don't wait for more

if TYPE_CHECKING:
    connect = cast(Callable[[], AsyncContextManager[AsyncConnection[DictRow]]], connect)  # type: ignore[invalid-assignment]


def _snapshot_defaults():
    # Support older versions of langgraph
    if not hasattr(StateSnapshot, "interrupts"):
        return {}
    return {"interrupts": tuple()}


# _message_content_length and merge_messages_from_snapshots moved to
# langgraph_runtime_postgres.message_utils for easier unit testing.


def _compare_stream_ids(stream_id_a: bytes, stream_id_b: bytes) -> int:
    """Compare Redis stream IDs in format 'ms-seq'.

    Returns:
        -1 if stream_id_a < stream_id_b
         0 if stream_id_a == stream_id_b
         1 if stream_id_a > stream_id_b
    """
    # Parse and compare as tuples of integers
    a_parts = tuple(map(int, stream_id_a.split(b"-", 1)))
    b_parts = tuple(map(int, stream_id_b.split(b"-", 1)))
    return (a_parts > b_parts) - (a_parts < b_parts)


class TTLSweepResult(NamedTuple):
    expired: int
    deleted: int


class Authenticated:
    resource: Literal["threads", "crons", "assistants"]

    @classmethod
    def _context(
        cls,
        ctx: Auth.types.BaseAuthContext | None,
        action: Literal["create", "read", "update", "delete", "search", "create_run"],
    ) -> Auth.types.AuthContext | None:
        if not ctx:
            return None
        return Auth.types.AuthContext(
            user=ctx.user,
            permissions=ctx.permissions,
            resource=cls.resource,
            action=action,
        )

    @classmethod
    async def handle_event(
        cls,
        ctx: Auth.types.BaseAuthContext | None,
        action: Literal["create", "read", "update", "delete", "search", "create_run"],
        value: Any,
    ) -> Auth.types.FilterType | None:
        ctx = ctx or get_auth_ctx()
        if not ctx:
            return None
        return await handle_event(cls._context(ctx, action), value)


class Assistants(Authenticated):
    resource = "assistants"

    @staticmethod
    async def search(
        conn: AsyncConnection[DictRow],
        *,
        graph_id: str | None,
        metadata: MetadataInput,
        limit: int,
        offset: int,
        sort_by: str | None = None,
        sort_order: str | None = None,
        select: list[AssistantSelectField] | None = None,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> tuple[AsyncIterator[Assistant], int | None]:
        metadata = metadata if metadata is not None else {}
        filters = await Assistants.handle_event(
            ctx,
            "search",
            Auth.types.AssistantsSearch(
                graph_id=graph_id, metadata=metadata, limit=limit, offset=offset
            ),
        )
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzAwNFF3PT06ZGEwODJkZTg=

        # Base query for filtering assistants
        query = """WITH filtered_assistants AS (
            SELECT * FROM assistant
            WHERE graph_id = ANY(%(graph_ids)s) AND metadata @> %(metadata)s"""

        params = {"graph_ids": list(GRAPHS.keys()), "metadata": Jsonb(metadata)}
        if graph_id:
            assert_graph_exists(graph_id)

            query += " AND graph_id = %(graph_id)s"
            params["graph_id"] = graph_id

        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="assistant",
        )
        if filter_params:
            query += filter_clause
            params.update(filter_params)

        selected_columns = ", ".join(select) if select else "*"

        query += f""")
        SELECT {selected_columns} FROM filtered_assistants
            """
        # Add sorting if specified
        sort_by = sort_by.lower() if sort_by else None
        if sort_by and sort_by in (
            "assistant_id",
            "graph_id",
            "name",
            "created_at",
            "updated_at",
        ):
            sort_direction = (
                "ASC" if sort_order and sort_order.upper() == "ASC" else "DESC"
            )
            # Use case-insensitive sorting for string fields
            if sort_by in ["name", "graph_id"]:
                query += f" ORDER BY LOWER({sort_by}) {sort_direction}"
            else:
                query += f" ORDER BY {sort_by} {sort_direction}"
        else:
            # Default sorting
            query += " ORDER BY created_at DESC"

        query += " LIMIT %(limit)s OFFSET %(offset)s"
        internal_limit = limit + 1
        params["limit"] = internal_limit
        params["offset"] = offset

        # Execute the main query
        cur = await conn.execute(query, params, binary=True)
        results = await cur.fetchall()

        if len(results) <= limit:
            cursor = None
        else:
            cursor = offset + limit
            results = results[:limit]

        async def generate_results():
            for row in results:
                yield row

        return generate_results(), cursor

    @staticmethod
    async def get(
        conn: AsyncConnection[DictRow],
        assistant_id: UUID,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[Assistant]:
        filters = await Assistants.handle_event(
            ctx,
            "read",
            Auth.types.AssistantsRead(assistant_id=assistant_id),
        )

        query = "SELECT * FROM assistant WHERE graph_id = ANY(%(graph_id)s) AND assistant_id = %(assistant_id)s"
        params = {"graph_id": list(GRAPHS.keys()), "assistant_id": assistant_id}

        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="assistant",
        )
        if filter_params:
            query += filter_clause
            params.update(filter_params)

        cur = await conn.execute(query, params, binary=True)
        return (
            row async for row in cur if graph_exists(cast(DictRow, row)["graph_id"])
        )

    @staticmethod
    async def put(
        conn: AsyncConnection[DictRow],
        assistant_id: UUID,
        *,
        graph_id: str,
        config: Config,
        context: Context,
        metadata: MetadataInput,
        if_exists: OnConflictBehavior,
        name: str,
        description: str | None = None,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[Assistant]:
        """Insert an assistant.

        Args:
            conn: The database connection.
            assistant_id: The assistant ID.
            graph_id: The graph ID.
            config: The assistant config.
            context: The static context of the assistant.
            metadata: The assistant metadata.
            if_exists: "do_nothing" or "raise"
            name: The name of the assistant.
            description: The description of the assistant.
            ctx: The authentication context.

        Returns:
            return the assistant model if inserted.
        """
        metadata = metadata if metadata is not None else {}
        config = config if config is not None else {}

        if config.get("configurable") and context:
            raise HTTPException(
                status_code=400,
                detail="Cannot specify both configurable and context. Prefer setting context alone. Context was introduced in LangGraph 0.6.0 and is the long term planned replacement for configurable.",
            )

        # Keep config and context up to date with one another
        if config.get("configurable"):
            context = config["configurable"]
        elif context:
            config["configurable"] = context

        assert_graph_exists(graph_id)
        filters = await Assistants.handle_event(
            ctx,
            "create",
            Auth.types.AssistantsCreate(
                assistant_id=assistant_id,
                graph_id=graph_id,
                config=config,
                context=context,
                metadata=metadata,
                name=name,
                description=description,
            ),
        )

        query = """WITH inserted_assistant as (
            INSERT INTO assistant (assistant_id, graph_id, config, context, metadata, name, description)
            VALUES (%(assistant_id)s, %(graph_id)s, %(config)s, %(context)s, %(metadata)s, %(name)s, %(description)s)
            ON CONFLICT (assistant_id) DO NOTHING
            RETURNING *
        ),
        inserted_version as (
            INSERT INTO assistant_versions (assistant_id, graph_id, config, context, metadata, version, name, description)
            SELECT assistant_id, graph_id, config, context, metadata, 1 as version, name, description
            FROM inserted_assistant
            ON CONFLICT (assistant_id, version) DO NOTHING
        )
        SELECT * FROM inserted_assistant
        """  # If Alice makes assistant abcd, and Bob tries to do the same, Alice will always have a version 1 existing, so this query will
        # do nothing
        params = {
            "assistant_id": assistant_id,
            "graph_id": graph_id,
            "config": Jsonb(config),
            "context": Jsonb(context),
            "metadata": Jsonb(metadata),
            "name": name,
            "description": description,
        }
        if if_exists == "do_nothing":
            filter_clause, filter_params = _build_filter_query(
                filters=filters,
            )
            # return the row if it already exists
            where_clause = "WHERE assistant_id = (%(assistant_id)s)"
            if filter_params:
                params.update(filter_params)
                where_clause += filter_clause

            query += f"""
            UNION ALL
            SELECT * FROM assistant
            {where_clause}
            LIMIT 1;
            """
        elif if_exists == "raise":
            # we'll raise downstream if there is a conflict
            pass
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzAwNFF3PT06ZGEwODJkZTg=

        cur = await conn.execute(
            query,
            params,
            binary=True,
        )
        return (row async for row in cur)

    @staticmethod
    async def patch(
        conn: AsyncConnection[DictRow],
        assistant_id: UUID,
        *,
        config: dict | None = None,
        context: Context | None = None,
        graph_id: str | None = None,
        metadata: MetadataInput | None = None,
        name: str | None = None,
        description: str | None = None,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[Assistant]:
        """Update an assistant.

        Args:
            conn: The database connection.
            assistant_id: The assistant ID.
            graph_id: The graph ID.
            config: The assistant config.
            context: The static context of the assistant.
            metadata: The assistant metadata.
            name: The assistant name.
            description: The assistant description.
            ctx: The authentication context.

        Returns:
            return the updated assistant model.
        """
        metadata = metadata if metadata is not None else {}
        config = config if config is not None else {}

        if config.get("configurable") and context:
            raise HTTPException(
                status_code=400,
                detail="Cannot specify both configurable and context. Prefer setting context alone. Context was introduced in LangGraph 0.6.0 and is the long term planned replacement for configurable.",
            )

        # Keep config and context up to date with one another
        if config.get("configurable"):
            context = config["configurable"]
        elif context:
            config["configurable"] = context

        filters = await Assistants.handle_event(
            ctx,
            "update",
            Auth.types.AssistantsUpdate(
                assistant_id=assistant_id,
                graph_id=graph_id,
                config=config,
                context=context,
                metadata=metadata,
                name=name,
            ),
        )
        args = {
            "assistant_id": assistant_id,
            "graph_id": graph_id,
            "config": Jsonb(config) if config is not None else None,
            "context": Jsonb(context) if context is not None else None,
            "metadata": Jsonb(metadata) if metadata is not None else None,
            "name": name,
            "description": description,
        }

        update_fields = []
        if filters:
            where_clause, filter_params = _build_filter_query(
                filters=filters,
                table_alias="assistant",
            )
            args.update(filter_params)
        else:
            where_clause = ""
        if graph_id is not None:
            assert_graph_exists(graph_id)
            update_fields.append("graph_id = %(graph_id)s")
        if config:
            update_fields.append("config = %(config)s")
        if context:
            update_fields.append("context = %(context)s")
        if metadata:
            update_fields.append("metadata = assistant.metadata || %(metadata)s")
        if name is not None:
            update_fields.append("name = %(name)s")
        if description is not None:
            update_fields.append("description = %(description)s")

        update_sql = ""
        if update_fields:
            update_sql = ", " + ", ".join(update_fields)
        query = f"""
            WITH current_assistant AS (
                SELECT * FROM assistant WHERE assistant_id = %(assistant_id)s{where_clause}
            ),
            inserted_version AS (
                INSERT INTO assistant_versions (assistant_id, graph_id, config, context, metadata, version, name, description)
                SELECT
                    current_assistant.assistant_id,
                    COALESCE(%(graph_id)s, current_assistant.graph_id),
                    COALESCE(%(config)s, current_assistant.config),
                    COALESCE(%(context)s, current_assistant.context),
                    CASE
                        WHEN %(metadata)s IS NULL THEN current_assistant.metadata
                        ELSE current_assistant.metadata || %(metadata)s::jsonb
                    END,
                    COALESCE((SELECT MAX(version) FROM assistant_versions WHERE assistant_id = %(assistant_id)s) + 1, 1),
                    COALESCE(%(name)s, current_assistant.name),
                    COALESCE(%(description)s, current_assistant.description)
                FROM current_assistant
                RETURNING *
            )
            UPDATE assistant
            SET version = inserted_version.version,
                updated_at = inserted_version.created_at
                {update_sql}
            FROM inserted_version
            WHERE assistant.assistant_id = %(assistant_id)s
            RETURNING *
        """

        cur = await conn.execute(query, args, binary=True)
        return (row async for row in cur)

    @staticmethod
    async def delete(
        conn: AsyncConnection[DictRow],
        assistant_id: UUID,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[UUID]:
        """Delete an assistant by ID."""
        filters = await Assistants.handle_event(
            ctx,
            "delete",
            Auth.types.AssistantsDelete(
                assistant_id=assistant_id,
            ),
        )
        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="assistant",
        )
        params = {"assistant_id": assistant_id, **filter_params}

        cur = await conn.execute(
            f"""
            DELETE FROM assistant
            WHERE assistant_id = %(assistant_id)s{filter_clause}
            RETURNING assistant_id
            """,
            params,
            binary=True,
        )

        return (row["assistant_id"] async for row in cur)

    @staticmethod
    async def set_latest(
        conn: AsyncConnection,
        assistant_id: UUID,
        version: int,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[Assistant]:
        filters = await Assistants.handle_event(
            ctx,
            "update",
            Auth.types.AssistantsUpdate(
                assistant_id=assistant_id,
                version=version,
            ),
        )
        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="assistant",
        )
        params = {"assistant_id": assistant_id, "version": version, **filter_params}
        assistants_join = ""
        if filter_clause:
            assistants_join = "JOIN assistant ON assistant.assistant_id = assistant_versions.assistant_id"

        query = f"""
            WITH versioned_assistant AS (
                SELECT assistant_versions.* FROM assistant_versions
                {assistants_join}
                WHERE assistant_versions.assistant_id = %(assistant_id)s AND assistant_versions.version = %(version)s{filter_clause}
            )

            UPDATE assistant
            SET
                config = versioned_assistant.config,
                context = versioned_assistant.context,
                metadata = versioned_assistant.metadata,
                version = versioned_assistant.version,
                name = versioned_assistant.name,
                description = versioned_assistant.description
            FROM versioned_assistant
            WHERE assistant.assistant_id = versioned_assistant.assistant_id
            RETURNING assistant.*;
        """
        cur = await conn.execute(query, params, binary=True)
        return (
            row async for row in cur if graph_exists(cast(DictRow, row)["graph_id"])
        )

    @staticmethod
    async def get_versions(
        conn: AsyncConnection[DictRow],
        assistant_id: UUID,
        metadata: MetadataInput,
        limit: int,
        offset: int,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[Assistant]:
        """Get all versions of an assistant."""
        metadata = metadata if metadata is not None else {}
        filters = await Assistants.handle_event(
            ctx,
            "search",
            Auth.types.AssistantsRead(assistant_id=assistant_id, metadata=metadata),
        )
        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="assistant",
        )
        params = {
            "assistant_id": assistant_id,
            "metadata": Jsonb(metadata),
            "limit": limit,
            "offset": offset,
            **filter_params,
        }
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YzAwNFF3PT06ZGEwODJkZTg=

        join_clause = "" if not filter_params else "JOIN assistant USING (assistant_id)"

        query = f"""SELECT assistant_versions.* FROM assistant_versions {join_clause}
        WHERE assistant_id = %(assistant_id)s AND assistant_versions.metadata @> %(metadata)s{filter_clause}
        ORDER BY assistant_versions.version DESC LIMIT %(limit)s OFFSET %(offset)s;"""

        cur = await conn.execute(query, params, binary=True)
        return (row async for row in cur)

    @staticmethod
    async def count(
        conn: AsyncConnection[DictRow],
        *,
        graph_id: str | None = None,
        metadata: MetadataInput = None,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> int:
        """Get count of assistants."""
        metadata = metadata if metadata is not None else {}
        filters = await Assistants.handle_event(
            ctx,
            "search",
            Auth.types.AssistantsSearch(
                graph_id=graph_id, metadata=metadata, limit=0, offset=0
            ),
        )
        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="assistant",
        )

        query = "SELECT COUNT(*) as count FROM assistant WHERE 1=1"
        params = {**filter_params}

        if graph_id:
            query += " AND graph_id = %(graph_id)s"
            params["graph_id"] = graph_id

        if metadata:
            query += " AND metadata @> %(metadata)s"
            params["metadata"] = Jsonb(metadata)

        if filter_clause:
            query += " " + filter_clause

        cur = await conn.execute(query, params)
        row = await cur.fetchone()
        return row["count"] if row else 0


class Threads(Authenticated):
    resource = "threads"

    @staticmethod
    async def sweep_ttl(
        conn: AsyncConnection[DictRow],
        *,
        limit: int | None = None,
        batch_size: int = 100,
    ) -> TTLSweepResult:
        """Sweep threads based on TTL configuration.

        Currently implements the 'delete' TTL strategy, which deletes entire threads
        that have reached their expires_at time.

        Args:
            conn: Database connection
            limit: Maximum number of threads to process in one sweep
            batch_size: Batch size for bulk delete operations

        Returns:
            tuple: (threads_processed, threads_deleted)
        """
        # Use half the sweep interval as the "recent" threshold
        thread_ttl_config = THREAD_TTL or {}
        sweep_interval_minutes = thread_ttl_config.get("sweep_interval_minutes", 5)
        recent_threshold_seconds = int((sweep_interval_minutes * 60) // 2)

        # Check if a sweep was recently performed by another replica (before acquiring lock)
        last_sweep = await get_redis().get(STRING_THREAD_LAST_SWEEP)
        if last_sweep:
            await logger.adebug(
                "Thread TTL sweep recently performed by another replica, skipping",
                last_sweep=last_sweep.decode() if last_sweep else None,
            )
            return TTLSweepResult(0, 0)

        # Hold for a max of 240s; give up if cannot acquire in 1s
        try:
            redis_client = get_redis()
            async with redis_client.lock(
                name=LOCK_THREAD_SWEEP,
                timeout=240.0,
                blocking_timeout=1.0,
            ):
                # Check again after acquiring lock (double-check pattern)
                last_sweep = await redis_client.get(STRING_THREAD_LAST_SWEEP)
                if last_sweep:
                    await logger.adebug(
                        "Thread TTL sweep recently performed by another replica (after lock), skipping",
                        last_sweep=last_sweep.decode() if last_sweep else None,
                    )
                    return TTLSweepResult(0, 0)

                limit_str = "" if limit is None else "LIMIT %(limit)s"
                params = {"limit": limit} if limit is not None else {}
                query = f"""
                SELECT thread_id, strategy, ttl_minutes
                FROM thread_ttl
                WHERE expires_at < NOW() AT TIME ZONE 'UTC'
                {limit_str}
                FOR UPDATE SKIP LOCKED
                """
                result = await conn.execute(query, params)
                to_sweep = defaultdict(list)
                async for row in result:
                    strategy = row["strategy"]
                    thread_ids = to_sweep[strategy]
                    thread_ids.append((row["thread_id"], row["ttl_minutes"]))
                await redis_client.set(
                    STRING_THREAD_LAST_SWEEP,
                    "1",
                    ex=recent_threshold_seconds,
                )
                if not to_sweep:
                    return TTLSweepResult(0, 0)

                deleted_count = await Threads._delete_bulk(
                    conn, [t[0] for t in to_sweep["delete"]], batch_size=batch_size
                )

                return TTLSweepResult(len(to_sweep["delete"]), deleted_count)
        except redis.exceptions.LockError as e:
            await logger.adebug("Skipping thread sweep; lock not available.", error=e)
            return TTLSweepResult(0, 0)
        except redis.exceptions.LockNotOwnedError as e:
            await logger.adebug("Failed to release lock: %s", e)
            return TTLSweepResult(0, 0)

    @staticmethod
    async def search(
        conn: AsyncConnection[DictRow],
        *,
        ids: list[str] | list[UUID] | None = None,
        metadata: MetadataInput,
        values: MetadataInput,
        status: ThreadStatus | None,
        limit: int,
        offset: int,
        sort_by: str | None = None,
        sort_order: str | None = None,
        select: list[ThreadSelectField] | None = None,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> tuple[AsyncIterator[Thread], int | None]:
        metadata = metadata if metadata is not None else {}
        values = values if values is not None else {}
        indexed = ("owner",)

        filters = await Threads.handle_event(
            ctx,
            "search",
            Auth.types.ThreadsSearch(
                metadata=metadata,
                values=values,
                status=status,
                limit=limit,
                offset=offset,
            ),
        )

        if filters:
            # Small optimization. Metadata and $eq filters are the same (@>) operator
            # Merge them to avoid duplicate queries. It's an AND condition anyway.
            equality = {
                k: v
                for k, v in filters.items()
                if not isinstance(v, dict) or "$eq" in v
            }
            metadata = {**metadata, **equality}
            filters = {k: v for k, v in (filters or {}).items() if k not in equality}

        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="thread",
            prefix="",
        )

        internal_limit = limit + 1
        params = {"limit": internal_limit, "offset": offset}
        where_clauses = []
        if ids:
            # Filter by a list of thread IDs
            where_clauses.append("thread_id = ANY(%(ids)s::uuid[])")
            params["ids"] = list(ids)
        if values:
            where_clauses.append("values @> %(values)s")
            params["values"] = Jsonb(values)
        if status:
            where_clauses.append("status = %(status)s")
            params["status"] = status
        if metadata:
            for k in indexed:
                if k in metadata and metadata[k] is not None:
                    # The index is only defined for non-null values
                    # If we don't include the `metadata ? '{k}' check, the query planer
                    # will not use this index (it will miscalculate the cost)
                    where_clauses.append(f"metadata ? '{k}'")
                    where_clauses.append(f"metadata->>'{k}' = %({k}_indexed_key)s")
                    params[f"{k}_indexed_key"] = metadata[k]
            gin_metadata = {k: v for k, v in metadata.items() if k not in indexed}
            # Only need to additionally filter by other metadata if there are other values to filter by
            # If this is present, the planner will likely skip the btree index above and have more
            # expensive queries (pull all matching threads first before excluding)
            if gin_metadata:
                where_clauses.append("metadata @> %(metadata)s")
                params["metadata"] = Jsonb(gin_metadata)
        if filter_clause:
            where_clauses.append(filter_clause)
            params.update(filter_params)

        selected_columns = ", ".join(select) if select else "*"
        where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        allowed_columns = ["thread_id", "created_at", "updated_at", "status"]
        if sort_by in allowed_columns:
            if sort_order is None:
                sort_direction = "DESC"
            else:
                sort_direction = sort_order.upper()
                if sort_direction not in ("ASC", "DESC"):
                    raise HTTPException(
                        status_code=422,
                        detail=f"Invalid sort_order: {sort_order}. Expected 'ASC' or 'DESC'",
                    )
            second_by = ", thread_id DESC" if sort_by != "thread_id" else ""
            order_by = f" ORDER BY {sort_by} {sort_direction}{second_by}"
        elif sort_by:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid sort_by: {sort_by}. Expected one of {allowed_columns}",
            )
        else:
            order_by = " ORDER BY updated_at DESC, thread_id DESC"
        query = f"""SELECT
            {selected_columns}
            FROM thread
            {where_clause}
            {order_by}
            LIMIT %(limit)s OFFSET %(offset)s"""

        cur = await conn.execute(query, params, binary=True)
        first_row = await cur.fetchone()
        if first_row is None:

            async def _empty():
                if False:
                    yield None

            return _empty(), 0
        rows = [first_row] if first_row else []
        async for r in cur:
            rows.append(r)
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
        cursor = offset + limit if has_more else None
        first_row = rows[0] if rows else None

        async def _row_iter():
            for row in rows:
                yield row

        return _row_iter(), cursor

    @staticmethod
    async def get(
        conn: AsyncConnection[DictRow],
        thread_id: UUID,
        ctx: Auth.types.BaseAuthContext | None = None,
        filters: Auth.types.FilterType | None = None,
    ) -> AsyncIterator[Thread]:
        get_filters = await Threads.handle_event(
            ctx,
            "read",
            Auth.types.ThreadsRead(thread_id=thread_id),
        )
        # The parent filters, if provided, take precedence
        # since this is called from e.g., update
        # and presumably you may want to have more restrictive
        # filters on writes than on reads
        filters = {**(get_filters or {}), **(filters or {})}
        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="thread",
        )
        params = {"thread_id": thread_id, **filter_params}
        query = f"SELECT * FROM thread WHERE thread_id = %(thread_id)s{filter_clause}"
        cur = await conn.execute(query, params, binary=True)
        return (row async for row in cur)

    @staticmethod
    async def put(
        conn: AsyncConnection[DictRow],
        thread_id: UUID,
        *,
        metadata: MetadataInput,
        if_exists: OnConflictBehavior,
        ttl: ThreadTTLConfig | None = None,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[Thread]:
        """Insert or update a thread."""
        metadata = metadata if metadata is not None else {}
        filters = await Threads.handle_event(
            ctx,
            "create",
            Auth.types.ThreadsCreate(
                thread_id=thread_id, metadata=metadata, if_exists=if_exists
            ),
        )

        ttl_config = ttl if ttl is not None else THREAD_TTL
        ttl_interval_minutes = None
        ttl_strategy = None

        if ttl_config:
            if (
                ttl_strategy := ttl_config.get("strategy", "delete")
            ) and ttl_strategy != "delete":
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid thread TTL strategy: {ttl_strategy}. Expected one of ['delete']",
                )
            ttl_interval_minutes = ttl_config.get(
                "ttl", ttl_config.get("default_ttl", None)
            )
            if ttl_interval_minutes is None:
                ttl_strategy = None

        # Build the query with TTL support, using jsonb_set for the expires_at field
        query = """WITH inserted_thread as (
            INSERT INTO thread (thread_id, metadata)
            values (%(thread_id)s, %(metadata)s)
            ON CONFLICT (thread_id) DO NOTHING
            RETURNING *
        )
        """
        params = {
            "thread_id": thread_id,
            "metadata": Jsonb(metadata),
        }
        # Add TTL entry in the thread_ttl table if ttl_interval is provided
        if ttl_interval_minutes is not None:
            query += """,
            inserted_ttl as (
                INSERT INTO thread_ttl (thread_id, strategy, ttl_minutes)
                VALUES (
                    %(thread_id)s,
                    %(ttl_strategy)s,
                    %(ttl_interval)s
                )
                ON CONFLICT (thread_id, strategy) DO UPDATE SET
                    ttl_minutes = %(ttl_interval)s,
                    created_at = NOW() AT TIME ZONE 'UTC'
                RETURNING *
            )"""
            params.update(
                {
                    "ttl_interval": ttl_interval_minutes,
                    "ttl_strategy": ttl_strategy,
                }
            )

        query += """
        SELECT * FROM inserted_thread
        """

        if if_exists == "do_nothing":
            # return the row if it already exists
            filter_clause, filter_params = _build_filter_query(
                filters=filters, metadata_field="metadata"
            )
            where_clause = "WHERE thread_id = %(thread_id)s"
            if filter_params:
                params.update(filter_params)
                where_clause += filter_clause

            query += f"""
            UNION ALL
            SELECT * FROM thread
            {where_clause}
            LIMIT 1;
            """
        elif if_exists == "raise":
            # we'll raise downstream if there is a conflict
            pass

        cur = await conn.execute(query, params, binary=True)
        return (row async for row in cur)

    @staticmethod
    async def patch(
        conn: AsyncConnection[DictRow],
        thread_id: UUID,
        *,
        metadata: MetadataValue,
        ttl: ThreadTTLConfig | None = None,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[Thread]:
        metadata = metadata if metadata is not None else {}
        filters = await Threads.handle_event(
            ctx,
            "update",
            Auth.types.ThreadsUpdate(thread_id=thread_id, metadata=metadata),
        )
        filter_clause, filter_params = _build_filter_query(
            filters=filters,
        )
        params = {"metadata": Jsonb(metadata), "thread_id": thread_id}
        where_clause = "WHERE thread_id = %(thread_id)s"
        if filter_params:
            params.update(filter_params)
            where_clause += filter_clause

        # If TTL is provided, upsert into thread_ttl before returning the updated thread
        ttl_query_cte = ""
        if ttl is not None:
            ttl_strategy = ttl.get("strategy", "delete")
            if ttl_strategy != "delete":
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid thread TTL strategy: {ttl_strategy}. Expected one of ['delete']",
                )
            ttl_interval_minutes = ttl.get("ttl", ttl.get("default_ttl", None))
            if ttl_interval_minutes is not None:
                ttl_query_cte = f"""
                    WITH inserted_ttl AS (
                        INSERT INTO thread_ttl (thread_id, strategy, ttl_minutes, created_at)
                        SELECT
                            thread_id,
                            %(ttl_strategy)s,
                            %(ttl_interval)s,
                            NOW() AT TIME ZONE 'UTC'
                        FROM thread
                        {where_clause}
                        ON CONFLICT (thread_id, strategy) DO UPDATE SET
                            ttl_minutes = EXCLUDED.ttl_minutes,
                            created_at = EXCLUDED.created_at
                        RETURNING *
                    )
                    """
                params.update(
                    {
                        "ttl_strategy": ttl_strategy,
                        "ttl_interval": ttl_interval_minutes,
                    }
                )

        # Build and execute final query
        cur = await conn.execute(
            "\n".join(
                (
                    ttl_query_cte,
                    f"""
                    UPDATE thread
                    SET metadata = metadata || %(metadata)s
                    {where_clause}
                    RETURNING *;
                    """,
                )
            ),
            params,
            binary=True,
        )
        return (row async for row in cur)

    @staticmethod
    async def set_status(
        conn: AsyncConnection[DictRow],
        thread_id: UUID,
        checkpoint: CheckpointPayload | None,
        exception: BaseException | None,
        expected_status: ThreadStatus | Sequence[ThreadStatus] | None = None,
    ) -> None:
        """Set the status of a thread."""
        # No auth since it's internal
        has_next = False if checkpoint is None else bool(checkpoint["next"])
        if exception and not isinstance(exception, UserInterrupt | UserRollback):
            status: ThreadStatus = "error"
        elif has_next:
            status = "interrupted"
        else:
            status = "idle"
        interrupts = (
            {
                t["id"]: [patch_interrupt(i) for i in t["interrupts"]]
                for t in checkpoint["tasks"]
                if t.get("interrupts")
            }
            if checkpoint
            else {}
        )
        if expected_status:
            if isinstance(expected_status, str):
                expected_status = [expected_status]
            expected_status = list(expected_status)
        async with await conn.execute(
            "\n".join(
                (
                    """update thread set
            updated_at = now(),
            values = %(values)s,
            interrupts = %(interrupts)s,
            error = %(error)s,
            status = case
                when exists(
                    select 1 from run
                    where thread_id = %(thread_id)s
                    and status in ('pending', 'running')
                ) then 'busy'
                else %(status)s
            end
            where thread_id = %(thread_id)s""",
                    "and status = ANY(%(expected_status)s)" if expected_status else "",
                    "returning status;",
                )
            ),
            {
                "thread_id": thread_id,
                "status": status,
                "values": Jsonb(checkpoint["values"]) if checkpoint else None,
                "interrupts": Jsonb(interrupts),
                "error": json_dumpb(exception) if exception else None,
                "expected_status": expected_status,
            },
            binary=True,
        ) as cur:
            if not cur.rowcount:
                status_code = 409 if expected_status else 404
                detail = (
                    "Thread not found"
                    if expected_status
                    else "Thread status does not match expected status"
                )
                raise HTTPException(
                    status_code=status_code,
                    detail=detail,
                )
            async for row in cur:
                if row["status"] == "busy":
                    # there's more runs for this thread, wake up the worker
                    # this happens when multitask_strategy != "reject"
                    await wake_up_worker()

    @staticmethod
    async def set_joint_status(
        conn: AsyncConnection[DictRow],
        thread_id: UUID,
        run_id: UUID,
        run_status: RunStatus | Literal["rollback"],
        graph_id: str,
        checkpoint: CheckpointPayload | None = None,
        exception: BaseException | None = None,
    ) -> None:
        """Set the status of both thread and run atomically in a single query.

        This is an optimized version that combines the logic from Threads.set_status
        and Runs.set_status to minimize database round trips and ensure atomicity.

        Args:
            conn: Database connection
            thread_id: Thread ID to update
            run_id: Run ID to update
            run_status: New status for the run (or "rollback" to delete the run)
            checkpoint: Checkpoint payload for thread status calculation
            exception: Exception that occurred (affects thread status)
        """
        # No auth since it's internal

        # Calculate thread status using same logic as Threads.set_status
        next_tasks = None
        if checkpoint is None:
            has_next = False
        else:
            next_tasks = checkpoint.get("next")
            has_next = bool(next_tasks)
        if exception and not isinstance(exception, UserInterrupt | UserRollback):
            thread_status: ThreadStatus = "error"
        elif has_next:
            thread_status = "interrupted"
        else:
            thread_status = "idle"

        interrupts = (
            {
                t["id"]: [patch_interrupt(i) for i in t["interrupts"]]
                for t in checkpoint["tasks"]
                if t.get("interrupts")
            }
            if checkpoint
            else {}
        )

        # For rollbacks, we want to delete the run and
        # associated checkpoints
        if run_status == "rollback":
            query_parts = [
                """WITH selected AS (
                    SELECT run_id
                    FROM run
                    WHERE run_id = %(run_id)s
                        AND thread_id = %(thread_id)s
                ),

                del_checkpoints AS (
                    DELETE FROM checkpoints
                    USING selected
                    WHERE checkpoints.run_id = selected.run_id
                ),

                del_checkpoint_writes AS (
                    DELETE FROM checkpoint_writes
                    USING selected
                    INNER JOIN checkpoints
                        ON checkpoints.run_id = selected.run_id
                    WHERE checkpoint_writes.checkpoint_id = checkpoints.checkpoint_id
                        AND checkpoint_writes.thread_id = checkpoints.thread_id
                        AND checkpoint_writes.checkpoint_ns = checkpoints.checkpoint_ns
                ),

                deleted_run AS (
                    DELETE FROM run
                    USING selected
                    WHERE run.run_id = selected.run_id
                    RETURNING run.run_id
                ),
                """,
                """
                updated_thread AS (
                    UPDATE thread SET
                        updated_at = now(),
                        values = %(values)s,
                        interrupts = %(interrupts)s,
                        metadata = metadata || %(metadata)s,
                        status = CASE
                            WHEN EXISTS(
                                SELECT 1 FROM run
                                WHERE thread_id = %(thread_id)s
                                AND status IN ('pending', 'running')
                            ) THEN 'busy'
                            ELSE %(thread_status)s
                        END
                    WHERE thread_id = %(thread_id)s
                    RETURNING status
                )""",
                """SELECT status FROM updated_thread""",
            ]
        else:
            # Normal case - update run status
            query_parts = [
                """WITH updated_run AS (
                    UPDATE run
                    SET status = %(run_status)s, updated_at = now()
                    WHERE run_id = %(run_id)s
                    RETURNING thread_id
                ),
                """,
                """
                updated_thread AS (
                    UPDATE thread SET
                        updated_at = now(),
                        values = %(values)s,
                        interrupts = %(interrupts)s,
                        metadata = metadata || %(metadata)s,
                        error = %(error)s,
                        status = CASE
                            WHEN EXISTS(
                                SELECT 1 FROM run
                                WHERE thread_id = %(thread_id)s
                                AND status IN ('pending', 'running')
                                AND run_id != %(run_id)s  -- Exclude the run we just updated
                            ) OR %(run_status)s IN ('pending', 'running') THEN 'busy'
                            ELSE %(thread_status)s
                        END
                    WHERE thread_id = %(thread_id)s
                    RETURNING status
                )""",
                """
                SELECT status FROM updated_thread""",
            ]

        full_query = "\n".join(query_parts)

        params = {
            "thread_id": thread_id,
            "run_id": run_id,
            "run_status": run_status,
            "thread_status": thread_status,
            "values": Jsonb(checkpoint["values"]) if checkpoint else None,
            "interrupts": Jsonb(interrupts),
            "error": json_dumpb(exception) if exception else None,
            "metadata": Jsonb({"graph_id": graph_id}),
        }

        async with await conn.execute(full_query, params, binary=True) as cur:
            if not cur.rowcount:
                status_code = 404
                detail = "Thread not found"
                raise HTTPException(
                    status_code=status_code,
                    detail=detail,
                )

            async for row in cur:
                final_thread_status = row["status"]
                if final_thread_status == "busy" or run_status == "pending":
                    await wake_up_worker()
        if thread_status == "interrupted":
            await logger.ainfo(
                f"Thread {thread_id} interrupted.",
                thread_id=thread_id,
                thread_status=thread_status,
                run_id=run_id,
                run_status=run_status,
                next=next_tasks,
            )

    @staticmethod
    async def delete(
        conn: AsyncConnection[DictRow],
        thread_id: UUID,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[UUID]:
        """Delete a thread by ID."""
        filters = await Threads.handle_event(
            ctx,
            "delete",
            Auth.types.ThreadsDelete(thread_id=thread_id),
        )
        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="thread",
        )
        params = {"thread_id": thread_id, **filter_params}

        # Don't allow deleting any related entities
        # unless the thread itself can also be deleted.
        cte_filter_clause = f""" AND EXISTS (
                SELECT 1 FROM thread
                WHERE thread_id = %(thread_id)s{filter_clause}
            )"""

        cur = await conn.execute(
            f"""
            with del_runs AS (
                DELETE FROM run
                WHERE run.thread_id = %(thread_id)s{cte_filter_clause}
                RETURNING run.run_id
            ),
            del_checkpoints AS (
                DELETE FROM checkpoints
                WHERE thread_id = %(thread_id)s{cte_filter_clause}
                RETURNING thread_id
            ),
            del_checkpoint_blobs AS (
                DELETE FROM checkpoint_blobs
                WHERE thread_id = %(thread_id)s{cte_filter_clause}
                RETURNING thread_id
            ),
            del_checkpoint_writes AS (
                DELETE FROM checkpoint_writes
                WHERE thread_id = %(thread_id)s{cte_filter_clause}
                RETURNING thread_id
            )

            DELETE FROM thread
            WHERE thread_id = %(thread_id)s{filter_clause}
            RETURNING thread_id
            """,
            params,
            binary=True,
        )
        return (row["thread_id"] async for row in cur)

    @staticmethod
    async def _delete_bulk(
        conn: AsyncConnection[DictRow],
        thread_ids: Sequence[UUID],
        *,
        batch_size: int = 100,
    ) -> int:
        """Delete multiple threads by ID in an efficient bulk operation.

        Args:
            conn: Database connection
            thread_ids: List of thread UUIDs to delete
            batch_size: Maximum number of threads to delete in one batch query

        Returns:
            int: Number of threads successfully deleted
        """
        if not thread_ids:
            return 0

        deleted_count = 0

        # We do a select for update so we can skip locked
        # in case there is contention / the thread happens to get
        # woken up at this time
        delete_stmt = """
        WITH target AS (
            SELECT thread_id
            FROM thread
            WHERE thread_id = ANY(%(thread_ids)s)
            FOR UPDATE SKIP LOCKED
        ), del_ckpt AS (
            DELETE FROM checkpoints
            USING target
            WHERE checkpoints.thread_id = target.thread_id
        ), del_ckpt_blobs AS (
            DELETE FROM checkpoint_blobs
            USING target
            WHERE checkpoint_blobs.thread_id = target.thread_id
        ), del_ckpt_writes AS (
            DELETE FROM checkpoint_writes
            USING target
            WHERE checkpoint_writes.thread_id = target.thread_id
        ), del_runs AS (
            DELETE FROM run
            USING target
            WHERE run.thread_id = target.thread_id
        ), del_threads AS (
            DELETE FROM thread
            USING target
            WHERE thread.thread_id = target.thread_id
            RETURNING 1                     -- one row per deleted thread
        )
        SELECT COUNT(*) AS deleted FROM del_threads;
        """

        for i in range(0, len(thread_ids), batch_size):
            batch = thread_ids[i : i + batch_size]
            try:
                cur = await conn.execute(
                    delete_stmt, {"thread_ids": list(batch)}, binary=True
                )
                row = await cur.fetchone()
                batch_deleted_count = row["deleted"] if row is not None else 0
                deleted_count += batch_deleted_count
            except Exception as e:
                await logger.aexception(f"Error in bulk delete batch: {e}")

        await logger.ainfo(
            "Bulk thread delete completed",
            n=deleted_count,
            total_requested=len(thread_ids),
        )
        return deleted_count

    @staticmethod
    async def _delete_with_run(
        conn: AsyncConnection[DictRow],
        thread_id: UUID,
        run_id: UUID,
    ) -> None:
        """Delete a thread by ID."""
        # Internal only
        params = {"thread_id": thread_id, "run_id": run_id}

        try:
            cur = await conn.execute(
                """WITH del_run AS (
                    DELETE FROM run
                    WHERE run_id = %(run_id)s
                ),
                del_thread AS (
                    DELETE FROM thread
                    WHERE thread_id = %(thread_id)s
                    RETURNING thread_id
                ),
                del_checkpoints AS (
                    DELETE FROM checkpoints
                    WHERE thread_id = %(thread_id)s
                    RETURNING thread_id
                ),
                del_checkpoint_blobs AS (
                    DELETE FROM checkpoint_blobs
                    WHERE thread_id = %(thread_id)s
                    RETURNING thread_id
                ),
                del_checkpoint_writes AS (
                    DELETE FROM checkpoint_writes
                    WHERE thread_id = %(thread_id)s
                    RETURNING thread_id
                )
                SELECT thread_id FROM del_thread;""",
                params,
                binary=True,
            )
            # Iterate over the cursor to raise any errors
            async for _ in cur:
                pass
        except Exception as e:
            await logger.aexception(f"Error in delete with run: {e}")

    @staticmethod
    async def copy(
        conn: AsyncConnection[DictRow],
        thread_id: UUID,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[Thread]:
        """Create a copy of an existing thread."""
        read_filters = await Threads.handle_event(
            ctx,
            "read",
            Auth.types.ThreadsRead(
                thread_id=thread_id,
            ),
        )

        new_thread_id = uuid4()
        # Assert that the user has permissions to create a new thread.
        # (We don't actually need the filters.)
        await Threads.handle_event(
            ctx,
            "create",
            Auth.types.ThreadsCreate(
                thread_id=new_thread_id,
            ),
        )

        filter_clause, filter_params = _build_filter_query(
            filters=read_filters,
            table_alias="thread",
        )
        where_clause = f"WHERE thread_id = %(thread_id)s{filter_clause}"
        thread_join = "JOIN thread USING (thread_id) " if filter_params else ""
        query_thread_params = {
            "new_thread_id": new_thread_id,
            "thread_id": thread_id,
            **filter_params,
        }

        async with conn.pipeline():
            cur = await conn.execute(
                f"""INSERT INTO thread (thread_id, metadata)
                SELECT %(new_thread_id)s, metadata
                FROM thread
                {where_clause}
                ON CONFLICT (thread_id) DO NOTHING
                RETURNING *""",
                query_thread_params,
            )
            # then, copy all of the checkpoint data in parallel
            await asyncio.gather(
                conn.execute(
                    f"""
                    INSERT INTO checkpoints (run_id, thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, checkpoint, metadata)
                    SELECT run_id, %(new_thread_id)s, checkpoint_ns, checkpoint_id, parent_checkpoint_id, checkpoint, jsonb_set(
                        checkpoints.metadata,
                        '{{thread_id}}',
                        to_jsonb(%(new_thread_id)s)
                    )
                    FROM checkpoints
                    {thread_join}
                    {where_clause}
                    ON CONFLICT DO NOTHING
                    """,
                    query_thread_params,
                ),
                conn.execute(
                    f"""
                    INSERT INTO checkpoint_blobs (thread_id, checkpoint_ns, channel, version, type, blob)
                    SELECT %(new_thread_id)s, checkpoint_ns, channel, version, type, blob
                    FROM checkpoint_blobs
                    {thread_join}
                    {where_clause}
                    ON CONFLICT DO NOTHING
                    """,
                    query_thread_params,
                ),
                conn.execute(
                    f"""
                    INSERT INTO checkpoint_writes (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, blob)
                    SELECT %(new_thread_id)s, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, blob
                    FROM checkpoint_writes
                    {thread_join}
                    {where_clause}
                    ON CONFLICT DO NOTHING
                    """,
                    query_thread_params,
                ),
            )
        return (row async for row in cur)

    class State(Authenticated):
        # treat this like threads resource
        resource = "threads"

        @staticmethod
        async def get(
            conn: AsyncConnection[DictRow],
            config: Config,
            subgraphs: bool,
            ctx: Auth.types.BaseAuthContext | None = None,
        ) -> StateSnapshot:
            checkpointer = Checkpointer(conn, unpack_hook=_msgpack_ext_hook_to_json)
            # fetch both in parallel
            async with conn.pipeline():
                thread, checkpoint, run_graph_id = await asyncio.gather(
                    Threads.get(conn, config["configurable"]["thread_id"], ctx=ctx),
                    checkpointer.aget_iter(config),
                    conn.execute(
                        "select kwargs -> 'config' -> 'configurable' ->> 'graph_id' as graph_id from run where thread_id = %(thread_id)s limit 1",
                        {"thread_id": config["configurable"]["thread_id"]},
                    ),
                )
            thread = await fetchone(thread)
            metadata = json_loads(thread["metadata"])
            thread_config = json_loads(thread["config"])
            thread_config = {
                **thread_config,
                "configurable": {
                    **thread_config.get("configurable", {}),
                    **config.get("configurable", {}),
                },
            }
            graph_id_row = await run_graph_id.fetchone()
            graph_id = (
                graph_id_row["graph_id"] if graph_id_row else metadata.get("graph_id")
            )

            # Filters already applied in Threads.get so no need to use them again here

            if graph_id:
                # format latest checkpoint for response
                checkpointer.latest_iter = checkpoint
                async with get_graph(
                    graph_id,
                    thread_config,
                    checkpointer=checkpointer,
                    store=(await api_store.get_store()),
                ) as graph:
                    return await graph.aget_state(config, subgraphs=subgraphs)
            else:
                _kwargs: dict[str, Any] = {
                    "values": {},
                    "next": tuple(),
                    "config": None,
                    "metadata": None,
                    "created_at": None,
                    "parent_config": None,
                    "tasks": tuple(),
                }
                _kwargs.update(_snapshot_defaults())
                return StateSnapshot(**_kwargs)  # type: ignore[missing-argument]

        @staticmethod
        async def post(
            conn: AsyncConnection[DictRow],
            config: Config,
            values: Sequence[dict] | dict[str, Any] | None,
            as_node: str | None = None,
            ctx: Auth.types.BaseAuthContext | None = None,
        ) -> ThreadUpdateResponse:
            thread_id = UUID(config["configurable"]["thread_id"])
            filters = await Threads.State.handle_event(
                ctx,
                "update",
                Auth.types.ThreadsUpdate(thread_id=thread_id),
            )

            checkpointer = Checkpointer(conn, use_direct_connection=True)
            # fetch both in parallel
            async with conn.pipeline():
                thread, checkpoint, run_count, run_graph_id = await asyncio.gather(
                    Threads.get(
                        conn,
                        config["configurable"]["thread_id"],
                        ctx=ctx,
                        # This lets us use update filters on the get
                        # operation if we want
                        filters=filters,
                    ),
                    checkpointer.aget_iter(config),
                    conn.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM run
                        WHERE thread_id = %(thread_id)s
                        AND status IN ('pending', 'running')
                        """,
                        {"thread_id": config["configurable"]["thread_id"]},
                    ),
                    conn.execute(
                        "select kwargs -> 'config' -> 'configurable' ->> 'graph_id' as graph_id from run where thread_id = %(thread_id)s limit 1",
                        {"thread_id": config["configurable"]["thread_id"]},
                    ),
                )
            thread = await fetchone(thread)
            metadata = json_loads(thread["metadata"])
            thread_config = json_loads(thread["config"])
            run_count = await run_count.fetchone()
            graph_id_row = await run_graph_id.fetchone()
            graph_id = (
                graph_id_row["graph_id"] if graph_id_row else metadata.get("graph_id")
            )

            # Check if thread is busy before allowing state update
            if run_count is not None and run_count["count"] > 0:
                raise HTTPException(
                    status_code=409,
                    detail="Thread is busy with a running job. Cannot update state.",
                )

            if graph_id:
                # update state
                config["configurable"].setdefault("graph_id", graph_id)
                checkpointer.latest_iter = checkpoint
                async with AsyncExitStack() as stack:
                    graph = await stack.enter_async_context(
                        get_graph(
                            graph_id,
                            thread_config,
                            checkpointer=checkpointer,
                            store=(await api_store.get_store()),
                        )
                    )
                    await stack.enter_async_context(conn.transaction())
                    next_config = await graph.aupdate_state(
                        config, values, as_node=as_node
                    )
                    # update thread values
                    state = await Threads.State.get(
                        conn, config, subgraphs=False, ctx=ctx
                    )
                    await Threads.set_status(
                        conn,
                        thread_id,
                        state_snapshot_to_thread_state(state),
                        None,
                        # Accept if NOT busy
                        expected_status=("interrupted", "idle", "error"),
                    )

                    # Publish state update event
                    event_data = {
                        "state": state_snapshot_to_thread_state(state),
                        "thread_id": str(thread_id),
                    }
                    await Runs.Stream.publish(
                        "*",
                        "state_update",
                        json_dumpb(event_data),
                        thread_id=thread_id,
                        resumable=True,
                    )

                    return {
                        "checkpoint": next_config["configurable"],
                        # below are deprecated
                        **next_config,
                        "checkpoint_id": next_config["configurable"]["checkpoint_id"],
                    }
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Thread '{thread['thread_id']}' has no assigned graph ID. This usually occurs when no runs have been made on this particular thread."
                    " This operation requires a graph ID. Please ensure a run has been made for the thread or manually update the thread metadata (by setting the 'graph_id' field) before running this operation.",
                )

        @staticmethod
        async def bulk(
            conn: AsyncConnection[DictRow],
            config: Config,
            supersteps: Sequence[dict],
            ctx: Auth.types.BaseAuthContext | None = None,
        ) -> ThreadUpdateResponse:
            """Update a thread with a batch of state updates."""

            from langgraph.types import StateUpdate

            thread_id = UUID(config["configurable"]["thread_id"])
            filters = await Threads.State.handle_event(
                ctx,
                "update",
                Auth.types.ThreadsUpdate(thread_id=thread_id),
            )

            checkpointer = Checkpointer(conn)

            async with conn.pipeline():
                thread, run_graph_id = await asyncio.gather(
                    Threads.get(conn, thread_id, ctx=ctx, filters=filters),
                    conn.execute(
                        "select kwargs -> 'config' -> 'configurable' ->> 'graph_id' as graph_id from run where thread_id = %(thread_id)s limit 1",
                        {"thread_id": config["configurable"]["thread_id"]},
                    ),
                )
            thread = await fetchone(thread)
            thread_config = json_loads(thread["config"])
            metadata = json_loads(thread["metadata"])
            graph_id_row = await run_graph_id.fetchone()
            graph_id = (
                graph_id_row["graph_id"] if graph_id_row else metadata.get("graph_id")
            )

            if graph_id:
                # update state
                config["configurable"].setdefault("graph_id", graph_id)
                config["configurable"].setdefault("checkpoint_ns", "")

                async with AsyncExitStack() as stack:
                    graph = await stack.enter_async_context(
                        get_graph(
                            graph_id,
                            thread_config,
                            checkpointer=checkpointer,
                            store=(await api_store.get_store()),
                        )
                    )

                    await stack.enter_async_context(conn.transaction())
                    next_config = await graph.abulk_update_state(
                        config,
                        [
                            [
                                StateUpdate(
                                    (
                                        map_cmd(update.get("command"))
                                        if update.get("command")
                                        else update.get("values")
                                    ),
                                    update.get("as_node"),
                                )
                                for update in superstep.get("updates", [])
                            ]
                            for superstep in supersteps
                        ],
                    )

                    # update thread values
                    state = await Threads.State.get(
                        conn, config, subgraphs=False, ctx=ctx
                    )

                    await Threads.set_status(
                        conn,
                        thread_id,
                        state_snapshot_to_thread_state(state),
                        None,
                    )

                    # Publish state update event
                    event_data = {
                        "state": state_snapshot_to_thread_state(state),
                        "thread_id": str(thread_id),
                    }
                    await Runs.Stream.publish(
                        "*",
                        "state_update",
                        json_dumpb(event_data),
                        thread_id=thread_id,
                        resumable=True,
                    )

                    return ThreadUpdateResponse(checkpoint=next_config["configurable"])
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Thread '{thread['thread_id']}' has no assigned graph ID. This usually occurs when no runs have been made on this particular thread."
                    " This operation requires a graph ID. Please ensure a run has been made for the thread or manually update the thread metadata (by setting the 'graph_id' field) before running this operation.",
                )

        @staticmethod
        async def list(
            conn: AsyncConnection[DictRow],
            *,
            config: Config,
            limit: int = 1,
            before: str | Checkpoint | None = None,
            metadata: MetadataInput = None,
            ctx: Auth.types.BaseAuthContext | None = None,
        ) -> list[StateSnapshot]:
            """Get the history of a thread."""
            async with conn.pipeline():
                thread, run_graph_id = await asyncio.gather(
                    Threads.get(conn, config["configurable"]["thread_id"], ctx=ctx),
                    conn.execute(
                        "select kwargs -> 'config' -> 'configurable' ->> 'graph_id' as graph_id from run where thread_id = %(thread_id)s limit 1",
                        {"thread_id": config["configurable"]["thread_id"]},
                    ),
                )
            thread = await fetchone(thread)
            thread_metadata = json_loads(thread["metadata"])
            thread_config = json_loads(thread["config"])
            thread_config = {
                **thread_config,
                "configurable": {
                    **thread_config.get("configurable", {}),
                    **config.get("configurable", {}),
                },
            }
            graph_id_row = await run_graph_id.fetchone()
            graph_id = (
                graph_id_row["graph_id"]
                if graph_id_row
                else thread_metadata.get("graph_id")
            )
            if graph_id:
                async with get_graph(
                    graph_id,
                    thread_config,
                    checkpointer=Checkpointer(
                        conn, unpack_hook=_msgpack_ext_hook_to_json
                    ),
                    store=(await api_store.get_store()),
                ) as graph:
                    return [
                        c
                        async for c in graph.aget_state_history(
                            config,
                            limit=limit,
                            filter=metadata,
                            before=(
                                {"configurable": {"checkpoint_id": before}}
                                if isinstance(before, str)
                                else before
                            ),
                        )
                    ]
            else:
                return []

        @staticmethod
        async def list_messages(
            conn: AsyncConnection[DictRow],
            *,
            thread_id: str,
            before: str | Checkpoint | None = None,
            limit: int = 20,
            ctx: Auth.types.BaseAuthContext | None = None,
        ) -> ThreadMessagesResponse:
            """Get a chronological, deduplicated page of messages for a thread.

            This method scans the checkpoint chain backwards, merges messages from
            each checkpoint, and returns a single page with a checkpoint-based
            cursor. Callers do not need to understand DeltaChannel vs cumulative
            checkpoints; the merge logic mirrors the front-end `mergedMessages`.

            Implementation note: we bypass ``graph.aget_state_history``. Reconstructing
            the full graph state for every checkpoint is extremely expensive for agent
            graphs with many tools (graph import/wrapping alone can take seconds per
            checkpoint). Instead we read the raw ``messages`` channel blobs directly
            from ``checkpoint_blobs`` and merge only the message deltas. This cuts
            latency from ~76s to sub-second for threads with hundreds of checkpoints.
            """
            MAX_SCAN_CHECKPOINTS = 100
            MESSAGES_TARGET = limit
            CHECKPOINT_PAGE_SIZE = 50

            thread = await fetchone(
                await Threads.get(conn, thread_id, ctx=ctx)
            )
            if thread is None:
                raise HTTPException(
                    status_code=404, detail=f"Thread '{thread_id}' not found."
                )

            class _MsgSnapshot(NamedTuple):
                values: dict[str, Any]
                config: Config

            serde = JsonPlusSerializer()
            all_snapshots: list[_MsgSnapshot] = []
            last_page_full = False
            next_checkpoint_id: str | None = None
            before_id = before if isinstance(before, str) else None
            oldest_parent_id: str | None = None

            while len(all_snapshots) < MAX_SCAN_CHECKPOINTS:
                # Fetch the next page of checkpoints (newest first).
                query = """
                    SELECT checkpoint_id, parent_checkpoint_id, checkpoint
                    FROM checkpoints
                    WHERE thread_id = %(thread_id)s AND checkpoint_ns = %(checkpoint_ns)s
                """
                params: dict[str, Any] = {
                    "thread_id": thread_id,
                    "checkpoint_ns": "",
                }
                if before_id is not None:
                    query += " AND checkpoint_id < %(before_id)s"
                    params["before_id"] = before_id
                query += " ORDER BY checkpoint_id DESC LIMIT %(limit)s"
                params["limit"] = CHECKPOINT_PAGE_SIZE

                rows = await conn.execute(query, params)
                page = [
                    {
                        "checkpoint_id": r["checkpoint_id"],
                        "parent_checkpoint_id": r["parent_checkpoint_id"],
                        "checkpoint": json_loads(r["checkpoint"]),
                    }
                    async for r in rows
                ]
                if not page:
                    last_page_full = False
                    break

                # Fetch the messages blob for each checkpoint in parallel.
                msg_versions = []
                for row in page:
                    checkpoint = row["checkpoint"]
                    versions = checkpoint.get("channel_versions") or {}
                    version = versions.get("messages")
                    msg_versions.append(
                        (row["checkpoint_id"], row["parent_checkpoint_id"], version)
                    )

                blob_rows = await conn.execute(
                    """
                    SELECT version, type, blob
                    FROM checkpoint_blobs
                    WHERE thread_id = %(thread_id)s
                      AND checkpoint_ns = %(checkpoint_ns)s
                      AND channel = 'messages'
                      AND version = ANY(%(versions)s)
                    """,
                    {
                        "thread_id": thread_id,
                        "checkpoint_ns": "",
                        "versions": [
                            v for _, _, v in msg_versions if v is not None
                        ],
                    },
                )
                blobs_by_version: dict[str, tuple[str, bytes]] = {
                    r["version"]: (r["type"], r["blob"])
                    async for r in blob_rows
                }

                for checkpoint_id, parent_id, version in msg_versions:
                    messages: list[Any] = []
                    if version is not None:
                        blob_info = blobs_by_version.get(version)
                        if blob_info is not None:
                            blob_type, blob_data = blob_info
                            try:
                                value = serde.loads_typed((blob_type, blob_data))
                                # DeltaChannel serializes writes as _DeltaSnapshot.
                                # The snapshot's ``value`` attribute holds the actual
                                # list of message deltas for this checkpoint.
                                if hasattr(value, "value"):
                                    value = value.value
                                if isinstance(value, list):
                                    messages = value
                            except Exception:
                                # Malformed blob: skip it rather than failing the
                                # whole request. The UI can still show other msgs.
                                pass

                    all_snapshots.append(
                        _MsgSnapshot(
                            values={"messages": messages},
                            config={
                                "configurable": {
                                    "thread_id": thread_id,
                                    "checkpoint_ns": "",
                                    "checkpoint_id": checkpoint_id,
                                }
                            },
                        )
                    )
                    oldest_parent_id = parent_id

                if len(page) < CHECKPOINT_PAGE_SIZE:
                    last_page_full = False
                    break

                last_page_full = True
                merged = merge_messages_from_snapshots(all_snapshots)
                if len(merged) >= MESSAGES_TARGET:
                    next_checkpoint_id = oldest_parent_id
                    break

                before_id = oldest_parent_id

            merged = merge_messages_from_snapshots(all_snapshots)
            messages = merged[:limit]

            if next_checkpoint_id is None and len(merged) > limit:
                # We scanned a full page and still have more messages; the cursor
                # for the next page is the parent of the oldest checkpoint scanned.
                next_checkpoint_id = oldest_parent_id

            has_more = next_checkpoint_id is not None or last_page_full

            return {
                "messages": messages,
                "has_more": has_more,
                "next_checkpoint_id": next_checkpoint_id,
            }

    @staticmethod
    async def count(
        conn: AsyncConnection[DictRow],
        *,
        metadata: MetadataInput = None,
        values: MetadataInput = None,
        status: ThreadStatus | None = None,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> int:
        """Get count of threads."""
        metadata = metadata if metadata is not None else {}
        values = values if values is not None else {}
        filters = await Threads.handle_event(
            ctx,
            "search",
            Auth.types.ThreadsSearch(
                metadata=metadata,
                values=values,
                status=status,
                limit=0,
                offset=0,
            ),
        )
        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="thread",
        )

        query = "SELECT COUNT(*) as count FROM thread WHERE 1=1"
        params = {**filter_params}

        if metadata:
            query += " AND metadata @> %(metadata)s"
            params["metadata"] = Jsonb(metadata)

        if values:
            query += " AND values @> %(values)s"
            params["values"] = Jsonb(values)

        if status:
            query += " AND status = %(status)s"
            params["status"] = status

        if filter_clause:
            query += " " + filter_clause

        cur = await conn.execute(query, params)
        row = await cur.fetchone()
        return row["count"] if row else 0

    class Stream(Authenticated):
        resource = "threads"

        @staticmethod
        async def subscribe(
            thread_id: UUID,
        ) -> StreamHandler:
            """Subscribe to the thread stream, returning a stream handler.
            The stream handler must be passed to `join` to receive messages."""
            pattern = CHANNEL_RUN_STREAM.format(thread_id, "*")
            pubsub = await get_pubsub(patterns=[pattern])
            return pubsub

        @staticmethod
        async def join(
            thread_id: UUID,
            *,
            last_event_id: str | None = None,
            stream_modes: list[ThreadStreamMode],
            ctx: Auth.types.BaseAuthContext | None = None,
        ) -> AsyncIterator[tuple[bytes, bytes, bytes | None]]:
            """Stream the thread output."""
            await Threads.Stream.check_thread_stream_auth(thread_id, ctx)

            def should_filter_event(event_name: str, message_bytes: bytes) -> bool:
                """Check if an event should be filtered out based on stream_modes."""
                if "run_modes" in stream_modes and event_name != "state_update":
                    return False
                if "state_update" in stream_modes and event_name == "state_update":
                    return False
                if "lifecycle" in stream_modes and event_name == "metadata":
                    try:
                        message_data = orjson.loads(message_bytes)
                        if message_data.get("status") == "run_done":
                            return False
                        if "attempt" in message_data and "run_id" in message_data:
                            return False
                    except (orjson.JSONDecodeError, TypeError):
                        pass
                return True

            start_time = datetime.now(UTC)
            try:
                pubsub = await Threads.Stream.subscribe(thread_id)

                async with pubsub:
                    logger.info(
                        "Joined thread stream",
                        thread_id=str(thread_id),
                    )
                    highest_stream_id: bytes | None = None

                    if last_event_id is not None:
                        # Use XRANGE on the unified thread cache stream
                        # last_event_id must be in ms-seq format (e.g., "1234567890123-0")
                        stream_key = STREAM_THREAD_CACHE.format(thread_id)
                        events = await get_redis().xrange(
                            stream_key, last_event_id, "+"
                        )

                        for stream_id, fields_list in events:
                            event_name = fields_list[b"event"].decode()
                            message = fields_list[b"message"].decode()
                            event_bytes = fields_list[b"event"]
                            message_bytes = fields_list[b"message"]

                            try:
                                if (
                                    highest_stream_id is None
                                    or _compare_stream_ids(stream_id, highest_stream_id)
                                    > 0
                                ):
                                    highest_stream_id = stream_id
                            except (ValueError, AttributeError):
                                pass

                            if message_bytes == b"done":
                                event_name = "metadata"
                                event_bytes = b"metadata"
                                message_bytes = json_dumpb(
                                    {
                                        "status": "run_done",
                                        "run_id": fields_list[b"run_id"].decode(),
                                    }
                                )
                            if not should_filter_event(event_name, message_bytes):
                                yield (
                                    event_bytes,
                                    message_bytes,
                                    stream_id,
                                )

                    while True:
                        if store := await pubsub.get_message():
                            if LOG_LEVEL_DEBUG:
                                await logger.adebug(
                                    "Received redis stream event",
                                    thread_id=str(thread_id),
                                    type=store["type"],
                                    channel=store["channel"],
                                    data=store["data"],
                                )

                            # Throw out subscription events that may happen if reconnection happens
                            if store["type"] not in PubSub.PUBLISH_MESSAGE_TYPES:
                                continue

                            decoded = decode_stream_message(
                                store["data"], channel=store["channel"]
                            )
                            # Dedupe messages from cached stream
                            if (
                                highest_stream_id is not None
                                and decoded.stream_id_bytes is not None
                                and _compare_stream_ids(
                                    decoded.stream_id_bytes, highest_stream_id
                                )
                                <= 0
                            ):
                                continue
                            event = decoded.event_bytes
                            event_name = event.decode("utf-8")
                            message = decoded.message_bytes
                            message_id = decoded.stream_id_bytes

                            if event_name == "control":
                                if message == b"done":
                                    # Extract run_id from channel: {prefix}thread:{thread_id}:run:{run_id}:control
                                    channel_parts = (
                                        store["channel"].decode("utf-8").split(":")
                                    )
                                    run_id_from_channel = channel_parts[
                                        channel_parts.index("run") + 1
                                    ]
                                    event_bytes = b"metadata"
                                    message_bytes = json_dumpb(
                                        {
                                            "status": "run_done",
                                            "run_id": run_id_from_channel,
                                        }
                                    )

                                    # Filter events based on stream_modes
                                    if not should_filter_event(
                                        "metadata", message_bytes
                                    ):
                                        yield (
                                            event_bytes,
                                            message_bytes,
                                            message_id,
                                        )

                            else:
                                # Filter events based on stream_modes
                                if not should_filter_event(event_name, message):
                                    yield (
                                        event,
                                        message,
                                        message_id,
                                    )

            except asyncio.CancelledError:
                elapsed_time = (datetime.now(UTC) - start_time).total_seconds()
                await logger.awarning(
                    f"Client disconnected after {elapsed_time} seconds. Consider adjusting the client or network timeouts if this is unexpected.",
                    thread_id=str(thread_id),
                    elapsed_time=elapsed_time,
                )
                raise

        @staticmethod
        async def check_thread_stream_auth(
            thread_id: UUID,
            ctx: Auth.types.BaseAuthContext | None = None,
        ) -> None:
            filters = await Threads.Stream.handle_event(
                ctx,
                "read",
                Auth.types.ThreadsRead(thread_id=thread_id),
            )
            filter_clause, filter_params = _build_filter_query(
                filters=filters,
                table_alias="thread",
            )
            if filter_params:
                query = f"""
                SELECT thread_id FROM thread
                WHERE thread_id = %(thread_id)s
                {filter_clause}
                """
                params = {**filter_params, "thread_id": thread_id}
                async with connect() as conn:
                    cur = await conn.execute(query, params, binary=True)
                    if not await cur.fetchone():
                        raise HTTPException(
                            status_code=404,
                            detail=f"Thread with ID '{thread_id}' not found. Please verify the ID is correct and the thread hasn't been deleted or expired.",
                        )


class Runs(Authenticated):
    # Auth for runs is applied at the thread level.
    # We do have a special "create_run" handler, however, to let
    # users add checks for runs in particular
    resource = "threads"

    # KEYS[1] = RUN_STATUS_STRING  key  (run:{id}:control)
    # KEYS[2] = CHANNEL_RUN_CONTROL channel (run:{id}:control)
    # ARGV[1] = action  ("interrupt" | "rollback" | "done")
    # ARGV[2] = TTL-seconds (string; "0" → skip EXPIRE)
    _control_signal_lua: str = """
        local key     = KEYS[1]
        local channel = KEYS[2]
        local action  = ARGV[1]
        local ttl     = tonumber(ARGV[2])

        redis.call('SET', key, action)
        if ttl and ttl > 0 then
            redis.call('EXPIRE', key, ttl)
        end
        redis.call('PUBLISH', channel, action)
        return 1
    """

    _control_signal_sha: str | None = None

    @staticmethod
    async def _signal_control(
        run_id: UUID,
        thread_id: UUID,
        action: str,  # "interrupt" | "rollback" | "done"
        ttl: int = 60,  # seconds for the control key to live
    ) -> None:
        """Atomically SET + optional EXPIRE + PUBLISH a control action."""
        key = RUN_STATUS_STRING.format(thread_id, run_id)
        channel = CHANNEL_RUN_CONTROL.format(thread_id, run_id)
        redis_client = get_redis()

        # Redis-py supports a lot of this natively via the AsyncScript, but doesn't allow caching the script
        # Would be nice to contribute that back and use that instead
        # https://github.com/redis/redis-py/blob/8403ddcfcf16c95baab330076b4905483e44fbb7/redis/commands/core.py#L5729
        if Runs._control_signal_sha is None:
            Runs._control_signal_sha = await redis_client.script_load(
                Runs._control_signal_lua
            )

        try:
            await redis_client.evalsha(  # type: ignore[valid-type]
                Runs._control_signal_sha,
                2,
                key,
                channel,
                action,
                str(ttl),
            )
        except redis.exceptions.NoScriptError:
            Runs._control_signal_sha = await redis_client.script_load(
                Runs._control_signal_lua
            )
            await redis_client.evalsha(  # type: ignore[valid-type]
                Runs._control_signal_sha,
                2,
                key,
                channel,
                action,
                str(ttl),
            )

    @staticmethod
    async def stats(conn: AsyncConnection[DictRow]) -> QueueStats:
        # We don't have auth on stats right now
        redis_client = get_redis()

        # Check cache
        cached = await redis_client.get(STRING_RUN_STATS_CACHE)
        if cached:
            try:
                return json_loads(cached)
            except Exception:
                pass

        try:
            async with redis_client.lock(
                name=LOCK_RUN_STATS,
                timeout=RUN_STATS_CACHE_SECONDS / 2,
                blocking_timeout=RUN_STATS_CACHE_SECONDS / 2,
            ):
                cached = await redis_client.get(STRING_RUN_STATS_CACHE)
                if cached:
                    try:
                        return json_loads(cached)
                    except Exception:
                        pass

                async with Runs._stats(conn) as stats:
                    await redis_client.set(
                        STRING_RUN_STATS_CACHE,
                        json_dumpb(dict(stats)),
                        ex=RUN_STATS_CACHE_SECONDS,
                    )

                    return stats
        except (redis.exceptions.LockError, redis.exceptions.LockNotOwnedError) as e:
            await logger.adebug("Failure with using Redis lock: %s", e)
            cached = await redis_client.get(STRING_RUN_STATS_CACHE)
            if cached:
                try:
                    return json_loads(cached)
                except Exception:
                    pass

            async with Runs._stats(conn) as stats:
                return stats

    @staticmethod
    @asynccontextmanager
    async def _stats(conn: AsyncConnection[DictRow]) -> AsyncIterator[QueueStats]:
        async with await conn.execute(
            """
    with queue as (
        select
            count(*) filter (where status = 'pending') as n_pending,
            count(*) filter (where status = 'running') as n_running
        from run
        where status in ('pending', 'running')
    ),
    pending as (
        select
            extract(epoch from max(now() - created_at)) as pending_runs_wait_time_max_secs,
            extract(
                epoch
                from percentile_cont(0.5) within group (order by now() - created_at)
            ) as pending_runs_wait_time_med_secs
        from run
        where status = 'pending'
    )
    select
        queue.n_pending,
        queue.n_running,
        pending.pending_runs_wait_time_max_secs,
        pending.pending_runs_wait_time_med_secs
    from queue
    left join pending on true
    """
        ) as cur:
            stats = await cur.fetchone()
            if stats["pending_runs_wait_time_max_secs"] is not None:
                stats["pending_runs_wait_time_max_secs"] = float(
                    stats["pending_runs_wait_time_max_secs"]
                )
            if stats["pending_runs_wait_time_med_secs"] is not None:
                stats["pending_runs_wait_time_med_secs"] = float(
                    stats["pending_runs_wait_time_med_secs"]
                )
            yield stats

    @staticmethod
    async def next(wait: bool, limit: int = 1) -> AsyncIterator[tuple[Run, int]]:
        """Get the next run from the queue, and the attempt number.
        1 is the first attempt, 2 is the first retry, etc."""
        # Internal for workers, no auth here.

        # wait for a run to be available
        # all scenarios that make a run available for running need to wake_up_worker()
        # - a new run is created - Runs.put()
        # - a run is marked for retry - Runs.set_status()
        # - a run finishes with other runs pending in same thread - Threads.set_status()
        # - Runs.sweep() finds pending runs and wakes up workers
        if wait:
            try:
                popped = await get_redis().blpop(  # type: ignore[valid-type]
                    [LIST_RUN_QUEUE], timeout=BG_JOB_INTERVAL
                )
            except redis.exceptions.ConnectionError as e:
                await logger.awarning("Handling Redis connection error.", exc_info=e)
                return

        # get the run (also poll Postgres on BLPOP timeout, so that a missed
        # Redis notification or a stale worker state does not leave pending
        # runs stuck forever).
        try:
            async with (
                get_redis().pipeline() as pipe,
                connect() as conn,
                conn.transaction(),
                await conn.execute(
                    """
                    WITH pending AS (
                            SELECT thread_id,
                                MIN(created_at) AS min_ts
                            FROM   run
                            WHERE  status = 'pending'
                            AND  created_at < NOW()
                            AND  NOT EXISTS (
                                    SELECT 1
                                    FROM   run r2
                                    WHERE  r2.thread_id = run.thread_id
                                    AND  r2.status    = 'running')
                            GROUP  BY thread_id
                            ORDER  BY min_ts, thread_id
                            LIMIT  %(limit)s
                        ),
                        first_in_thread AS (
                            SELECT r.run_id
                            FROM   run r
                            JOIN   pending p
                            ON   r.thread_id  = p.thread_id
                            AND   r.created_at = p.min_ts
                            FOR UPDATE SKIP LOCKED
                        )
                        UPDATE run
                        SET    status     = 'running',
                            updated_at = NOW()
                        FROM   first_in_thread
                        WHERE  run.run_id = first_in_thread.run_id
                        AND  run.status = 'pending'
                        RETURNING run.*;
                    """,
                    {"limit": limit},
                    binary=True,
                ) as cur,
            ):
                runs = await cur.fetchall()
                # get attempt number, and set running marker
                for run in runs:
                    pipe.set(
                        STRING_RUN_RUNNING.format(run["run_id"]),
                        "1",
                        ex=BG_JOB_HEARTBEAT,
                    )
                    pipe.expire(
                        STRING_RUN_ATTEMPT.format(run["run_id"]),
                        int(BG_JOB_TIMEOUT_SECS * 2),
                    )
                    pipe.incrby(STRING_RUN_ATTEMPT.format(run["run_id"]), 1)
                redis_results = await pipe.execute()
        except psycopg.errors.IntegrityError:
            # if the unique constraint is violated, just return
            await wake_up_worker()
            return
        except psycopg.errors.LockNotAvailable:
            await logger.awarning("Lock not available in Runs.next. Returning.")
            await wake_up_worker()
            return

        # yield each run and its attempt number
        for idx, run in enumerate(runs):
            run["kwargs"] = json_loads(run["kwargs"])
            run["metadata"] = json_loads(run["metadata"])
            attempt = redis_results[idx * 3 + 2]
            yield run, attempt

    @asynccontextmanager
    @staticmethod
    async def enter(
        run_id: UUID, thread_id: UUID, loop: asyncio.AbstractEventLoop, resumable: bool
    ) -> AsyncIterator[ValueEvent]:
        """Enter a run, listen for cancellation while running, signal when done."
        This method should be called as a context manager by a worker executing a run.
        """
        channels = [
            CHANNEL_RUN_CONTROL.format(thread_id, run_id),
        ]
        if not REDIS_CLUSTER:
            # Don't add old channel if we're in a cluster as it will usually hash to a different node
            channels.append(CHANNEL_RUN_CONTROL_OLD.format(run_id))
        async with (
            await get_pubsub(
                channels=channels,
            ) as pubsub,
            SimpleTaskGroup(cancel=True, taskgroup_name="Runs.enter") as tg,
        ):
            done = ValueEvent()
            # start listener, will be cancelled when exiting context
            tg.create_task(listen_for_cancellation(pubsub, run_id, thread_id, done))
            # start heartbeat, will be cancelled when exiting context
            hb = asyncio.run_coroutine_threadsafe(heartbeat(run_id), loop)
            # give done event to caller
            try:
                yield done
                # signal done
                await mark_done(run_id, thread_id, resumable)
            except RETRIABLE_EXCEPTIONS:
                # don't signal done, will be retried
                pass
            except BaseException:
                await wake_up_worker()
                raise
            finally:
                hb.cancel()

    @staticmethod
    async def sweep() -> list[UUID]:
        """Sweep runs that have been in running state for too long."""
        redis_client = get_redis()
        async with redis_client.lock(
            name=LOCK_RUN_SWEEP,
            timeout=BG_JOB_HEARTBEAT + BG_JOB_INTERVAL,
            sleep=BG_JOB_INTERVAL,
        ) as lock:
            loop = asyncio.get_running_loop()
            while True:
                start = loop.time()
                try:
                    async with connect() as conn:
                        # wake workers if there are pending runs
                        cur = await conn.execute(
                            """
                                SELECT COUNT(*) as count
                                FROM   run
                                WHERE  status = 'pending'
                                AND    created_at < NOW()
                                AND    NOT EXISTS (
                                        SELECT 1
                                        FROM   run r2
                                        WHERE  r2.thread_id = run.thread_id
                                        AND    r2.status    = 'running')
                            """
                        )
                        pending_count = await cur.fetchone()
                        if pending_count and pending_count["count"] > 0:
                            await logger.ainfo(
                                f"Sweep woke up {pending_count['count']} workers."
                            )
                            await wake_up_worker(count=pending_count["count"])

                        # find abandoned runs and put back in queue
                        cur = await conn.execute(
                            """
                                select run_id
                                from run
                                where run.status = 'running'
                            """
                        )
                        run_ids = [row["run_id"] async for row in cur]
                        if not run_ids:
                            return []
                        if not REDIS_CLUSTER:
                            exists = await get_redis().mget(
                                [
                                    STRING_RUN_RUNNING.format(run_id)
                                    for run_id in run_ids
                                ]
                            )
                        else:
                            exists = await asyncio.gather(
                                *[
                                    redis_client.get(STRING_RUN_RUNNING.format(run_id))
                                    for run_id in run_ids
                                ]
                            )
                        to_sweep = [
                            run_id
                            for run_id, exists in zip(run_ids, exists, strict=True)
                            if exists is None
                        ]
                        if to_sweep:
                            try:
                                await conn.execute(
                                    """
                                    update run
                                    set status = 'pending', updated_at = now()
                                    where run_id = any(%(run_ids)s)
                                        and status = 'running'
                                    """,
                                    {"run_ids": to_sweep},
                                )
                                await wake_up_worker(count=len(to_sweep))
                                logger.info("Swept runs", run_ids=to_sweep)
                            except psycopg.errors.IntegrityError:
                                # catch concurrent update error
                                logger.warning(
                                    "Tried to sweep runs that are no longer running",
                                    run_ids=to_sweep,
                                )
                except Exception as exc:
                    logger.exception("Sweep iteration failed", exc_info=exc)
                finally:
                    await asyncio.sleep(BG_JOB_HEARTBEAT)
                    elapsed = loop.time() - start
                    try:
                        await lock.extend(elapsed + BG_JOB_INTERVAL)
                    except redis.exceptions.LockError as exc:
                        logger.warning("Failed to extend lock", exc_info=exc)
                        return []

    @staticmethod
    async def put(
        conn: AsyncConnection[DictRow],
        assistant_id: UUID,
        kwargs: dict,
        *,
        thread_id: UUID | None = None,
        user_id: str | None = None,
        run_id: UUID | None = None,
        status: RunStatus | None = "pending",
        metadata: MetadataInput,
        prevent_insert_if_inflight: bool,
        multitask_strategy: MultitaskStrategy = "reject",
        if_not_exists: IfNotExists = "reject",
        after_seconds: int = 0,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[Run]:
        """Create a run."""
        metadata = metadata or {}
        metadata.setdefault("assistant_id", assistant_id)
        kwargs = kwargs or {}
        kwargs.setdefault("config", {})
        temporary = kwargs.get("temporary", False)
        filters = await Runs.handle_event(
            ctx,
            "create_run",
            Auth.types.RunsCreate(
                thread_id=None if temporary else thread_id,
                assistant_id=assistant_id,
                run_id=run_id,
                status=status,
                metadata=metadata,
                prevent_insert_if_inflight=prevent_insert_if_inflight,
                multitask_strategy=multitask_strategy,
                if_not_exists=if_not_exists,
                after_seconds=after_seconds,
                kwargs=kwargs,
            ),
        )
        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="thread",
        )
        thread_join = "JOIN thread USING (thread_id) " if filter_params else ""
        ttl_interval_minutes = None
        strategy = None
        env_ttl_interval_minutes = None
        env_strategy = None
        if THREAD_TTL:
            env_strategy = THREAD_TTL.get("strategy", "delete")
            env_ttl_interval_minutes = THREAD_TTL.get("default_ttl", None)
        ttl_config = None
        if (
            kwargs
            and (config := kwargs.get("config"))
            and (configurable := config.get("configurable"))
            and (ttl_config := configurable.get("ttl"))
        ):
            if isinstance(ttl_config, int | float):
                strategy = env_strategy or "delete"
                ttl_interval_minutes = ttl_config
            elif not isinstance(ttl_config, dict):
                await logger.aerror("TTL configuration must be a dictionary")
                raise HTTPException(
                    status_code=422, detail="TTL configuration must be a dictionary"
                )
            else:
                if (
                    strategy := ttl_config.get("strategy", "delete")
                    and strategy != "delete"
                ):
                    raise HTTPException(
                        status_code=422, detail=f"Invalid strategy: {strategy}"
                    )
                ttl_interval_minutes = ttl_config.get(
                    "ttl", ttl_config.get("default_ttl", None)
                )
        ttl_insert_query = (
            """inserted_ttl AS (
                INSERT INTO thread_ttl (thread_id, strategy, ttl_minutes, created_at)
                SELECT
                    run_thread.thread_id,
                    COALESCE(%(strategy)s, %(env_strategy)s, 'delete'),
                    CASE
                        -- Explicit TTL provided in request (highest precedence)
                        WHEN %(ttl_interval)s::float IS NOT NULL THEN %(ttl_interval)s::float
                        -- Environment default TTL (fallback)
                        WHEN %(env_ttl_interval)s::float IS NOT NULL THEN %(env_ttl_interval)s::float
                        ELSE NULL
                    END,
                    (now() + %(after_seconds)s::interval) AT TIME ZONE 'UTC'
                FROM run_thread
                WHERE
                    (%(ttl_interval)s::float IS NOT NULL) OR (%(env_ttl_interval)s::float IS NOT NULL)
                LIMIT 1
                ON CONFLICT (thread_id, strategy) DO UPDATE SET
                    ttl_minutes = EXCLUDED.ttl_minutes,
                    created_at = EXCLUDED.created_at
                RETURNING *
            ),
"""
            if (ttl_interval_minutes is not None)
            or (env_ttl_interval_minutes is not None)
            else ""
        )

        insert_thread_sql = """
            INSERT INTO thread (thread_id, status, metadata, config)
            SELECT
                %(thread_id)s,
                'busy',
                jsonb_build_object(
                    'graph_id', assistant.graph_id,
                    'assistant_id', assistant.assistant_id
                ) ||  coalesce(%(config)s::jsonb -> 'metadata', '{}') || %(metadata)s::jsonb,
                assistant.config
                || %(config)s::jsonb
                || jsonb_build_object(
                    'configurable',
                        coalesce((assistant.config -> 'configurable'), '{}')
                    )
            FROM assistant
            WHERE assistant_id = %(assistant_id)s
            ON CONFLICT (thread_id) DO UPDATE
                -- Return existing thread; otherwise the CTE below could return nothing
                -- if there's a conflict here in an uncommitted transaction in another worker
                -- but it hasn't been inserted to be available for the SELECT statement below
                SET status = 'busy'
            RETURNING thread.*
        """

        thread_query_cte = (
            f"""WITH run_thread AS ({insert_thread_sql}), """
            if thread_id is None
            else (
                f"""WITH inserted_thread AS (
                {insert_thread_sql}
            ),
            run_thread AS (
                SELECT * FROM thread where thread_id = %(thread_id)s {filter_clause}
                UNION
                SELECT * FROM inserted_thread
                LIMIT 1
            ),
            {ttl_insert_query}"""
                if if_not_exists == "create"
                else f"""WITH run_thread AS (
                        SELECT * FROM thread
                        WHERE thread_id = %(thread_id)s
                             {filter_clause}),
                             {ttl_insert_query}"""
            )
        )

        params = {
            "multitask_strategy": multitask_strategy,
            "run_id": run_id or uuid7(),
            "thread_id": thread_id or uuid4(),
            "assistant_id": assistant_id,
            "metadata": Jsonb(metadata),
            "kwargs": Jsonb(kwargs),
            "config": Jsonb(kwargs.get("config")),
            "status": status,
            "user_id": user_id,
            "after_seconds": f"{after_seconds} second",
            "strategy": strategy,
            "env_strategy": env_strategy,
            "ttl_interval": ttl_interval_minutes,
            "env_ttl_interval": env_ttl_interval_minutes,
        }
        params.update(filter_params)

        needs_inflight = thread_id is not None and (
            multitask_strategy in ("rollback", "interrupt")
            or prevent_insert_if_inflight
        )
        query = thread_query_cte

        if needs_inflight:
            query += f"""
                inflight_runs AS (
                    SELECT run.*
                    FROM run
                    {thread_join}
                    WHERE thread_id = %(thread_id)s AND run.status in ('pending', 'running') {filter_clause}
                ),
            """

        query += (
            """
inserted_run AS (
    INSERT INTO run (run_id, thread_id, assistant_id, metadata, status, kwargs, multitask_strategy, created_at)
    SELECT
        %(run_id)s,
        thread_id,
        assistant_id,
        %(metadata)s,
        %(status)s,
        %(kwargs)s::jsonb || jsonb_build_object(
            'config', assistant.config || run_thread.config || %(config)s::jsonb || jsonb_build_object(
                'configurable',
                    coalesce((assistant.config -> 'configurable'), '{}') ||
                    coalesce((run_thread.config -> 'configurable'), '{}') ||
                    coalesce(%(config)s::jsonb -> 'configurable', '{}') ||
                    jsonb_build_object(
                        'run_id', %(run_id)s::text,
                        'thread_id', thread_id,
                        'graph_id', graph_id,
                        'assistant_id', assistant_id,
                        'user_id', coalesce(
                            %(config)s::jsonb -> 'configurable' ->> 'user_id',
                            run_thread.config -> 'configurable' ->> 'user_id',
                            assistant.config -> 'configurable' ->> 'user_id',
                            %(user_id)s::text
                        )
                    ),
                'metadata',
                    assistant.metadata || run_thread.metadata || coalesce(%(config)s::jsonb -> 'metadata', '{}') || %(metadata)s
            ),
            'context', coalesce(assistant.context, '{}') || coalesce(%(kwargs)s::jsonb -> 'context', '{}')
        ),
        %(multitask_strategy)s,
        now() + %(after_seconds)s::interval
    FROM run_thread
    CROSS JOIN assistant
    WHERE thread_id = %(thread_id)s
        AND assistant_id = %(assistant_id)s"""
            + (
                " AND NOT EXISTS (SELECT 1 FROM inflight_runs)"
                if prevent_insert_if_inflight and thread_id is not None
                else ""
            )
            + """ RETURNING run.*
)"""
        )
        query += """
                ,

updated_thread AS (
    UPDATE thread SET
        metadata = jsonb_set(
            jsonb_set(thread.metadata, '{graph_id}', to_jsonb(assistant.graph_id)),
            '{assistant_id}',
            to_jsonb(assistant.assistant_id)
        ),
        config = assistant.config
            || thread.config
            || %(config)s::jsonb
            || jsonb_build_object(
                'configurable',
                    coalesce((assistant.config -> 'configurable'), '{}') ||
                    coalesce(thread.config -> 'configurable', '{}')
            ),
        status = 'busy'
    FROM inserted_run
    INNER JOIN assistant
        ON assistant.assistant_id = inserted_run.assistant_id
    WHERE
        thread.thread_id = inserted_run.thread_id
        AND thread.status != 'busy'
)"""

        if needs_inflight:
            query += """
                SELECT * FROM inserted_run
                UNION ALL
                SELECT * FROM inflight_runs
            """
        else:
            query += """
                SELECT * FROM inserted_run
            """

        try:
            cur = await conn.execute(query, params, binary=True)
        except:
            if FF_LOG_QUERY_AND_PARAMS:
                logger.exception(f"Failed to execute query:{query}\nParams:{params}")
            raise

        async def consume() -> AsyncIterator[Run]:
            async for row in cur:
                yield row
                if row["run_id"] == run_id:
                    # inserted run, notify queue
                    if not after_seconds:
                        await wake_up_worker()
                    else:
                        create_task(wake_up_worker(after_seconds))

        return consume()

    @staticmethod
    async def get(
        conn: AsyncConnection[DictRow],
        run_id: UUID,
        *,
        thread_id: UUID,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[Run]:
        """Get a run by ID."""
        filters = await Runs.handle_event(
            ctx,
            "read",
            Auth.types.ThreadsRead(run_id=run_id, thread_id=thread_id),
        )

        where_clause, where_params = _build_filter_query(
            filters=filters,
            table_alias="thread",
        )

        query = f"""SELECT run.*
        FROM run
        JOIN thread USING (thread_id)
        WHERE run_id = %(run_id)s AND run.thread_id = %(thread_id)s
        {where_clause}
        """
        cur = await conn.execute(
            query,
            {**where_params, "run_id": run_id, "thread_id": thread_id},
            binary=True,
        )
        return (row async for row in cur)

    @staticmethod
    async def delete(
        conn: AsyncConnection[DictRow],
        run_id: UUID,
        *,
        thread_id: UUID,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[UUID]:
        filters = await Runs.handle_event(
            ctx,
            "delete",
            Auth.types.ThreadsDelete(run_id=run_id, thread_id=thread_id),
        )

        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="thread",
        )
        thread_join = (
            "JOIN thread USING (thread_id) WHERE" if filter_params else "WHERE"
        )

        params = {**filter_params, "run_id": run_id, "thread_id": thread_id}
        async with conn.transaction():
            cur = await conn.execute(
                f"""
                WITH selected AS (
                    SELECT run_id
                    FROM run
                    {thread_join}
                    run_id = %(run_id)s
                        AND run.thread_id = %(thread_id)s
                        {filter_clause}
                ),

                del_checkpoint_writes AS (
                    DELETE FROM checkpoint_writes
                    USING selected
                    INNER JOIN checkpoints
                        ON checkpoints.run_id = selected.run_id
                    WHERE checkpoint_writes.checkpoint_id = checkpoints.checkpoint_id
                        AND checkpoint_writes.thread_id = checkpoints.thread_id
                        AND checkpoint_writes.checkpoint_ns = checkpoints.checkpoint_ns
                )

                DELETE FROM run
                USING selected
                WHERE run.run_id = selected.run_id
                RETURNING run.run_id""",
                params,
                binary=True,
            )
        return (row["run_id"] async for row in cur)

    @staticmethod
    async def cancel(
        conn: AsyncConnection[DictRow],
        run_ids: Sequence[UUID] | None = None,
        *,
        action: Literal["interrupt", "rollback"] = "interrupt",
        thread_id: UUID | None = None,
        status: Literal["pending", "running", "all"] | None = None,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> None:
        """
        Cancel a run. Must provide either:
        1) thread_id + run_ids, or
        2) a status (pending, running, all).

        If status=all, we treat it as ('pending', 'running').

        Steps:
        - Raise ValueError if conflicting or missing arguments are passed.
        - Gather runs matching the requested condition(s).
        - Issue Redis control signals for each run.
        - For runs still pending, interrupt/rollback them in the database.
        - For runs actively running, only the worker picks up the control key.
        - If no runs matched, raise HTTP 404.
        """
        if status is not None:
            # Must NOT specify thread_id or run_ids if status is provided
            if thread_id is not None or run_ids is not None:
                raise HTTPException(
                    status_code=422,
                    detail="Cannot specify 'thread_id' or 'run_ids' when using 'status'",
                )
        else:
            # Must specify thread_id and run_ids if no status is provided
            if thread_id is None or run_ids is None:
                raise HTTPException(
                    status_code=422,
                    detail="Please provide a thread_id and run_ids, or a status to cancel",
                )

        # Possibly record an event or retrieve filters from external logic
        filters = await Runs.handle_event(
            ctx,
            "update",
            Auth.types.ThreadsUpdate(
                thread_id=thread_id,  # type: ignore
                action=action,
                metadata={"run_ids": run_ids, "status": status},
            ),
        )
        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            prefix="",
            table_alias="thread",
        )

        # Build the status clause if status is set
        status_list: tuple[str, ...] = ()
        if status is not None:
            if status == "all":
                status_list = ("pending", "running")
            elif status in ("pending", "running"):
                status_list = (status,)
            else:
                raise HTTPException(
                    status_code=422, detail=f"Unsupported status: {status}"
                )
        # Build a single SELECT that handles either:
        #   - run_id in %(run_ids)s and thread_id = %(thread_id)s
        #   - or run.status in status_list
        # (only one of these disjunctions is used, based on provided arguments)
        # We also apply any filter_clause (e.g. access restrictions).
        where_parts = []
        if status_list:
            placeholders = ", ".join(f"'{s}'" for s in status_list)
            where_parts.append(f"run.status IN ({placeholders})")
        else:
            where_parts.append("run_id = ANY(%(run_ids)s)")
            where_parts.append("thread_id = %(thread_id)s")

        # Add any extra filters from the "filter_clause" (depends on environment).
        if filter_clause.strip():
            where_parts.append(filter_clause)
        query_where = " AND ".join(where_parts)

        # Combine parameters
        params: dict[str, Any] = {
            "action": action,
        }
        if run_ids is not None:
            params["run_ids"] = run_ids
        if thread_id is not None:
            params["thread_id"] = thread_id
        params.update(filter_params)

        # 1) Gather matching runs
        thread_join = "JOIN thread USING (thread_id)" if filter_params else ""
        select_sql = f"""
            SELECT run_id, thread_id
            FROM run
            {thread_join}
            WHERE {query_where}
        """
        matching = await conn.execute(select_sql, params, binary=True)
        found_runs = [(row["run_id"], row["thread_id"]) async for row in matching]
        found_run_ids = [run_id for run_id, _ in found_runs]

        if not found_run_ids:
            raise HTTPException(
                status_code=404,
                detail="No matching runs to cancel. Please verify the thread ID and run IDs are correct and the runs haven't been deleted or expired.",
            )

        # We do a single CTE to handle:
        #   - (running)  no DB change, only external signals
        #   - (pending)  update (interrupt) or delete (rollback)
        #   - union them, verifying that we accounted for each
        sql = f"""
            WITH
            running AS (
                SELECT run_id
                FROM run
                {thread_join}
                WHERE run_id = ANY(%(found_run_ids)s)
                AND run.status = 'running'
                {f" AND {filter_clause}" if filter_clause.strip() else ""}
            ),

            pending AS (
                SELECT run_id
                FROM run
                {thread_join}
                WHERE run_id = ANY(%(found_run_ids)s)
                AND run.status = 'pending'
                {f" AND {filter_clause}" if filter_clause.strip() else ""}
            ),

            stateless_deleted AS (
                DELETE FROM run
                USING pending
                WHERE run.run_id = pending.run_id
                AND (run.kwargs->>'temporary')::boolean = true
                RETURNING run.run_id
            ),

            updated AS (
                UPDATE run
                SET status = 'interrupted', updated_at = now()
                FROM pending
                WHERE run.run_id = pending.run_id
                AND %(action)s = 'interrupt'
                AND (run.kwargs->>'temporary')::boolean IS DISTINCT FROM true
                RETURNING run.run_id
            ),

            deleted AS (
                DELETE FROM run
                USING pending
                WHERE run.run_id = pending.run_id
                AND %(action)s = 'rollback'
                AND (run.kwargs->>'temporary')::boolean IS DISTINCT FROM true
                RETURNING run.run_id
            ),
            updated_threads AS (
                UPDATE thread
                SET status = 'idle', updated_at = now()
                FROM updated u
                JOIN run r ON r.run_id = u.run_id
                WHERE thread.thread_id = r.thread_id
                RETURNING thread.thread_id
            ),
            --- Should we also delete stateless threads?

            unioned AS (
                SELECT run_id, TRUE AS done FROM stateless_deleted
                UNION ALL
                SELECT run_id, TRUE AS done FROM updated
                UNION ALL
                SELECT run_id, TRUE AS done FROM deleted
                UNION ALL
                SELECT run_id, FALSE AS done FROM running
            )

            SELECT run_id, bool_and(done) AS done
            FROM unioned
            GROUP BY run_id
        """
        cancel_params = {
            "found_run_ids": found_run_ids,
            "action": action,
        }
        cancel_params.update(filter_params)

        try:
            cur = await conn.execute(sql, cancel_params, binary=True)
        except psycopg.errors.LockNotAvailable as e:
            logger.exception("Lock not available: ", exc_info=e)
            raise HTTPException(
                status_code=409,
                detail="Another operation is preventing this cancel from being completed. Please try again.",
            ) from e

        await asyncio.gather(
            *(
                Runs._signal_control(run_id, thread_id, action)
                for run_id, thread_id in found_runs
            )
        )

        # 4) Verify we accounted for all runs
        updated_rows = [(row["run_id"], row["done"]) async for row in cur]
        if len(updated_rows) == len(found_run_ids):
            logger.info(
                "Cancelled runs",
                run_ids=found_run_ids,
                done_run_ids=[row[0] for row in updated_rows if row[1]],
                action=action,
                status=status,
            )
            return
        else:
            raise HTTPException(
                status_code=404, detail="Some runs were not found or not cancelable."
            )

    @staticmethod
    async def search(
        conn: AsyncConnection[DictRow],
        thread_id: UUID,
        *,
        limit: int = 10,
        offset: int = 0,
        status: RunStatus | None = None,
        select: list[RunSelectField] | None = None,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[Run]:
        """List all runs by thread."""
        metadata = {}
        filters = await Runs.handle_event(
            ctx,
            "search",
            Auth.types.ThreadsSearch(thread_id=thread_id, metadata=metadata),
        )
        filters_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="thread",
        )
        threads_join = "" if not filter_params else "JOIN thread USING (thread_id)"
        selected_columns = ", ".join(f"run.{col}" for col in select) if select else "*"
        query = f"""SELECT {selected_columns} FROM run
        {threads_join}
        WHERE run.thread_id = %(thread_id)s {filters_clause}"""
        params = {**filter_params, "thread_id": thread_id}

        if status is not None:
            query += " AND run.status = %(status)s::text"
            params["status"] = status

        query += " ORDER BY run.created_at DESC LIMIT %(limit)s OFFSET %(offset)s"
        params["limit"] = limit
        params["offset"] = offset

        cur = await conn.execute(query, params, binary=True)
        return (row async for row in cur)

    @staticmethod
    async def set_status(
        conn: AsyncConnection[DictRow], run_id: UUID, status: RunStatus
    ) -> None:
        """Set the status of a run."""
        # Internal method - no auth
        await conn.execute(
            "UPDATE run SET status = %s, updated_at = now() WHERE run_id = %s",
            (status, run_id),
            binary=True,
        )
        if status == "pending":
            await wake_up_worker()

    class Stream(Authenticated):
        resource = "threads"
        _resumable_stream_publish_lua = """
            local stream_key = KEYS[1]
            local channel    = KEYS[2]
            local raw_msg    = ARGV[1]
            local event      = ARGV[2]
            local ttl        = tonumber(ARGV[3])
            local run_id     = ARGV[4]

            -- Add message to stream with auto-generated ID, including run_id for filtering
            local stream_id = redis.call('XADD', stream_key, '*',
            'run_id', run_id,
            'event', event,
            'message', raw_msg)

            -- Handle TTL using XTRIM to remove old entries
            if ttl > 0 then
            local current_time = redis.call('TIME')
            local current_ms = tonumber(current_time[1]) * 1000 + math.floor(tonumber(current_time[2]) / 1000)
            local min_time_ms = current_ms - (ttl * 1000)
            if min_time_ms < 0 then min_time_ms = 0 end

            redis.call('XTRIM', stream_key, 'MINID', min_time_ms)
            redis.call('EXPIRE', stream_key, ttl)
            end

            -- Build protocol v1 pubsub payload
            local VERSION = 1

            local event_len = string.len(event or "")
            local stream_len = string.len(stream_id or "")

            if event_len == 0 then
            return redis.error_reply('event cannot be empty')
            end
            if event_len > 65535 then
            return redis.error_reply('event too large')
            end
            if stream_len > 65535 then
            return redis.error_reply('stream id too large')
            end

            local function hi(x) return math.floor(x / 256) end
            local function lo(x) return x % 256 end

            -- [version][stream_id_len:2][event_len:2][stream_id][event][message]
            local live_msg =
            string.char(VERSION) ..
            string.char(hi(stream_len)) .. string.char(lo(stream_len)) ..
            string.char(hi(event_len))  .. string.char(lo(event_len))  ..
            stream_id .. event .. raw_msg

            redis.call('PUBLISH', channel, live_msg)

            return stream_id
        """
        _resumable_stream_script_sha: str | None = None

        # Lua script to filter stream messages by run_id from a starting point
        # KEYS[1] = stream key (STREAM_THREAD_CACHE)
        # ARGV[1] = run_id string to filter by
        # ARGV[2] = start ID (use "-" for all messages, or specific ms-seq ID)
        _stream_filter_by_run_lua = """
            local stream_key = KEYS[1]
            local target_run_id = ARGV[1]
            local start_id = ARGV[2]

            -- Get all messages from start_id to the end
            local entries = redis.call('XRANGE', stream_key, start_id, '+')
            local filtered = {}

            -- Filter by run_id (run_id is always the first field. Structure is: 'run_id', RUN_ID, 'event', EVENT, 'message', MESSAGE)
            for i, entry in ipairs(entries) do
                local fields = entry[2]
                if fields[2] == target_run_id then
                    table.insert(filtered, entry)
                end
            end

            return filtered
        """
        _stream_filter_script_sha: str | None = None

        @staticmethod
        async def subscribe(
            run_id: UUID,
            thread_id: UUID | None = None,
        ) -> StreamHandler:
            """Subscribe to the run stream, returning a stream handler.
            The stream handler must be passed to `join` to receive messages."""
            channels = [CHANNEL_RUN_STREAM.format(thread_id, run_id)]
            if not REDIS_CLUSTER:
                # Don't add old channel if we're in a cluster as it will usually hash to a different node
                channels.append(CHANNEL_RUN_STREAM_OLD.format(run_id))
            # Keeping the pattern for rollout so that existing other streams still get picked up
            patterns = [
                CHANNEL_RUN_STREAM.format(thread_id, run_id) + ":*",
            ]
            if not REDIS_CLUSTER:
                # Don't add old pattern if we're in a cluster as it will usually hash to a different node
                patterns.append(CHANNEL_RUN_STREAM_OLD.format(run_id) + ":*")
            pubsub = await get_pubsub(
                channels=channels,
                patterns=patterns,
            )
            return pubsub

        @staticmethod
        async def join(
            run_id: UUID,
            *,
            stream_channel: StreamHandler,
            thread_id: UUID,
            ignore_404: bool = False,
            cancel_on_disconnect: bool = False,
            stream_mode: StreamMode | list[StreamMode] | None = None,
            last_event_id: str | None = None,
            ctx: Auth.types.BaseAuthContext | None = None,
        ) -> AsyncIterator[tuple[bytes, bytes, bytes | None]]:
            """Stream the run output, either from a stream handler or a stream mode."""
            start_time = datetime.now(UTC)
            await Runs.Stream.check_run_stream_auth(run_id, thread_id, ctx)

            pubsub: StreamHandler = stream_channel
            try:
                logger.info(
                    "Joined run stream",
                    run_id=str(run_id),
                    thread_id=str(thread_id),
                    cancel_on_disconnect=cancel_on_disconnect,
                )

                run_status_string = RUN_STATUS_STRING.format(thread_id, run_id)
                if value := await get_redis().get(run_status_string):
                    if value == b"done":
                        # if already done, we can drain the stream
                        timeout: int | float = DRAIN_TIMEOUT
                    else:
                        timeout = WAIT_LESS_TIMEOUT
                else:
                    # Start with shorter timeout for cases after the control channel has expired or the run doesn't exist
                    timeout = WAIT_LESS_TIMEOUT
                highest_stream_id: bytes | None = None

                # Obtain events starting from the last event id
                if last_event_id is not None:
                    stream_key = STREAM_THREAD_CACHE.format(thread_id)
                    try:
                        # Try to parse as integer first (old method)
                        start_idx = int(last_event_id)
                        await logger.awarning(
                            "Using deprecated integer last_event_id format. Please use ms-seq format.",
                            run_id=str(run_id),
                            thread_id=str(thread_id),
                            last_event_id=last_event_id,
                        )
                        # Get all messages and filter by run_id, then slice from start_idx+1
                        events = await Runs.Stream._eval_filter_script(
                            stream_key, str(run_id), "-"
                        )

                        for stream_id, fields_list in events[start_idx + 1 :]:
                            # fields_list is [run_id, run_id_val, event, event_val, message, message_val]
                            event = fields_list[3]  # event value
                            message = fields_list[5]  # message value
                            event_name = event.decode()

                            if event_name == "control" and message == b"done":
                                continue

                            try:
                                if (
                                    highest_stream_id is None
                                    or _compare_stream_ids(stream_id, highest_stream_id)
                                    > 0
                                ):
                                    highest_stream_id = stream_id
                            except (ValueError, AttributeError):
                                pass

                            if (
                                not stream_mode
                                or event_name in stream_mode
                                or (
                                    (
                                        "messages" in stream_mode
                                        or "messages-tuple" in stream_mode
                                    )
                                    and event_name.startswith("messages")
                                )
                            ):
                                yield (event, message, stream_id)
                    except ValueError:
                        # New method, where last_event_id is a ms-seq ID
                        events = await Runs.Stream._eval_filter_script(
                            stream_key, str(run_id), last_event_id
                        )
                        for stream_id, fields_list in events:
                            # fields_list is [run_id, run_id_val, event, event_val, message, message_val]
                            event = fields_list[3]  # event value
                            message = fields_list[5]  # message value
                            event_name = event.decode()

                            try:
                                if (
                                    highest_stream_id is None
                                    or _compare_stream_ids(stream_id, highest_stream_id)
                                    > 0
                                ):
                                    highest_stream_id = stream_id
                            except (ValueError, AttributeError):
                                pass

                            if (
                                not stream_mode
                                or event_name in stream_mode
                                or (
                                    (
                                        "messages" in stream_mode
                                        or "messages-tuple" in stream_mode
                                    )
                                    and event_name.startswith("messages")
                                )
                            ):
                                yield (event, message, stream_id)
                # stream events
                while True:
                    if store := await pubsub.get_message(timeout=timeout):
                        if LOG_LEVEL_DEBUG:
                            await logger.adebug(
                                "Received redis stream event",
                                run_id=str(run_id),
                                type=store["type"],
                                channel=store["channel"],
                                data=store["data"],
                            )

                        # Throw out subscription events that may happen if reconnection happens
                        if store["type"] not in PubSub.PUBLISH_MESSAGE_TYPES:
                            continue

                        decoded = decode_stream_message(
                            store["data"], channel=store["channel"]
                        )
                        # Dedupe messages from cached stream
                        if (
                            highest_stream_id is not None
                            and decoded.stream_id_bytes is not None
                            and _compare_stream_ids(
                                decoded.stream_id_bytes, highest_stream_id
                            )
                            <= 0
                        ):
                            continue
                        event = decoded.event_bytes
                        event_name = event.decode("utf-8")
                        message = decoded.message_bytes
                        len_str = decoded.stream_id_bytes
                        if event_name == "control":
                            if message == b"done":
                                timeout = DRAIN_TIMEOUT
                            else:
                                timeout = WAIT_LESS_TIMEOUT

                        # Here be dragons. For just about everything, stream_mode is None.
                        # The case where it's not is join_stream, and in that case there's a bunch of special cases (like messages and subgraphs) that have been broken for a while.
                        # This should add support for a lot of those cases, but it's finicky at best and really should just be removed.
                        elif (
                            not stream_mode
                            or event_name in stream_mode
                            or (
                                (
                                    "messages" in stream_mode
                                    or "messages-tuple" in stream_mode
                                )
                                and event_name.startswith("messages")
                            )
                        ):
                            yield (
                                event,
                                message,
                                len_str,
                            )
                    elif timeout == DRAIN_TIMEOUT:
                        break
                    else:
                        async with connect() as conn:
                            run_iter = await Runs.get(
                                conn, run_id, thread_id=thread_id, ctx=ctx
                            )
                            run = await anext(run_iter, None)
                        if run is None or run["status"] not in (
                            "pending",
                            "running",
                        ):
                            timeout = DRAIN_TIMEOUT
                        else:
                            # If the run is still running but we haven't gotten any events, go to the longer timeout
                            timeout = WAIT_TIMEOUT

                        if run is None and not ignore_404:
                            yield (
                                b"error",
                                json_dumpb(
                                    HTTPException(
                                        status_code=404,
                                        detail=f"Run with ID '{run_id}' not found. Please verify the ID is correct and the run hasn't been deleted or expired.",
                                    )
                                ),
                                None,
                            )
            except asyncio.CancelledError:
                if cancel_on_disconnect:
                    create_task(cancel_run(thread_id, run_id))

                # Don't do anything before cancelling the run to minimize race conditions
                elapsed_time = (datetime.now(UTC) - start_time).total_seconds()
                await logger.awarning(
                    f"Client disconnected after {elapsed_time} seconds. Consider adjusting the client or network timeouts if this is unexpected.",
                    run_id=str(run_id),
                    elapsed_time=elapsed_time,
                )
                raise
            finally:
                # Make sure to always clean up the pubsub
                await pubsub.__aexit__(None, None, None)

        @staticmethod
        async def check_run_stream_auth(
            run_id: UUID,
            thread_id: UUID,
            ctx: Auth.types.BaseAuthContext | None = None,
        ) -> None:
            filters = await Runs.Stream.handle_event(
                ctx,
                "read",
                Auth.types.ThreadsRead(run_id=run_id, thread_id=thread_id),
            )
            filter_clause, filter_params = _build_filter_query(
                filters=filters,
                table_alias="thread",
            )
            # TODO: There's definitely some bugs here when calling join with auth, need to fix: https://linear.app/langchain/issue/LGP-398/clean-up-stream-mode-in-runs
            if filter_params:
                query = f"""
                SELECT run_id FROM run
                JOIN thread USING (thread_id)
                WHERE run_id = %(run_id)s AND thread_id = %(thread_id)s
                {filter_clause}
                """
                params = {**filter_params, "run_id": run_id, "thread_id": thread_id}
                async with connect() as conn:
                    cur = await conn.execute(query, params, binary=True)
                    if not await cur.fetchone():
                        raise HTTPException(
                            status_code=404,
                            detail=f"Thread with ID '{thread_id}' not found. Please verify the ID is correct and the thread hasn't been deleted or expired.",
                        )

        @staticmethod
        async def _eval_script(
            stream_key: str,
            channel: str,
            event: str,
            raw_message: bytes,
            run_id: str,
        ) -> None:
            """Load-once & eval the Lua script."""
            redis_client = get_redis()
            if Runs.Stream._resumable_stream_script_sha is None:
                # SCRIPT LOAD is cheap and avoids race conditions
                Runs.Stream._resumable_stream_script_sha = (
                    await redis_client.script_load(
                        Runs.Stream._resumable_stream_publish_lua
                    )
                )
            try:
                await redis_client.evalsha(  # type: ignore[valid-type]
                    Runs.Stream._resumable_stream_script_sha,
                    2,
                    stream_key,
                    channel,
                    raw_message,  # type: ignore[valid-type] - if this isn't bytes, it's turned into a utf8 string that's not decoded
                    event,
                    str(RESUMABLE_STREAM_TTL_SECONDS),
                    run_id,
                )
            except redis.exceptions.NoScriptError:
                # Rare: script evicted from cache → fall back to full EVAL
                await logger.ainfo(
                    "Resumable stream script evicted from cache. Re-loading LUA script.",
                    stream_key=stream_key,
                    channel=channel,
                    run_event=event,
                    raw_message=raw_message,
                )
                Runs.Stream._resumable_stream_script_sha = (
                    await redis_client.script_load(
                        Runs.Stream._resumable_stream_publish_lua
                    )
                )
                await redis_client.evalsha(  # type: ignore[valid-type]
                    Runs.Stream._resumable_stream_script_sha,
                    2,
                    stream_key,
                    channel,
                    raw_message,  # type: ignore[valid-type] - if this isn't bytes, it's turned into a utf8 string that's not decoded
                    event,
                    str(RESUMABLE_STREAM_TTL_SECONDS),
                    run_id,
                )

        @staticmethod
        async def _eval_filter_script(
            stream_key: str,
            run_id: str,
            start_id: str,
        ) -> list:
            """Load-once & eval the filter Lua script."""
            redis_client = get_redis()
            if Runs.Stream._stream_filter_script_sha is None:
                # SCRIPT LOAD is cheap and avoids race conditions
                Runs.Stream._stream_filter_script_sha = await redis_client.script_load(
                    Runs.Stream._stream_filter_by_run_lua
                )
            try:
                return await redis_client.evalsha(  # type: ignore[valid-type]
                    Runs.Stream._stream_filter_script_sha,
                    1,
                    stream_key,
                    run_id,
                    start_id,
                )
            except redis.exceptions.NoScriptError:
                # Rare: script evicted from cache → fall back to full EVAL
                await logger.ainfo(
                    "Stream filter script evicted from cache. Re-loading LUA script.",
                    stream_key=stream_key,
                    run_id=run_id,
                    start_id=start_id,
                )
                Runs.Stream._stream_filter_script_sha = await redis_client.script_load(
                    Runs.Stream._stream_filter_by_run_lua
                )
                return await redis_client.evalsha(  # type: ignore[valid-type]
                    Runs.Stream._stream_filter_script_sha,
                    1,
                    stream_key,
                    run_id,
                    start_id,
                )

        @staticmethod
        async def publish(
            run_id: UUID | str,
            event: str,
            message: bytes,
            *,
            thread_id: UUID | str | None = None,
            resumable: bool = False,
        ) -> None:
            if len(message) > MAX_STREAM_CHUNK_SIZE_BYTES:
                await logger.awarning(
                    "Message too large to stream. Ignoring.",
                    run_id=run_id,
                    publish_event=event,
                    message_len=len(message),
                )
                return
            if not resumable:
                packet = STREAM_CODEC.encode(event, message)

                subs = await get_redis().publish(
                    CHANNEL_RUN_STREAM.format(thread_id, run_id), packet
                )
                if subs == 0:
                    if FF_LOG_DROPPED_EVENTS:
                        await logger.awarning(
                            "There were no subscribers when this event was published.",
                            run_id=run_id,
                            publish_event=event,
                            message_len=len(message),
                        )
                    else:
                        await logger.adebug(
                            "There were no subscribers when this event was published.",
                            run_id=run_id,
                            publish_event=event,
                            message_len=len(message),
                        )
                return
            stream_key = STREAM_THREAD_CACHE.format(thread_id)
            channel = CHANNEL_RUN_STREAM.format(thread_id, run_id)
            await Runs.Stream._eval_script(
                stream_key, channel, event, message, str(run_id)
            )


class Crons(Authenticated):
    resource = "crons"

    @staticmethod
    async def put(
        conn: AsyncConnection[DictRow],
        *,
        payload: dict,
        schedule: str,
        cron_id: UUID | None = None,
        thread_id: UUID | None = None,
        on_run_completed: Literal["delete", "keep"] | None = None,
        end_time: datetime | None = None,
        metadata: dict | None = None,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[Cron]:
        ctx = get_auth_ctx()
        user_id = ctx.user.identity if ctx is not None else None
        cron_id = cron_id or uuid7()
        try:
            thread_id = str(UUID(str(thread_id))) if thread_id else None  # type: ignore[invalid-assignment]
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid thread ID {thread_id}. Expected a UUID.",
            ) from None

        if thread_id is not None:
            effective_on_run_completed = None
        else:
            effective_on_run_completed = on_run_completed or "delete"

        metadata = metadata if metadata is not None else {}
        payload = payload if payload is not None else {}
        config = payload.get("config")
        if config is None:
            config = {}
            payload["config"] = config
        configurable = config.get("configurable")
        if configurable is None:
            configurable = {}
            config["configurable"] = configurable
        configurable["cron_id"] = str(cron_id)

        request_data = Auth.types.CronsCreate(
            payload=payload,
            schedule=schedule,
            cron_id=cron_id,
            thread_id=thread_id,
            user_id=user_id,
            end_time=end_time,
        )
        request_data["metadata"] = metadata  # type: ignore
        filters = await Crons.handle_event(ctx, "create", request_data)

        if not croniter.is_valid(schedule):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid cron schedule: '{schedule}'. Reason: Invalid cron schedule. "
                    "Ensure the schedule uses the standard cron format (minute hour day_of_month month day_of_week). "
                    "Example: '*/5 * * * *' for every 5 minutes."
                ),
            )

        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="c",
        )

        if filter_params and payload["assistant_id"] not in GRAPHS:
            # Auth filters present and assistant is a custom one (not a generic graph)
            # Need to build assistant filter queries too.
            assistant_filter_clause, assistant_filter_params = _build_filter_query(
                filters=filters,
                table_alias="assistant",
                start=len(filter_params),
            )
            filter_params.update(assistant_filter_params)
            authorized_assistant_cte = f"""
WITH authorized_assistant AS (
    SELECT assistant.assistant_id
    FROM assistant
    WHERE assistant.assistant_id = %(assistant_id)s
    {assistant_filter_clause}  -- only yield assistant if user can see it
), """
            insert_assistant_select = "authorized_assistant.assistant_id"
            insert_assistant_from = "FROM authorized_assistant"
        else:
            # Auth filters not present or assistant is a generic graph
            authorized_assistant_cte = "with "
            insert_assistant_select = "%(assistant_id)s"
            insert_assistant_from = ""

        assistant_id = get_assistant_id(payload["assistant_id"])
        payload["assistant_id"] = assistant_id

        if thread_id:
            thread_filter_clause, thread_filter_params = _build_filter_query(
                filters=filters,
                table_alias="thread",
                start=len(filter_params),
            )
            filter_params.update(thread_filter_params)

            authorized_thread_cte = f"""
{authorized_assistant_cte}authorized_thread AS (
    SELECT thread.thread_id
    FROM thread
    WHERE thread.thread_id = %(thread_id)s
    {thread_filter_clause}
),
"""
            insert_select = "authorized_thread.thread_id"
            insert_from = (
                "CROSS JOIN authorized_thread"
                if insert_assistant_from
                else "FROM authorized_thread"
            )
        else:
            # no thread_id => no separate thread filter needed
            authorized_thread_cte = authorized_assistant_cte
            insert_select = "%(thread_id)s"
            insert_from = ""

        query = f"""
{authorized_thread_cte}inserted_cron AS (
    INSERT INTO cron (
        cron_id, assistant_id, thread_id, user_id, end_time,
        schedule, payload, next_run_date, metadata, on_run_completed
    )
    SELECT
        %(cron_id)s, {insert_assistant_select}, {insert_select},
        %(user_id)s, %(end_time)s,
        %(schedule)s, %(payload)s, %(next_run_date)s, %(metadata)s, %(on_run_completed)s
    {insert_assistant_from}
    {insert_from}
    ON CONFLICT (cron_id) DO NOTHING
    RETURNING *
)
SELECT c.*
FROM inserted_cron c
UNION ALL
SELECT c.*
FROM cron c
WHERE c.cron_id = %(cron_id)s
{filter_clause if filter_params else ""}
LIMIT 1
        """

        params = {
            "cron_id": cron_id,
            "assistant_id": assistant_id,
            "thread_id": thread_id,
            "user_id": user_id,
            "end_time": end_time,
            "schedule": schedule,
            "payload": Jsonb(payload),
            "next_run_date": next_cron_date(schedule, datetime.now(UTC)),
            "metadata": Jsonb(metadata),
            "on_run_completed": effective_on_run_completed,
        }
        if filter_params:
            params.update(filter_params)
        cur = await conn.execute(query, params, binary=True)
        results = [row async for row in cur]

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"Thread with ID '{thread_id}' not found. Please verify the ID is correct and the thread hasn't been deleted or expired.",
            )

        async def consume():
            for row in results:
                yield {**row, "payload": json_loads(row["payload"])}

        return consume()

    @staticmethod
    async def delete(
        conn: AsyncConnection[DictRow],
        cron_id: UUID,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> AsyncIterator[UUID]:
        """Delete a cron by ID."""
        filters = await Crons.handle_event(
            ctx,
            "delete",
            Auth.types.CronsDelete(cron_id=cron_id),
        )

        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="cron",
        )

        query = """DELETE FROM cron WHERE cron.cron_id = %(cron_id)s"""

        params = {"cron_id": cron_id}
        if filter_params:
            query += filter_clause
            params.update(filter_params)

        query += " RETURNING cron_id"
        cur = await conn.execute(query, params, binary=True)

        return (row["cron_id"] async for row in cur)

    @staticmethod
    async def next(
        conn: AsyncConnection[DictRow],
    ) -> AsyncIterator[Cron]:
        """Get the next cron job to run."""
        # Internal API. Needs on auth.
        query = """select *, now() as now from cron
                where (end_time is null or end_time >= now())
                and next_run_date <= now()
                for no key update skip locked"""

        # Fetch all results before yielding first, to allow for connection re-use
        async with conn.transaction():
            async with await conn.execute(query, binary=True) as cur:
                rows = await cur.fetchall()
            for row in rows:
                yield {**row, "payload": json_loads(row["payload"])}

    @staticmethod
    async def set_next_run_date(
        conn: AsyncConnection[DictRow],
        cron_id: UUID,
        next_run_date: datetime,
    ) -> None:
        """Update next run date for a cron job."""
        # Internal API. No auth needed.
        query = "UPDATE cron SET next_run_date = %(next_run_date)s WHERE cron_id = %(cron_id)s"
        params = {"next_run_date": next_run_date, "cron_id": cron_id}
        await conn.execute(query, params)

    @staticmethod
    async def search(
        conn: AsyncConnection[DictRow],
        *,
        assistant_id: UUID | None,
        thread_id: UUID | None,
        limit: int,
        offset: int,
        sort_by: str | None = None,
        sort_order: str | None = None,
        select: list[CronSelectField] | None = None,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> tuple[AsyncIterator[Cron], int | None]:
        """Search all cron jobs"""
        filters = await Crons.handle_event(
            ctx,
            "search",
            Auth.types.CronsSearch(
                assistant_id=assistant_id,
                thread_id=thread_id,
                limit=limit,
                offset=offset,
            ),
        )

        table_aliases = ("cron", "thread") if thread_id else ("cron",)
        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias=table_aliases,
        )
        threads_join = (
            "JOIN thread USING (thread_id)" if (thread_id and filter_params) else ""
        )

        # Add sorting if specified
        sort_by = sort_by.lower() if sort_by else None
        if sort_by and sort_by in (
            "cron_id",
            "assistant_id",
            "thread_id",
            "next_run_date",
            "end_time",
            "created_at",
            "updated_at",
        ):
            sort_direction = (
                "ASC" if sort_order and sort_order.upper() == "ASC" else "DESC"
            )
            # Use case-insensitive sorting for UUID/string fields
            if sort_by in ["cron_id", "assistant_id", "thread_id"]:
                order_by = f" ORDER BY LOWER({sort_by}::text) {sort_direction}"
            else:
                # For datetime fields, sort normally
                order_by = f" ORDER BY {sort_by} {sort_direction}"
        elif sort_by is None:
            sort_by = "created_at"
            # Default sorting
            order_by = " ORDER BY created_at DESC"
        else:
            # Invalid sort_by value
            raise HTTPException(
                status_code=422,
                detail=f"Invalid sort_by field: '{sort_by}'. Valid options are: cron_id, assistant_id, thread_id, next_run_date, end_time, created_at, updated_at",
            )

        selected_columns = ", ".join(f"cron.{col}" for col in select) if select else "*"

        if thread_id:
            filter_thread = " AND cron.thread_id = %(thread_id)s"
            filter_params["thread_id"] = thread_id
        else:
            filter_thread = ""

        if assistant_id:
            filter_assistant = " AND cron.assistant_id = %(assistant_id)s"
            filter_params["assistant_id"] = assistant_id
        else:
            filter_assistant = ""
        query = f"""
                SELECT {selected_columns}
                    FROM cron {threads_join}
                    WHERE 1=1
                    {filter_thread}
                    {filter_assistant}
                    {filter_clause}
                {order_by}
                LIMIT %(limit)s OFFSET %(offset)s
                """
        filter_params.update(
            {
                "limit": limit + 1,
                "offset": offset,
            }
        )
        # Execute the main query
        cur = await conn.execute(query, filter_params, binary=True)
        results = await cur.fetchall()
        if len(results) <= limit:
            cursor = None
        else:
            cursor = offset + limit
            results = results[:limit]

        # Create cron objects from results, excluding the total_count field
        async def generate_results():
            for row in results:
                yield row

        return generate_results(), cursor

    @staticmethod
    async def count(
        conn: AsyncConnection[DictRow],
        *,
        assistant_id: UUID | None = None,
        thread_id: UUID | None = None,
        ctx: Auth.types.BaseAuthContext | None = None,
    ) -> int:
        """Get count of crons."""
        filters = await Crons.handle_event(
            ctx,
            "search",
            Auth.types.CronsSearch(
                assistant_id=assistant_id,
                thread_id=thread_id,
                limit=0,
                offset=0,
            ),
        )
        filter_clause, filter_params = _build_filter_query(
            filters=filters,
            table_alias="cron",
        )

        query = "SELECT COUNT(*) as count FROM cron WHERE 1=1"
        params = {**filter_params}

        if assistant_id:
            query += " AND assistant_id = %(assistant_id)s"
            params["assistant_id"] = assistant_id

        if thread_id:
            query += " AND thread_id = %(thread_id)s"
            params["thread_id"] = thread_id

        if filter_clause:
            query += " " + filter_clause

        cur = await conn.execute(query, params)
        row = await cur.fetchone()
        return row["count"] if row else 0


async def cancel_run(
    thread_id: UUID, run_id: UUID, ctx: Auth.types.BaseAuthContext | None = None
) -> None:
    async with connect() as conn:
        await Runs.cancel(conn, [run_id], thread_id=thread_id, ctx=ctx)


def _get_conn_info(pubsub: StreamHandler) -> dict[str, Any]:
    try:
        connection = pubsub.connection
        if connection is not None:
            return {
                "is_connected": connection.is_connected,
                "requests_pending": connection.requests_pending,
                "lag": connection.lag,
                "estimated_time_to_idle": connection.estimated_time_to_idle,
            }
    except Exception as exc:
        logger.warning(f"Error getting connection info: {repr(exc)}")
    return {}


async def mark_done(run_id: UUID, thread_id: UUID, resumable: bool) -> None:
    """Mark a run as done by setting its status to 'done'."""
    await Runs._signal_control(run_id, thread_id, "done", ttl=60)
    await Runs.Stream.publish(
        run_id, "control", b"done", thread_id=thread_id, resumable=resumable
    )


async def listen_for_cancellation(
    pubsub: StreamHandler, run_id: UUID, thread_id: UUID, done: ValueEvent
) -> None:
    await logger.ainfo("Listening for cancellation", run_id=str(run_id))
    try:
        if start_value := await get_redis().get(
            RUN_STATUS_STRING.format(thread_id, run_id)
        ):
            if start_value == b"rollback":
                await logger.ainfo("Received rollback signal", run_id=str(run_id))
                done.set(UserRollback())
            elif start_value == b"interrupt":
                await logger.ainfo("Received interrupt signal", run_id=str(run_id))
                done.set(UserInterrupt())

        async for event in pubsub.listen():
            payload = event["data"].decode()
            if payload == "rollback":
                await logger.ainfo("Received rollback signal", run_id=str(run_id))
                done.set(UserRollback())
            elif payload == "interrupt":
                await logger.ainfo("Received interrupt signal", run_id=str(run_id))
                done.set(UserInterrupt())
            return
    except Exception as exc:
        conn_info = _get_conn_info(pubsub)
        await logger.aexception(
            "listen_for_cancellation failed", exc_info=exc, **conn_info
        )
        done.set(
            RetryableException(f"listen_for_cancellation failed. \nError: {repr(exc)}")
        )
        raise


async def heartbeat(run_id: UUID):
    """Heartbeat to keep run from getting sweeped back to pending."""
    redis = get_redis()
    while True:
        await asyncio.sleep(BG_JOB_HEARTBEAT / 2)
        try:
            await redis.set(STRING_RUN_RUNNING.format(run_id), "1", ex=BG_JOB_HEARTBEAT)
        except Exception as exc:
            logger.exception(
                "Heartbeat iteration failed", exc_info=exc, run_id=str(run_id)
            )


async def wake_up_worker(delay: float = 0, count: int = 1) -> None:
    if delay:
        await asyncio.sleep(delay)
    await get_redis().lpush(LIST_RUN_QUEUE, *([1] * count))  # type: ignore[valid-type]


def _build_filter_query(
    *,
    filters: Auth.types.FilterType | None,
    metadata_field: str = "metadata",
    table_alias: str | tuple[str, ...] | None = None,
    prefix: str = " AND ",
    start: int = 0,
) -> tuple[str, dict]:
    if not filters:
        return "", {}

    conditions = []
    params = {}
    aliases = (
        (table_alias,)
        if table_alias is None or isinstance(table_alias, str)
        else table_alias
    )
    for i, (key, value) in enumerate(filters.items(), start=start):
        for alias in aliases:
            param_key = f"filter_{i}"
            field_path = f"{alias + '.' if alias else ''}{metadata_field}"

            if isinstance(value, dict):
                value_ops = set(value)
                if value_ops == {"$eq"}:
                    filter_value = value["$eq"]
                    conditions.append(f"{field_path} @> %({param_key})s::jsonb")
                    params[param_key] = orjson.dumps({key: filter_value}).decode(
                        "utf-8"
                    )
                elif value_ops == {"$contains"}:
                    filter_value = value["$contains"]
                    # array contains logic
                    # We'll assume metadata[key] is an array and filter_value must be in it
                    # We'll use a containment check: value in array
                    # One approach: ((metadata->key)::jsonb) @> [filter_value]::jsonb
                    # But we must ensure metadata[key] is array. Let's just guess:
                    if isinstance(filter_value, list):
                        # cast to text[] so to_jsonb(text[]) works
                        conditions.append(
                            f"(({field_path} -> %({param_key}_key)s)::jsonb) @> to_jsonb(%({param_key})s::text[])"
                        )
                    else:
                        # scalar – cast to the correct scalar type
                        cast = "text" if isinstance(filter_value, str) else "numeric"
                        conditions.append(
                            f"(({field_path} -> %({param_key}_key)s)::jsonb) @> to_jsonb(%({param_key})s::{cast})"
                        )
                    params[param_key] = filter_value
                    params[f"{param_key}_key"] = key
                else:
                    raise HTTPException(
                        status_code=500,
                        detail="Cannot filter entities: invalid filter expression.",
                    )
            else:
                conditions.append(f"{field_path} @> %({param_key})s::jsonb")
                params[param_key] = orjson.dumps({key: value}).decode("utf-8")

    if not conditions:
        return "", {}
    conditions_str = " AND ".join(conditions)
    return prefix + conditions_str, params


__all__ = [
    "Assistants",
    "Crons",
    "Runs",
    "Threads",
]
