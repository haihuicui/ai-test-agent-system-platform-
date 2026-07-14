"""
P0 修复单元测试

覆盖本次手动运行 P0 缺陷修复中可脱离数据库验证的纯逻辑：
- decide_final_state：根据全部作业状态决定测试运行最终状态
- _spawn_tracked：后台任务跟踪（防止 GC、结束后自动清理、异常不静默）
"""

import asyncio

import pytest

from app.schemas.enums import JobStatus, TestRunState
from app.services.execution.engine import decide_final_state
from app.services.test_run_service import _background_tasks, _spawn_tracked


# =============== decide_final_state ===============


def test_final_state_all_completed():
    jobs = [
        (JobStatus.COMPLETED, None),
        (JobStatus.COMPLETED, "assertion"),
        (JobStatus.SKIPPED, None),
    ]
    assert decide_final_state(jobs) == TestRunState.DONE


def test_final_state_business_failure():
    jobs = [
        (JobStatus.COMPLETED, None),
        (JobStatus.FAILED, "assertion"),
    ]
    assert decide_final_state(jobs) == TestRunState.DONE_WITH_FAILURES


def test_final_state_failure_without_category_is_business():
    # failure_category 为 None 时不应误判为基础设施失败
    jobs = [(JobStatus.FAILED, None)]
    assert decide_final_state(jobs) == TestRunState.DONE_WITH_FAILURES


@pytest.mark.parametrize("category", ["infra", "environment"])
def test_final_state_infra_failure_rejected(category):
    jobs = [
        (JobStatus.COMPLETED, None),
        (JobStatus.FAILED, category),
    ]
    assert decide_final_state(jobs) == TestRunState.REJECTED


def test_final_state_pending_keeps_in_progress():
    jobs = [
        (JobStatus.COMPLETED, None),
        (JobStatus.PENDING, None),
    ]
    assert decide_final_state(jobs) == TestRunState.IN_PROGRESS


def test_final_state_running_keeps_in_progress():
    jobs = [
        (JobStatus.FAILED, "assertion"),
        (JobStatus.RUNNING, None),
    ]
    # 仍有 running 作业时优先保持进行中，而非提前定案
    assert decide_final_state(jobs) == TestRunState.IN_PROGRESS


def test_final_state_empty_is_done():
    assert decide_final_state([]) == TestRunState.DONE


# =============== _spawn_tracked ===============


async def test_spawn_tracked_retains_and_cleans_up():
    async def _quick():
        await asyncio.sleep(0)
        return 1

    task = _spawn_tracked(_quick(), label="unit-quick")
    # 任务创建后应被集合持有，防止被 GC
    assert task in _background_tasks

    result = await task
    assert result == 1

    # 让 done_callback 有机会执行
    await asyncio.sleep(0)
    assert task not in _background_tasks


async def test_spawn_tracked_exception_does_not_leak_and_cleans_up():
    async def _boom():
        raise RuntimeError("boom")

    task = _spawn_tracked(_boom(), label="unit-boom")
    assert task in _background_tasks

    with pytest.raises(RuntimeError):
        await task

    # done_callback 会检索异常（避免"exception was never retrieved"警告）并清理集合
    await asyncio.sleep(0)
    assert task not in _background_tasks
