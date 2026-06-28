"""
Android 测试仓储

处理 Android 测试相关的数据库操作
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVUwM2FBPT06ZmE0YjJlNmI=

from sqlalchemy import Integer, and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.repositories.base import BaseRepository
from app.models.android_test import AndroidTest, AndroidTestRun, AndroidTestResult


class AndroidTestRepository(BaseRepository[AndroidTest]):
    """Android 测试仓储类"""

    def __init__(self, session: AsyncSession):
        super().__init__(AndroidTest, session)

    async def get_by_identifier(self, identifier: str) -> Optional[AndroidTest]:
        """
        根据标识符获取 Android 测试

        Args:
            identifier: Android 测试标识符 (ANT-xxx)

        Returns:
            Optional[AndroidTest]: Android 测试实例或 None
        """
        result = await self.session.execute(
            select(AndroidTest)
            .options(selectinload(AndroidTest.test_runs))
            .where(AndroidTest.identifier == identifier)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(self, id: UUID) -> Optional[AndroidTest]:
        """根据 ID 获取 Android 测试（包含关联数据）"""
        result = await self.session.execute(
            select(AndroidTest)
            .options(selectinload(AndroidTest.test_case))
            .options(selectinload(AndroidTest.project))
            .options(selectinload(AndroidTest.test_runs))
            .where(AndroidTest.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_project(
        self,
        project_id: UUID,
        offset: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        script_format: Optional[str] = None,
    ) -> tuple[list[AndroidTest], int]:
        """
        获取项目下的 Android 测试列表

        Args:
            project_id: 项目 ID
            offset: 偏移量
            limit: 限制数量
            search: 搜索关键词
            script_format: 脚本格式过滤

        Returns:
            tuple[list[AndroidTest], int]: Android 测试列表和总数
        """
        query = select(AndroidTest).where(AndroidTest.project_id == project_id)

        if search:
            query = query.where(
                (AndroidTest.name.ilike(f"%{search}%")) |
                (AndroidTest.identifier.ilike(f"%{search}%")) |
                (AndroidTest.description.ilike(f"%{search}%"))
            )

        if script_format:
            query = query.where(AndroidTest.script_format == script_format)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(AndroidTest.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_by_folder(
        self,
        folder_id: UUID,
        offset: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
    ) -> tuple[list[AndroidTest], int]:
        """
        获取文件夹下的 Android 测试列表

        Args:
            folder_id: 文件夹 ID
            offset: 偏移量
            limit: 限制数量
            search: 搜索关键词

        Returns:
            tuple[list[AndroidTest], int]: Android 测试列表和总数
        """
        query = select(AndroidTest).where(AndroidTest.folder_id == folder_id)

        if search:
            query = query.where(
                (AndroidTest.name.ilike(f"%{search}%")) |
                (AndroidTest.identifier.ilike(f"%{search}%")) |
                (AndroidTest.description.ilike(f"%{search}%"))
            )

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(AndroidTest.created_at.desc())
        query = query.offset(offset).limit(limit)
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVUwM2FBPT06ZmE0YjJlNmI=

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def get_next_identifier(self, project_id: UUID) -> str:
        """
        生成下一个 Android 测试标识符

        格式: ANT-1001, ANT-1002, ...

        通过 PG advisory 事务锁串行化"同 project"的并发写入，提交/回滚时
        自动释放。使用 MAX 而非 COUNT，避免删除记录后编号冲突。

        Args:
            project_id: 项目 ID

        Returns:
            str: 标识符 (ANT-xxx)
        """
        await self._acquire_xact_lock(f"ant_identifier:{project_id}")

        numeric_part = cast(
            func.regexp_replace(AndroidTest.identifier, r"^\D+", ""),
            Integer,
        )
        result = await self.session.execute(
            select(func.max(numeric_part))
            .where(AndroidTest.project_id == project_id)
            .where(AndroidTest.identifier.op("~")(r"^ANT-\d+$"))
        )
        max_number = result.scalar_one_or_none()
        next_number = (max_number or 1000) + 1
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVUwM2FBPT06ZmE0YjJlNmI=

        return f"ANT-{next_number}"


class AndroidTestRunRepository(BaseRepository[AndroidTestRun]):
    """Android 测试运行仓储类"""

    def __init__(self, session: AsyncSession):
        super().__init__(AndroidTestRun, session)

    async def get_by_identifier(self, identifier: str) -> Optional[AndroidTestRun]:
        """根据标识符获取 Android 测试运行"""
        result = await self.session.execute(
            select(AndroidTestRun)
            .options(selectinload(AndroidTestRun.test_results))
            .options(selectinload(AndroidTestRun.android_test))
            .where(AndroidTestRun.identifier == identifier)
        )
        return result.scalar_one_or_none()

    async def get_by_android_test(
        self,
        android_test_id: UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[AndroidTestRun], int]:
        """
        获取 Android 测试的运行历史

        Args:
            android_test_id: Android 测试 ID
            offset: 偏移量
            limit: 限制数量

        Returns:
            tuple[list[AndroidTestRun], int]: 运行列表和总数
        """
        count_result = await self.session.execute(
            select(func.count())
            .select_from(AndroidTestRun)
            .where(AndroidTestRun.android_test_id == android_test_id)
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            select(AndroidTestRun)
            .where(AndroidTestRun.android_test_id == android_test_id)
            .order_by(AndroidTestRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(result.scalars().all())

        return items, total

    async def get_next_identifier(self, android_test_id: UUID) -> str:
        """生成下一个运行标识符

        格式: ANTR-YYYYMMDD-NNN

        通过 PG advisory 事务锁串行化"同 android_test 同日期"的并发写入，
        使用 MAX 而非 COUNT，避免删除记录后编号冲突。
        """
        today = datetime.utcnow().date()
        date_str = today.strftime("%Y%m%d")
        prefix = f"ANTR-{date_str}-"

        await self._acquire_xact_lock(f"antr_identifier:{android_test_id}:{date_str}")

        numeric_part = cast(
            func.regexp_replace(AndroidTestRun.identifier, r"^\D+\d+-", ""),
            Integer,
        )
        result = await self.session.execute(
            select(func.max(numeric_part))
            .where(AndroidTestRun.android_test_id == android_test_id)
            .where(AndroidTestRun.identifier.like(f"{prefix}%"))
        )
        max_number = result.scalar_one_or_none() or 0
        next_number = max_number + 1

        return f"{prefix}{next_number:03d}"


class AndroidTestResultRepository(BaseRepository[AndroidTestResult]):
    """Android 测试结果仓储类"""

    def __init__(self, session: AsyncSession):
        super().__init__(AndroidTestResult, session)

    async def get_by_test_run(
        self,
        test_run_id: UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AndroidTestResult], int]:
        """
        获取测试运行的结果列表

        Args:
            test_run_id: 测试运行 ID
            offset: 偏移量
            limit: 限制数量

        Returns:
            tuple[list[AndroidTestResult], int]: 结果列表和总数
        """
        count_result = await self.session.execute(
            select(func.count())
            .select_from(AndroidTestResult)
            .where(AndroidTestResult.test_run_id == test_run_id)
        )
        total = count_result.scalar_one()
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVUwM2FBPT06ZmE0YjJlNmI=

        result = await self.session.execute(
            select(AndroidTestResult)
            .where(AndroidTestResult.test_run_id == test_run_id)
            .order_by(AndroidTestResult.created_at)
            .offset(offset)
            .limit(limit)
        )
        items = list(result.scalars().all())

        return items, total

    async def get_by_status(
        self,
        test_run_id: UUID,
        status: str,
    ) -> list[AndroidTestResult]:
        """根据状态获取测试结果"""
        result = await self.session.execute(
            select(AndroidTestResult)
            .where(
                and_(
                    AndroidTestResult.test_run_id == test_run_id,
                    AndroidTestResult.status == status
                )
            )
        )
        return list(result.scalars().all())
