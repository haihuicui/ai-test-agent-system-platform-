"""子进程树资源看门狗（沙箱 L0 资源限制）。

LLM 生成的测试脚本在子进程中运行，可能出现内存失控（死循环分配、浏览器
崩溃泄漏等）。单用户场景只是自身失败，多人并发时会把共享 Agent/后端
服务器拖垮，殃及所有会话。本模块提供跨平台（psutil）的进程树内存监控：
RSS 合计超阈值即 kill 整棵树。

两种接入方式：
- asyncio 子进程（``asyncio.create_subprocess_exec``）：spawn 后
  ``asyncio.create_task(watch_async_proc(proc, ...))``，执行结束 cancel。
- 同步 ``subprocess.run`` 调用点：改用 ``run_cmd_with_watchdog``（线程池
  场景无需跨线程传递 Popen 句柄）。

容器化（L1）落地后由 ``docker run --memory`` 原生接管，本模块作为
非容器环境的兜底继续保留。
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from typing import Optional, Sequence

import psutil

logger = logging.getLogger(__name__)

# 看门狗轮询间隔（秒）。内存增长曲线在秒级粒度内足够平滑，无需更密。
_POLL_INTERVAL = 2.0


def _tree_rss_bytes(pid: int) -> int:
    """计算进程树（自身 + 所有后代）的 RSS 合计字节数。

    进程可能随时退出，单个节点读取失败按 0 计（竞态安全）。
    """
    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return 0

    total = 0
    try:
        total += root.memory_info().rss
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    try:
        children = root.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        children = []
    for child in children:
        try:
            total += child.memory_info().rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return total


def _kill_tree(pid: int) -> None:
    """kill 整棵进程树（先后代后根，尽量降低孤儿进程概率）。"""
    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    try:
        children = root.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        children = []
    for child in children:
        try:
            child.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    try:
        root.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass


async def watch_async_proc(
    proc: asyncio.subprocess.Process,
    max_memory_mb: int,
    label: str = "",
) -> Optional[int]:
    """监控 asyncio 子进程的进程树内存，超限即 kill 整棵树。

    Args:
        proc: ``asyncio.create_subprocess_exec`` 返回的进程对象。
        max_memory_mb: 进程树 RSS 上限（MB）。
        label: 日志标签（如 run_id），便于定位是哪个执行被熔断。

    Returns:
        超限时返回当时的进程树 RSS（MB）；进程正常退出返回 None。
        调用方执行结束后应 ``cancel()`` 本协程对应的 task。
    """
    while proc.returncode is None:
        await asyncio.sleep(_POLL_INTERVAL)
        rss_mb = _tree_rss_bytes(proc.pid) / (1024 * 1024)
        if rss_mb > max_memory_mb:
            logger.error(
                "[ProcWatchdog] %s 进程树内存超限（%.0fMB > %dMB），已 kill 整棵树 pid=%s",
                label, rss_mb, max_memory_mb, proc.pid,
            )
            _kill_tree(proc.pid)
            return int(rss_mb)
    return None


def run_cmd_with_watchdog(
    cmd,
    *,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    timeout: float,
    max_memory_mb: int,
    shell: bool = False,
    label: str = "",
) -> subprocess.CompletedProcess:
    """``subprocess.run`` 的看门狗变体：超时或进程树内存超限即 kill 整棵树。

    轮询基于 ``communicate(timeout=...)`` 的官方认可重入模式（超时重试不丢
    输出），无需额外线程读取管道。

    超时行为与 ``subprocess.run`` 一致（抛 ``subprocess.TimeoutExpired``）；
    内存超限不抛异常，返回的 CompletedProcess 带 ``watchdog_killed=True``
    属性，stderr 尾部追加熔断说明。

    Args:
        cmd: 命令（list 或 shell=True 时的字符串）。
        cwd / env / shell: 同 subprocess.run。
        timeout: 总超时（秒）。
        max_memory_mb: 进程树 RSS 上限（MB）。
        label: 日志标签。
    """
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    deadline = time.monotonic() + timeout
    stdout: str = ""
    stderr: str = ""
    killed_by: Optional[str] = None

    while True:
        try:
            stdout, stderr = proc.communicate(timeout=_POLL_INTERVAL)
            break
        except subprocess.TimeoutExpired:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                killed_by = "timeout"
            else:
                rss_mb = _tree_rss_bytes(proc.pid) / (1024 * 1024)
                if rss_mb > max_memory_mb:
                    killed_by = f"memory({rss_mb:.0f}MB>{max_memory_mb}MB)"
            if killed_by:
                _kill_tree(proc.pid)
                stdout, stderr = proc.communicate()
                break

    if killed_by == "timeout":
        raise subprocess.TimeoutExpired(cmd, timeout, output=stdout, stderr=stderr)

    result = subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    if killed_by:
        logger.error(
            "[ProcWatchdog] %s 进程树内存超限被熔断: %s", label, killed_by
        )
        result.watchdog_killed = True  # type: ignore[attr-defined]
        result.stderr = (result.stderr or "") + (
            f"\n[watchdog] 进程树内存超限（{killed_by}），已强制终止。"
        )
    return result
