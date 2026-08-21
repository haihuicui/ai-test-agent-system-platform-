"""
API 业务语义标注仓储

提供标注的查询、自然键去重 upsert、过期失效等操作。
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_annotation import APIAnnotation
from app.repositories.base import BaseRepository


class APIAnnotationRepository(BaseRepository[APIAnnotation]):
    """API 业务语义标注仓储"""

    def __init__(self, session: AsyncSession):
        super().__init__(APIAnnotation, session)

    async def list_for_endpoint(
        self,
        project_id: UUID,
        endpoint_id: Optional[UUID] = None,
        annotation_type: Optional[str] = None,
        include_disabled: bool = False,
    ) -> list[APIAnnotation]:
        """
        查询项目或端点的标注列表

        Args:
            project_id: 项目 ID
            endpoint_id: 端点 ID（为 None 时查项目级）
            annotation_type: 标注类型过滤
            include_disabled: 是否包含已失效标注

        Returns:
            标注列表
        """
        query = select(APIAnnotation).where(
            APIAnnotation.project_id == project_id
        )

        if endpoint_id is not None:
            query = query.where(APIAnnotation.endpoint_id == endpoint_id)
        else:
            query = query.where(APIAnnotation.endpoint_id.is_(None))

        if annotation_type:
            query = query.where(APIAnnotation.annotation_type == annotation_type)

        if not include_disabled:
            query = query.where(APIAnnotation.enabled.is_(True))

        query = query.order_by(
            APIAnnotation.annotation_type,
            APIAnnotation.field_path,
            APIAnnotation.confidence.desc(),
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_for_project(
        self,
        project_id: UUID,
        annotation_type: Optional[str] = None,
        include_disabled: bool = False,
    ) -> list[APIAnnotation]:
        """
        查询项目下所有标注（含端点级和项目级）

        Args:
            project_id: 项目 ID
            annotation_type: 标注类型过滤
            include_disabled: 是否包含已失效标注

        Returns:
            标注列表
        """
        query = select(APIAnnotation).where(
            APIAnnotation.project_id == project_id
        )

        if annotation_type:
            query = query.where(APIAnnotation.annotation_type == annotation_type)

        if not include_disabled:
            query = query.where(APIAnnotation.enabled.is_(True))

        query = query.order_by(
            APIAnnotation.endpoint_id,
            APIAnnotation.annotation_type,
            APIAnnotation.field_path,
            APIAnnotation.confidence.desc(),
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def upsert_by_natural_key(
        self,
        project_id: UUID,
        annotation_type: str,
        source: str,
        endpoint_id: Optional[UUID] = None,
        http_status: Optional[int] = None,
        business_code: Optional[str] = None,
        field_path: Optional[str] = None,
        condition: Optional[str] = None,
        message_pattern: Optional[str] = None,
        expected_value: Optional[dict[str, Any]] = None,
        source_metadata: Optional[dict[str, Any]] = None,
        confidence_delta: float = 0.1,
        max_confidence: float = 0.95,
    ) -> APIAnnotation:
        """
        按自然键去重 upsert。

        - 首次插入：confidence = 0.5，hit_count = 1
        - 非 manual 来源重复命中：hit_count += 1，confidence 提升（不超过 max_confidence）
        - manual 来源不覆盖已有记录，也不被覆盖

        Args:
            ... 标注字段
            confidence_delta: 每次重复命中提升的置信度
            max_confidence: 自动提升置信度上限

        Returns:
            插入或更新后的标注
        """
        # manual 来源走显式更新，不参与自动 upsert
        if source == "manual":
            raise ValueError("manual 来源请使用 create/update，不要走自动 upsert")

        natural_key = {
            "endpoint_id": endpoint_id,
            "annotation_type": annotation_type,
            "http_status": http_status,
            "business_code": business_code,
            "field_path": field_path,
            "condition": condition,
        }

        # 先尝试查询已有记录
        existing_stmt = select(APIAnnotation).where(
            and_(
                APIAnnotation.endpoint_id == endpoint_id,
                APIAnnotation.annotation_type == annotation_type,
                APIAnnotation.http_status == http_status,
                APIAnnotation.business_code == business_code,
                APIAnnotation.field_path == field_path,
                APIAnnotation.condition == condition,
                APIAnnotation.source != "manual",
            )
        )
        existing_result = await self.session.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if existing:
            new_hit_count = existing.hit_count + 1
            new_confidence = min(
                existing.confidence + confidence_delta,
                max_confidence,
            )
            update_values = {
                "hit_count": new_hit_count,
                "confidence": new_confidence,
                "last_seen_at": now,
                "enabled": True,
            }
            if message_pattern:
                update_values["message_pattern"] = message_pattern
            if expected_value is not None:
                update_values["expected_value"] = expected_value
            if source_metadata is not None:
                # 合并元数据，保留最近一条的关键字段
                merged_meta = existing.source_metadata or {}
                merged_meta.update(source_metadata)
                update_values["source_metadata"] = merged_meta

            for key, value in update_values.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        # 首次插入
        annotation = APIAnnotation(
            project_id=project_id,
            endpoint_id=endpoint_id,
            annotation_type=annotation_type,
            source=source,
            http_status=http_status,
            business_code=business_code,
            field_path=field_path,
            condition=condition,
            message_pattern=message_pattern,
            expected_value=expected_value,
            confidence=0.5,
            hit_count=1,
            enabled=True,
            first_seen_at=now,
            last_seen_at=now,
            source_metadata=source_metadata,
        )
        self.session.add(annotation)
        await self.session.flush()
        await self.session.refresh(annotation)
        return annotation

    async def disable_stale(
        self,
        project_id: UUID,
        older_than_days: int = 90,
        max_confidence: float = 0.8,
    ) -> int:
        """
        将超过指定天数未命中且置信度较低的标注标记为失效

        Args:
            project_id: 项目 ID
            older_than_days: 未命中天数阈值
            max_confidence: 置信度上限（低于此值才失效）

        Returns:
            失效的记录数
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

        stmt = (
            select(APIAnnotation)
            .where(
                and_(
                    APIAnnotation.project_id == project_id,
                    APIAnnotation.last_seen_at < cutoff,
                    APIAnnotation.confidence < max_confidence,
                    APIAnnotation.enabled.is_(True),
                )
            )
        )
        result = await self.session.execute(stmt)
        stale_items = result.scalars().all()

        count = 0
        for item in stale_items:
            item.enabled = False
            count += 1

        await self.session.flush()
        return count

    async def count_by_project(
        self,
        project_id: UUID,
        annotation_type: Optional[str] = None,
    ) -> int:
        """统计项目下有效标注数量"""
        stmt = select(func.count()).where(
            and_(
                APIAnnotation.project_id == project_id,
                APIAnnotation.enabled.is_(True),
            )
        )
        if annotation_type:
            stmt = stmt.where(APIAnnotation.annotation_type == annotation_type)

        result = await self.session.execute(stmt)
        return result.scalar_one()
