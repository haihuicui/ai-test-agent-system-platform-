"""把同步阻塞工作放到共享线程池执行，避免卡住事件循环。

典型使用场景：
- PDF/Excel 解析与生成
- subprocess.run 外部命令
- MinIO 同步上传/下载
- sqlite3 读写
- 大文件同步 I/O

为什么不直接用 asyncio.to_thread？
asyncio.to_thread 每次都会新建线程，且使用默认的 loop.run_in_executor(None, ...)。
这里使用独立的 ThreadPoolExecutor，可以控制最大线程数、统一线程命名前缀，
并避免和 loop 默认 executor 争抢。
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial

# 共享线程池。线程名前缀便于调试时识别哪些工作来自 Agent 同步工具。
_executor = ThreadPoolExecutor(
    max_workers=16,
    thread_name_prefix="agent-sync-",
)


async def run_sync(fn, *args, **kwargs):
    """在线程池中执行同步函数，返回其结果。

    与 asyncio.to_thread 等价，但使用共享 ThreadPoolExecutor。
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, partial(fn, *args, **kwargs))


async def run_sync_with_timeout(fn, *args, timeout: float | None = None, **kwargs):
    """带超时版本的 run_sync。

    注意：超时只会取消协程侧的等待，**不会中断线程中正在执行的函数**。
    因此不应用于无法安全超时的长任务（如不可中断的外部进程）。
    """
    return await asyncio.wait_for(run_sync(fn, *args, **kwargs), timeout=timeout)
