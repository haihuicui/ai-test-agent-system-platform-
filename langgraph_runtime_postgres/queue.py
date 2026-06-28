
import asyncio
import asyncio.events
import asyncio.exceptions
import concurrent.futures
import functools
import time
from collections.abc import Callable, Coroutine
from contextlib import ExitStack, suppress
from typing import cast

import structlog
from langgraph_api import config
from langgraph_api import store as api_store
from langgraph_api.utils import future as lg_future
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTJGdE9RPT06M2Y0OGVjMzA=

from langgraph_runtime_postgres import database, ops

logger = structlog.stdlib.get_logger(__name__)

WORKERS: set[lg_future.AnyFuture] = set()
WEBHOOKS: set[concurrent.futures.Future] = set()
SHUTDOWN_GRACE_PERIOD_SECS = 5


def get_num_workers():
    return len(WORKERS)


class BgLoopRunner(asyncio.Runner):  # type: ignore[subclass-of-final-class]
    """
    A runner that runs a loop in a separate thread. It's very important to
    use run the loop always in the same thread, as some objects may be created
    which are bound to the loop's thread.
    """

    executor: concurrent.futures.ThreadPoolExecutor

    def __init__(self, idx: int):
        super().__init__()
        self.idx = idx

    def __enter__(self):
        self.executor = concurrent.futures.ThreadPoolExecutor(
            1, thread_name_prefix=f"bg-loop-{self.idx}"
        )
        self.executor.submit(self.get_loop).result()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        loop = self.get_loop()
        # cancel all remaining tasks
        for task in asyncio.all_tasks(loop):
            task.cancel("Stopping background loop")
        # close postgres connection pool
        try:
            if not loop.is_running():
                self.executor.submit(self.run, database.stop_pool()).result(
                    SHUTDOWN_GRACE_PERIOD_SECS / 2
                )
            else:
                asyncio.run_coroutine_threadsafe(database.stop_pool(), loop).result(
                    SHUTDOWN_GRACE_PERIOD_SECS / 2
                )
        except TimeoutError:
            pass
        try:
            if not loop.is_running():
                self.executor.submit(self.run, api_store.exit_store()).result(
                    SHUTDOWN_GRACE_PERIOD_SECS / 2
                )
            else:
                asyncio.run_coroutine_threadsafe(api_store.exit_store(), loop).result(
                    SHUTDOWN_GRACE_PERIOD_SECS / 2
                )
        except TimeoutError:
            pass
        self.executor.shutdown(wait=False)

    def submit(
        self,
        coro: Coroutine,
        *,
        name: str | None = None,
        callback: Callable[[lg_future.AnyFuture], None] | None = None,
    ):
        fut = self.executor.submit(
            self.run,
            coro,
            name=name,
        )
        WORKERS.add(fut)
        if callback:
            fut.add_done_callback(callback)
        return fut

    def run(
        self,
        coro: Coroutine,
        *,
        name: str | None = None,
    ):
        """Run a coroutine inside the embedded event loop.
        Modified from asyncio.Runner.run
        - Removed main thread check (we only use it on bg threads)
        - Added callback and name arguments
        - Added WORKERS set to track tasks
        """

        if asyncio.events._get_running_loop() is not None:
            # fail fast with short traceback
            raise RuntimeError(
                "Runner.run() cannot be called from a running event loop"
            )
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTJGdE9RPT06M2Y0OGVjMzA=

        self._lazy_init()

        task = self._loop.create_task(coro, name=name)

        try:
            return self._loop.run_until_complete(task)
        except asyncio.exceptions.CancelledError:
            raise  # CancelledError


async def sweep_loop():
    while True:
        try:
            await ops.Runs.sweep()
        except asyncio.exceptions.CancelledError:
            await logger.awarning("Sweep loop cancelled")
            return
        except Exception as e:
            # This happens when redis times out during the initial connection.
            # In that case, we haven't entered the loop yet, so we'll just end up looping infinitely with no delays here.
            # Sleep on the delay to avoid that.
            await logger.awarning(
                "Sweep loop iteration failed. Continuing...", exc_info=e
            )
            await asyncio.sleep(config.BG_JOB_INTERVAL)


async def stats_loop():
    while True:
        await asyncio.sleep(config.STATS_INTERVAL_SECS)
        # worker stats
        active = len(WORKERS)
        await logger.ainfo(
            "Worker stats",
            max=config.N_JOBS_PER_WORKER,
            available=config.N_JOBS_PER_WORKER - active,
            active=active,
        )


async def shutdown_queue(
    loop: asyncio.AbstractEventLoop,
    timeout: float,
    futs: list[asyncio.Future] | None = None,
):
    # run all pending workers and webhooks in a timeout
    if not futs:
        futs = []

    # when BG_JOB_ISOLATED_LOOPS is enabled, WORKERS will contain concurrent.futures.Future objects instead of asyncio.Future objects
    # in order to correctly asyncio.gather this future, we call chain_future to convert this into an asyncio.Future
    if config.BG_JOB_ISOLATED_LOOPS:
        futs.extend(
            [
                cast(
                    asyncio.Future,
                    lg_future.chain_future(f, loop.create_future()),
                )
                for f in WORKERS
            ],
        )
    else:
        futs.extend([cast(asyncio.Future, f) for f in WORKERS])

    futs.extend(
        [
            cast(asyncio.Future, lg_future.chain_future(w, loop.create_future()))
            for w in WEBHOOKS
        ]
    )

    await asyncio.wait_for(
        asyncio.gather(
            *futs,
            return_exceptions=True,
        ),
        timeout,
    )
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTJGdE9RPT06M2Y0OGVjMzA=


