"""
测试运行 API 路由

提供测试运行相关的 RESTful API 接口
参考: https://www.browserstack.com/docs/test-management/api-reference/test-runs
"""

from datetime import date
from typing import Optional, Union

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Query, status, Request
from fastapi.responses import StreamingResponse, HTMLResponse, Response

from app.api.deps import (
    TestRunServiceDep,
    PaginationDep,
    DbSessionDep,
)
from app.schemas.common import SuccessResponse, MessageResponse
from app.schemas.pagination import PaginatedResponse, PaginationInfo
from app.schemas.test_run import (
    TestRunCreate,
    TestRunPatchUpdate,
    TestRunFullReplace,
    TestRunInfo,
    TestRunListInfo,
    TestRunMinifiedInfo,
    TestRunTestCaseInfo,
    TestRunTestCaseMinifiedInfo,
    AddTestCasesRequest,
    RemoveTestCasesRequest,
    TestRunAssignRequest,
    CloseTestRunRequest,
    TestRunScriptJobInfo,
    TestRunScriptJobCreate,
    TestRunScheduleInfo,
    TestRunScheduleCreate,
    TestRunScheduleUpdate,
    BatchRetryJobsRequest,
    TestRunExecutionSnapshotInfo,
)
from app.schemas.enums import TestResultStatus, TestRunState, ScriptType, TriggerType

router = APIRouter(
    prefix="/projects/{project_identifier}/test-runs",
    tags=["测试运行"],
)


def _csv_to_list(value: Optional[str]) -> Optional[list[str]]:
    """逗号分隔字符串 → list[str]"""
    if value is None or value == "":
        return None
    return [v.strip() for v in value.split(",") if v.strip()]
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WTIxcVVnPT06ZGNhNTJiOWI=


def _csv_to_run_states(value: Optional[str]) -> Optional[list[TestRunState]]:
    items = _csv_to_list(value)
    if not items:
        return None
    return [TestRunState(v) for v in items]


def _csv_to_trigger_types(value: Optional[str]) -> Optional[list[TriggerType]]:
    items = _csv_to_list(value)
    if not items:
        return None
    return [TriggerType(v) for v in items]


def _csv_to_uuids(value: Optional[str]) -> Optional[list[UUID]]:
    """逗号分隔字符串 → list[UUID]"""
    items = _csv_to_list(value)
    if not items:
        return None
    return [UUID(v) for v in items]


# =============== 列表 / 详情 / 创建 ===============


@router.get(
    "",
    response_model=PaginatedResponse[TestRunListInfo],
    summary="获取测试运行列表",
    description="按 BrowserStack 规范获取项目下的测试运行列表，支持多组合过滤",
)
async def list_test_runs(
    project_identifier: str,
    service: TestRunServiceDep,
    pagination: PaginationDep,
    run_state: Optional[str] = Query(
        default=None,
        description="运行状态过滤，逗号分隔多值 (new_run, in_progress, etc.)",
    ),
    assignee: Optional[str] = Query(
        default=None,
        description="负责人邮箱过滤，逗号分隔多值",
    ),
    test_plan_id: Optional[str] = Query(
        default=None,
        description="测试计划标识符 (TP-x / STP-x)",
    ),
    include_closed: bool = Query(
        default=False,
        description="是否包含已关闭的测试运行",
    ),
    closed_before: Optional[date] = Query(
        default=None, description="关闭时间早于该日期"
    ),
    closed_after: Optional[date] = Query(
        default=None, description="关闭时间晚于该日期"
    ),
    created_before: Optional[date] = Query(
        default=None, description="创建时间早于该日期"
    ),
    created_after: Optional[date] = Query(
        default=None, description="创建时间晚于该日期"
    ),
    search: Optional[str] = Query(default=None, description="按名称/标识符/调度名称搜索"),
    trigger_type: Optional[str] = Query(
        default=None,
        description="触发方式过滤，逗号分隔多值 (manual, scheduled, api)",
    ),
    scheduled_by: Optional[str] = Query(
        default=None, description="按来源调度 ID 过滤"
    ),
    script_ids: Optional[str] = Query(
        default=None,
        description="按脚本 ID 集合过滤，逗号分隔；返回包含这些脚本的测试运行",
    ),
) -> PaginatedResponse[TestRunListInfo]:
    """获取测试运行列表 (BS GET /test-runs)"""
    items, total = await service.get_list(
        project_identifier,
        run_states=_csv_to_run_states(run_state),
        assignees=_csv_to_list(assignee),
        test_plan_id=test_plan_id,
        include_closed=include_closed,
        closed_before=closed_before,
        closed_after=closed_after,
        created_before=created_before,
        created_after=created_after,
        search=search,
        trigger_types=_csv_to_trigger_types(trigger_type),
        scheduled_by=UUID(scheduled_by) if scheduled_by else None,
        script_ids=_csv_to_uuids(script_ids),
        offset=pagination.offset,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        success=True,
        data=items,
        pagination=PaginationInfo(
            total=total,
            page=pagination.page,
            page_size=pagination.limit,
        ),
    )


