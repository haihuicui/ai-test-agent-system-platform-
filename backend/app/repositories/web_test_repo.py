"""
Web 测试仓储

处理 Web 测试相关的数据库操作
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.repositories.base import BaseRepository
from app.models.web_test import WebTest, WebTestRun, WebTestResult
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VlVaTlVBPT06ZjJmYzY2OGI=


class WebTestRepository(BaseRepository[WebTest]):
    """Web 测试仓储类"""

    def __init__(self, session: AsyncSession):
        super().__init__(WebTest, session)

    async def get_by_identifier(self, identifier: str) -> Optional[WebTest]:
        """根据标识符获取 Web 测试"""
        result = await self.session.execute(
            select(WebTest)
            .options(selectinload(WebTest.test_runs))
            .where(WebTest.identifier == identifier)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(self, id: UUID) -> Optional[WebTest]:
        """根据 ID 获取 Web 测试（包含关联数据）"""
        result = await self.session.execute(
            select(WebTest)
            .options(selectinload(WebTest.test_case))
            .options(selectinload(WebTest.project))
            .options(selectinload(WebTest.test_runs))
            .where(WebTest.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_project(
        self,
        project_id: UUID,
        offset: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        script_format: Optional[str] = None,
    ) -> tuple[list[WebTest], int]:
        """获取项目下的 Web 测试列表"""
        query = select(WebTest).where(WebTest.project_id == project_id)

        if search:
            query = query.where(
                (WebTest.name.ilike(f"%{search}%")) |
                (WebTest.identifier.ilike(f"%{search}%")) |
                (WebTest.description.ilike(f"%{search}%"))
            )

        if script_format:
            query = query.where(WebTest.script_format == script_format)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(WebTest.created_at.desc())
        query = query.offset(offset).limit(limit)
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VlVaTlVBPT06ZjJmYzY2OGI=

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_by_sub_function(
        self,
        sub_function_id: UUID,
    ) -> Optional[WebTest]:
        """根据子功能 ID 获取 Web 测试（取最新一条）"""
        result = await self.session.execute(
            select(WebTest)
            .where(WebTest.sub_function_id == sub_function_id)
            .order_by(WebTest.created_at.desc())
        )
        return result.scalar_one_or_none()


class WebTestRunRepository(BaseRepository[WebTestRun]):
    """Web 测试运行仓储类"""

    def __init__(self, session: AsyncSession):
        super().__init__(WebTestRun, session)

    async def get_by_web_test(
        self,
        web_test_id: UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[WebTestRun], int]:
        """获取 Web 测试的运行列表"""
        query = select(WebTestRun).where(WebTestRun.web_test_id == web_test_id)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(WebTestRun.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VlVaTlVBPT06ZjJmYzY2OGI=


class WebTestResultRepository(BaseRepository[WebTestResult]):
    """Web 测试结果仓储类"""

    def __init__(self, session: AsyncSession):
        super().__init__(WebTestResult, session)

    async def get_by_test_run(
        self,
        test_run_id: UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[WebTestResult], int]:
        """获取测试运行的结果列表"""
        query = select(WebTestResult).where(WebTestResult.test_run_id == test_run_id)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(WebTestResult.created_at.asc())
        query = query.offset(offset).limit(limit)
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VlVaTlVBPT06ZjJmYzY2OGI=

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total
