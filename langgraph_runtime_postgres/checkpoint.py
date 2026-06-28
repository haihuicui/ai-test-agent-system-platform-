
import asyncio
import builtins
import contextlib
import random
import typing
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from enum import Enum
from typing import Any, NamedTuple, cast

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.constants import TASKS
from langgraph_api import config as api_config
from langgraph_api.asyncio import (
    AsyncQueue,
    aclosing_aiter,
    call_soon_threadsafe,
)
from langgraph_api.feature_flags import OMIT_PENDING_SENDS
from langgraph_api.logging import LOG_LEVEL_DEBUG
from langgraph_api.schema import MetadataInput
from langgraph_api.serde import Fragment, Serializer, json_loads
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

logger = structlog.stdlib.get_logger(__name__)
PENDING_SENDS_CTE = (
    ""
    if OMIT_PENDING_SENDS
    else f""",
    (
        select array_agg(array[cw.type::bytea, cw.blob] order by cw.task_id, cw.idx)
        from checkpoint_writes cw
        where cw.thread_id = checkpoints.thread_id
            and cw.checkpoint_ns = checkpoints.checkpoint_ns
            and cw.checkpoint_id = checkpoints.parent_checkpoint_id
            and cw.channel = '{TASKS}'
    ) as pending_sends
"""
)

SELECT_SQL = f"""
select
    thread_id,
    checkpoint,
    checkpoint_ns,
    checkpoint_id,
    parent_checkpoint_id,
    metadata,
    (
        select array_agg(array[bl.channel::bytea, bl.type::bytea, bl.blob])
        from jsonb_each_text(checkpoint -> 'channel_versions')
        inner join checkpoint_blobs bl
            on bl.thread_id = checkpoints.thread_id
            and bl.checkpoint_ns = checkpoints.checkpoint_ns
            and bl.channel = jsonb_each_text.key
            and bl.version = jsonb_each_text.value
    ) as channel_values,
    (
        select
        array_agg(array[cw.task_id::text::bytea, cw.channel::bytea, cw.type::bytea, cw.blob] order by cw.task_id, cw.idx)
        from checkpoint_writes cw
        where cw.thread_id = checkpoints.thread_id
            and cw.checkpoint_ns = checkpoints.checkpoint_ns
            and cw.checkpoint_id = checkpoints.checkpoint_id
    ) as pending_writes{PENDING_SENDS_CTE}
from checkpoints """


class CheckpointBlob(NamedTuple):
    thread_id: str
    checkpoint_ns: str
    channel: str
    version: str
    type: str
    blob: bytes | None


class CheckpointPut(NamedTuple):
    run_id: str | None
    thread_id: str
    checkpoint_ns: str
    checkpoint_id: uuid.UUID
    parent_checkpoint_id: uuid.UUID | None
    checkpoint: Jsonb
    metadata: Jsonb

# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YkZkaU53PT06MzdkMTA5MjE=

class CheckpointWrite(NamedTuple):
    # thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, blob
    thread_id: str
    checkpoint_ns: str
    checkpoint_id: str
    task_id: str
    idx: int
    channel: str
    type: str
    blob: bytes


class ItemType(Enum):
    CHECKPOINT = "put"
    WRITE = "write"
    BLOB = "blob"


class CheckpointQueueItem(NamedTuple):
    fut: tuple[asyncio.AbstractEventLoop, asyncio.Future]
    items: typing.Sequence[CheckpointPut | CheckpointWrite | CheckpointBlob]


PUTS_QUEUE = AsyncQueue[CheckpointQueueItem]()