# =============== 定时调度子资源 ===============


@router.get(
    "/schedules",
    response_model=SuccessResponse,
    summary="获取定时调度列表",
    description="获取项目下的所有测试运行定时调度",
)
async def list_schedules(
    project_identifier: str,
    service: TestRunServiceDep,
    pagination: PaginationDep,
) -> SuccessResponse:
    result = await service.get_schedules(
        project_identifier,
        page=pagination.page,
        page_size=pagination.limit,
    )
    return SuccessResponse(success=True, data=result)


@router.get(
    "/schedules/{schedule_id}",
    response_model=SuccessResponse[TestRunScheduleInfo],
    summary="获取定时调度详情",
    description="获取指定定时调度的详细信息",
)
async def get_schedule(
    project_identifier: str,
    schedule_id: str,
    service: TestRunServiceDep,
) -> SuccessResponse:
    schedule = await service.get_schedule(project_identifier, schedule_id)
    return SuccessResponse(success=True, data=schedule)


@router.post(
    "/schedules",
    response_model=SuccessResponse[TestRunScheduleInfo],
    status_code=status.HTTP_201_CREATED,
    summary="创建定时调度",
    description="创建新的测试运行定时调度",
)
async def create_schedule(
    project_identifier: str,
    data: TestRunScheduleCreate,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse:
    schedule = await service.create_schedule(project_identifier, data)
    await db.commit()
    return SuccessResponse(success=True, data=schedule)


@router.patch(
    "/schedules/{schedule_id}",
    response_model=SuccessResponse[TestRunScheduleInfo],
    summary="更新定时调度",
    description="更新定时调度的配置",
)
async def update_schedule(
    project_identifier: str,
    schedule_id: str,
    data: TestRunScheduleUpdate,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse:
    schedule = await service.update_schedule(
        project_identifier, schedule_id, data
    )
    await db.commit()
    return SuccessResponse(success=True, data=schedule)


@router.delete(
    "/schedules/{schedule_id}",
    response_model=MessageResponse,
    summary="删除定时调度",
    description="删除指定的定时调度",
)
async def delete_schedule(
    project_identifier: str,
    schedule_id: str,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> MessageResponse:
    await service.delete_schedule(project_identifier, schedule_id)
    await db.commit()
    return MessageResponse(
        success=True,
        message=f"Schedule {schedule_id} has been deleted successfully",
    )


@router.post(
    "/schedules/{schedule_id}/trigger",
    response_model=SuccessResponse,
    summary="立即触发调度",
    description="手动触发一次定时调度，生成 TestRun 并执行（含幂等保护）",
)
async def trigger_schedule(
    project_identifier: str,
    schedule_id: str,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse:
    result = await service.trigger_schedule(project_identifier, schedule_id)
    await db.commit()
    return SuccessResponse(success=True, data=result)


@router.get(
    "/schedules/{schedule_id}/runs",
    response_model=SuccessResponse,
    summary="获取调度的执行历史",
    description="获取指定定时调度产生的所有 TestRun 执行记录",
)
async def get_schedule_runs(
    project_identifier: str,
    schedule_id: str,
    service: TestRunServiceDep,
    pagination: PaginationDep,
) -> SuccessResponse:
    result = await service.get_schedule_runs(
        project_identifier,
        schedule_id,
        page=pagination.page,
        page_size=pagination.limit,
    )
    return SuccessResponse(success=True, data=result)


@router.get(
    "/{test_run_identifier}",
    response_model=SuccessResponse[Union[TestRunInfo, TestRunMinifiedInfo]],
    summary="获取测试运行详情",
    description="支持 minify=true 返回精简详情，默认返回完整详情（含 inline test_cases[]）",
)
async def get_test_run(
    project_identifier: str,
    test_run_identifier: str,
    service: TestRunServiceDep,
    minify: bool = Query(default=False, description="是否返回精简详情"),
) -> SuccessResponse:
    test_run = await service.get_detail(
        project_identifier, test_run_identifier, minify=minify
    )
    return SuccessResponse(success=True, data=test_run)


@router.post(
    "",
    response_model=SuccessResponse[TestRunInfo],
    status_code=status.HTTP_201_CREATED,
    summary="创建测试运行",
    description=(
        "BS POST /test-runs。支持 5 级用例解析: "
        "include_all → folder_ids+filter(within_folders) → folder_ids → filter(global) → "
        "显式 test_cases。configuration_map 覆盖全局 configurations。"
    ),
)
async def create_test_run(
    project_identifier: str,
    data: TestRunCreate,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[TestRunInfo]:
    test_run = await service.create(project_identifier, data)
    await db.commit()
    return SuccessResponse(success=True, data=test_run)


# =============== 更新 (PATCH 部分 / POST 全量) ===============


@router.patch(
    "/{test_run_identifier}/update",
    response_model=SuccessResponse[TestRunInfo],
    summary="部分更新测试运行 (PATCH /update)",
    description="按 BS PATCH /test-runs/{id}/update，仅更新提供的字段",
)
async def patch_test_run(
    project_identifier: str,
    test_run_identifier: str,
    data: TestRunPatchUpdate,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[TestRunInfo]:
    test_run = await service.patch_update(
        project_identifier, test_run_identifier, data
    )
    await db.commit()
    return SuccessResponse(success=True, data=test_run)
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WTIxcVVnPT06ZGNhNTJiOWI=


@router.post(
    "/{test_run_identifier}/update",
    response_model=SuccessResponse[TestRunInfo],
    summary="全量替换测试运行 (POST /update)",
    description="按 BS POST /test-runs/{id}/update，整体替换字段并重建关联用例",
)
async def replace_test_run(
    project_identifier: str,
    test_run_identifier: str,
    data: TestRunFullReplace,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[TestRunInfo]:
    test_run = await service.full_replace(
        project_identifier, test_run_identifier, data
    )
    await db.commit()
    return SuccessResponse(success=True, data=test_run)


# =============== 关闭 / 删除 ===============


@router.post(
    "/{test_run_identifier}/close",
    response_model=SuccessResponse[TestRunInfo],
    summary="关闭测试运行",
    description="将 active_state 置为 closed 并记录 closed_at",
)
async def close_test_run(
    project_identifier: str,
    test_run_identifier: str,
    data: CloseTestRunRequest,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[TestRunInfo]:
    test_run = await service.close_test_run(
        project_identifier, test_run_identifier, data
    )
    await db.commit()
    return SuccessResponse(success=True, data=test_run)


@router.post(
    "/{test_run_identifier}/delete",
    response_model=MessageResponse,
    summary="删除测试运行",
    description="BS POST /test-runs/{id}/delete",
)
async def delete_test_run(
    project_identifier: str,
    test_run_identifier: str,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> MessageResponse:
    await service.delete(project_identifier, test_run_identifier)
    await db.commit()
    return MessageResponse(
        success=True,
        message=f"Test Run {test_run_identifier} has been deleted successfully",
    )


# =============== 标准 REST 兼容端点 ===============


@router.patch(
    "/{test_run_identifier}",
    response_model=SuccessResponse[TestRunInfo],
    summary="部分更新测试运行 (PATCH)",
    description="标准 REST 风格的部分更新，与 POST /update 行为一致",
)
async def patch_test_run_rest(
    project_identifier: str,
    test_run_identifier: str,
    data: TestRunPatchUpdate,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[TestRunInfo]:
    test_run = await service.patch_update(
        project_identifier, test_run_identifier, data
    )
    await db.commit()
    return SuccessResponse(success=True, data=test_run)


@router.put(
    "/{test_run_identifier}",
    response_model=SuccessResponse[TestRunInfo],
    summary="全量替换测试运行 (PUT)",
    description="标准 REST 风格的全量替换，与 POST /update 行为一致",
)
async def put_test_run_rest(
    project_identifier: str,
    test_run_identifier: str,
    data: TestRunFullReplace,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[TestRunInfo]:
    test_run = await service.full_replace(
        project_identifier, test_run_identifier, data
    )
    await db.commit()
    return SuccessResponse(success=True, data=test_run)


@router.delete(
    "/{test_run_identifier}",
    response_model=MessageResponse,
    summary="删除测试运行 (DELETE)",
    description="标准 REST 风格的删除，与 POST /delete 行为一致",
)
async def delete_test_run_rest(
    project_identifier: str,
    test_run_identifier: str,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> MessageResponse:
    await service.delete(project_identifier, test_run_identifier)
    await db.commit()
    return MessageResponse(
        success=True,
        message=f"Test Run {test_run_identifier} has been deleted successfully",
    )


# =============== 分配负责人 ===============


@router.post(
    "/{test_run_identifier}/assign",
    response_model=SuccessResponse[TestRunInfo],
    summary="批量分配测试用例负责人",
    description="BS POST /test-runs/{id}/assign",
)
async def assign_test_run(
    project_identifier: str,
    test_run_identifier: str,
    data: TestRunAssignRequest,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[TestRunInfo]:
    test_run = await service.assign(
        project_identifier, test_run_identifier, data
    )
    await db.commit()
    return SuccessResponse(success=True, data=test_run)


# =============== 测试用例子资源 ===============


@router.get(
    "/{test_run_identifier}/test-cases",
    response_model=PaginatedResponse[
        Union[TestRunTestCaseInfo, TestRunTestCaseMinifiedInfo]
    ],
    summary="获取测试运行中的测试用例",
    description=(
        "BS GET /test-runs/{id}/test-cases。"
        "minify=true 返回精简字段；fetch_steps=true 返回前 30 条步骤且禁用分页"
    ),
)
async def list_test_run_test_cases(
    project_identifier: str,
    test_run_identifier: str,
    service: TestRunServiceDep,
    pagination: PaginationDep,
    status: Optional[TestResultStatus] = Query(
        default=None, description="按最新状态过滤"
    ),
    assignee: Optional[str] = Query(default=None, description="按负责人过滤"),
    search: Optional[str] = Query(default=None, description="按名称/标识符搜索"),
    minify: bool = Query(default=False, description="返回精简字段"),
    fetch_steps: bool = Query(
        default=False,
        description="返回前 30 条步骤（禁用分页，与 minify 互斥）",
    ),
) -> PaginatedResponse:
    items, total = await service.get_test_cases(
        project_identifier,
        test_run_identifier,
        status=status,
        assignee=assignee,
        search=search,
        minify=minify,
        fetch_steps=fetch_steps,
        offset=pagination.offset,
        limit=pagination.limit,
    )
    return PaginatedResponse(
        success=True,
        data=items,
        pagination=PaginationInfo(
            total=total,
            page=pagination.page,
            page_size=pagination.limit,
        ),
    )


@router.post(
    "/{test_run_identifier}/test-cases",
    response_model=SuccessResponse[TestRunInfo],
    summary="添加测试用例到测试运行",
    description="便利扩展接口：向测试运行添加测试用例",
)
async def add_test_cases_to_run(
    project_identifier: str,
    test_run_identifier: str,
    data: AddTestCasesRequest,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[TestRunInfo]:
    test_run = await service.add_test_cases(
        project_identifier, test_run_identifier, data
    )
    await db.commit()
    return SuccessResponse(success=True, data=test_run)
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WTIxcVVnPT06ZGNhNTJiOWI=


@router.delete(
    "/{test_run_identifier}/test-cases",
    response_model=SuccessResponse[TestRunInfo],
    summary="从测试运行移除测试用例",
    description="便利扩展接口：移除测试运行中的测试用例",
)
async def remove_test_cases_from_run(
    project_identifier: str,
    test_run_identifier: str,
    data: RemoveTestCasesRequest,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[TestRunInfo]:
    test_run = await service.remove_test_cases(
        project_identifier, test_run_identifier, data
    )
    await db.commit()
    return SuccessResponse(success=True, data=test_run)


@router.post(
    "/{test_run_identifier}/execute",
    response_model=SuccessResponse,
    summary="执行测试运行",
    description="遍历测试运行中的所有测试用例，执行关联的 API/Web 测试脚本，并将结果回写到测试运行",
)
async def execute_test_run(
    project_identifier: str,
    test_run_identifier: str,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse:
    """
    执行测试运行

    触发测试运行的自动化执行（fire-and-forget）：
    1. 更新测试运行状态为 IN_PROGRESS
    2. 将实际执行提交到后台任务
    3. 立即返回，前端通过轮询获取执行状态
    """
    result = await service.execute_test_run(
        project_identifier, test_run_identifier
    )
    return SuccessResponse(success=True, data=result)


@router.post(
    "/{test_run_identifier}/cancel",
    response_model=SuccessResponse,
    summary="取消测试运行执行",
    description="取消正在执行的测试运行",
)
async def cancel_test_run(
    project_identifier: str,
    test_run_identifier: str,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse:
    """取消测试运行"""
    from app.services.test_execution_engine import TestExecutionService

    # 获取 test_run 的 project_id 以查找对应的 TestRun
    test_run = await service.get_detail(
        project_identifier, test_run_identifier, minify=True
    )
    test_run_id = test_run.id
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WTIxcVVnPT06ZGNhNTJiOWI=

    execution_service = TestExecutionService()
    await execution_service.cancel_run(test_run_id)

    await db.commit()
    return SuccessResponse(success=True, data={"cancelled": True})


@router.get(
    "/{test_run_identifier}/events",
    summary="实时执行状态推送 (SSE)",
    description="Server-Sent Events 推送测试运行执行状态变更",
)
async def test_run_events(
    project_identifier: str,
    test_run_identifier: str,
    service: TestRunServiceDep,
) -> StreamingResponse:
    """SSE 实时推送测试运行状态"""
    async def event_generator():
        last_jobs: dict | None = None
        last_run_state: str | None = None

        while True:
            try:
                # 获取测试运行详情
                test_run = await service.get_detail(
                    project_identifier, test_run_identifier, minify=True
                )
                current_state = test_run.run_state

                # 获取脚本作业列表
                jobs_result = await service.get_script_jobs(
                    project_identifier,
                    test_run_identifier,
                    page=1,
                    page_size=100,
                )
                current_jobs = {
                    str(j.id): {
                        "status": j.status,
                        "duration_ms": j.duration_ms,
                        "error_message": j.error_message,
                        "result_summary": j.result_summary,
                    }
                    for j in jobs_result["items"]
                }

                # 如果有变化则推送
                if current_jobs != last_jobs or current_state != last_run_state:
                    payload = {
                        "run_state": current_state,
                        "active_state": test_run.active_state,
                        "overall_progress": test_run.overall_progress.model_dump(),
                        "jobs": [j.model_dump() for j in jobs_result["items"]],
                    }
                    yield f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
                    last_jobs = current_jobs
                    last_run_state = current_state

                # 如果执行完成，发送完成事件后关闭
                if current_state in ("done", "rejected", "closed"):
                    yield f"data: {json.dumps({'event': 'completed', 'run_state': current_state}, ensure_ascii=False)}\n\n"
                    break

                await asyncio.sleep(2)

            except Exception as e:
                yield f"data: {json.dumps({'event': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============== 执行快照子资源 ===============


@router.get(
    "/{test_run_identifier}/snapshots",
    response_model=SuccessResponse,
    summary="获取测试运行执行快照列表",
    description="获取同一 TestRun 每次执行结束后的快照，用于在详情页切换历史执行结果",
)
async def list_execution_snapshots(
    project_identifier: str,
    test_run_identifier: str,
    service: TestRunServiceDep,
    pagination: PaginationDep,
) -> SuccessResponse:
    result = await service.get_execution_snapshots(
        project_identifier,
        test_run_identifier,
        page=pagination.page,
        page_size=pagination.limit,
    )
    return SuccessResponse(success=True, data=result)


@router.get(
    "/{test_run_identifier}/snapshots/{snapshot_id}",
    response_model=SuccessResponse[TestRunExecutionSnapshotInfo],
    summary="获取执行快照详情",
    description="获取指定快照的详细信息及该次执行时所有脚本作业的状态",
)
async def get_execution_snapshot(
    project_identifier: str,
    test_run_identifier: str,
    snapshot_id: str,
    service: TestRunServiceDep,
) -> SuccessResponse:
    snapshot = await service.get_execution_snapshot_detail(
        project_identifier, test_run_identifier, snapshot_id
    )
    return SuccessResponse(success=True, data=snapshot)


@router.get(
    "/{test_run_identifier}/snapshots/{snapshot_id}/jobs/{snapshot_job_id}/logs",
    response_model=SuccessResponse,
    summary="获取快照作业日志",
    description="获取快照作业执行时的 stdout/stderr 日志",
)
async def get_snapshot_job_logs_endpoint(
    project_identifier: str,
    test_run_identifier: str,
    snapshot_id: str,
    snapshot_job_id: str,
    service: TestRunServiceDep,
) -> SuccessResponse:
    result = await service.get_snapshot_job_logs(
        project_identifier, test_run_identifier, snapshot_id, snapshot_job_id
    )
    return SuccessResponse(success=True, data=result)


@router.get(
    "/{test_run_identifier}/snapshots/{snapshot_id}/jobs/{snapshot_job_id}/report-url",
    response_model=SuccessResponse,
    summary="获取快照作业报告浏览 URL",
    description="获取可直接在浏览器中打开的快照报告预览 URL",
)
async def get_snapshot_job_report_url_endpoint(
    project_identifier: str,
    test_run_identifier: str,
    snapshot_id: str,
    snapshot_job_id: str,
    service: TestRunServiceDep,
) -> SuccessResponse:
    result = await service.get_snapshot_job_report_url(
        project_identifier, test_run_identifier, snapshot_id, snapshot_job_id
    )
    return SuccessResponse(success=True, data=result)


@router.get(
    "/{test_run_identifier}/snapshots/{snapshot_id}/jobs/{snapshot_job_id}/report-preview",
    response_class=HTMLResponse,
    summary="预览快照作业 HTML 报告",
    description="从 MinIO 下载 ZIP 报告并解压返回 index.html 内容",
)
@router.get(
    "/{test_run_identifier}/snapshots/{snapshot_id}/jobs/{snapshot_job_id}/report-preview/",
    response_class=HTMLResponse,
    include_in_schema=False,
    operation_id="get_snapshot_job_report_preview_slash",
)
async def get_snapshot_job_report_preview_endpoint(
    project_identifier: str,
    test_run_identifier: str,
    snapshot_id: str,
    snapshot_job_id: str,
    service: TestRunServiceDep,
) -> HTMLResponse:
    html = await service.get_snapshot_job_report_preview(
        project_identifier, test_run_identifier, snapshot_id, snapshot_job_id
    )
    return HTMLResponse(content=html)


@router.get(
    "/{test_run_identifier}/snapshots/{snapshot_id}/jobs/{snapshot_job_id}/report-download",
    summary="下载快照作业报告 ZIP",
    description="从 MinIO 下载快照作业报告 ZIP 文件并返回，触发浏览器下载",
)
async def get_snapshot_job_report_download(
    project_identifier: str,
    test_run_identifier: str,
    snapshot_id: str,
    snapshot_job_id: str,
    service: TestRunServiceDep,
) -> Response:
    zip_bytes = await service.get_snapshot_job_report_download(
        project_identifier, test_run_identifier, snapshot_id, snapshot_job_id
    )
    filename = f"snapshot-{snapshot_id}-job-{snapshot_job_id}-report.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(zip_bytes)),
        },
    )


@router.get(
    "/{test_run_identifier}/snapshots/{snapshot_id}/jobs/{snapshot_job_id}/report-preview/{resource_path:path}",
    summary="获取快照作业报告资源",
    description="从 ZIP 报告中解压并返回指定资源文件（CSS/JS/图片等）",
)
async def get_snapshot_job_report_resource(
    project_identifier: str,
    test_run_identifier: str,
    snapshot_id: str,
    snapshot_job_id: str,
    resource_path: str,
    service: TestRunServiceDep,
) -> Response:
    # 复用脚本作业报告资源下载逻辑：先拿到报告路径，再按路径解压资源
    from app.repositories.test_run_repo import TestRunExecutionSnapshotRepository
    from app.config.minio_client import MinIOClient
    import zipfile
    import tempfile
    import mimetypes
    from pathlib import Path

    project = await service._get_project_by_identifier(project_identifier)
    test_run = await service._require_test_run(project.id, test_run_identifier)

    try:
        snapshot_uuid = UUID(snapshot_id)
        snapshot_job_uuid = UUID(snapshot_job_id)
    except ValueError:
        from app.utils.exceptions import BadRequestException
        raise BadRequestException(message="快照 ID 或快照作业 ID 格式不正确")

    snapshot = await service.snapshot_repo.get_by_id(snapshot_uuid)
    if not snapshot or snapshot.test_run_id != test_run.id:
        from app.utils.exceptions import NotFoundException
        raise NotFoundException(resource_type="执行快照", resource_id=snapshot_id)

    snapshot_job = next(
        (j for j in (snapshot.snapshot_jobs or []) if j.id == snapshot_job_uuid), None
    )
    if not snapshot_job:
        from app.utils.exceptions import NotFoundException
        raise NotFoundException(resource_type="快照作业", resource_id=snapshot_job_id)

    if not snapshot_job.report_path:
        from app.utils.exceptions import NotFoundException
        raise NotFoundException(
            resource_type="报告", resource_id=snapshot_job_id, message="该快照作业暂无报告"
        )

    zip_bytes = MinIOClient.download_file(snapshot_job.report_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        zip_file = tmp_path / "report.zip"
        zip_file.write_bytes(zip_bytes)

        with zipfile.ZipFile(zip_file, "r") as zf:
            resource_file = None
            matched_name = resource_path

            # 兼容：某些浏览器/代理会去掉 base href 末尾斜杠，请求到 html/
            # 目录本身，返回报告首页避免白屏。
            if resource_path in ("html", "html/"):
                for name in zf.namelist():
                    if name.endswith("/"):
                        continue
                    if name.endswith("index.html") and name.startswith("html/"):
                        resource_file = zf.read(name)
                        matched_name = name
                        break

            if resource_file is None:
                for name in zf.namelist():
                    if name.endswith("/"):
                        continue
                    # 去除可能的顶级目录前缀，兼容 base href 指向 report-preview/ 或
                    # report-preview/html/ 两种场景。
                    clean_name = name.split("/", 1)[1] if "/" in name else name
                    if clean_name == resource_path or name == resource_path:
                        resource_file = zf.read(name)
                        matched_name = name
                        break

            if resource_file is None:
                from app.utils.exceptions import NotFoundException
                raise NotFoundException(
                    resource_type="报告资源", resource_id=resource_path
                )

            content_type = mimetypes.guess_type(matched_name)[0] or "application/octet-stream"
            return Response(content=resource_file, media_type=content_type)


# =============== 脚本作业子资源 ===============


@router.get(
    "/{test_run_identifier}/script-jobs",
    response_model=SuccessResponse,
    summary="获取测试运行的脚本作业",
    description="获取测试运行中的所有脚本作业列表，支持按脚本类型过滤",
)
async def list_script_jobs(
    project_identifier: str,
    test_run_identifier: str,
    service: TestRunServiceDep,
    pagination: PaginationDep,
    script_type: Optional[str] = Query(default=None, description="脚本类型过滤"),
) -> SuccessResponse:
    from app.schemas.enums import ScriptType
    st = ScriptType(script_type) if script_type else None
    result = await service.get_script_jobs(
        project_identifier,
        test_run_identifier,
        script_type=st,
        page=pagination.page,
        page_size=pagination.limit,
    )
    return SuccessResponse(success=True, data=result)


@router.post(
    "/{test_run_identifier}/script-jobs",
    response_model=SuccessResponse[TestRunInfo],
    summary="添加脚本作业到测试运行",
    description="向测试运行添加一个或多个脚本作业",
)
async def add_script_jobs(
    project_identifier: str,
    test_run_identifier: str,
    data: list[TestRunScriptJobCreate],
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse:
    test_run = await service.add_script_jobs(
        project_identifier, test_run_identifier, data
    )
    await db.commit()
    return SuccessResponse(success=True, data=test_run)


@router.delete(
    "/{test_run_identifier}/script-jobs/{job_id}",
    response_model=SuccessResponse[TestRunInfo],
    summary="从测试运行移除脚本作业",
    description="移除测试运行中的指定脚本作业",
)
async def remove_script_job(
    project_identifier: str,
    test_run_identifier: str,
    job_id: str,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse:
    test_run = await service.remove_script_job(
        project_identifier, test_run_identifier, job_id
    )
    await db.commit()
    return SuccessResponse(success=True, data=test_run)


@router.get(
    "/{test_run_identifier}/script-jobs/{job_id}/report-url",
    response_model=SuccessResponse,
    summary="获取脚本作业报告浏览 URL",
    description="获取可直接在浏览器中打开的报告预览 URL",
)
async def get_job_report_url(
    project_identifier: str,
    test_run_identifier: str,
    job_id: str,
    service: TestRunServiceDep,
) -> SuccessResponse:
    # 验证作业存在且有报告路径
    project = await service._get_project_by_identifier(project_identifier)
    test_run = await service._require_test_run(project.id, test_run_identifier)
    from app.repositories.test_run_repo import TestRunScriptJobRepository
    job_repo = TestRunScriptJobRepository(service.session)
    job = await job_repo.get_by_id(UUID(job_id))
    if not job or job.test_run_id != test_run.id:
        from app.utils.exceptions import NotFoundException
        raise NotFoundException(resource_type="脚本作业", resource_id=job_id)
    if not job.report_path:
        from app.utils.exceptions import NotFoundException
        raise NotFoundException(
            resource_type="报告", resource_id=job_id, message="该作业暂无报告"
        )
    url = (
        f"/api/v2/projects/{project_identifier}"
        f"/test-runs/{test_run_identifier}"
        f"/script-jobs/{job_id}/report-preview"
    )
    return SuccessResponse(success=True, data={"url": url, "expires_in": 3600})


@router.get(
    "/{test_run_identifier}/script-jobs/{job_id}/report-download",
    summary="下载脚本作业报告 ZIP",
    description="从 MinIO 下载脚本作业报告 ZIP 文件并返回，触发浏览器下载",
)
async def get_job_report_download(
    project_identifier: str,
    test_run_identifier: str,
    job_id: str,
    service: TestRunServiceDep,
) -> Response:
    zip_bytes = await service.get_job_report_download(
        project_identifier, test_run_identifier, job_id
    )
    filename = f"job-{job_id}-report.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(zip_bytes)),
        },
    )


@router.post(
    "/{test_run_identifier}/script-jobs/{job_id}/retry",
    response_model=SuccessResponse[TestRunScriptJobInfo],
    summary="重试脚本作业",
    description="将失败的脚本作业重置为 pending 状态并增加重试计数",
)
async def retry_script_job(
    project_identifier: str,
    test_run_identifier: str,
    job_id: str,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse:
    job = await service.retry_job(
        project_identifier, test_run_identifier, job_id
    )
    await db.commit()
    return SuccessResponse(success=True, data=job)


@router.get(
    "/{test_run_identifier}/script-jobs/{job_id}/logs",
    response_model=SuccessResponse,
    summary="获取脚本作业日志",
    description="获取脚本作业的 stdout/stderr 输出日志",
)
async def get_job_logs(
    project_identifier: str,
    test_run_identifier: str,
    job_id: str,
    service: TestRunServiceDep,
) -> SuccessResponse:
    result = await service.get_job_logs(
        project_identifier, test_run_identifier, job_id
    )
    return SuccessResponse(success=True, data=result)


@router.post(
    "/{test_run_identifier}/script-jobs/batch-retry",
    response_model=SuccessResponse,
    summary="批量重试脚本作业",
    description="批量将失败的脚本作业重置为 pending 状态",
)
async def batch_retry_script_jobs(
    project_identifier: str,
    test_run_identifier: str,
    data: BatchRetryJobsRequest,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse:
    jobs = await service.batch_retry_jobs(
        project_identifier, test_run_identifier, data.job_ids
    )
    await db.commit()
    return SuccessResponse(success=True, data={"retried": len(jobs), "jobs": jobs})


@router.get(
    "/{test_run_identifier}/script-jobs/history",
    response_model=SuccessResponse,
    summary="获取脚本执行历史趋势",
    description="获取同一脚本的历史执行记录和成功率统计",
)
async def get_script_history(
    project_identifier: str,
    test_run_identifier: str,
    service: TestRunServiceDep,
    script_type: ScriptType = Query(..., description="脚本类型"),
    script_id: str = Query(..., description="脚本 ID"),
    limit: int = Query(default=30, description="返回记录数"),
) -> SuccessResponse:
    result = await service.get_script_history(
        project_identifier, script_type, script_id, limit=limit
    )
    return SuccessResponse(success=True, data=result)


@router.get(
    "/{test_run_identifier}/script-jobs/benchmark",
    response_model=SuccessResponse,
    summary="获取脚本性能基准",
    description="获取同一脚本的耗时趋势和统计数据（avg/min/max/median）",
)
async def get_script_benchmark(
    project_identifier: str,
    test_run_identifier: str,
    service: TestRunServiceDep,
    script_type: ScriptType = Query(..., description="脚本类型"),
    script_id: str = Query(..., description="脚本 ID"),
    limit: int = Query(default=30, description="返回记录数"),
) -> SuccessResponse:
    result = await service.get_script_benchmark(
        project_identifier, script_type, script_id, limit=limit
    )
    return SuccessResponse(success=True, data=result)


@router.get(
    "/{test_run_identifier}/script-jobs/{job_id}/report-preview/",
    response_class=HTMLResponse,
    include_in_schema=False,
    operation_id="get_job_report_preview_slash",
)
@router.get(
    "/{test_run_identifier}/script-jobs/{job_id}/report-preview",
    response_class=HTMLResponse,
    summary="预览脚本作业 HTML 报告",
    description="从 MinIO 下载 ZIP 报告并解压返回 index.html 内容；service 层已根据 index.html 在包内的实际路径注入 base 标签，使截图/视频/trace 等相对资源可正常加载",
)
async def get_job_report_preview(
    project_identifier: str,
    test_run_identifier: str,
    job_id: str,
    service: TestRunServiceDep,
) -> HTMLResponse:
    # service 层已根据 ZIP 中 index.html 的实际位置注入正确的 <base> 标签，
    # 此处直接返回，避免重复/覆盖导致截图/视频/trace 资源路径错位 404。
    html = await service.get_job_report_preview(
        project_identifier, test_run_identifier, job_id
    )
    return HTMLResponse(content=html)


@router.get(
    "/{test_run_identifier}/script-jobs/{job_id}/report-preview/{resource_path:path}",
    summary="获取脚本作业报告资源",
    description="从 ZIP 报告中解压并返回指定资源文件（CSS/JS/图片等）",
)
async def get_job_report_resource(
    project_identifier: str,
    test_run_identifier: str,
    job_id: str,
    resource_path: str,
    service: TestRunServiceDep,
) -> Response:
    data, content_type = await service.get_job_report_resource(
        project_identifier, test_run_identifier, job_id, resource_path
    )
    return Response(content=data, media_type=content_type)


@router.post(
    "/{test_run_identifier}/map-jobs-to-cases",
    response_model=SuccessResponse[TestRunInfo],
    summary="将脚本作业结果映射到测试用例",
    description="将 script_job 的执行结果反向映射回 test_run_cases 的状态",
)
async def map_jobs_to_test_cases(
    project_identifier: str,
    test_run_identifier: str,
    service: TestRunServiceDep,
    db: DbSessionDep,
) -> SuccessResponse:
    test_run = await service.map_jobs_to_test_cases(
        project_identifier, test_run_identifier
    )
    await db.commit()
    return SuccessResponse(success=True, data=test_run)

