"""
API 测试仓储

处理 API 测试相关的数据库操作
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Integer, and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.repositories.base import BaseRepository
from app.models.api_test import APITest, APITestRun, APITestResult


class APITestRepository(BaseRepository[APITest]):
    """API 测试仓储类"""

    def __init__(self, session: AsyncSession):
        super().__init__(APITest, session)
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1ZadFl3PT06MWFkZDU3NjI=

    async def get_by_identifier(self, identifier: str) -> Optional[APITest]:
        """
        根据标识符获取 API 测试

        Args:
            identifier: API 测试标识符 (AT-xxx)

        Returns:
            Optional[APITest]: API 测试实例或 None
        """
        result = await self.session.execute(
            select(APITest)
            .options(selectinload(APITest.test_runs))
            .where(APITest.identifier == identifier)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(self, id: UUID) -> Optional[APITest]:
        """根据 ID 获取 API 测试（包含关联数据）"""
        result = await self.session.execute(
            select(APITest)
            .options(selectinload(APITest.test_case))
            .options(selectinload(APITest.project))
            .options(selectinload(APITest.test_runs))
            .where(APITest.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_project(
        self,
        project_id: UUID,
        offset: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        script_format: Optional[str] = None,
    ) -> tuple[list[APITest], int]:
        """
        获取项目下的 API 测试列表

        Args:
            project_id: 项目 ID
            offset: 偏移量
            limit: 限制数量
            search: 搜索关键词
            script_format: 脚本格式过滤

        Returns:
            tuple[list[APITest], int]: API 测试列表和总数
        """
        query = select(APITest).where(APITest.project_id == project_id)

        # 搜索过滤
        if search:
            query = query.where(
                (APITest.name.ilike(f"%{search}%")) |
                (APITest.identifier.ilike(f"%{search}%")) |
                (APITest.description.ilike(f"%{search}%"))
            )

        # 格式过滤
        if script_format:
            query = query.where(APITest.script_format == script_format)

        # 获取总数
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        # 获取数据
        query = query.order_by(APITest.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1ZadFl3PT06MWFkZDU3NjI=

    async def get_by_folder(
        self,
        folder_id: UUID,
        offset: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
    ) -> tuple[list[APITest], int]:
        """
        获取文件夹下的 API 测试列表

        Args:
            folder_id: 文件夹 ID
            offset: 偏移量
            limit: 限制数量
            search: 搜索关键词

        Returns:
            tuple[list[APITest], int]: API 测试列表和总数
        """
        query = select(APITest).where(APITest.folder_id == folder_id)

        # 搜索过滤
        if search:
            query = query.where(
                (APITest.name.ilike(f"%{search}%")) |
                (APITest.identifier.ilike(f"%{search}%")) |
                (APITest.description.ilike(f"%{search}%"))
            )

        # 获取总数
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        # 获取数据
        query = query.order_by(APITest.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_next_identifier(self, project_id: UUID) -> str:
        """
        生成下一个 API 测试标识符

        格式: AT-1001, AT-1002, ...

        通过 PG advisory 事务锁串行化"同 project"的并发写入，提交/回滚时
        自动释放。使用 MAX 而非 COUNT，避免删除记录后编号冲突。

        Args:
            project_id: 项目 ID

        Returns:
            str: 标识符 (AT-xxx)
        """
        await self._acquire_xact_lock(f"at_identifier:{project_id}")

        numeric_part = cast(
            func.regexp_replace(APITest.identifier, r"^\D+", ""),
            Integer,
        )
        result = await self.session.execute(
            select(func.max(numeric_part))
            .where(APITest.project_id == project_id)
            .where(APITest.identifier.op("~")(r"^AT-\d+$"))
        )
        max_number = result.scalar_one_or_none()
        next_number = (max_number or 1000) + 1

        return f"AT-{next_number}"


class APITestRunRepository(BaseRepository[APITestRun]):
    """API 测试运行仓储类"""

    def __init__(self, session: AsyncSession):
        super().__init__(APITestRun, session)
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1ZadFl3PT06MWFkZDU3NjI=

    async def get_by_identifier(self, identifier: str) -> Optional[APITestRun]:
        """根据标识符获取 API 测试运行"""
        result = await self.session.execute(
            select(APITestRun)
            .options(selectinload(APITestRun.test_results))
            .options(selectinload(APITestRun.api_test))
            .where(APITestRun.identifier == identifier)
        )
        return result.scalar_one_or_none()

    async def get_by_api_test(
        self,
        api_test_id: UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[APITestRun], int]:
        """
        获取 API 测试的运行历史

        Args:
            api_test_id: API 测试 ID
            offset: 偏移量
            limit: 限制数量

        Returns:
            tuple[list[APITestRun], int]: 运行列表和总数
        """
        # 获取总数
        count_result = await self.session.execute(
            select(func.count())
            .select_from(APITestRun)
            .where(APITestRun.api_test_id == api_test_id)
        )
        total = count_result.scalar_one()

        # 获取数据
        result = await self.session.execute(
            select(APITestRun)
            .where(APITestRun.api_test_id == api_test_id)
            .order_by(APITestRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(result.scalars().all())

        return items, total

    async def get_next_identifier(self, api_test_id: UUID) -> str:
        """生成下一个运行标识符

        格式: ATR-YYYYMMDD-NNN

        通过 PG advisory 事务锁串行化"同 api_test 同日期"的并发写入，
        使用 MAX 而非 COUNT，避免删除记录后编号冲突。
        """
        today = datetime.utcnow().date()
        date_str = today.strftime("%Y%m%d")
        prefix = f"ATR-{date_str}-"

        await self._acquire_xact_lock(f"atr_identifier:{api_test_id}:{date_str}")

        # 取 prefix 之后的数字部分的最大值
        numeric_part = cast(
            func.regexp_replace(APITestRun.identifier, r"^\D+\d+-", ""),
            Integer,
        )
        result = await self.session.execute(
            select(func.max(numeric_part))
            .where(APITestRun.api_test_id == api_test_id)
            .where(APITestRun.identifier.like(f"{prefix}%"))
        )
        max_number = result.scalar_one_or_none() or 0
        next_number = max_number + 1

        return f"{prefix}{next_number:03d}"


class APITestResultRepository(BaseRepository[APITestResult]):
    """API 测试结果仓储类"""

    def __init__(self, session: AsyncSession):
        super().__init__(APITestResult, session)

    async def get_by_test_run(
        self,
        test_run_id: UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[APITestResult], int]:
        """
        获取测试运行的结果列表

        Args:
            test_run_id: 测试运行 ID
            offset: 偏移量
            limit: 限制数量

        Returns:
            tuple[list[APITestResult], int]: 结果列表和总数
        """
        # 获取总数
        count_result = await self.session.execute(
            select(func.count())
            .select_from(APITestResult)
            .where(APITestResult.test_run_id == test_run_id)
        )
        total = count_result.scalar_one()
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1ZadFl3PT06MWFkZDU3NjI=

        # 获取数据
        result = await self.session.execute(
            select(APITestResult)
            .where(APITestResult.test_run_id == test_run_id)
            .order_by(APITestResult.created_at)
            .offset(offset)
            .limit(limit)
        )
        items = list(result.scalars().all())

        return items, total

    async def get_by_status(
        self,
        test_run_id: UUID,
        status: str,
    ) -> list[APITestResult]:
        """根据状态获取测试结果"""
        result = await self.session.execute(
            select(APITestResult)
            .where(
                and_(
                    APITestResult.test_run_id == test_run_id,
                    APITestResult.status == status
                )
            )
        )
        return list(result.scalars().all())
