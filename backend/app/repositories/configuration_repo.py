"""
配置仓储

提供配置数据访问层
参考: https://www.browserstack.com/docs/test-management/api-reference/configurations
"""

from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuration import Configuration


class ConfigurationRepository:
    """配置数据仓储"""
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0hCS1NBPT06ZjQwNDYxYTc=
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, config_id: int) -> Optional[Configuration]:
        """根据 ID 获取配置"""
        stmt = select(Configuration).where(Configuration.id == config_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_name(self, name: str) -> Optional[Configuration]:
        """根据名称获取配置"""
        stmt = select(Configuration).where(Configuration.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_list(
        self,
        is_system: Optional[bool] = None,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[Configuration], int]:
        """获取配置列表"""
        conditions = []
        
        if is_system is not None:
            conditions.append(Configuration.is_system == is_system)
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0hCS1NBPT06ZjQwNDYxYTc=
        
        # 构建查询
        base_query = select(Configuration)
        count_query = select(func.count()).select_from(Configuration)
        
        if conditions:
            base_query = base_query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        # 排序：系统配置优先，然后按名称排序
        stmt = (
            base_query
            .order_by(Configuration.is_system.desc(), Configuration.name)
            .offset(offset)
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        count_result = await self.session.execute(count_query)
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0hCS1NBPT06ZjQwNDYxYTc=
        
        return list(result.scalars().all()), count_result.scalar() or 0
    
    async def get_all(self) -> list[Configuration]:
        """获取所有配置（不分页）"""
        stmt = select(Configuration).order_by(
            Configuration.is_system.desc(),
            Configuration.name
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def create(self, configuration: Configuration) -> Configuration:
        """创建配置"""
        self.session.add(configuration)
        await self.session.flush()
        await self.session.refresh(configuration)
        return configuration
    
    async def update(self, configuration: Configuration) -> Configuration:
        """更新配置"""
        await self.session.flush()
        await self.session.refresh(configuration)
        return configuration
    
    async def delete(self, configuration: Configuration) -> None:
        """删除配置"""
        await self.session.delete(configuration)
        await self.session.flush()
    
    async def exists_by_name(self, name: str, exclude_id: Optional[int] = None) -> bool:
        """检查配置名称是否存在"""
        conditions = [Configuration.name == name]
        if exclude_id:
            conditions.append(Configuration.id != exclude_id)
        
        stmt = select(func.count()).select_from(Configuration).where(and_(*conditions))
        result = await self.session.execute(stmt)
        return (result.scalar() or 0) > 0
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0hCS1NBPT06ZjQwNDYxYTc=
    
    async def get_by_ids(self, config_ids: list[int]) -> list[Configuration]:
        """根据 ID 列表获取配置"""
        stmt = select(Configuration).where(Configuration.id.in_(config_ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

