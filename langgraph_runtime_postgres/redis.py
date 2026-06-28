
import asyncio
import itertools
import logging
import threading
from collections.abc import Callable
from typing import cast

import structlog
from langgraph_api.config import (
    REDIS_CLUSTER,
    REDIS_CONNECT_TIMEOUT,
    REDIS_HEALTH_CHECK_INTERVAL,
    REDIS_MAX_CONNECTIONS,
    REDIS_URI,
    STATS_INTERVAL_SECS,
)
from langgraph_api.config import (
    REDIS_KEY_PREFIX as _REDIS_KEY_PREFIX,
)
from redis.asyncio import Redis, RedisCluster
from redis.asyncio.client import PubSub
from redis.asyncio.cluster import ClusterNode, NodesManager
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialWithJitterBackoff
from redis.commands.core import AsyncPubSubCommands
from redis.event import (
    AfterPubSubConnectionInstantiationEvent,
    ClientType,
    EventDispatcher,
)

logger = structlog.stdlib.get_logger(__name__)


class LanggraphRedisCluster(RedisCluster, AsyncPubSubCommands):
    # We just need the publish command which isn't added to the RedisCluster class today
    pass
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTBkcU13PT06YzRmNmQ0ZDM=


class ClusterPubSub(PubSub):
    """
    Redis-py doesn't have an async cluster pubsub out of the box, so we implement it here.
    This builds on the async PubSub class, but uses a ClusterNode to manage connections instead of the connection pool.

    Other changes include:
    - ClusterNode doesn't have an encoder, so use the one from the cluster client
    - We dispatch a slightly malformed event because we don't have a connection pool (don't think this is used anywhere)
    """

    def __init__(
        self,
        cluster_node: ClusterNode,
        cluster_client: LanggraphRedisCluster,
        shard_hint: str | None = None,
        ignore_subscribe_messages: bool = False,
        encoder=None,
        push_handler_func: Callable | None = None,
        event_dispatcher: EventDispatcher | None = None,
    ):
        if event_dispatcher is None:
            self._event_dispatcher = EventDispatcher()
        else:
            self._event_dispatcher = event_dispatcher
        self.cluster_node = cluster_node
        self.cluster_client = cluster_client
        self.shard_hint = shard_hint
        self.ignore_subscribe_messages = ignore_subscribe_messages
        self.connection = None
        # we need to know the encoding options for this connection in order
        # to lookup channel and pattern names for callback handlers.
        self.encoder = encoder
        self.push_handler_func = push_handler_func
        if self.encoder is None:
            self.encoder = self.cluster_client.get_encoder()
        if self.encoder.decode_responses:
            self.health_check_response = [
                ["pong", self.HEALTH_CHECK_MESSAGE],
                self.HEALTH_CHECK_MESSAGE,
            ]
        else:
            self.health_check_response = [
                [b"pong", self.encoder.encode(self.HEALTH_CHECK_MESSAGE)],
                self.encoder.encode(self.HEALTH_CHECK_MESSAGE),
            ]
        if self.push_handler_func is None:
            _set_info_logger()
        self.channels = {}
        self.pending_unsubscribe_channels = set()
        self.patterns = {}
        self.pending_unsubscribe_patterns = set()
        self._lock = asyncio.Lock()

    async def aclose(self):
        # In case a connection property does not yet exist
        # (due to a crash earlier in the Redis() constructor), return
        # immediately as there is nothing to clean-up.
        if not hasattr(self, "connection"):
            return
        async with self._lock:
            if self.connection:
                await self.connection.disconnect()
                self.connection.deregister_connect_callback(self.on_connect)
                self.cluster_node.release(self.connection)
                self.connection = None
            self.channels = {}
            self.pending_unsubscribe_channels = set()
            self.patterns = {}
            self.pending_unsubscribe_patterns = set()

    async def connect(self):
        """
        Ensure that the PubSub is connected
        """
        if self.connection is None:
            self.connection = self.cluster_node.acquire_connection()
            # register a callback that re-subscribes to any channels we
            # were listening to when we were disconnected
            self.connection.register_connect_callback(self.on_connect)
        else:
            await self.connection.connect()
        if self.push_handler_func is not None:
            self.connection._parser.set_pubsub_push_handler(self.push_handler_func)

        self._event_dispatcher.dispatch(
            AfterPubSubConnectionInstantiationEvent(
                self.connection, self.cluster_node, ClientType.ASYNC, self._lock
            )
        )


# We create a global Redis client for the main thread
_aredis: Redis | LanggraphRedisCluster
_stats_task: asyncio.Task

# Thread-local storage for per-thread Redis clients
# This is used when BG_JOB_ISOLATED_LOOPS is True
_thread_local = threading.local()

# Determine the relevant classes to use depending on if the deployment uses a Redis cluster
_cls_cl = Redis if not REDIS_CLUSTER else LanggraphRedisCluster


