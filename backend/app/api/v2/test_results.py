"""
测试结果 API 路由

提供测试结果相关的 RESTful API 接口
参考: https://www.browserstack.com/docs/test-management/api-reference/test-results
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query, status
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZVhrM1RBPT06MTUwMzRiMmU=

from app.api.deps import (
    TestResultServiceDep,
    PaginationDep,
    DbSessionDep,
)
from app.schemas.common import SuccessResponse
from app.schemas.pagination import PaginatedResponse, PaginationInfo
from app.schemas.test_result import (
    TestResultCreate,
    TestResultInfo,
    TestResultListInfo,
    TestResultHistoryInfo,
)
from app.schemas.enums import TestResultStatus

# 测试结果路由 - 使用 /results 匹配 BrowserStack API
router = APIRouter(
    prefix="/projects/{project_identifier}/test-runs/{test_run_identifier}",
    tags=["测试结果"],
)

# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZVhrM1RBPT06MTUwMzRiMmU=

@router.get(
    "/results",
    response_model=PaginatedResponse[TestResultListInfo],
    summary="获取测试结果列表",
    description="获取测试运行中的所有测试结果",
)
async def list_test_results(
    project_identifier: str,
    test_run_identifier: str,
    service: TestResultServiceDep,
    pagination: PaginationDep,
    status: Optional[TestResultStatus] = Query(default=None, description="状态过滤"),
) -> PaginatedResponse[TestResultListInfo]:
    """
    获取测试结果列表
    
    - **status**: 状态过滤 (passed, failed, etc.)
    """
    items, total = await service.get_list(
        project_identifier,
        test_run_identifier,
        status=status,
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


@router.get(
    "/results/{result_id}",
    response_model=SuccessResponse[TestResultInfo],
    summary="获取测试结果详情",
    description="根据 ID 获取测试结果详情",
)
async def get_test_result(
    project_identifier: str,
    test_run_identifier: str,
    result_id: UUID,
    service: TestResultServiceDep,
) -> SuccessResponse[TestResultInfo]:
    """
    获取测试结果详情

    - **result_id**: 测试结果 ID
    """
    result = await service.get_by_id(project_identifier, test_run_identifier, result_id)
    return SuccessResponse(success=True, data=result)
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZVhrM1RBPT06MTUwMzRiMmU=


@router.get(
    "/test-cases/{test_case_identifier}/results",
    response_model=PaginatedResponse[TestResultHistoryInfo],
    summary="获取测试用例结果历史",
    description="获取测试用例在测试运行中的历史执行结果",
)
async def get_test_case_results(
    project_identifier: str,
    test_run_identifier: str,
    test_case_identifier: str,
    service: TestResultServiceDep,
    pagination: PaginationDep,
    configuration_id: Optional[int] = Query(default=None, description="配置 ID"),
) -> PaginatedResponse[TestResultHistoryInfo]:
    """
    获取测试用例在测试运行中的历史执行结果

    - **test_case_identifier**: 测试用例标识符
    - **configuration_id**: 配置 ID (可选)
    """
    items, total = await service.get_history(
        project_identifier,
        test_run_identifier,
        test_case_identifier,
        configuration_id=configuration_id,
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
    "/results",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="添加测试结果",
    description="""
为测试用例添加执行结果，支持单个和批量添加。

根据 BrowserStack 官方 API 规范，此端点同时支持:
- 单个结果添加
- 批量结果添加 (通过 results 数组)

最多支持 300 个唯一测试用例 ID。
""",
)
async def add_test_result(
    project_identifier: str,
    test_run_identifier: str,
    data: TestResultCreate,
    service: TestResultServiceDep,
    db: DbSessionDep,
) -> SuccessResponse:
    """
    添加测试结果

    支持单个结果和批量结果添加。

    **单个结果请求体:**
    ```json
    {
      "test_result": {
        "status": "passed",
        "description": "Test passed successfully"
      },
      "test_case_id": "TC-123"
    }
    ```

    **批量结果请求体 (使用 results 数组):**
    ```json
    {
      "results": [
        {"test_result": {"status": "passed"}, "test_case_id": "TC-123"},
        {"test_result": {"status": "failed"}, "test_case_id": "TC-124"}
      ]
    }
    ```

    注意: 根据 BrowserStack 官方 API，不再提供单独的 /results/bulk 端点
    """
    result = await service.add_result(project_identifier, test_run_identifier, data)
    await db.commit()
    return SuccessResponse(success=True, data=result)

# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZVhrM1RBPT06MTUwMzRiMmU=
