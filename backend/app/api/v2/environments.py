"""
项目环境配置 API

提供项目环境配置的 CRUD 操作接口
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import DbSessionDep, EnvironmentServiceDep
from app.schemas.environment import EnvironmentCreate, EnvironmentUpdate, EnvironmentInfo
from app.schemas.common import SuccessResponse, MessageResponse


router = APIRouter(prefix="/projects/{project_identifier}/environments")


@router.get(
    "",
    response_model=SuccessResponse[list[EnvironmentInfo]],
    summary="获取项目环境配置列表",
    description="获取指定项目的所有环境配置",
)
async def list_environments(
    project_identifier: str,
    service: EnvironmentServiceDep,
) -> SuccessResponse[list[EnvironmentInfo]]:
    """
    获取项目环境配置列表

    - **project_identifier**: 项目标识符，如 PR-1234
    """
    envs = await service.list_environments(project_identifier)
    return SuccessResponse(success=True, data=envs)


@router.get(
    "/{env_id}",
    response_model=SuccessResponse[EnvironmentInfo],
    summary="获取环境配置详情",
    description="获取指定环境配置的详细信息",
)
async def get_environment(
    project_identifier: str,
    env_id: UUID,
    service: EnvironmentServiceDep,
) -> SuccessResponse[EnvironmentInfo]:
    """
    获取环境配置详情

    - **project_identifier**: 项目标识符，如 PR-1234
    - **env_id**: 环境配置 ID
    """
    env = await service.get_environment(project_identifier, env_id)
    return SuccessResponse(success=True, data=env)


@router.post(
    "",
    response_model=SuccessResponse[EnvironmentInfo],
    status_code=status.HTTP_201_CREATED,
    summary="创建环境配置",
    description="为指定项目创建新的环境配置",
)
async def create_environment(
    project_identifier: str,
    data: EnvironmentCreate,
    service: EnvironmentServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[EnvironmentInfo]:
    """
    创建环境配置

    - **project_identifier**: 项目标识符，如 PR-1234
    - **name**: 环境名称（必填）
    - **base_url**: API Base URL（必填）
    - **auth_type**: 认证类型（可选，默认 none）
    - **auth_secret**: 敏感凭据（可选，明文入参）
    - **auth_config**: 非敏感认证配置（可选）
    - **headers**: 额外请求头（可选）
    - **timeout_ms**: 默认超时（可选，默认 30000）
    - **is_default**: 是否设为默认环境（可选，默认 false）
    """
    env = await service.create_environment(project_identifier, data)
    await db.commit()
    return SuccessResponse(success=True, data=env)


@router.patch(
    "/{env_id}",
    response_model=SuccessResponse[EnvironmentInfo],
    summary="更新环境配置",
    description="更新指定环境配置的信息",
)
async def update_environment(
    project_identifier: str,
    env_id: UUID,
    data: EnvironmentUpdate,
    service: EnvironmentServiceDep,
    db: DbSessionDep,
) -> SuccessResponse[EnvironmentInfo]:
    """
    更新环境配置

    - **project_identifier**: 项目标识符，如 PR-1234
    - **env_id**: 环境配置 ID
    """
    env = await service.update_environment(project_identifier, env_id, data)
    await db.commit()
    return SuccessResponse(success=True, data=env)


@router.post(
    "/{env_id}/test-connection",
    response_model=SuccessResponse[dict],
    summary="测试环境连通性",
    description="测试动态 Bearer 认证环境的 token 获取连通性",
)
async def test_environment_connection(
    project_identifier: str,
    env_id: UUID,
    service: EnvironmentServiceDep,
) -> SuccessResponse[dict]:
    """
    测试环境连通性

    - **project_identifier**: 项目标识符，如 PR-1234
    - **env_id**: 环境配置 ID
    """
    result = await service.test_dynamic_token_connection(project_identifier, env_id)
    return SuccessResponse(success=result.get("success", False), data=result)


@router.delete(
    "/{env_id}",
    response_model=MessageResponse,
    summary="删除环境配置",
    description="删除指定的环境配置",
)
async def delete_environment(
    project_identifier: str,
    env_id: UUID,
    service: EnvironmentServiceDep,
    db: DbSessionDep,
) -> MessageResponse:
    """
    删除环境配置

    - **project_identifier**: 项目标识符，如 PR-1234
    - **env_id**: 环境配置 ID
    """
    await service.delete_environment(project_identifier, env_id)
    await db.commit()
    return MessageResponse(success=True, message="环境配置已删除")