def _create_redis_client() -> Redis | LanggraphRedisCluster:
    return _cls_cl.from_url(
        REDIS_URI,
        max_connections=REDIS_MAX_CONNECTIONS,
        socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
        socket_keepalive=True,
        decode_responses=False,
        health_check_interval=REDIS_HEALTH_CHECK_INTERVAL,
        retry=Retry(retries=3, backoff=ExponentialWithJitterBackoff(base=0.1, cap=2.0)),
    )


async def start_redis() -> None:
    global _aredis, _stats_task
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTBkcU13PT06YzRmNmQ0ZDM=

    try:
        # Create a redis client with retries
        # Note max_connections is per node in a cluster, might want to make this smaller so a single host doesn't get too many connections
        _aredis = _create_redis_client()

        # test the connection
        await asyncio.wait_for(_aredis.ping(), timeout=5.0)
    except TimeoutError:
        logger.exception("Redis ping timed out", redis_uri=REDIS_URI)
    except Exception as e:
        logger.exception("Redis ping failed", error=str(e), redis_uri=REDIS_URI)

    # start stats loop
    _stats_task = asyncio.create_task(stats_loop())


async def stop_redis() -> None:
    _stats_task.cancel("Shutting down Redis")
    await _aredis.aclose()


async def stats_loop() -> None:
    while True:
        pool_stats = redis_stats()
        await logger.ainfo("Redis pool stats", **pool_stats)
        await asyncio.sleep(STATS_INTERVAL_SECS)


def redis_stats() -> dict[str, int]:
    """Get stats for the main Redis client"""
    global _aredis
    if REDIS_CLUSTER:
        idle_connections = 0
        in_use_connections = 0
        max_connections = 0
        max_connections_per_node = REDIS_MAX_CONNECTIONS

        # Redis-py maintains a connection pool for each node
        for node in cast(
            LanggraphRedisCluster, _aredis
        ).nodes_manager.nodes_cache.values():
            idle_connections += len(node._free)
            in_use_connections += len(node._connections) - len(node._free)
            max_connections += node.max_connections

        return {
            "idle_connections": idle_connections,
            "in_use_connections": in_use_connections,
            "max_connections": max_connections,
            "max_connections_per_node": max_connections_per_node,
        }
    return {
        "idle_connections": len(_aredis.connection_pool._available_connections),
        "in_use_connections": len(_aredis.connection_pool._in_use_connections),
        "max_connections": _aredis.connection_pool.max_connections,
    }

# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTBkcU13PT06YzRmNmQ0ZDM=

def get_redis() -> Redis | LanggraphRedisCluster:
    if threading.current_thread() is threading.main_thread():
        return _aredis
    else:
        # Create a new Redis client for this thread if it doesn't exist
        if not hasattr(_thread_local, "redis_client"):
            _thread_local.redis_client = _create_redis_client()
            logger.info(
                "Created new thread-local Redis client",
                thread_name=threading.current_thread().name,
            )

        return _thread_local.redis_client


async def get_pubsub(
    *, channels: list[str] | None = None, patterns: list[str] | None = None
) -> PubSub:
    # Handle None values by converting to empty lists
    channels = channels or []
    patterns = patterns or []

    # Make sure there's at least one pattern or channel to subscribe to
    if not channels and not patterns:
        raise ValueError("At least one channel or pattern must be provided")

    redis = get_redis()
    if REDIS_CLUSTER:
        # Make sure the cluster client has been initialized or we'll try to check a slot before we've determined the relevant nodes
        await redis.initialize()

        # In order for pubsubs to work with patterns, we hash all the channels/patterns to the same slot. Assert this is true here.
        slot = None
        cluster = cast(LanggraphRedisCluster, redis)
        for key in [*channels, *patterns]:
            cur_slot = cluster.keyslot(key)
            if slot is None:
                slot = cur_slot
            elif slot != cur_slot:
                raise ValueError("All channels/patterns must hash to the same slot")

        # Each node has a separate redis client for that node. We can just leverage the underlying pubsub for this.
        # Might run into some scaling issues if the cluster re-slots due to scaling, but that's pretty rare and the next time we connect this should work fine.
        nodes_manager = cast(NodesManager, cluster.nodes_manager)
        node = nodes_manager.get_node_from_slot(int(slot))
        pubsub = ClusterPubSub(node, cluster)
    else:
        pubsub = redis.pubsub()

    if channels:
        await pubsub.subscribe(*channels)
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YTBkcU13PT06YzRmNmQ0ZDM=

    # There's a limitation in the Redis cluster client where we can't subscribe to patterns in a cluster
    # because you could end up on a different node from some of the channels.
    # We can kind of circumvent this by making sure to hash our patterns/channels so all channels for a
    # given pattern end up on the same node. Kind of difficult to enforce this though!
    # https://redis.readthedocs.io/en/stable/clustering.html#known-pubsub-limitations
    if patterns:
        await pubsub.psubscribe(*patterns)

    # Wait for receipt of the subscriptions so we know it's safe to start a run
    # Use a relatively short timeout so we don't hang too long if there are acknowledgement issues
    for _ in itertools.chain(channels, patterns):
        message = await pubsub.get_message(timeout=0.5)
        if message is None:
            await logger.awarning(
                "Timed out waiting for acknowledgement of subscription, continuing anyway"
            )
        else:
            await logger.adebug(
                "Received acknowledgement of subscription",
                message=message,
            )

    return pubsub


