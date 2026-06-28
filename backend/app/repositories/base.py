"""
基础仓储类

提供通用的 CRUD 操作
"""

from typing import Generic, Optional, Type, TypeVar
from uuid import UUID
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFhkNmVnPT06OGY3Y2IyMzM=

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base


ModelType = TypeVar("ModelType", bound=Base)

# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFhkNmVnPT06OGY3Y2IyMzM=

class BaseRepository(Generic[ModelType]):
    """
    基础仓储类

    提供通用的数据库 CRUD 操作
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """
        初始化仓储

        Args:
            model: SQLAlchemy 模型类
            session: 数据库会话
        """
        self.model = model
        self.session = session

    async def _acquire_xact_lock(self, lock_key: str) -> None:
        """
        在当前事务内获取一个 PostgreSQL advisory 锁，提交/回滚时自动释放。

        用于在生成"下一个 identifier"这类 read-modify-write 流程中，串行化
        同一 project + 同一资源类型的并发写入，避免唯一约束冲突。

        Args:
            lock_key: 锁的稳定字符串键（如 f"wsf_identifier:{project_id}"）。
                      不同 key 互不影响。
        """
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
            {"k": lock_key},
        )
    
    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        """
        根据 ID 获取记录
        
        Args:
            id: 记录 ID
            
        Returns:
            Optional[ModelType]: 记录实例或 None
        """
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFhkNmVnPT06OGY3Y2IyMzM=
    
    async def get_all(
        self,
        offset: int = 0,
        limit: int = 30,
    ) -> list[ModelType]:
        """
        获取所有记录（分页）
        
        Args:
            offset: 偏移量
            limit: 限制数量
            
        Returns:
            list[ModelType]: 记录列表
        """
        result = await self.session.execute(
            select(self.model)
            .offset(offset)
            .limit(limit)
            .order_by(self.model.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def count(self) -> int:
        """
        获取记录总数
        
        Returns:
            int: 记录总数
        """
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar_one()
    
    async def create(self, **kwargs) -> ModelType:
        """
        创建记录
        
        Args:
            **kwargs: 记录属性
            
        Returns:
            ModelType: 创建的记录
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance
    
    async def update(
        self, instance: ModelType, **kwargs
    ) -> ModelType:
        """
        更新记录
        
        Args:
            instance: 要更新的记录
            **kwargs: 要更新的属性
            
        Returns:
            ModelType: 更新后的记录
        """
        for key, value in kwargs.items():
            if hasattr(instance, key) and value is not None:
                setattr(instance, key, value)
        
        await self.session.flush()
        await self.session.refresh(instance)
        return instance
    
    async def delete(self, instance: ModelType) -> None:
        """
        删除记录
        
        Args:
            instance: 要删除的记录
        """
        await self.session.delete(instance)
        await self.session.flush()
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZFhkNmVnPT06OGY3Y2IyMzM=
    
    async def exists(self, id: UUID) -> bool:
        """
        检查记录是否存在
        
        Args:
            id: 记录 ID
            
        Returns:
            bool: 是否存在
        """
        result = await self.session.execute(
            select(func.count()).select_from(self.model).where(self.model.id == id)
        )
        return result.scalar_one() > 0

