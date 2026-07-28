"""测试 threading.Lock 在 asyncio 多线程场景下的安全性。

模拟 shell_env.py 中 ensure_playwright_mcp_project 的锁使用模式：
- threading.Lock 保护临界区
- 临界区内有 await 点（run_sync / create_subprocess_exec）
- 多个线程各自运行独立事件循环

验证点：
1. 多线程并发：threading.Lock 跨线程正确串行化，不抛异常
2. 对照实验：asyncio.Lock 跨线程确实会抛 RuntimeError
3. 同线程死锁风险（用子进程隔离执行）
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import textwrap
import threading
import time

import pytest


# ── 模拟 shell_env.py 的核心模式 ──────────────────────────────────────────

_LOCK = threading.Lock()


async def _simulate_protected_work(work_id: int, work_duration: float) -> str:
    """模拟 ensure_playwright_mcp_project 的锁保护逻辑：锁内包含 await 点。"""
    with _LOCK:
        await asyncio.sleep(0.01)             # 模拟 run_sync(file_exists)
        await asyncio.sleep(work_duration)     # 模拟 npm install
        return f"worker-{work_id}: done"


# ══════════════════════════════════════════════════════════════════════════════
# 多线程并发 — 模拟 LangGraph 多工作线程场景
# ══════════════════════════════════════════════════════════════════════════════

class TestThreadingLockMultiThread:
    """threading.Lock 跨线程安全，是 LangGraph 多 worker 的正确选择。"""

    def test_multi_thread_concurrent_access(self):
        """4 个线程各自运行独立 event loop，并发访问锁保护区域 → 全部成功。"""
        results: list[str] = []
        errors: list[Exception] = []

        async def runner(worker_id: int):
            try:
                r = await _simulate_protected_work(worker_id, work_duration=0.03)
                results.append(r)
            except Exception as e:
                errors.append(e)

        def thread_target(worker_id: int):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(runner(worker_id))
            finally:
                loop.close()

        threads = [threading.Thread(target=thread_target, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"多线程出错: {errors}"
        assert len(results) == 4, f"应完成 4 个任务，实际: {len(results)}"

    def test_lock_serializes_execution(self):
        """锁串行化验证：4×0.1s 任务 → 总耗时 > 0.3s，时间无重叠。"""
        start_times: list[float] = []
        end_times: list[float] = []

        async def timed_runner():
            with _LOCK:
                start_times.append(time.monotonic())
                await asyncio.sleep(0.05)
                await asyncio.sleep(0.05)
                end_times.append(time.monotonic())

        def thread_target():
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(timed_runner())
            finally:
                loop.close()

        t0 = time.monotonic()
        threads = [threading.Thread(target=thread_target) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.monotonic() - t0

        assert len(start_times) == 4 and len(end_times) == 4
        # 串行化：总时间 ≈ 4 × 0.1s
        assert elapsed > 0.3, f"串行化耗时 {elapsed:.3f}s 应 > 0.3s"
        # 时间不应重叠
        for i in range(len(end_times) - 1):
            assert end_times[i] <= start_times[i + 1] + 0.01, (
                f"task-{i} ({end_times[i]:.3f}s) 和 task-{i+1} ({start_times[i+1]:.3f}s) 时间重叠"
            )

    def test_same_thread_sequential(self):
        """同线程顺序调用：安全无虞。"""
        results: list[str] = []

        async def do_work(name: str):
            with _LOCK:
                await asyncio.sleep(0.01)
                results.append(name)

        async def main():
            await do_work("first")
            await do_work("second")

        asyncio.run(main())
        assert results == ["first", "second"]


# ══════════════════════════════════════════════════════════════════════════════
# 对照实验：asyncio.Lock 跨线程 → RuntimeError
# ══════════════════════════════════════════════════════════════════════════════

class TestAsyncioLockFailsMultiThread:
    """证明 asyncio.Lock 跨线程不稳定 — 这就是 500 错误的根因。

    真实场景：shell_env.py 被 FastAPI/Uvicorn 在启动时 import，此时主事件循环
    已在运行。asyncio.Lock() 因此绑定到主事件循环。LangGraph worker 线程有自己
    独立的事件循环，访问绑定了其他循环的锁 → RuntimeError。

    注意：Python 3.13 改变了 asyncio.Lock 的内部实现，使其不再绑定特定事件循环。
    但在 Python 3.10-3.12 上（常见于 Docker 镜像），问题依然存在。
    threading.Lock 在所有 Python 版本上都稳定工作。
    """

    @pytest.mark.skipif(
        sys.version_info >= (3, 13),
        reason="Python 3.13+ 的 asyncio.Lock 不再绑定事件循环，跨线程不抛异常",
    )
    def test_asyncio_lock_fails_on_older_python(self):
        """Python < 3.13：主事件循环内创建的 asyncio.Lock → 子线程用 → RuntimeError。"""
        async_lock_holder: list[asyncio.Lock] = []

        async def create_lock_in_main_loop():
            async_lock_holder.append(asyncio.Lock())

        asyncio.run(create_lock_in_main_loop())
        async_lock = async_lock_holder[0]

        errors: list[Exception] = []

        async def use_lock():
            try:
                async with async_lock:
                    await asyncio.sleep(0.01)
            except Exception as e:
                errors.append(e)

        def thread_target():
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(use_lock())
            finally:
                loop.close()

        t = threading.Thread(target=thread_target)
        t.start()
        t.join()

        assert len(errors) == 1, f"预期 1 错，实际: {len(errors)}"
        assert isinstance(errors[0], RuntimeError)
        assert "different event loop" in str(errors[0]).lower()

    def test_threading_lock_always_works(self):
        """对照：threading.Lock 在所有 Python 版本上跨线程稳定工作。"""
        lock = threading.Lock()
        results: list[str] = []

        async def use_lock(name: str):
            with lock:
                await asyncio.sleep(0.01)
                results.append(name)

        def thread_target(name: str):
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(use_lock(name))
            finally:
                loop.close()

        threads = [
            threading.Thread(target=thread_target, args=(f"worker-{i}",))
            for i in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 3, f"threading.Lock 跨线程应始终正常: {results}"


# ══════════════════════════════════════════════════════════════════════════════
# 同线程死锁风险 — 子进程隔离
# ══════════════════════════════════════════════════════════════════════════════

DEADLOCK_SCRIPT = textwrap.dedent("""\
import asyncio, threading