def _set_info_logger():
    # Copied from redis.utils
    if "push_response" not in logging.root.manager.loggerDict:
        logger = logging.getLogger("push_response")
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)


# keys
REDIS_KEY_PREFIX = f"{_REDIS_KEY_PREFIX.rstrip(':')}:" if _REDIS_KEY_PREFIX else ""
# Redis cluster needs something in "{}" to indicate a consistent "key"
# Alwyas use one of the hashed segements, but only use one at a time to ensure consistent hashing
RUN_ID_SEGMENT = "{{{}}}" if REDIS_CLUSTER else "{}"
RUN_ID_SEGMENT_NON_HASH = "{}"
THREAD_ID_SEGMENT = "{{{}}}" if REDIS_CLUSTER else "{}"
LICENSE_KEY_SEGMENT = "{{{}}}" if REDIS_CLUSTER else "{}"

# Channel for all run events, including control events. Should be used for general streaming.
CHANNEL_RUN_STREAM = (
    f"{REDIS_KEY_PREFIX}thread:{THREAD_ID_SEGMENT}:run:{RUN_ID_SEGMENT_NON_HASH}:stream"
)
CHANNEL_RUN_STREAM_OLD = f"{REDIS_KEY_PREFIX}run:{RUN_ID_SEGMENT}:stream"
# Stream to cache all run events for a thread. New unified cache using Redis streams.
STREAM_THREAD_CACHE = f"{REDIS_KEY_PREFIX}thread:{THREAD_ID_SEGMENT}:cache"
# Channel for control run events. Should be used to avoid checking all events of a run (e.g. cancellation listener).
CHANNEL_RUN_CONTROL = f"{REDIS_KEY_PREFIX}thread:{THREAD_ID_SEGMENT}:run:{RUN_ID_SEGMENT_NON_HASH}:control"
CHANNEL_RUN_CONTROL_OLD = f"{REDIS_KEY_PREFIX}run:{RUN_ID_SEGMENT}:control"
# Keep track of the run status as a key in redis. Should be used for initial checks to optimize if a run is already done.
RUN_STATUS_STRING = f"{REDIS_KEY_PREFIX}thread:{THREAD_ID_SEGMENT}:run:{RUN_ID_SEGMENT_NON_HASH}:control"
STRING_RUN_ATTEMPT = f"{REDIS_KEY_PREFIX}run:{RUN_ID_SEGMENT}:attempt"
STRING_RUN_RUNNING = f"{REDIS_KEY_PREFIX}run:{RUN_ID_SEGMENT}:running"

LIST_RUN_QUEUE = f"{REDIS_KEY_PREFIX}run:" + ("{queue}" if REDIS_CLUSTER else "queue")
LOCK_RUN_SWEEP = f"{REDIS_KEY_PREFIX}run:" + ("{sweep}" if REDIS_CLUSTER else "sweep")
LOCK_THREAD_SWEEP = f"{REDIS_KEY_PREFIX}thread:" + (
    "{sweep}" if REDIS_CLUSTER else "sweep"
)
LOCK_STORE_SWEEP = f"{REDIS_KEY_PREFIX}store:" + (
    "{sweep}" if REDIS_CLUSTER else "sweep"
)
# Keys to track when last sweep was performed to prevent thundering herd
STRING_THREAD_LAST_SWEEP = f"{REDIS_KEY_PREFIX}thread:" + (
    "{last_sweep}" if REDIS_CLUSTER else "last_sweep"
)
STRING_STORE_LAST_SWEEP = f"{REDIS_KEY_PREFIX}store:" + (
    "{last_sweep}" if REDIS_CLUSTER else "last_sweep"
)
# Keys for run stats caching to prevent thundering herd
LOCK_RUN_STATS = f"{REDIS_KEY_PREFIX}run:" + (
    "{stats_lock}" if REDIS_CLUSTER else "stats_lock"
)
STRING_RUN_STATS_CACHE = f"{REDIS_KEY_PREFIX}run:" + (
    "{stats_cache}" if REDIS_CLUSTER else "stats_cache"
)
# Keys for long query monitoring coordination
LOCK_LONG_QUERY_MONITOR = f"{REDIS_KEY_PREFIX}monitor:" + (
    "{long_query}" if REDIS_CLUSTER else "long_query"
)
STRING_LONG_QUERY_LAST_SCAN = f"{REDIS_KEY_PREFIX}monitor:" + (
    "{last_scan}" if REDIS_CLUSTER else "last_scan"
)
# Keys for license key coordination
LOCK_LICENSE_KEY = f"{REDIS_KEY_PREFIX}license_key_lock:{LICENSE_KEY_SEGMENT}"
STRING_LICENSE_KEY = f"{REDIS_KEY_PREFIX}license_key:{LICENSE_KEY_SEGMENT}"
# Keys for database migration coordination
LOCK_MIGRATION = f"{REDIS_KEY_PREFIX}migration:" + (
    "{lock}" if REDIS_CLUSTER else "lock"
)
