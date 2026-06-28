"""
速率限制中间件

基于 BrowserStack API 的速率限制规则实现
参考: https://www.browserstack.com/docs/test-management/api-reference/rate-limit-for-api-calls

规则:
- 每分钟最多 300 个请求
- 超过限制返回 429 状态码
- 需要等待 60 秒后重试
"""

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import settings
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUhKaGRBPT06NjEzZjEwZDU=


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    速率限制中间件
    
    使用滑动窗口算法实现每分钟请求次数限制
    """
    
    def __init__(self, app, max_requests: int = None, window_seconds: int = None):
        super().__init__(app)
        self.max_requests = max_requests or settings.rate_limit_requests
        self.window_seconds = window_seconds or settings.rate_limit_window
        # 存储每个客户端的请求时间戳
        # 格式: {client_key: [timestamp1, timestamp2, ...]}
        self.request_timestamps: dict[str, list[float]] = defaultdict(list)
    
    def _get_client_key(self, request: Request) -> str:
        """
        获取客户端标识键
        
        优先使用认证用户 ID，否则使用 IP 地址
        
        Args:
            request: 请求对象
            
        Returns:
            str: 客户端标识键
        """
        # 尝试从认证信息获取用户 ID
        user = getattr(request.state, "user", None)
        if user:
            return f"user:{user.id}"
        
        # 使用客户端 IP
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUhKaGRBPT06NjEzZjEwZDU=
        
        return f"ip:{client_ip}"
    
    def _cleanup_old_requests(self, client_key: str, current_time: float) -> None:
        """
        清理过期的请求记录
        
        Args:
            client_key: 客户端标识键
            current_time: 当前时间戳
        """
        cutoff_time = current_time - self.window_seconds
        self.request_timestamps[client_key] = [
            ts for ts in self.request_timestamps[client_key]
            if ts > cutoff_time
        ]
    
    def _is_rate_limited(self, client_key: str) -> tuple[bool, int]:
        """
        检查是否超出速率限制
        
        Args:
            client_key: 客户端标识键
            
        Returns:
            tuple: (是否被限制, 剩余请求数)
        """
        current_time = time.time()
        self._cleanup_old_requests(client_key, current_time)
        
        request_count = len(self.request_timestamps[client_key])
        remaining = max(0, self.max_requests - request_count)
        
        if request_count >= self.max_requests:
            return True, 0
        
        # 记录当前请求
        self.request_timestamps[client_key].append(current_time)
        return False, remaining - 1
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUhKaGRBPT06NjEzZjEwZDU=
    
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        处理请求
        
        Args:
            request: 请求对象
            call_next: 下一个处理函数
            
        Returns:
            Response: 响应对象
        """
        client_key = self._get_client_key(request)
        is_limited, remaining = self._is_rate_limited(client_key)
        
        if is_limited:
            return Response(
                content='{"success": false, "error": "rate_limit_exceeded", '
                        '"message": "请求过于频繁，请在60秒后重试"}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": str(self.window_seconds),
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + self.window_seconds),
                },
            )
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUhKaGRBPT06NjEzZjEwZDU=
        
        response = await call_next(request)
        
        # 添加速率限制响应头
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(
            int(time.time()) + self.window_seconds
        )
        
        return response

