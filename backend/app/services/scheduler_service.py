"""
定时调度服务

封装 APScheduler，提供测试运行定时调度的注册、执行和管理。
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from app.config.database import async_session_factory
from app.config.settings import settings
from app.models.test_run import TestRunSchedule
from app.repositories.project_repo import ProjectRepository
from app.repositories.test_run_repo import TestRunScheduleRepository, TestRunRepository
from app.schemas.enums import TriggerType
from app.schemas.test_run import TestRunCreate
from app.services.test_run_service import TestRunService


class TestRunSchedulerService:
    """测试运行定时调度服务"""
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVhSb05BPT06ZTVlYmNmZTU=

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._initialized = False

    def start(self) -> None:
        """启动调度器"""
        if not self._initialized:
            self.scheduler.start()
            self._initialized = True

    def shutdown(self) -> None:
        """关闭调度器"""
        if self._initialized:
            self.scheduler.shutdown(wait=False)
            self._initialized = False

    def _build_trigger(self, trigger_type: str, trigger_config: dict) -> Any:
        """根据配置构建 APScheduler 触发器"""
        if trigger_type == "cron":
            cron_expression = trigger_config.get("cron_expression")
            if cron_expression:
                return CronTrigger.from_crontab(cron_expression)
            return CronTrigger(**trigger_config)
        elif trigger_type == "interval":
            config = dict(trigger_config)
            # 支持 minutes/hours/days 简写
            if "minutes" in config:
                config["seconds"] = config.pop("minutes") * 60
            elif "hours" in config:
                config["seconds"] = config.pop("hours") * 3600
            elif "days" in config:
                config["seconds"] = config.pop("days") * 86400
            return IntervalTrigger(**config)
        elif trigger_type == "date":
            run_date = trigger_config.get("run_date")
            if isinstance(run_date, str):
                run_date = datetime.fromisoformat(run_date.replace("Z", "+00:00"))
            return DateTrigger(run_date=run_date)
        else:
            raise ValueError(f"不支持的触发器类型: {trigger_type}")

    def compute_next_run_at(
        self, trigger_type: str, trigger_config: dict
    ) -> Optional[datetime]:
        """根据触发器配置计算下次执行时间（UTC）"""
        try:
            trigger = self._build_trigger(trigger_type, trigger_config)
            now = datetime.now(timezone.utc)
            next_time = trigger.get_next_fire_time(None, now)
            if next_time is None:
                return None
            # APScheduler 可能返回 naive datetime，统一按 UTC 处理
            if next_time.tzinfo is None:
                next_time = next_time.replace(tzinfo=timezone.utc)
            # 一次性 date 触发器若已过期，则没有下次执行时间
            if next_time <= now:
                return None
            return next_time
        except Exception as e:
            print(f"[Scheduler] 计算下次执行时间失败: {e}")
            return None

    def add_schedule(self, schedule: TestRunSchedule) -> None:
        """将调度添加到 APScheduler"""
        if not schedule.is_enabled:
            return

        job_id = str(schedule.id)
        self.remove_schedule(job_id)

        try:
            trigger = self._build_trigger(
                schedule.trigger_type.value,
                schedule.trigger_config,
            )
            self.scheduler.add_job(
                func=self._execute_scheduled_run,
                trigger=trigger,
                id=job_id,
                replace_existing=True,
                args=[job_id],
            )
        except Exception as e:
            print(f"[Scheduler] 添加调度失败 {job_id}: {e}")

    def remove_schedule(self, schedule_id: str) -> None:
        """从 APScheduler 移除调度"""
        try:
            self.scheduler.remove_job(schedule_id)
        except Exception:
            pass

    def pause_schedule(self, schedule_id: str) -> None:
        """暂停调度"""
        try:
            self.scheduler.pause_job(schedule_id)
        except Exception:
            pass
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVhSb05BPT06ZTVlYmNmZTU=

    def resume_schedule(self, schedule_id: str) -> None:
        """恢复调度"""
        try:
            self.scheduler.resume_job(schedule_id)
        except Exception:
            pass

    async def load_schedules_from_db(self) -> None:
        """从数据库加载所有启用的调度"""
        async with async_session_factory() as session:
            repo = TestRunScheduleRepository(session)
            stmt = select(TestRunSchedule).where(TestRunSchedule.is_enabled.is_(True))
            result = await session.execute(stmt)
            schedules = result.scalars().all()

            for schedule in schedules:
                self.add_schedule(schedule)
                # 同步下次执行时间；若已过期则重新计算
                schedule.next_run_at = self.compute_next_run_at(
                    schedule.trigger_type.value,
                    schedule.trigger_config,
                )

            await session.commit()
            print(f"[Scheduler] 已加载 {len(schedules)} 个定时调度")

    async def _execute_scheduled_run(self, schedule_id: str) -> None:
        """定时触发的回调：统一通过 TestRunService 创建测试运行并执行"""
        print(f"[Scheduler] 执行定时调度: {schedule_id}")

        async with async_session_factory() as session:
            repo = TestRunScheduleRepository(session)
            schedule = await repo.get_by_id(UUID(schedule_id))
            if not schedule or not schedule.is_enabled:
                print(f"[Scheduler] 调度不存在或已禁用: {schedule_id}")
                return

            project_repo = ProjectRepository(session)
            project = await project_repo.get_by_id(schedule.project_id)
            if not project:
                print(f"[Scheduler] 项目不存在: {schedule.project_id}")
                return

            run_repo = TestRunRepository(session)

            # 幂等保护 1：最近 N 秒内已触发过则跳过
            recent_run = await run_repo.get_recent_by_schedule(
                schedule.id, seconds=60
            )
            if recent_run:
                print(
                    f"[Scheduler] 调度 {schedule_id} 最近已触发 "
                    f"({recent_run.identifier})，跳过"
                )
                return

            # 幂等保护 2：存在执行中的 run 则跳过
            in_progress_run = await run_repo.get_in_progress_by_schedule(
                schedule.id
            )
            if in_progress_run:
                print(
                    f"[Scheduler] 调度 {schedule_id} 存在执行中的 run "
                    f"({in_progress_run.identifier})，跳过"
                )
                return

            template = schedule.test_run_template or {}
            service = TestRunService(session)

            # 统一通过 Service 创建 TestRun，复用所有校验、默认值、脚本作业创建逻辑
            test_run = await service.create(
                project.identifier,
                TestRunCreate(
                    name=template.get("name", f"定时执行 - {schedule.name}"),
                    description=template.get(
                        "description", schedule.description
                    ),
                    execution_mode=template.get("execution_mode", "sequential"),
                    max_concurrency=template.get("max_concurrency", 5),
                    environment_id=template.get("environment_id"),
                    scripts=template.get("scripts", []),
                    trigger_type=TriggerType.SCHEDULED,
                    scheduled_by=str(schedule.id),
                ),
            )

            # 统一通过 Service 执行
            await service.execute_test_run(
                project.identifier, test_run.identifier
            )

            # 更新调度上次执行时间，并重新计算下次执行时间
            schedule.last_run_at = datetime.utcnow()
            schedule.next_run_at = self.compute_next_run_at(
                schedule.trigger_type.value,
                schedule.trigger_config,
            )
            await session.commit()

            print(
                f"[Scheduler] 调度 {schedule_id} 已创建并执行: "
                f"{test_run.identifier}"
            )


# 全局单例
_scheduler_service: Optional[TestRunSchedulerService] = None


def get_scheduler_service() -> TestRunSchedulerService:
    """获取调度服务单例"""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = TestRunSchedulerService()
    return _scheduler_service