async def queue():
    # Avoid impact of cyclic imports
    from langgraph_api import graph, webhook, worker
    from langgraph_api.asyncio import AsyncQueue
    from langgraph_api.schema import Run

    concurrency = config.N_JOBS_PER_WORKER
    loop = asyncio.get_running_loop()
    # when not using isolated event loops the queue is used to limit concurrency
    # where every task checks out a token before running, and returns it when done
    runners = AsyncQueue[BgLoopRunner](concurrency)
    with ExitStack() as stack:
        if config.BG_JOB_ISOLATED_LOOPS:
            await logger.ainfo("Starting queue with isolated loops")
            executor = stack.enter_context(concurrent.futures.ThreadPoolExecutor())
            RUNNERS = {
                stack.enter_context(BgLoopRunner(idx)) for idx in range(concurrency)
            }
            for r in RUNNERS:
                runners.put_nowait(r)
                r.get_loop().set_default_executor(executor)
        else:
            await logger.ainfo("Starting queue with shared loop")
            # when not using isolated event loops the queue items are used as
            # tokens to limit concurrency, so we just create empty objects
            for _ in range(concurrency):
                runners.put_nowait(cast(BgLoopRunner, object()))
        expired_runners = []

        def cleanup(
            task: lg_future.AnyFuture,
            runner: BgLoopRunner,
        ):
            WORKERS.discard(task)
            try:
                if config.BG_JOB_ISOLATED_LOOPS:
                    loop.call_soon_threadsafe(runners.put_nowait, runner)
                else:
                    # We don't use isolated loops, so we can just put the runner back in the queue
                    runners.put_nowait(runner)
            except Exception as exc:
                expired_runners.append(runner)
                logger.exception("Background worker cleanup failed", exc_info=exc)

            try:
                if task.cancelled():
                    return
                if exc := task.exception():
                    if not isinstance(exc, asyncio.CancelledError):
                        logger.exception(
                            f"Background worker failed for task {task}",
                            exc_info=exc,
                        )
                    return
                result: worker.WorkerResult | None = task.result()
                if result and result["webhook"]:
                    hook_fut = asyncio.run_coroutine_threadsafe(
                        webhook.call_webhook(result), loop
                    )
                    WEBHOOKS.add(hook_fut)
                    hook_fut.add_done_callback(WEBHOOKS.remove)
            except Exception as exc:
                logger.exception("Background worker cleanup failed", exc_info=exc)

        await logger.ainfo(f"Starting {concurrency} background workers")
        sweep_task = asyncio.create_task(sweep_loop())
        stats_task = asyncio.create_task(stats_loop())
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTJGdE9RPT06M2Y0OGVjMzA=

        try:
            while True:
                if expired_runners:
                    # Should never happen.
                    await logger.awarning(
                        "Background worker expired, adding to queue",
                        num=len(expired_runners),
                    )
                    for runner in expired_runners:
                        await runners.put(runner)
                    expired_runners.clear()
                await runners.wait()
                try:
                    # try to get a run, handle it
                    run: Run | None = None
                    async for run, attempt in ops.Runs.next(
                        wait=True, limit=runners.qsize()
                    ):
                        # we know a runner exists, so get it
                        runner = runners.get_nowait()

                        graph_id = (
                            run["kwargs"]
                            .get("config", {})
                            .get("configurable", {})
                            .get("graph_id")
                        )

                        if not config.BG_JOB_ISOLATED_LOOPS or (
                            graph_id and graph.is_js_graph(graph_id)
                        ):
                            task = asyncio.create_task(
                                worker.worker(run, attempt, loop),
                                name=f"run-{run['run_id']}-attempt-{attempt}",
                            )
                            task.add_done_callback(
                                functools.partial(cleanup, runner=runner)
                            )
                            WORKERS.add(task)
                        else:
                            runner.submit(
                                worker.worker(run, attempt, loop),
                                name=f"run-{run['run_id']}-attempt-{attempt}",
                                callback=functools.partial(cleanup, runner=runner),
                            )
                except Exception as exc:
                    # keep trying to run the scheduler indefinitely
                    logger.exception("Background worker scheduler failed", exc_info=exc)
                    # Avoid shutting down the queue when redis is struggling
                    try:
                        await ops.wake_up_worker()
                    except Exception as e:
                        logger.exception("Failed to wake up worker", exc_info=e)

        except asyncio.CancelledError as e:
            # If k8s signals a sigterm, the queue task gets cancelled.
            # wait up to BG_JOB_SHUTDOWN_GRACE_PERIOD_SECS for workers to finish
            log_kwargs = {}
            if e.args:
                log_kwargs["reason"] = " ".join(map(str, e.args))
            await logger.awarning(
                "Queue task cancelled. Shutting down workers. "
                f"Will terminate after {config.BG_JOB_SHUTDOWN_GRACE_PERIOD_SECS}s",
                **log_kwargs,
            )
            start = time.perf_counter()
            await shutdown_queue(loop, config.BG_JOB_SHUTDOWN_GRACE_PERIOD_SECS)
            elapsed = time.perf_counter() - start
            await logger.ainfo("Workers finished.")
        finally:
            sweep_task.cancel("Shutting down background workers")
            stats_task.cancel("Shutting down background workers")

            remaining_shutdown_time = 0
            with suppress(UnboundLocalError):
                remaining_shutdown_time = (
                    config.BG_JOB_SHUTDOWN_GRACE_PERIOD_SECS - elapsed
                )

            # we may have additional webhook tasks created after runs finish in the previous except block, so we repeat shutdown
            await shutdown_queue(
                loop,
                max(
                    remaining_shutdown_time,
                    SHUTDOWN_GRACE_PERIOD_SECS,
                ),
                [sweep_task, stats_task],
            )
            await logger.ainfo("Successfully shutdown queue")
