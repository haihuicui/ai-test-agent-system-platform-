"""
TestRunService 单元测试

覆盖本次改造新增逻辑：
- scheduled_by / schedule_id 解析
- 批量调度名称获取
- trigger_type 过滤参数解析
- Schema alias 序列化
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.api.v2.test_runs import _csv_to_trigger_types
from app.schemas.enums import TriggerType
from app.schemas.test_run import TestRunInfo, TestRunListInfo
from app.services.scheduler_service import TestRunSchedulerService
from app.services.test_run_service import TestRunService
from app.utils.exceptions import BadRequestException


class DummySchedule:
    def __init__(self, schedule_id: UUID, name: str):
        self.id = schedule_id
        self.name = name


class DummyTestRun:
    """模拟 TestRun ORM 对象的最小属性集"""

    def __init__(self, schedule_id: UUID | None = None):
        self.id = uuid4()
        self.identifier = "TR-1"
        self.name = "test run"
        self.description = None
        self.run_state = "new_run"
        self.active_state = "active"
        self.assignee = None
        self.test_case_assignee = None
        self.project_id = uuid4()
        self.test_plan_id = None
        self.sub_test_plan_id = None
        self.test_cases_count = 0
        self.passed_count = 0
        self.failed_count = 0
        self.custom_status_count = 0
        self.tags = []
        self.issues = []
        self.issue_tracker = None
        self.configurations = []
        self.configuration_map = None
        self.folder_ids = None
        self.include_all = False
        self.filter_scope = "global"
        self.filter_test_cases = None
        self.execution_mode = "sequential"
        self.max_concurrency = 5
        self.failure_policy = "continue"
        self.trigger_type = TriggerType.SCHEDULED
        self.environment_id = None
        self.scheduled_by = schedule_id
        self.untested_count = 0
        self.passed_count = 0
        self.retest_count = 0
        self.failed_count = 0
        self.blocked_count = 0
        self.skipped_count = 0
        self.in_progress_count = 0
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = None
        self.closed_at = None


class TestCsvToTriggerTypes:
    def test_single_value(self):
        result = _csv_to_trigger_types("manual")
        assert result == [TriggerType.MANUAL]

    def test_multiple_values(self):
        result = _csv_to_trigger_types("manual,scheduled,api")
        assert result == [
            TriggerType.MANUAL,
            TriggerType.SCHEDULED,
            TriggerType.API,
        ]

    def test_empty_returns_none(self):
        assert _csv_to_trigger_types(None) is None
        assert _csv_to_trigger_types("") is None


class TestResolveScheduleId:
    @pytest.mark.asyncio
    async def test_empty_returns_none(self):
        service = TestRunService.__new__(TestRunService)
        service.schedule_repo = None  # type: ignore
        result = await service._resolve_schedule_id(None, uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_uuid_raises(self):
        service = TestRunService.__new__(TestRunService)
        service.schedule_repo = None  # type: ignore
        with pytest.raises(BadRequestException):
            await service._resolve_schedule_id("not-a-uuid", uuid4())

    @pytest.mark.asyncio
    async def test_valid_uuid_not_found_raises(self):
        service = TestRunService.__new__(TestRunService)

        class FakeRepo:
            async def get_by_id(self, _):
                return None

        service.schedule_repo = FakeRepo()  # type: ignore
        with pytest.raises(BadRequestException):
            await service._resolve_schedule_id(str(uuid4()), uuid4())

    @pytest.mark.asyncio
    async def test_valid_uuid_wrong_project_raises(self):
        service = TestRunService.__new__(TestRunService)
        project_id = uuid4()
        schedule_id = uuid4()

        class FakeRepo:
            async def get_by_id(self, _):
                schedule = DummySchedule(schedule_id, "test")
                schedule.project_id = uuid4()
                return schedule

        service.schedule_repo = FakeRepo()  # type: ignore
        with pytest.raises(BadRequestException):
            await service._resolve_schedule_id(str(schedule_id), project_id)

    @pytest.mark.asyncio
    async def test_valid_uuid_returns_uuid(self):
        service = TestRunService.__new__(TestRunService)
        project_id = uuid4()
        schedule_id = uuid4()

        class FakeRepo:
            async def get_by_id(self, sid):
                assert sid == schedule_id
                schedule = DummySchedule(schedule_id, "test")
                schedule.project_id = project_id
                return schedule

        service.schedule_repo = FakeRepo()  # type: ignore
        result = await service._resolve_schedule_id(str(schedule_id), project_id)
        assert result == schedule_id


class TestBatchScheduleNames:
    @pytest.mark.asyncio
    async def test_empty_set_returns_empty(self):
        service = TestRunService.__new__(TestRunService)
        service.schedule_repo = None  # type: ignore
        result = await service._batch_schedule_names(set())
        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_name_mapping(self):
        service = TestRunService.__new__(TestRunService)
        s1, s2 = uuid4(), uuid4()

        class FakeRepo:
            async def get_by_ids(self, ids):
                return [DummySchedule(s1, "A"), DummySchedule(s2, "B")]

        service.schedule_repo = FakeRepo()  # type: ignore
        result = await service._batch_schedule_names({s1, s2})
        assert result == {s1: "A", s2: "B"}


class TestToInfoScheduleFields:
    @pytest.mark.asyncio
    async def test_to_info_populates_schedule_id_and_name(self):
        service = TestRunService.__new__(TestRunService)
        schedule_id = uuid4()

        class FakeScheduleRepo:
            async def get_by_id(self, sid):
                assert sid == schedule_id
                return DummySchedule(schedule_id, "daily")

        service.schedule_repo = FakeScheduleRepo()  # type: ignore
        service.test_plan_repo = type(
            "R", (), {"get_by_id": lambda *_a, **_k: None}
        )()  # type: ignore
        async def _empty_cases(*_a, **_k):
            return []

        async def _empty_jobs(*_a, **_k):
            return [], 0

        service.tc_repo = type(
            "R", (), {"get_all_for_run": _empty_cases}
        )()  # type: ignore
        service.script_job_repo = type(
            "R", (), {"get_by_test_run": _empty_jobs}
        )()  # type: ignore

        test_run = DummyTestRun(schedule_id)
        info = await service._to_info(test_run, "P-1")
        assert info.scheduled_by == schedule_id
        assert info.schedule_name == "daily"

    def test_to_list_info_populates_schedule_id_and_name(self):
        service = TestRunService.__new__(TestRunService)
        schedule_id = uuid4()
        test_run = DummyTestRun(schedule_id)

        info = service._to_list_info(
            test_run, schedule_names={schedule_id: "daily"}
        )
        assert info.scheduled_by == schedule_id
        assert info.schedule_name == "daily"

    def test_to_list_info_without_schedule(self):
        service = TestRunService.__new__(TestRunService)
        test_run = DummyTestRun(None)

        info = service._to_list_info(test_run)
        assert info.scheduled_by is None
        assert info.schedule_name is None


class TestScheduleIdAlias:
    def test_test_run_info_serializes_scheduled_by_as_schedule_id(self):
        schedule_id = uuid4()
        info = TestRunInfo(
            id=uuid4(),
            identifier="TR-1",
            name="test",
            run_state="new_run",
            active_state="active",
            project_id=uuid4(),
            scheduled_by=schedule_id,
            created_at=datetime.now(timezone.utc),
        )
        data = info.model_dump(mode="json", by_alias=True)
        assert data["schedule_id"] == str(schedule_id)
        assert "scheduled_by" not in data

    def test_test_run_list_info_serializes_scheduled_by_as_schedule_id(self):
        schedule_id = uuid4()
        info = TestRunListInfo(
            id=uuid4(),
            identifier="TR-1",
            name="test",
            run_state="new_run",
            active_state="active",
            project_id=uuid4(),
            scheduled_by=schedule_id,
            created_at=datetime.now(timezone.utc),
        )
        data = info.model_dump(mode="json", by_alias=True)
        assert data["schedule_id"] == str(schedule_id)
        assert "scheduled_by" not in data


class TestComputeNextRunAt:
    def test_cron_next_run_in_future(self):
        svc = TestRunSchedulerService()
        next_run = svc.compute_next_run_at("cron", {"cron_expression": "0 9 * * *"})
        assert next_run is not None
        assert next_run.tzinfo is not None
        assert next_run > datetime.now(timezone.utc)

    def test_interval_next_run_in_future(self):
        svc = TestRunSchedulerService()
        next_run = svc.compute_next_run_at("interval", {"minutes": 30})
        assert next_run is not None
        assert next_run.tzinfo is not None
        # 30 分钟间隔，下次执行应在 30 分钟内
        assert (next_run - datetime.now(timezone.utc)).total_seconds() <= 30 * 60

    def test_date_in_past_returns_none(self):
        svc = TestRunSchedulerService()
        past = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        next_run = svc.compute_next_run_at("date", {"run_date": past.isoformat()})
        assert next_run is None

    def test_date_in_future_returns_run_date(self):
        svc = TestRunSchedulerService()
        future = datetime.now(timezone.utc) + timedelta(days=1)
        next_run = svc.compute_next_run_at("date", {"run_date": future.isoformat()})
        assert next_run is not None
        # 允许秒级误差
        assert abs((next_run - future).total_seconds()) < 1

    def test_invalid_trigger_returns_none(self):
        svc = TestRunSchedulerService()
        assert svc.compute_next_run_at("unknown", {}) is None
