"""
全局错误处理器

处理应用中的所有异常，返回统一格式的错误响应
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorResponse, ErrorDetail
from app.utils.exceptions import AppException, RateLimitExceededException
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UW5kM1VBPT06ZjU5MDQxYmI=


def setup_exception_handlers(app: FastAPI) -> None:
    """
    设置全局异常处理器
    
    Args:
        app: FastAPI 应用实例
    """
    
    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        """处理自定义应用异常"""
        headers = {}
        
        # 速率限制异常需要添加 Retry-After 头
        if isinstance(exc, RateLimitExceededException):
            headers["Retry-After"] = str(exc.retry_after)
        
        response = ErrorResponse(
            success=False,
            error=exc.error_type,
            message=exc.message,
            details=[
                ErrorDetail(**detail) for detail in exc.details
            ] if exc.details else None,
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(exclude_none=True),
            headers=headers,
        )
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UW5kM1VBPT06ZjU5MDQxYmI=
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """处理 HTTP 异常"""
        error_type_map = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            422: "unprocessable_entity",
            429: "rate_limit_exceeded",
            500: "internal_server_error",
        }
        
        response = ErrorResponse(
            success=False,
            error=error_type_map.get(exc.status_code, "error"),
            message=str(exc.detail),
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(exclude_none=True),
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """处理请求验证异常"""
        details = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            details.append(
                ErrorDetail(
                    field=field,
                    message=error["msg"],
                    code=error["type"],
                )
            )
        
        response = ErrorResponse(
            success=False,
            error="validation_error",
            message="请求参数验证失败",
            details=details,
        )
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UW5kM1VBPT06ZjU5MDQxYmI=
        
        return JSONResponse(
            status_code=422,
            content=response.model_dump(exclude_none=True),
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """处理未捕获的异常"""
        import traceback
        tb = traceback.format_exc()
        print(f"[ERROR] {exc}\n{tb}")
        response = ErrorResponse(
            success=False,
            error="internal_server_error",
            message=f"{type(exc).__name__}: {str(exc)}",
        )

        return JSONResponse(
            status_code=500,
            content=response.model_dump(exclude_none=True),
        )
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UW5kM1VBPT06ZjU5MDQxYmI=

