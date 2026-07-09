"""
API Agent 环境配置工具

提供查询项目环境配置的能力（不暴露敏感凭据）。
"""

import json
from uuid import UUID

from langchain_core.tools import tool

from app.config.database import get_db
from app.services.environment_service import EnvironmentService
from app.utils.exceptions import NotFoundException


@tool
async def get_project_environments(project_identifier: str) -> str:
    """
    获取项目的所有环境配置（不包含敏感凭据）

    Args:
        project_identifier: 项目标识符（如 "PR-1"）

    Returns:
        JSON 格式的环境列表，包含：
        - id: 环境 ID
        - name: 环境名称
        - base_url: API Base URL
        - auth_type: 认证类型（none/bearer/dynamic_bearer/api_key/oauth2）
        - auth_config: 非敏感认证配置
        - timeout_ms: 超时时间
        - is_default: 是否为默认环境
        - has_auth_secret: 是否已配置静态敏感凭据

    注意：
        - dynamic_bearer 类型的环境没有 auth_secret，token 通过 auth_config.token_url 动态获取
        - 判断 dynamic_bearer 是否已配置，应检查 auth_config.token_url 是否存在

    Example:
        >>> result = await get_project_environments(project_identifier="PR-1")
    """
    async for db in get_db():
        try:
            service = EnvironmentService(db)
            envs = await service.list_environments(project_identifier)
            return json.dumps({
                "success": True,
                "total": len(envs),
                "environments": [env.model_dump(mode="json") for env in envs]
            }, ensure_ascii=False, indent=2)
        except NotFoundException as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"获取项目环境配置失败: {str(e)}"
            }, ensure_ascii=False, indent=2)


@tool
async def get_environment_details(project_identifier: str, env_id: str) -> str:
    """
    获取单个环境配置的详细信息（不包含敏感凭据）

    Args:
        project_identifier: 项目标识符（如 "PR-1"）
        env_id: 环境 ID

    Returns:
        JSON 格式的环境详情。
        对于 dynamic_bearer 类型，重点关注 auth_config.token_url / token_body / token_path。

    Example:
        >>> result = await get_environment_details(
        ...     project_identifier="PR-1",
        ...     env_id="550e8400-e29b-41d4-a716-446655440000"
        ... )
    """
    async for db in get_db():
        try:
            service = EnvironmentService(db)
            env = await service.get_environment(project_identifier, UUID(env_id))
            return json.dumps({
                "success": True,
                "environment": env.model_dump(mode="json")
            }, ensure_ascii=False, indent=2)
        except NotFoundException as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"获取环境详情失败: {str(e)}"
            }, ensure_ascii=False, indent=2)
