"""
配置服务

处理配置相关的业务逻辑
参考: https://www.browserstack.com/docs/test-management/api-reference/configurations
"""

from typing import Optional
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0RSM013PT06MTY2NmRmYjk=

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuration import Configuration
from app.repositories.configuration_repo import ConfigurationRepository
from app.schemas.configuration import (
    ConfigurationCreate,
    ConfigurationInfo,
    ConfigurationDetailInfo,
    ConfigurationCreateResponse,
)
from app.utils.exceptions import NotFoundException, ConflictException


class ConfigurationService:
    """配置服务类"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ConfigurationRepository(session)
    
    def _to_info(self, config: Configuration) -> ConfigurationInfo:
        """转换为配置信息"""
        return ConfigurationInfo(
            id=config.id,
            name=config.name,
            os=config.os,
            os_version=config.os_version,
            device=config.device,
            browser=config.browser,
            browser_version=config.browser_version,
            is_system=config.is_system,
        )
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0RSM013PT06MTY2NmRmYjk=
    
    def _to_detail_info(self, config: Configuration) -> ConfigurationDetailInfo:
        """转换为配置详细信息"""
        return ConfigurationDetailInfo(
            id=config.id,
            name=config.name,
            os=config.os,
            os_version=config.os_version,
            device=config.device,
            browser=config.browser,
            browser_version=config.browser_version,
            is_system=config.is_system,
            description=config.description,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )
    
    async def get_list(
        self,
        is_system: Optional[bool] = None,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[ConfigurationInfo], int]:
        """
        获取配置列表
        
        Args:
            is_system: 可选过滤，True 为系统配置，False 为自定义配置
            offset: 偏移量
            limit: 限制数量
            
        Returns:
            Tuple[list[ConfigurationInfo], int]: 配置列表和总数
        """
        configs, total = await self.repo.get_list(
            is_system=is_system,
            offset=offset,
            limit=limit,
        )
        
        return [self._to_info(c) for c in configs], total
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0RSM013PT06MTY2NmRmYjk=
    
    async def get_by_id(self, config_id: int) -> ConfigurationDetailInfo:
        """
        根据 ID 获取配置详情
        
        Args:
            config_id: 配置 ID
            
        Returns:
            ConfigurationDetailInfo: 配置详细信息
            
        Raises:
            NotFoundException: 配置不存在
        """
        config = await self.repo.get_by_id(config_id)
        if not config:
            raise NotFoundException(resource_type="配置", resource_id=str(config_id))
        
        return self._to_detail_info(config)
    
    async def create(self, data: ConfigurationCreate) -> ConfigurationCreateResponse:
        """
        创建自定义配置
        
        Args:
            data: 创建配置请求
            
        Returns:
            ConfigurationCreateResponse: 创建响应
            
        Raises:
            ConflictException: 配置名称已存在
        """
        # 检查名称是否已存在
        if await self.repo.exists_by_name(data.name):
            raise ConflictException(f"配置名称 '{data.name}' 已存在")
        
        # 创建配置
        config = Configuration(
            name=data.name,
            os=data.os,
            os_version=data.os_version,
            device=data.device,
            browser=data.browser,
            browser_version=data.browser_version,
            description=data.description,
            is_system=False,  # 用户创建的都是自定义配置
        )
        config = await self.repo.create(config)
        
        return ConfigurationCreateResponse(
            success=True,
            id=config.id,
            name=config.name,
        )
    
    async def delete(self, config_id: int) -> None:
        """
        删除自定义配置
        
        Args:
            config_id: 配置 ID
            
        Raises:
            NotFoundException: 配置不存在
            ConflictException: 不能删除系统配置
        """
        config = await self.repo.get_by_id(config_id)
        if not config:
            raise NotFoundException(resource_type="配置", resource_id=str(config_id))
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0RSM013PT06MTY2NmRmYjk=
        
        if config.is_system:
            raise ConflictException("不能删除系统定义的配置")
        
        await self.repo.delete(config)