lock = threading.Lock()
hit = 0

async def worker_a():
    global hit
    with lock:
        hit += 1
        await asyncio.sleep(0.5)
    return "A"

async def worker_b():
    global hit
    with lock:  # 阻塞整个线程 → 死锁
        hit += 1
    return "B"

async def main():
    try:
        await asyncio.wait_for(asyncio.gather(worker_a(), worker_b()), timeout=1.5)
        print("COMPLETED")
    except asyncio.TimeoutError:
        print("TIMEOUT")
    print(f"HIT={hit}")

asyncio.run(main())
""")


class TestSameThreadDeadlock:
    """threading.Lock + await 在同线程中会导致死锁 — 边界需文档化。

    本项目使用场景是 LangGraph 多工作线程（每个线程独立事件循环），
    因此同线程并发竞争不会发生。但此测试文档化这个边界风险。
    """

    def test_deadlock_cannot_be_resolved_by_asyncio_timeout(self):
        """验证：同线程死锁无法被 asyncio.wait_for 恢复。

        子进程应在 2.5s 后被子进程级超时杀死，而不会正常退出。
        """
        try:
            subprocess.run(
                [sys.executable, "-c", DEADLOCK_SCRIPT],
                capture_output=True, text=True, timeout=2.5,
            )
            pytest.fail("预期死锁导致子进程超时，但子进程意外正常退出")
        except subprocess.TimeoutExpired:
            # 预期结果：死锁导致进程不响应，被 kill
            pass

    def test_single_thread_no_deadlock(self):
        """对照：同线程非并发调用 → 一切正常（验证脚本本身没问题）。"""
        result = subprocess.run(
            [sys.executable, "-c", textwrap.dedent("""\
import asyncio, threading
lock = threading.Lock()
results = []
async def do_work(name):
    with lock:
        await asyncio.sleep(0.01)
        results.append(name)
async def main():
    await do_work("A")
    await do_work("B")
    print("OK")
asyncio.run(main())
""")],
            capture_output=True, text=True, timeout=3,
        )
        assert result.stdout.strip() == "OK", f"顺序调用应正常: {result.stdout} {result.stderr}"
