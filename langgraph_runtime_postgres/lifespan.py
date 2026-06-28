
import asyncio
import signal
from contextlib import asynccontextmanager
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkhsbmFRPT06NzY0NjYxYTE=

import structlog
from langchain_core.runnables.config import RunnableConfig, var_child_runnable_config
from langgraph.constants import CONF
from langgraph_license.validation import (
    check_license_periodically,
    get_license_status,
    plus_features_enabled,
)
from starlette.applications import Starlette

from langgraph_runtime_postgres import checkpoint, database, long_query_monitor, queue

logger = structlog.stdlib.get_logger(__name__)
# Tracks the most recent uncaught startup failure so callers can report it.
_LAST_LIFESPAN_ERROR: BaseException | None = None


def get_last_error() -> BaseException | None:
    return _LAST_LIFESPAN_ERROR


@asynccontextmanager
async def lifespan(
    app: Starlette | None = None,
    *,
    cancel_event: asyncio.Event | None = None,
    with_cron_scheduler: bool = True,
    taskset: set[asyncio.Task] | None = None,
    grpc_port: int | None = None,
):
    # Import at point of use to avoid circular dependencies
    from langgraph_api import (
        __version__,
        config,
        cron_scheduler,
        feature_flags,
        graph,
        http,
        metadata,
        thread_ttl,
    )
    from langgraph_api import asyncio as langgraph_asyncio
    from langgraph_api import (
        store as api_store,
    )
    from langgraph_api.js import ui

    global _LAST_LIFESPAN_ERROR
    _LAST_LIFESPAN_ERROR = None

    await logger.ainfo(
        f"Starting Postgres runtime with langgraph-api={__version__}",
        version=__version__,
    )

    try:
        current_loop = asyncio.get_running_loop()
        langgraph_asyncio.set_event_loop(current_loop)
    except RuntimeError:
        await logger.aerror("Failed to set loop")

    # Need access to redis client in get_license_status
    await database.start_pool()
    await checkpoint.start_checkpoint_ingestion_loop()

    if not await get_license_status():
        raise ValueError(
            "License verification failed. Please ensure proper configuration:\n"
            "- For local development, set a valid LANGSMITH_API_KEY for an account with LangGraph Cloud access "
            "in the environment defined in your langgraph.json file.\n"
            "- For production, configure the LANGGRAPH_CLOUD_LICENSE_KEY environment variable "
            "with your LangGraph Cloud license key.\n"
            "Review your configuration settings and try again. If issues persist, "
            "contact support for assistance."
        )
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkhsbmFRPT06NzY0NjYxYTE=

    # needs to be initialized after get_license_status to get CUSTOMER_ID and CUSTOMER_NAME
    if config.LANGGRAPH_LOGS_ENABLED:
        from langgraph_api import self_hosted_logs

        self_hosted_logs.initialize_self_hosted_logs()

    await http.start_http_client()
    await ui.start_ui_bundler()

    # Connect to shared gRPC client if using core API--this warms the pool of
    # connections and verifies initial connectivity.
    if feature_flags.FF_USE_CORE_API:
        from langgraph_api.grpc.client import get_shared_client

        await get_shared_client()

    # needs to be initialized after get_license_status to get CUSTOMER_ID and CUSTOMER_NAME
    if config.LANGGRAPH_METRICS_ENABLED:
        from langgraph_api import self_hosted_metrics

        self_hosted_metrics.initialize_self_hosted_metrics()

    async def _log_graph_load_failure(err: graph.GraphLoadError) -> None:
        cause = err.__cause__ or err.cause
        log_fields = err.log_fields()
        log_fields["action"] = "fix_user_graph"
        await logger.aerror(
            f"Graph '{err.spec.id}' failed to load: {err.cause_message}",
            **log_fields,
        )
        await logger.adebug(
            "Full graph load failure traceback (internal)",
            **{k: v for k, v in log_fields.items() if k != "user_traceback"},
            exc_info=cause,
        )

    try:
        async with langgraph_asyncio.SimpleTaskGroup(
            cancel=True, cancel_event=cancel_event, taskgroup_name="Lifespan"
        ) as tg:
            tg.create_task(metadata.metadata_loop())
            tg.create_task(check_license_periodically())
            await api_store.collect_store_from_env()
            store_instance = await api_store.get_store()
            if not api_store.CUSTOM_STORE:
                tg.create_task(store_instance.start_ttl_sweeper())  # type: ignore
            else:
                await logger.ainfo("Using custom store. Skipping store TTL sweeper.")
            tg.create_task(thread_ttl.thread_ttl_sweep_loop())
            tg.create_task(long_query_monitor.long_query_monitor_loop())

            if feature_flags.USE_RUNTIME_CONTEXT_API:
                from langgraph._internal._constants import CONFIG_KEY_RUNTIME
                from langgraph.runtime import Runtime

                langgraph_config: RunnableConfig = {
                    CONF: {CONFIG_KEY_RUNTIME: Runtime(store=store_instance)}
                }
            else:
                from langgraph.constants import CONFIG_KEY_STORE
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkhsbmFRPT06NzY0NjYxYTE=

                langgraph_config = {CONF: {CONFIG_KEY_STORE: store_instance}}

            var_child_runnable_config.set(langgraph_config)

            # Keep after the setter above so users can access the store from within the factory function
            try:
                await graph.collect_graphs_from_env(True)
            except graph.GraphLoadError as exc:
                _LAST_LIFESPAN_ERROR = exc
                await _log_graph_load_failure(exc)
                raise
            if grpc_port:
                from langgraph_runtime_postgres.executor_service import start_executor

                tg.create_task(start_executor(grpc_port))
            elif config.N_JOBS_PER_WORKER > 0:
                tg.create_task(queue_with_signal())
            else:
                await logger.ainfo("N_JOBS_PER_WORKER is 0. Skipping queue.")
            if (
                with_cron_scheduler
                and config.FF_CRONS_ENABLED
                and plus_features_enabled()
            ):
                tg.create_task(cron_scheduler.cron_scheduler())
            yield
    except graph.GraphLoadError as exc:
        _LAST_LIFESPAN_ERROR = exc
        raise
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        _LAST_LIFESPAN_ERROR = exc
        logger.exception("Lifespan failed", exc_info=True)
    finally:
        await api_store.exit_store()
        await ui.stop_ui_bundler()
        if config.LANGGRAPH_METRICS_ENABLED:
            from langgraph_api import self_hosted_metrics

            self_hosted_metrics.shutdown_self_hosted_metrics()

        await graph.stop_remote_graphs()
        await http.stop_http_client()

        # Close shared gRPC client if using core API
        if feature_flags.FF_USE_CORE_API:
            from langgraph_api.grpc.client import close_shared_client

            await close_shared_client()

        await checkpoint.stop_checkpoint_ingestion_loop()
        await database.stop_pool()

        if config.LANGGRAPH_LOGS_ENABLED:
            from langgraph_api import self_hosted_logs

            self_hosted_logs.shutdown_self_hosted_logs()
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UkhsbmFRPT06NzY0NjYxYTE=


async def queue_with_signal():
    try:
        await queue.queue()
    except asyncio.CancelledError:
        pass
    except TimeoutError as e:
        await logger.awarning(
            "Timed out waiting for task. Signaling shutdown", exc_info=e
        )
        signal.raise_signal(signal.SIGINT)
    except Exception as exc:
        await logger.aexception("Queue failed. Signaling shutdown", exc_info=exc)
        signal.raise_signal(signal.SIGINT)


lifespan.get_last_error = get_last_error  # type: ignore[attr-defined]