class Checkpointer(BaseCheckpointSaver):
    latest_iter: AsyncIterator[CheckpointTuple] | None

    def __init__(
        self,
        conn: AsyncConnection | None = None,
        latest: AsyncIterator[CheckpointTuple] | None = None,
        unpack_hook: Callable[[int, bytes], Any] | None = None,
        use_direct_connection: bool = False,
    ) -> None:
        if unpack_hook is not None:
            serde = Serializer(__unpack_ext_hook__=unpack_hook)
        else:
            serde = Serializer()
        if api_config.LANGGRAPH_AES_KEY:
            serde = EncryptedSerializer.from_pycryptodome_aes(
                serde, key=api_config.LANGGRAPH_AES_KEY
            )
        super().__init__(serde=serde)
        self.loop = asyncio.get_running_loop()
        self.latest_iter = latest
        self.latest_tuple: CheckpointTuple | None = None
        self.conn = conn
        self.use_direct_connection = use_direct_connection
        if conn is None and use_direct_connection:
            raise ValueError(
                "use_direct_connection requires a connection to be provided."
            )

    @contextlib.asynccontextmanager
    async def _connect(self) -> AsyncIterator[AsyncConnection]:
        from langgraph_runtime_postgres import database

        if self.conn is None:
            async with database.connect() as conn:
                yield conn
        else:
            yield self.conn

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        where, args = self._search_where(config, filter, before)
        query = SELECT_SQL + where + " ORDER BY checkpoint_id DESC"
        if limit:
            query += f" LIMIT {limit}"
        async with self._connect() as conn, conn.cursor(binary=True) as cur:
            async for value in await cur.execute(query, args, binary=True):
                yield CheckpointTuple(
                    {
                        "configurable": {
                            "thread_id": value["thread_id"],
                            "checkpoint_ns": value["checkpoint_ns"],
                            "checkpoint_id": value["checkpoint_id"],
                        }
                    },
                    await asyncio.to_thread(
                        self._load_checkpoint,
                        value["checkpoint"],
                        value["channel_values"],
                        None if OMIT_PENDING_SENDS else value["pending_sends"],
                    ),
                    json_loads(value["metadata"]),
                    (
                        {
                            "configurable": {
                                "thread_id": value["thread_id"],
                                "checkpoint_ns": value["checkpoint_ns"],
                                "checkpoint_id": value["parent_checkpoint_id"],
                            }
                        }
                        if value["parent_checkpoint_id"]
                        else None
                    ),
                    await asyncio.to_thread(self._load_writes, value["pending_writes"]),
                )
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YkZkaU53PT06MzdkMTA5MjE=

    async def aget_iter(self, config: RunnableConfig) -> AsyncIterator[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id")
        if checkpoint_id:
            args = (thread_id, checkpoint_ns, checkpoint_id)
            where = "WHERE thread_id = %s AND checkpoint_ns = %s AND checkpoint_id = %s"
        else:
            args = (thread_id, checkpoint_ns)
            where = "WHERE thread_id = %s AND checkpoint_ns = %s ORDER BY checkpoint_id DESC LIMIT 1"
        async with self._connect() as conn:
            cur = await conn.execute(
                SELECT_SQL + where,
                args,
                binary=True,
            )

            return (
                CheckpointTuple(
                    {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": value["checkpoint_ns"],
                            "checkpoint_id": value["checkpoint_id"],
                        }
                    },
                    await asyncio.to_thread(
                        self._load_checkpoint,
                        value["checkpoint"],
                        value["channel_values"],
                        None if OMIT_PENDING_SENDS else value["pending_sends"],
                    ),
                    json_loads(value["metadata"]),
                    (
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": value["checkpoint_ns"],
                                "checkpoint_id": value["parent_checkpoint_id"],
                            }
                        }
                        if value["parent_checkpoint_id"]
                        else None
                    ),
                    await asyncio.to_thread(self._load_writes, value["pending_writes"]),
                )
                async for value in aclosing_aiter(cur)
            )

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        if self.latest_iter is not None:
            try:
                latest_tuple = await anext(self.latest_iter, None)
                if not latest_tuple:
                    return None
                elif latest_tuple.config["configurable"]["thread_id"] == config[
                    "configurable"
                ]["thread_id"] and latest_tuple.config["configurable"][
                    "checkpoint_ns"
                ] == config["configurable"].get("checkpoint_ns", ""):
                    return latest_tuple
            finally:
                self.latest_iter = None

        ckpt_tuple = await anext(await self.aget_iter(config), None)
        if LOG_LEVEL_DEBUG and ckpt_tuple is not None:
            parent_config = ckpt_tuple.parent_config or {}
            await logger.adebug(
                "Checkpoint retrieved",
                thread_id=ckpt_tuple.config["configurable"]["thread_id"],
                checkpoint_ns=ckpt_tuple.config["configurable"]["checkpoint_ns"],
                checkpoint_id=ckpt_tuple.config["configurable"]["checkpoint_id"],
                parent_checkpoint_id=parent_config.get("configurable", {}).get(
                    "checkpoint_id"
                ),
                requested_checkpoint_ns=config["configurable"].get("checkpoint_ns", ""),
                requested_checkpoint_id=config["configurable"].get("checkpoint_id"),
            )
        return ckpt_tuple

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        next_versions: dict[str, str],
    ) -> RunnableConfig:
        configurable = config["configurable"].copy()
        run_id = configurable.pop("run_id", None)
        thread_id = configurable.pop("thread_id")
        checkpoint_ns = configurable.pop("checkpoint_ns", "")
        checkpoint_id = configurable.pop("checkpoint_id", None)
        copy = checkpoint.copy()
        copy["channel_values"] = copy["channel_values"].copy()
        copy.pop("pending_sends", None)  # saved in aput_writes
        next_config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }
        # inline primitive values in checkpoint table
        # others are stored in blobs table
        blob_values = {}
        for k, v in checkpoint["channel_values"].items():
            if v is None or isinstance(v, str | int | float | bool):
                pass
            else:
                blob_values[k] = copy["channel_values"].pop(k)
        if blob_versions := {
            k: v for k, v in next_versions.items() if k in blob_values
        }:
            blobs = await asyncio.to_thread(
                self._dump_blobs,
                thread_id,
                checkpoint_ns,
                blob_values,
                blob_versions,
            )
        else:
            blobs = []
        puts = CheckpointPut(
            run_id,
            thread_id,
            checkpoint_ns,
            _ensure_uuid(checkpoint["id"]),
            _ensure_uuid(checkpoint_id)
            if checkpoint_id
            else None,  # parent_checkpoint_id
            Jsonb(copy),
            # Merging `configurable` and `metadata` will persist graph_id,
            # assistant_id, and all assistant and run configurable fields
            # to the checkpoint metadata.
            Jsonb(
                {
                    **{k: v for k, v in configurable.items() if not k.startswith("__")},
                    **config.get("metadata", {}),
                    **metadata,
                }
            ),
        )

        try:
            if self.use_direct_connection and self.conn is not None:
                await self._execute_puts_direct(self.conn, blobs, [puts], [])
            else:
                put_fut = self.loop.create_future()
                call_soon_threadsafe(
                    PUTS_QUEUE.put_nowait,
                    CheckpointQueueItem((self.loop, put_fut), (puts, *blobs)),
                )
                await put_fut
            return next_config
        except Exception as e:
            await logger.aerror(
                "Failed to put checkpoint",
                thread_id=config["configurable"]["thread_id"],
                checkpoint_ns=config["configurable"].get("checkpoint_ns"),
                checkpoint_id=config["configurable"].get("checkpoint_id"),
                exc_info=e,
            )
            raise

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        checkpoint_writes = await asyncio.to_thread(
            self._dump_writes,
            config["configurable"]["thread_id"],
            config["configurable"]["checkpoint_ns"],
            config["configurable"]["checkpoint_id"],
            task_id,
            writes,
        )
        try:
            if self.use_direct_connection and self.conn is not None:
                await self._execute_puts_direct(self.conn, [], [], checkpoint_writes)
            else:
                fut = self.loop.create_future()
                call_soon_threadsafe(
                    PUTS_QUEUE.put_nowait,
                    CheckpointQueueItem((self.loop, fut), checkpoint_writes),
                )
                await fut
        except Exception as e:
            await logger.aerror(
                "Failed to put writes",
                thread_id=config["configurable"]["thread_id"],
                checkpoint_ns=config["configurable"]["checkpoint_ns"],
                checkpoint_id=config["configurable"]["checkpoint_id"],
                task_id=task_id,
                exc_info=e,
            )
            raise

    def get_next_version(self, current: str | None, channel: None) -> str:
        if current is None:
            current_v = 0
        elif isinstance(current, int):
            current_v = current
        else:
            current_v = int(current.split(".")[0])
        next_v = current_v + 1
        next_h = random.random()
        return f"{next_v:032}.{next_h:016}"

    def _load_checkpoint(
        self,
        checkpoint_f: Fragment,
        blob_values: list[tuple[bytes, bytes, bytes]],
        pending_sends: list[tuple[bytes, bytes]] | None,
    ) -> Checkpoint:
        checkpoint = json_loads(checkpoint_f)
        return {
            **checkpoint,
            "pending_sends": [
                self.serde.loads_typed((c.decode(), b)) for c, b in pending_sends or []
            ],
            "channel_values": {
                **checkpoint.get("channel_values", {}),
                **self._load_blobs(blob_values),
            },
        }

    def _load_blobs(
        self, blob_values: list[tuple[bytes, bytes, bytes]]
    ) -> dict[str, Any]:
        if not blob_values:
            return {}
        return {
            k.decode(): self.serde.loads_typed((t.decode(), v))
            for k, t, v in blob_values
            if t.decode() != "empty"
        }

    def _dump_blobs(
        self,
        thread_id: str,
        checkpoint_ns: str,
        values: dict[str, Any],
        versions: dict[str, str],
    ) -> list[CheckpointBlob]:
        if not versions:
            return []

        rows: list[CheckpointBlob] = []
        for k, ver in versions.items():
            if k in values:
                t, b = cast(tuple[str, bytes], self.serde.dumps_typed(values[k]))
            else:
                t, b = "empty", None
            rows.append(CheckpointBlob(thread_id, checkpoint_ns, k, ver, t, b))
        return rows
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YkZkaU53PT06MzdkMTA5MjE=

    def _load_writes(
        self, writes: list[tuple[bytes, bytes, bytes, bytes]]
    ) -> list[tuple[str, str, Any]]:
        return (
            [
                (
                    tid.decode(),
                    channel.decode(),
                    self.serde.loads_typed((t.decode(), v)),
                )
                for tid, channel, t, v in writes
            ]
            if writes
            else []
        )

    def _dump_writes(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        task_id: str,
        writes: list[tuple[str, Any]],
    ) -> list[CheckpointWrite]:
        return [
            CheckpointWrite(
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                task_id,
                WRITES_IDX_MAP.get(channel, idx),
                channel,
                *self.serde.dumps_typed(value),
            )
            for idx, (channel, value) in enumerate(writes)
        ]

    def _search_where(
        self,
        config: RunnableConfig | None,
        filter: MetadataInput,
        before: RunnableConfig | None = None,
    ) -> tuple[str, list[Any]]:
        """Return WHERE clause predicates for alist() given config, filter, cursor.

        This method returns a tuple of a string and a tuple of values. The string
        is the parametered WHERE clause predicate (including the WHERE keyword):
        "WHERE column1 = $1 AND column2 IS $2". The list of values contains the
        values for each of the corresponding parameters.
        """
        wheres = []
        param_values = []

        # construct predicate for config filter
        if config:
            wheres.append("thread_id = %s ")
            param_values.append(config["configurable"]["thread_id"])
            checkpoint_ns = config["configurable"].get("checkpoint_ns")
            if checkpoint_ns is not None:
                wheres.append("checkpoint_ns = %s ")
                param_values.append(checkpoint_ns)

        # construct predicate for metadata filter
        if filter:
            wheres.append("metadata @> %s ")
            param_values.append(Jsonb(filter))

        # construct predicate for `before`
        if before is not None:
            wheres.append("checkpoint_id < %s ")
            param_values.append(before["configurable"]["checkpoint_id"])

        return (
            "WHERE " + " AND ".join(wheres) if wheres else "",
            param_values,
        )

    async def _execute_puts_direct(
        self,
        conn: AsyncConnection,
        blobs: list[CheckpointBlob],
        checkpoints: list[CheckpointPut],
        writes: list[CheckpointWrite],
    ) -> None:
        """Execute checkpoint puts directly using the provided connection."""
        async with conn.cursor(binary=True) as cur:
            # Insert blobs
            if blobs:
                copy_sql = """
                    COPY checkpoint_blobs
                         (thread_id, checkpoint_ns, channel, version, type, blob)
                    FROM STDIN
                """
                async with cur.copy(copy_sql) as cp:
                    for row in blobs:
                        await cp.write_row(row)

            if checkpoints:
                copy_sql = """
                    COPY checkpoints
                         (run_id, thread_id, checkpoint_ns, checkpoint_id,
                          parent_checkpoint_id, checkpoint, metadata)
                    FROM STDIN
                """
                async with cur.copy(copy_sql) as cp:
                    for row in checkpoints:
                        await cp.write_row(row)

            # Insert writes and check for data conflicts
            if writes:
                await cur.executemany(
                    """INSERT INTO checkpoint_writes (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, blob)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
                    DO UPDATE SET blob = EXCLUDED.blob
                    WHERE checkpoint_writes.channel = EXCLUDED.channel
                      AND checkpoint_writes.type = EXCLUDED.type""",
                    writes,
                )

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        """List checkpoints from the database.

        This method retrieves a list of checkpoint tuples from the Postgres database based
        on the provided config. The checkpoints are ordered by checkpoint ID in descending order (newest first).

        Args:
            config (Optional[RunnableConfig]): Base configuration for filtering checkpoints.
            filter (Optional[Dict[str, Any]]): Additional filtering criteria for metadata.
            before (Optional[RunnableConfig]): If provided, only checkpoints before the specified checkpoint ID are returned. Defaults to None.
            limit (Optional[int]): Maximum number of checkpoints to return.

        Yields:
            Iterator[CheckpointTuple]: An iterator of matching checkpoint tuples.
        """
        aiter_ = self.alist(config, filter=filter, before=before, limit=limit)
        while True:
            try:
                yield asyncio.run_coroutine_threadsafe(
                    anext(aiter_), self.loop
                ).result()
            except StopAsyncIteration:
                break

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Get a checkpoint tuple from the database.

        This method retrieves a checkpoint tuple from the Postgres database based on the
        provided config. If the config contains a "checkpoint_id" key, the checkpoint with
        the matching thread ID and "checkpoint_id" is retrieved. Otherwise, the latest checkpoint
        for the given thread ID is retrieved.

        Args:
            config (RunnableConfig): The config to use for retrieving the checkpoint.

        Returns:
            Optional[CheckpointTuple]: The retrieved checkpoint tuple, or None if no matching checkpoint was found.
        """
        return asyncio.run_coroutine_threadsafe(
            self.aget_tuple(config), self.loop
        ).result()

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict[str, str],
    ) -> RunnableConfig:
        """Save a checkpoint to the database.

        This method saves a checkpoint to the Postgres database. The checkpoint is associated
        with the provided config and its parent config (if any).

        Args:
            config (RunnableConfig): The config to associate with the checkpoint.
            checkpoint (Checkpoint): The checkpoint to save.
            metadata (CheckpointMetadata): Additional metadata to save with the checkpoint.
            new_versions (ChannelVersions): New channel versions as of this write.

        Returns:
            RunnableConfig: Updated configuration after storing the checkpoint.
        """
        return asyncio.run_coroutine_threadsafe(
            self.aput(config, checkpoint, metadata, new_versions), self.loop
        ).result()

    def put_writes(
        self,
        config: RunnableConfig,
        writes: builtins.list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Store intermediate writes linked to a checkpoint.

        This method saves intermediate writes associated with a checkpoint to the database.

        Args:
            config (RunnableConfig): Configuration of the related checkpoint.
            writes (Sequence[Tuple[str, Any]]): List of writes to store, each as (channel, value) pair.
            task_id (str): Identifier for the task creating the writes.
        """
        return asyncio.run_coroutine_threadsafe(
            self.aput_writes(config, writes, task_id), self.loop
        ).result()


