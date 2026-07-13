
import asyncio
import functools
import inspect
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import ParamSpec, TypeVar
# fmt: off  MC8zOmFIVnBZMlhsdEpUbXRiZm92b2s2T1doTmJRPT06YmJlNDQwN2Q=

from psycopg.errors import (
    ConnectionTimeout,
    InternalError,
    OperationalError,
    UndefinedTable,
)
from psycopg_pool.errors import PoolTimeout, TooManyRequests

P = ParamSpec("P")
T = TypeVar("T")


class RetryableException(Exception):
    pass


RETRIABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    OperationalError,
    InternalError,
    RetryableException,
)

OVERLOADED_EXCEPTIONS: tuple[type[BaseException], ...] = (
    PoolTimeout,
    ConnectionTimeout,
    TooManyRequests,
)
# type: ignore  MS8zOmFIVnBZMlhsdEpUbXRiZm92b2s2T1doTmJRPT06YmJlNDQwN2Q=

# type: ignore  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b2s2T1doTmJRPT06YmJlNDQwN2Q=

def retry_db(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    attempts = 3

    if inspect.isasyncgenfunction(func):

        @functools.wraps(func)
        async def asyncgen_wrapper(*args: P.args, **kwargs: P.kwargs) -> AsyncIterator[T]:
            for i in range(attempts):
                try:
                    async for item in func(*args, **kwargs):
                        yield item
                    return
                except UndefinedTable:
                    if i == attempts - 1:
                        raise
                    await asyncio.sleep(5)
                except RETRIABLE_EXCEPTIONS:
                    if i == attempts - 1:
                        raise
                    await asyncio.sleep(0.01)

        return asyncgen_wrapper  # type: ignore[return-value]

    @functools.wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        for i in range(attempts):
            if i == attempts - 1:
                return await func(*args, **kwargs)
            try:
                return await func(*args, **kwargs)
            except UndefinedTable:
                await asyncio.sleep(5)
            except RETRIABLE_EXCEPTIONS:
                await asyncio.sleep(0.01)

    return wrapper
