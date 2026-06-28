"""
附件仓储

提供附件数据访问层
参考: https://www.browserstack.com/docs/test-management/api-reference/attachments
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZGtaa1N3PT06MzNhYWQzNDg=

from app.models.attachment import Attachment, AttachmentEntityType


class AttachmentRepository:
    """附件数据仓储"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, attachment_id: UUID) -> Optional[Attachment]:
        """根据 ID 获取附件"""
        stmt = select(Attachment).where(Attachment.id == attachment_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_entity(
        self,
        entity_type: AttachmentEntityType,
        entity_id: UUID,
        step_index: Optional[int] = None,
    ) -> list[Attachment]:
        """获取实体关联的附件列表"""
        conditions = [
            Attachment.entity_type == entity_type,
            Attachment.entity_id == entity_id,
        ]
        if step_index is not None:
            conditions.append(Attachment.step_index == step_index)
        
        stmt = (
            select(Attachment)
            .where(and_(*conditions))
            .order_by(Attachment.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_step_attachments(
        self,
        entity_type: AttachmentEntityType,
        entity_id: UUID,
    ) -> dict[int, list[Attachment]]:
        """获取实体所有步骤的附件，按步骤索引分组"""
        conditions = [
            Attachment.entity_type == entity_type,
            Attachment.entity_id == entity_id,
            Attachment.step_index.isnot(None),
        ]
        
        stmt = (
            select(Attachment)
            .where(and_(*conditions))
            .order_by(Attachment.step_index, Attachment.created_at.desc())
        )
        result = await self.session.execute(stmt)
        attachments = result.scalars().all()
        
        # 按 step_index 分组
        grouped: dict[int, list[Attachment]] = {}
        for att in attachments:
            if att.step_index not in grouped:
                grouped[att.step_index] = []
            grouped[att.step_index].append(att)
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZGtaa1N3PT06MzNhYWQzNDg=
        
        return grouped
    
    async def get_by_project(
        self,
        project_id: UUID,
        entity_type: Optional[AttachmentEntityType] = None,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[Attachment], int]:
        """获取项目的附件列表"""
        conditions = [Attachment.project_id == project_id]
        
        if entity_type:
            conditions.append(Attachment.entity_type == entity_type)
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZGtaa1N3PT06MzNhYWQzNDg=
        
        stmt = (
            select(Attachment)
            .where(and_(*conditions))
            .order_by(Attachment.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        
        count_stmt = (
            select(func.count())
            .select_from(Attachment)
            .where(and_(*conditions))
        )
        
        result = await self.session.execute(stmt)
        count_result = await self.session.execute(count_stmt)
        
        return list(result.scalars().all()), count_result.scalar() or 0
    
    async def create(self, attachment: Attachment) -> Attachment:
        """创建附件记录"""
        self.session.add(attachment)
        await self.session.flush()
        return attachment
    
    async def delete(self, attachment: Attachment) -> None:
        """删除附件记录"""
        await self.session.delete(attachment)
        await self.session.flush()
    
    async def delete_by_ids(self, attachment_ids: list[UUID]) -> int:
        """批量删除附件记录"""
        stmt = delete(Attachment).where(Attachment.id.in_(attachment_ids))
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
    
    async def delete_by_entity(
        self,
        entity_type: AttachmentEntityType,
        entity_id: UUID,
    ) -> int:
        """删除实体关联的所有附件"""
        stmt = delete(Attachment).where(
            and_(
                Attachment.entity_type == entity_type,
                Attachment.entity_id == entity_id,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
    
    async def get_by_ids(self, attachment_ids: list[UUID]) -> list[Attachment]:
        """根据 ID 列表获取附件"""
        stmt = select(Attachment).where(Attachment.id.in_(attachment_ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZGtaa1N3PT06MzNhYWQzNDg=

