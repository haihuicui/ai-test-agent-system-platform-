"""
API 依赖注入

提供 API 路由所需的依赖项
"""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Ulc1NU9BPT06YTNiYjZkOWY=

from app.config.database import get_db
from app.config.settings import settings
from app.services.project_service import ProjectService
from app.services.folder_service import FolderService
from app.services.test_case_service import TestCaseService
from app.services.export_service import ExportService
from app.services.test_run_service import TestRunService
from app.services.test_result_service import TestResultService
from app.services.test_plan_service import TestPlanService
from app.services.api_test_service import APITestService
from app.services.environment_service import EnvironmentService
from app.services.web_function_service import WebFunctionService
from app.services.storage_state_service import StorageStateService
from app.services.pentest_service import PentestService
from app.schemas.pagination import PaginationParams
from app.config.database import get_mongodb


async def get_project_service(
    db: AsyncSession = Depends(get_db),
) -> ProjectService:
    """获取项目服务实例"""
    return ProjectService(db)


async def get_folder_service(
    db: AsyncSession = Depends(get_db),
) -> FolderService:
    """获取文件夹服务实例"""
    return FolderService(db)


async def get_test_case_service(
    db: AsyncSession = Depends(get_db),
    mongodb = Depends(get_mongodb),
) -> TestCaseService:
    """获取测试用例服务实例"""
    return TestCaseService(db, mongodb)


async def get_export_service(
    db: AsyncSession = Depends(get_db),
    mongodb = Depends(get_mongodb),
) -> ExportService:
    """获取导出服务实例"""
    return ExportService(db, mongodb)


async def get_test_run_service(
    db: AsyncSession = Depends(get_db),
    mongodb = Depends(get_mongodb),
) -> TestRunService:
    """获取测试运行服务实例"""
    return TestRunService(db, mongodb)


async def get_test_result_service(
    db: AsyncSession = Depends(get_db),
) -> TestResultService:
    """获取测试结果服务实例"""
    return TestResultService(db)
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Ulc1NU9BPT06YTNiYjZkOWY=


async def get_test_plan_service(
    db: AsyncSession = Depends(get_db),
) -> TestPlanService:
    """获取测试计划服务实例"""
    return TestPlanService(db)


async def get_api_test_service(
    db: AsyncSession = Depends(get_db),
    mongodb = Depends(get_mongodb),
) -> APITestService:
    """获取 API 测试服务实例"""
    return APITestService(db, mongodb)


async def get_environment_service(
    db: AsyncSession = Depends(get_db),
) -> EnvironmentService:
    """获取项目环境配置服务实例"""
    return EnvironmentService(db)


async def get_web_function_service(
    db: AsyncSession = Depends(get_db),
) -> WebFunctionService:
    """获取 Web 功能服务实例"""
    return WebFunctionService(db)


async def get_storage_state_service(
    db: AsyncSession = Depends(get_db),
) -> StorageStateService:
    """获取登录态生成服务实例"""
    return StorageStateService(db)


async def get_pentest_service(
    db: AsyncSession = Depends(get_db),
) -> PentestService:
    """获取渗透测试服务实例"""
    return PentestService(db)
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Ulc1NU9BPT06YTNiYjZkOWY=


def get_pagination_params(
    p: int = Query(
        default=1,
        ge=1,
        description="页码，从 1 开始",
    ),
    page_size: int = Query(
        default=settings.pagination_default_size,
        ge=1,
        le=settings.pagination_max_size,
        description=f"每页数量，默认 {settings.pagination_default_size}，最大 {settings.pagination_max_size}",
    ),
) -> PaginationParams:
    """
    获取分页参数

    参考: https://www.browserstack.com/docs/test-management/api-reference/pagination
    """
    return PaginationParams(
        p=p,
        page_size=page_size,
    )


# 类型别名，用于依赖注入
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
FolderServiceDep = Annotated[FolderService, Depends(get_folder_service)]
TestCaseServiceDep = Annotated[TestCaseService, Depends(get_test_case_service)]
ExportServiceDep = Annotated[ExportService, Depends(get_export_service)]
TestRunServiceDep = Annotated[TestRunService, Depends(get_test_run_service)]
TestResultServiceDep = Annotated[TestResultService, Depends(get_test_result_service)]
TestPlanServiceDep = Annotated[TestPlanService, Depends(get_test_plan_service)]
APITestServiceDep = Annotated[APITestService, Depends(get_api_test_service)]
EnvironmentServiceDep = Annotated[EnvironmentService, Depends(get_environment_service)]
WebFunctionServiceDep = Annotated[WebFunctionService, Depends(get_web_function_service)]
StorageStateServiceDep = Annotated[StorageStateService, Depends(get_storage_state_service)]
PentestServiceDep = Annotated[PentestService, Depends(get_pentest_service)]
PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db)]


def get_current_user_id() -> UUID:
    """
    获取当前用户 ID

    注意: 这是一个简化实现，实际应用中应该从认证中间件获取
    目前使用配置中的默认用户ID
    """
    # TODO: 实现真正的用户认证
    return UUID(settings.default_user_id)


CurrentUserIdDep = Annotated[UUID, Depends(get_current_user_id)]

# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Ulc1NU9BPT06YTNiYjZkOWY=