_ingestion_loop_task: asyncio.Task | None = None


async def start_checkpoint_ingestion_loop() -> None:
    global _ingestion_loop_task
    if _ingestion_loop_task is not None:
        return
    _ingestion_loop_task = asyncio.create_task(checkpoint_ingestion_loop())


async def stop_checkpoint_ingestion_loop() -> None:
    global _ingestion_loop_task
    if _ingestion_loop_task is None:
        return
    _ingestion_loop_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await _ingestion_loop_task
    _ingestion_loop_task = None


async def checkpoint_ingestion_loop() -> None:
    if api_config.IS_EXECUTOR_ENTRYPOINT:
        await logger.adebug("Executor entrypoint, skipping checkpointer ingestion loop")
        return
    await logger.ainfo("Starting checkpointer ingestion loop")
    while True:
        try:
            await PUTS_QUEUE.wait()
            await _ingest_batch()
        except asyncio.CancelledError:
            await logger.ainfo("Checkpointer ingestion task cancelled. Draining queue.")
            break
        except Exception as e:
            await logger.aexception("Checkpointer ingestion task failed", exc_info=e)

    # One last batch
    try:
        await _ingest_batch()
    except Exception as e:
        await logger.aexception("Final checkpointer ingestion batch failed", exc_info=e)
        raise


