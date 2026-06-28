"""
配置管理 API

提供配置的获取和创建操作
参考: https://www.browserstack.com/docs/test-management/api-reference/configurations
"""

from typing import Annotated, Optional

from fastapi import APIRouter, status, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUZoc1NBPT06MWU0ZDRhY2Q=

from app.api.deps import DbSessionDep, get_pagination_params
from app.services.configuration_service import ConfigurationService
from app.schemas.configuration import (
    ConfigurationCreate,
    ConfigurationInfo,
    ConfigurationDetailInfo,
    ConfigurationCreateResponse,
)
from app.schemas.common import SuccessResponse, MessageResponse
from app.schemas.pagination import PaginationParams
from app.config.database import get_db


router = APIRouter(prefix="/configurations", tags=["配置管理"])


def get_configuration_service(session: AsyncSession = Depends(get_db)) -> ConfigurationService:
    """获取配置服务"""
    return ConfigurationService(session)


ConfigurationServiceDep = Annotated[ConfigurationService, Depends(get_configuration_service)]
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUZoc1NBPT06MWU0ZDRhY2Q=


@router.get(
    "",
    response_model=SuccessResponse[list[ConfigurationInfo]],
    summary="获取配置列表",
    description="""
获取所有系统和自定义配置列表。

配置包括操作系统、浏览器、设备的组合，用于跟踪测试运行中测试用例在不同配置下的状态。

可选参数：
- `is_system`: 过滤系统配置（true）或自定义配置（false）
""",
)
async def get_configurations(
    service: ConfigurationServiceDep,
    pagination: PaginationParams = Depends(get_pagination_params),
    is_system: Optional[bool] = Query(
        default=None,
        description="过滤配置类型: true=系统配置, false=自定义配置"
    ),
) -> SuccessResponse[list[ConfigurationInfo]]:
    """获取配置列表"""
    configs, total = await service.get_list(
        is_system=is_system,
        offset=pagination.offset,
        limit=pagination.limit,
    )
    
    # 返回符合 BrowserStack API 格式的响应
    return SuccessResponse(
        success=True,
        data=configs,
    )

# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUZoc1NBPT06MWU0ZDRhY2Q=

@router.get(
    "/{configuration_id}",
    response_model=SuccessResponse[ConfigurationDetailInfo],
    summary="获取配置详情",
    description="""
根据配置 ID 获取配置的详细信息。

返回配置的所有属性，包括操作系统、浏览器、设备信息等。
""",
)
async def get_configuration(
    configuration_id: int,
    service: ConfigurationServiceDep,
) -> SuccessResponse[ConfigurationDetailInfo]:
    """获取配置详情"""
    config = await service.get_by_id(configuration_id)
    return SuccessResponse(success=True, data=config)


@router.post(
    "",
    response_model=ConfigurationCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建自定义配置",
    description="""
创建新的自定义配置。

配置名称必须唯一。创建的配置将标记为 `is_system=false`。
""",
)
async def create_configuration(
    data: ConfigurationCreate,
    service: ConfigurationServiceDep,
    db: DbSessionDep,
) -> ConfigurationCreateResponse:
    """创建自定义配置"""
    result = await service.create(data)
    await db.commit()
    return result

# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUZoc1NBPT06MWU0ZDRhY2Q=

# 注意: 根据 BrowserStack 官方 API 文档，配置 API 不提供 DELETE 端点
# 官方 API 仅支持: GET /configurations, GET /configurations/{id}, POST /configurations

