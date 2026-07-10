"""
定时调度服务

封装 APScheduler，提供测试运行定时调度的注册、执行和管理。
"""

from datetime import datetime
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
from app.services.test_execution_engine import TestExecutionService


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

            print(f"[Scheduler] 已加载 {len(schedules)} 个定时调度")

    async def _execute_scheduled_run(self, schedule_id: str) -> None:
        """定时触发的回调：创建测试运行并执行"""
        print(f"[Scheduler] 执行定时调度: {schedule_id}")

        test_run_id: UUID | None = None

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

            template = schedule.test_run_template or {}

            # 创建测试运行
            from app.models.test_run import TestRun
            from app.schemas.enums import ExecutionMode, TestRunState

            run_repo = TestRunRepository(session)
            identifier = await run_repo.generate_identifier(project.id)

            test_run = TestRun(
                project_id=project.id,
                identifier=identifier,
                name=template.get("name", f"定时执行 - {schedule.name}"),
                description=template.get("description", schedule.description),
                run_state=TestRunState.NEW_RUN,
                execution_mode=ExecutionMode(
                    template.get("execution_mode", "sequential")
                ),
                max_concurrency=template.get("max_concurrency", 5),
                trigger_type=TriggerType.SCHEDULED,
                scheduled_by=schedule.id,
                environment_id=UUID(template["environment_id"])
                if template.get("environment_id")
                else None,
            )
            session.add(test_run)
            await session.flush()
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVhSb05BPT06ZTVlYmNmZTU=

            # 如果有 scripts 配置，创建 script_jobs
            scripts = template.get("scripts", [])
            if scripts:
                from app.models.test_run import TestRunScriptJob
                from app.schemas.enums import JobStatus

                jobs = []
                for i, sel in enumerate(scripts):
                    jobs.append(
                        TestRunScriptJob(
                            test_run_id=test_run.id,
                            script_type=sel["script_type"],
                            script_id=UUID(sel["script_id"]),
                            script_identifier=sel.get("script_identifier", ""),
                            script_name=sel.get("script_name"),
                            execution_order=sel.get("execution_order", i),
                            execution_mode=ExecutionMode(
                                sel.get("execution_mode", "sequential")
                            ),
                            status=JobStatus.PENDING,
                            max_retries=sel.get("max_retries", 0),
                        )
                    )
                session.add_all(jobs)

            await session.commit()
            test_run_id = test_run.id

            # 更新调度上次执行时间
            schedule.last_run_at = datetime.utcnow()
            await session.commit()

            print(f"[Scheduler] 创建测试运行: {test_run.identifier}")
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVhSb05BPT06ZTVlYmNmZTU=

        if not test_run_id:
            print("[Scheduler] 测试运行创建失败")
            return

        # 使用独立的 session 执行测试运行
        execution_service = TestExecutionService()
        try:
            result = await execution_service.execute_run(
                test_run_id, trigger="scheduled"
            )
            print(f"[Scheduler] 执行完成: {result}")
        except Exception as e:
            print(f"[Scheduler] 执行失败: {e}")


# 全局单例
_scheduler_service: Optional[TestRunSchedulerService] = None


def get_scheduler_service() -> TestRunSchedulerService:
    """获取调度服务单例"""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = TestRunSchedulerService()
    return _scheduler_service
