"""gRPC-based operations for LangGraph API."""

from __future__ import annotations

import asyncio
import functools
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, overload

from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import Struct  # type: ignore[import]
from grpc import StatusCode
from grpc.aio import AioRpcError
from langgraph_sdk.schema import Config
from starlette.exceptions import HTTPException

from langgraph_api.serde import json_dumpb

if TYPE_CHECKING:
    from langgraph_api.schema import Context

__all__ = ["Assistants", "Threads"]
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFV4MmJBPT06N2ZhMDk0MmU=

GRPC_STATUS_TO_HTTP_STATUS = {
    StatusCode.NOT_FOUND: HTTPStatus.NOT_FOUND,
    StatusCode.ALREADY_EXISTS: HTTPStatus.CONFLICT,
    StatusCode.INVALID_ARGUMENT: HTTPStatus.UNPROCESSABLE_ENTITY,
}


def map_if_exists(if_exists: str) -> Any:
    """Map if_exists string to protobuf OnConflictBehavior."""
    from langgraph_api.grpc.generated import core_api_pb2 as pb

    if if_exists == "do_nothing":
        return pb.OnConflictBehavior.DO_NOTHING
    return pb.OnConflictBehavior.RAISE


@overload
def consolidate_config_and_context(
    config: Config | None, context: None
) -> tuple[Config, None]: ...


@overload
def consolidate_config_and_context(
    config: Config | None, context: Context
) -> tuple[Config, Context]: ...


def consolidate_config_and_context(
    config: Config | None, context: Context | None
) -> tuple[Config, Context | None]:
    """Return a new (config, context) with consistent configurable/context.

    Does not mutate the passed-in objects. If both configurable and context
    are provided, raises 400. If only one is provided, mirrors it to the other.
    """
    cfg: Config = Config(config or {})
    ctx: Context | None = dict(context) if context is not None else None
    configurable = cfg.get("configurable")

    if configurable and ctx:
        raise HTTPException(
            status_code=400,
            detail="Cannot specify both configurable and context. Prefer setting context alone."
            " Context was introduced in LangGraph 0.6.0 and "
            "is the long term planned replacement for configurable.",
        )

    if configurable:
        ctx = configurable
    elif ctx is not None:
        cfg["configurable"] = ctx

    return cfg, ctx
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFV4MmJBPT06N2ZhMDk0MmU=


def dict_to_struct(data: dict[str, Any]) -> Struct:
    """Convert a dictionary to a protobuf Struct."""
    struct = Struct()
    if data:
        struct.update(data)
    return struct


def struct_to_dict(struct: Struct) -> dict[str, Any]:
    """Convert a protobuf Struct to a dictionary."""
    return MessageToDict(struct) if struct else {}

# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFV4MmJBPT06N2ZhMDk0MmU=

def exception_to_struct(exception: BaseException | None) -> Struct | None:
    """Convert an exception to a protobuf Struct."""
    if exception is None:
        return None
    import orjson

    try:
        payload = orjson.loads(json_dumpb(exception))
    except orjson.JSONDecodeError:
        payload = {"error": type(exception).__name__, "message": str(exception)}
    return dict_to_struct(payload)


def _map_sort_order(sort_order: str | None) -> Any:
    """Map string sort_order to protobuf enum."""
    from langgraph_api.grpc.generated import core_api_pb2 as pb

    if sort_order and sort_order.upper() == "ASC":
        return pb.SortOrder.ASC
    return pb.SortOrder.DESC


def _handle_grpc_error(error: AioRpcError) -> None:
    """Handle gRPC errors and convert to appropriate exceptions."""
    raise HTTPException(
        status_code=GRPC_STATUS_TO_HTTP_STATUS.get(
            error.code(), HTTPStatus.INTERNAL_SERVER_ERROR
        ),
        detail=str(error.details()),
    )


class Authenticated:
    """Base class for authenticated operations (matches storage_postgres interface)."""

    resource: str = "assistants"

    @classmethod
    async def handle_event(
        cls,
        ctx: Any,  # Auth context
        action: str,
        value: Any,
    ) -> dict[str, Any] | None:
        """Handle authentication event - stub implementation for now."""
        # TODO: Implement proper auth handling that converts auth context
        # to gRPC AuthFilter format when needed
        return None
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFV4MmJBPT06N2ZhMDk0MmU=


def grpc_error_guard(cls):
    """Class decorator to wrap async methods and handle gRPC errors uniformly."""
    for name, attr in list(cls.__dict__.items()):
        func = None
        wrapper_type = None
        if isinstance(attr, staticmethod):
            func = attr.__func__
            wrapper_type = staticmethod
        elif isinstance(attr, classmethod):
            func = attr.__func__
            wrapper_type = classmethod
        elif callable(attr):
            func = attr

        if func and asyncio.iscoroutinefunction(func):

            def make_wrapper(f):
                @functools.wraps(f)
                async def wrapped(*args, **kwargs):
                    try:
                        return await f(*args, **kwargs)
                    except AioRpcError as e:
                        _handle_grpc_error(e)

                return wrapped  # noqa: B023

            wrapped = make_wrapper(func)
            if wrapper_type is staticmethod:
                setattr(cls, name, staticmethod(wrapped))
            elif wrapper_type is classmethod:
                setattr(cls, name, classmethod(wrapped))
            else:
                setattr(cls, name, wrapped)
    return cls


# Import at the end to avoid circular imports
from .assistants import Assistants  # noqa: E402
from .threads import Threads  # noqa: E402
