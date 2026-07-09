"""
项目环境配置服务

处理项目环境配置的 CRUD、执行时环境变量组装。
注意：按业务要求，所有认证凭据（auth_secret）均以明文存储。
"""

import json
import logging
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_endpoint import APIEndpoint
from app.models.environment import AuthType, ProjectEnvironment
from app.repositories.environment_repo import EnvironmentRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.environment import EnvironmentCreate, EnvironmentUpdate, EnvironmentInfo
from app.utils.auth_resolver import (
    DynamicTokenError,
    build_auth_headers,
    resolve_auth_credentials,
    resolve_dynamic_bearer_token,
)
from app.utils.exceptions import NotFoundException, ConflictException, BadRequestException

logger = logging.getLogger(__name__)


class EnvironmentService:
    """
    项目环境配置服务类
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = EnvironmentRepository(session)
        self.project_repo = ProjectRepository(session)

    async def _get_project_id(self, project_identifier: str | UUID) -> UUID:
        """
        根据项目标识符或 ID 获取项目 ID
        """
        try:
            project_id = UUID(str(project_identifier))
            # 按 ID 查询
            project = await self.project_repo.get_by_id(project_id)
        except ValueError:
            # 按标识符查询
            project = await self.project_repo.get_by_identifier(str(project_identifier))

        if not project:
            raise NotFoundException(resource_type="项目", resource_id=str(project_identifier))
        return project.id

    async def list_environments(
        self,
        project_identifier: str
    ) -> list[EnvironmentInfo]:
        """
        获取项目的所有环境配置
        """
        project_id = await self._get_project_id(project_identifier)
        envs = await self.repo.list_by_project(project_id)
        return [self._to_info(env) for env in envs]

    async def get_environment(
        self,
        project_identifier: str,
        env_id: UUID
    ) -> EnvironmentInfo:
        """
        获取环境配置详情
        """
        project_id = await self._get_project_id(project_identifier)
        env = await self.repo.get_by_id(env_id)
        if not env or env.project_id != project_id:
            raise NotFoundException(resource_type="环境", resource_id=str(env_id))
        return self._to_info(env)

    async def create_environment(
        self,
        project_identifier: str,
        data: EnvironmentCreate
    ) -> EnvironmentInfo:
        """
        创建环境配置
        """
        project_id = await self._get_project_id(project_identifier)

        # 检查同名环境
        existing = await self.repo.get_by_project_and_name(project_id, data.name)
        if existing:
            raise ConflictException(f"环境名称 '{data.name}' 已存在")

        # 如果设置为默认，先取消其他默认环境
        if data.is_default:
            await self.repo.unset_default_for_project(project_id)

        env = await self.repo.create(
            project_id=project_id,
            name=data.name,
            is_default=data.is_default,
            base_url=str(data.base_url),
            auth_type=data.auth_type,
            auth_secret=data.auth_secret,
            auth_config=data.auth_config or {},
            timeout_ms=data.timeout_ms,
        )
        return self._to_info(env)

    async def update_environment(
        self,
        project_identifier: str,
        env_id: UUID,
        data: EnvironmentUpdate
    ) -> EnvironmentInfo:
        """
        更新环境配置
        """
        project_id = await self._get_project_id(project_identifier)
        env = await self.repo.get_by_id(env_id)
        if not env or env.project_id != project_id:
            raise NotFoundException(resource_type="环境", resource_id=str(env_id))

        update_data: dict[str, Any] = {}

        if data.name is not None and data.name != env.name:
            existing = await self.repo.get_by_project_and_name(project_id, data.name)
            if existing and existing.id != env.id:
                raise ConflictException(f"环境名称 '{data.name}' 已存在")
            update_data["name"] = data.name

        if data.base_url is not None:
            update_data["base_url"] = str(data.base_url)

        if data.auth_type is not None:
            update_data["auth_type"] = data.auth_type

        if data.auth_secret is not None:
            # 空字符串表示清除凭据
            if data.auth_secret == "":
                env.auth_secret = None
            else:
                update_data["auth_secret"] = data.auth_secret

        if data.auth_config is not None:
            update_data["auth_config"] = data.auth_config

        if data.timeout_ms is not None:
            update_data["timeout_ms"] = data.timeout_ms

        # 默认环境切换
        if data.is_default is not None:
            if data.is_default and not env.is_default:
                await self.repo.unset_default_for_project(project_id)
            update_data["is_default"] = data.is_default

        if update_data:
            env = await self.repo.update(env, **update_data)
            await self.session.flush()
            await self.session.refresh(env)

        return self._to_info(env)

    async def delete_environment(
        self,
        project_identifier: str,
        env_id: UUID
    ) -> None:
        """
        删除环境配置
        """
        project_id = await self._get_project_id(project_identifier)
        env = await self.repo.get_by_id(env_id)
        if not env or env.project_id != project_id:
            raise NotFoundException(resource_type="环境", resource_id=str(env_id))
        await self.repo.delete(env)

    async def get_effective_base_url(
        self,
        project_identifier: str,
        execution_config: Optional[dict[str, Any]] = None,
        endpoint_id: Optional[UUID | str] = None,
        env_id: Optional[UUID | str] = None,
    ) -> str:
        """
        获取有效的 base_url，按以下优先级：
        1. execution_config.base_url
        2. 指定 env_id 的 ProjectEnvironment.base_url
        3. 项目默认 ProjectEnvironment.base_url
        4. APIEndpoint.custom_config["servers"][0]["url"]
        """
        execution_config = execution_config or {}

        # 1. 用户显式传入
        if execution_config.get("base_url"):
            return str(execution_config["base_url"])

        project_id = await self._get_project_id(project_identifier)

        # 2. 指定环境
        if env_id:
            env = await self.repo.get_by_id(UUID(str(env_id)))
            if env and env.project_id == project_id:
                return env.base_url

        # 3. 项目默认环境
        default_env = await self.repo.get_default_by_project(project_id)
        if default_env:
            return default_env.base_url

        # 4. OpenAPI servers
        if endpoint_id:
            result = await self.session.execute(
                select(APIEndpoint).where(APIEndpoint.id == UUID(str(endpoint_id)))
            )
            endpoint = result.scalar_one_or_none()
            if endpoint and endpoint.custom_config:
                servers = endpoint.custom_config.get("servers", [])
                if servers and servers[0].get("url"):
                    return servers[0]["url"]

        raise BadRequestException(
            "未配置 API_BASE_URL。请在 execution_config 中传入 base_url，"
            "或前往项目设置 > 环境管理配置默认环境。"
        )

    async def _resolve_dynamic_bearer_token(
        self,
        env: ProjectEnvironment,
        *,
        force_refresh: bool = False,
    ) -> str:
        """
        解析动态 Bearer Token（委托到 auth_resolver 工具模块）。
        """
        return await resolve_dynamic_bearer_token(env, force_refresh=force_refresh)

    async def test_dynamic_token_connection(
        self,
        project_identifier: str,
        env_id: UUID,
    ) -> dict[str, Any]:
        """
        测试动态 token 连通性。

        强制刷新 token，返回 token 长度、缓存策略等信息，不返回 token 本身。

        Args:
            project_identifier: 项目标识符
            env_id: 环境 ID

        Returns:
            连通性结果
        """
        project_id = await self._get_project_id(project_identifier)
        env = await self.repo.get_by_id(env_id)
        if not env or env.project_id != project_id:
            raise NotFoundException(resource_type="环境", resource_id=str(env_id))

        if env.auth_type != AuthType.DYNAMIC_BEARER.value:
            raise BadRequestException("该环境不是动态 Bearer 认证类型，无需测试 token 连通性")

        try:
            token = await self._resolve_dynamic_bearer_token(env, force_refresh=True)
            cfg = env.auth_config or {}
            return {
                "success": True,
                "token_length": len(token),
                "token_preview": f"{token[:8]}..." if len(token) > 12 else "***",
                "cache_ttl_seconds": cfg.get("token_ttl_seconds") or 0,
            }
        except (BadRequestException, DynamicTokenError) as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def get_execution_env_vars(
        self,
        project_identifier: str,
        execution_config: Optional[dict[str, Any]] = None,
        endpoint_id: Optional[UUID | str] = None,
        env_id: Optional[UUID | str] = None,
    ) -> dict[str, str]:
        """
        组装执行测试时需要注入的环境变量
        """
        execution_config = execution_config or {}
        env_vars: dict[str, str] = {}

        # 1. 从项目环境读取配置
        project_id = await self._get_project_id(project_identifier)
        env: Optional[ProjectEnvironment] = None

        if env_id:
            env = await self.repo.get_by_id(UUID(str(env_id)))
            if env and env.project_id != project_id:
                env = None

        if not env:
            env = await self.repo.get_default_by_project(project_id)

        # 2. base_url（execution_config 优先级最高）
        base_url = execution_config.get("base_url")
        if not base_url and env:
            base_url = env.base_url
        if not base_url and endpoint_id:
            result = await self.session.execute(
                select(APIEndpoint).where(APIEndpoint.id == UUID(str(endpoint_id)))
            )
            endpoint = result.scalar_one_or_none()
            if endpoint and endpoint.custom_config:
                servers = endpoint.custom_config.get("servers", [])
                if servers and servers[0].get("url"):
                    base_url = servers[0]["url"]
        if base_url:
            env_vars["API_BASE_URL"] = str(base_url)

        # 3. 认证信息
        if env:
            env_vars["AUTH_TYPE"] = env.auth_type
            env_vars["AUTH_CONFIG_JSON"] = json.dumps(env.auth_config or {}, ensure_ascii=False)
            if env.auth_secret:
                env_vars["AUTH_SECRET"] = env.auth_secret

            # 检查 execution_config 是否已显式覆盖 token
            extra_env = execution_config.get("env") or execution_config.get("environment_variables") or {}
            explicit_token = extra_env.get("AUTH_TOKEN") or extra_env.get("Authorization")

            if env.auth_type == AuthType.DYNAMIC_BEARER.value and not explicit_token:
                token = await resolve_dynamic_bearer_token(env)
                env_vars["AUTH_TOKEN"] = token
                env_vars["Authorization"] = f"Bearer {token}"

                # 如果 token 缓存时间很短，给出警告
                cfg = env.auth_config or {}
                token_ttl = cfg.get("token_ttl_seconds") or 0
                execution_timeout = execution_config.get("timeout")
                if token_ttl > 0 and execution_timeout and token_ttl < execution_timeout:
                    logger.warning(
                        "[EnvironmentService] 动态 token 缓存 TTL（%ss）小于执行超时（%ss），"
                        "子进程内可能过期: env=%s",
                        token_ttl,
                        execution_timeout,
                        env.id,
                    )
            else:
                # 静态认证类型或用户显式覆盖 token
                if explicit_token:
                    logger.debug(
                        "[EnvironmentService] execution_config 已提供 token，跳过动态获取: env=%s",
                        env.id,
                    )
                credentials = build_auth_headers(
                    env.auth_type,
                    env.auth_secret,
                    env.auth_config,
                )
                for key, value in credentials.items():
                    env_vars[key] = value
                    # Bearer / OAuth2 时同时生成 AUTH_TOKEN 便于脚本读取
                    if key == "Authorization" and value.startswith("Bearer "):
                        env_vars["AUTH_TOKEN"] = value[7:]

                if env.auth_type == AuthType.OAUTH2.value and env.auth_secret:
                    env_vars["OAUTH2_TOKEN"] = env.auth_secret
                    env_vars["AUTH_TOKEN"] = env.auth_secret

        # 4. execution_config.env 优先级最高，覆盖以上
        extra_env = execution_config.get("env") or execution_config.get("environment_variables") or {}
        for key, value in extra_env.items():
            env_vars[key] = str(value)

        return env_vars

    def _to_info(self, env: ProjectEnvironment) -> EnvironmentInfo:
        """
        将 ORM 模型转换为 API 返回的 DTO。
        按业务要求，auth_secret 以明文返回。
        """
        return EnvironmentInfo(
            id=env.id,
            name=env.name,
            is_default=env.is_default,
            base_url=env.base_url,
            auth_type=env.auth_type,
            auth_config=env.auth_config or {},
            timeout_ms=env.timeout_ms,
            has_auth_secret=bool(env.auth_secret),
            auth_secret=env.auth_secret,
            created_at=env.created_at,
            updated_at=env.updated_at,
        )
