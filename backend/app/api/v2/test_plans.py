"""
测试计划 API 路由

提供测试计划相关的 RESTful API 接口
参考: https://www.browserstack.com/docs/test-management/api-reference/test-plans
"""

from typing import Optional
from fastapi import APIRouter, Query, status
from app.api.deps import (
    TestPlanServiceDep,
    PaginationDep,
    DbSessionDep,
)
from app.schemas.common import SuccessResponse
from app.schemas.pagination import PaginatedResponse, PaginationInfo
from app.schemas.test_plan import (
    TestPlanCreate,
    TestPlanUpdate,
    TestPlanInfo,
    TestPlanListInfo,
    TestRunBrief,
)
router = APIRouter(
    prefix="/projects/{project_identifier}/test-plans",
    tags=["测试计划"],
)

# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2V2xFeVZnPT06MjIzMmU3OWQ=

@router.get(
    "",
    response_model=PaginatedResponse[TestPlanListInfo],
    summary="获取测试计划列表",
    description="获取项目下的所有测试计划，支持分页",
)
async def list_test_plans(
    project_identifier: str,
    service: TestPlanServiceDep,
    pagination: PaginationDep,
) -> PaginatedResponse[TestPlanListInfo]:
    """
    获取测试计划列表
    
    - **project_identifier**: 项目标识符，如 PR-1
    """
    items, total = await service.get_test_plans(
        project_identifier,
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

# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2V2xFeVZnPT06MjIzMmU3OWQ=

@router.get(
    "/{test_plan_identifier}",
    response_model=SuccessResponse[TestPlanInfo],
    summary="获取测试计划详情",
    description="根据标识符获取测试计划详情，包含关联的测试运行信息",
)
async def get_test_plan(
    project_identifier: str,
    test_plan_identifier: str,
    service: TestPlanServiceDep,
) -> SuccessResponse[TestPlanInfo]:
    """
    获取测试计划详情
    
    - **project_identifier**: 项目标识符，如 PR-1
    - **test_plan_identifier**: 测试计划标识符，如 TP-1
    """
    test_plan = await service.get_test_plan(project_identifier, test_plan_identifier)
    return SuccessResponse(success=True, data=test_plan)


@router.post(
    "",
    response_model=SuccessResponse[TestPlanInfo],
    status_code=status.HTTP_201_CREATED,
    summary="创建测试计划",
    description="在项目中创建新的测试计划",
)
async def create_test_plan(
    project_identifier: str,
    data: TestPlanCreate,
    service: TestPlanServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[TestPlanInfo]:
    """
    创建测试计划
    
    - **project_identifier**: 项目标识符，如 PR-1
    - **name**: 测试计划名称（必填）
    - **description**: 测试计划描述（可选）
    - **start_date**: 开始日期（可选）
    - **end_date**: 结束日期（可选）
    """
    test_plan = await service.create_test_plan(project_identifier, data)
    await db.commit()
    return SuccessResponse(success=True, data=test_plan)

# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2V2xFeVZnPT06MjIzMmU3OWQ=

@router.post(
    "/{test_plan_identifier}/update",
    response_model=SuccessResponse[TestPlanInfo],
    summary="更新测试计划",
    description="更新测试计划信息（使用 POST 方法，符合 BrowserStack API 规范）",
)
async def update_test_plan(
    project_identifier: str,
    test_plan_identifier: str,
    data: TestPlanUpdate,
    service: TestPlanServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[TestPlanInfo]:
    """
    更新测试计划
    
    - **project_identifier**: 项目标识符，如 PR-1
    - **test_plan_identifier**: 测试计划标识符，如 TP-1
    """
    test_plan = await service.update_test_plan(
        project_identifier, test_plan_identifier, data
    )
    await db.commit()
    return SuccessResponse(success=True, data=test_plan)


# 注意: 根据 BrowserStack 官方 API 文档，测试计划 API 不提供以下端点:
# - PATCH /{test_plan_identifier} (部分更新)
# - DELETE /{test_plan_identifier} (删除)
# - POST /{test_plan_identifier}/close (关闭)
# 官方 API 仅支持: GET list, GET details, POST create, POST update, GET test-runs
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2V2xFeVZnPT06MjIzMmU3OWQ=


@router.get(
    "/{test_plan_identifier}/test-runs",
    response_model=PaginatedResponse[TestRunBrief],
    summary="获取测试计划关联的测试运行",
    description="获取测试计划中关联的所有测试运行列表",
)
async def list_test_plan_test_runs(
    project_identifier: str,
    test_plan_identifier: str,
    service: TestPlanServiceDep,
    pagination: PaginationDep,
) -> PaginatedResponse[TestRunBrief]:
    """
    获取测试计划关联的测试运行列表

    - **project_identifier**: 项目标识符，如 PR-1
    - **test_plan_identifier**: 测试计划标识符，如 TP-1
    """
    items, total = await service.get_test_runs(
        project_identifier,
        test_plan_identifier,
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

