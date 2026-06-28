"""
自定义异常类

基于 BrowserStack API 状态码定义的异常类
参考: https://www.browserstack.com/docs/test-management/api-reference/status-code
"""

from typing import Optional
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkVaMlVBPT06ZWY2M2Y3ODU=


class AppException(Exception):
    """
    应用基础异常类
    
    所有自定义异常的基类
    """
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_type: str = "internal_error",
        details: Optional[list[dict]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.details = details
        super().__init__(self.message)


class BadRequestException(AppException):
    """
    400 Bad Request 异常
    
    请求格式错误或参数无效
    """
    def __init__(
        self,
        message: str = "请求参数无效",
        details: Optional[list[dict]] = None,
    ):
        super().__init__(
            message=message,
            status_code=400,
            error_type="bad_request",
            details=details,
        )

# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkVaMlVBPT06ZWY2M2Y3ODU=

class UnauthorizedException(AppException):
    """
    401 Unauthorized 异常
    
    未授权访问，无效的访问凭证
    """
    def __init__(
        self,
        message: str = "未授权访问，请提供有效的凭证",
    ):
        super().__init__(
            message=message,
            status_code=401,
            error_type="unauthorized",
        )


class ForbiddenException(AppException):
    """
    403 Forbidden 异常
    
    禁止访问，权限不足
    """
    def __init__(
        self,
        message: str = "禁止访问，权限不足",
    ):
        super().__init__(
            message=message,
            status_code=403,
            error_type="forbidden",
        )


class NotFoundException(AppException):
    """
    404 Not Found 异常
    
    请求的资源不存在
    """
    def __init__(
        self,
        message: str = "请求的资源不存在",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ):
        if resource_type and resource_id:
            message = f"{resource_type} '{resource_id}' 不存在"
        super().__init__(
            message=message,
            status_code=404,
            error_type="not_found",
        )
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkVaMlVBPT06ZWY2M2Y3ODU=


class ConflictException(AppException):
    """
    409 Conflict 异常
    
    资源冲突，如重复创建
    """
    def __init__(
        self,
        message: str = "资源冲突",
    ):
        super().__init__(
            message=message,
            status_code=409,
            error_type="conflict",
        )


class UnprocessableEntityException(AppException):
    """
    422 Unprocessable Entity 异常
    
    请求格式正确但语义错误
    """
    def __init__(
        self,
        message: str = "请求格式正确但无法处理",
        details: Optional[list[dict]] = None,
    ):
        super().__init__(
            message=message,
            status_code=422,
            error_type="unprocessable_entity",
            details=details,
        )


class RateLimitExceededException(AppException):
    """
    429 Too Many Requests 异常
    
    超出速率限制
    参考: https://www.browserstack.com/docs/test-management/api-reference/rate-limit-for-api-calls
    """
    def __init__(
        self,
        message: str = "请求过于频繁，请在60秒后重试",
        retry_after: int = 60,
    ):
        super().__init__(
            message=message,
            status_code=429,
            error_type="rate_limit_exceeded",
        )
        self.retry_after = retry_after
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkVaMlVBPT06ZWY2M2Y3ODU=