async def _ingest_batch():
    from langgraph_runtime_postgres import database
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YkZkaU53PT06MzdkMTA5MjE=

    futs = []
    blobs: list[CheckpointBlob] = []
    checkpoints: list[CheckpointPut] = []
    writes: list[CheckpointWrite] = []
    # accumulate operations scheduled in same tick
    thread_ids = set()
    while True:
        try:
            (loop, fut), items = PUTS_QUEUE.get_nowait()
            for item in items:
                thread_ids.add(item.thread_id)
                if isinstance(item, CheckpointBlob):
                    blobs.append(item)
                elif isinstance(item, CheckpointPut):
                    checkpoints.append(item)
                elif isinstance(item, CheckpointWrite):
                    writes.append(item)
                else:
                    raise ValueError(f"Unknown item type: {type(item)}")
            futs.append((loop, fut))
        except asyncio.QueueEmpty:
            break

    try:
        await logger.adebug(
            "Ingesting puts",
            n_threads=len(thread_ids),
            blobs=len(blobs),
            checkpoints=len(checkpoints),
            writes=len(writes),
        )
        async with (
            database.connect() as conn,
            conn.transaction(),
            conn.cursor(binary=True) as cur,
        ):
            # Insert blobs
            if blobs:
                copy_sql = """
                    COPY checkpoint_blobs
                         (thread_id, checkpoint_ns, channel, version, type, blob)
                    FROM STDIN
                """
                async with cur.copy(copy_sql) as cp:
                    for row in blobs:
                        await cp.write_row(row)

            if checkpoints:
                copy_sql = """
                    COPY checkpoints
                         (run_id, thread_id, checkpoint_ns, checkpoint_id,
                          parent_checkpoint_id, checkpoint, metadata)
                    FROM STDIN
                """
                async with cur.copy(copy_sql) as cp:
                    for row in checkpoints:
                        await cp.write_row(row)
                        if LOG_LEVEL_DEBUG:
                            await logger.adebug(
                                "Checkpoint put",
                                run_id=row.run_id,
                                thread_id=row.thread_id,
                                checkpoint_ns=row.checkpoint_ns,
                                checkpoint_id=row.checkpoint_id,
                                parent_checkpoint_id=row.parent_checkpoint_id,
                            )

            # Insert writes and check for data conflicts
            if writes:
                await cur.executemany(
                    """INSERT INTO checkpoint_writes (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, blob)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
                    DO UPDATE SET blob = EXCLUDED.blob
                    WHERE checkpoint_writes.channel = EXCLUDED.channel
                      AND checkpoint_writes.type = EXCLUDED.type""",
                    writes,
                )
        for loop, fut in futs:
            if not fut.done():
                try:
                    loop.call_soon_threadsafe(fut.set_result, None)
                except Exception as e:
                    logger.exception("Failed to set result", exc_info=e)
    except (asyncio.CancelledError, Exception) as e:
        for loop, fut in futs:
            if not fut.done():
                try:
                    loop.call_soon_threadsafe(fut.set_exception, e)
                except Exception as e:
                    logger.exception("Failed to set exception", exc_info=e)
        raise


def _ensure_uuid(value: str | uuid.UUID) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(value)


__all__ = ["Checkpointer", "checkpoint_ingestion_loop"]
