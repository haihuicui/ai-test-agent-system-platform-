"""
测试运行服务

处理测试运行相关的业务逻辑
参考: https://www.browserstack.com/docs/test-management/api-reference/test-runs
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from app.config.minio_client import MinIOClient
from app.models.test_run import TestRun, TestRunTestCase, TestRunScriptJob, TestRunSchedule
from app.models.api_test import APITestRun
from app.models.test_scenario import ScenarioRun
from app.models.web_test import WebTestRun
from app.repositories.api_test_repo import APITestRunRepository
from app.services.test_execution_engine import TestExecutionService
from app.models.test_case import TestCase
from app.repositories.test_run_repo import (
    TestRunRepository,
    TestRunTestCaseRepository,
    TestRunScriptJobRepository,
    TestRunScheduleRepository,
)
from app.repositories.project_repo import ProjectRepository
from app.repositories.test_case_repo import TestCaseRepository
from app.repositories.test_plan_repo import TestPlanRepository
from app.repositories.web_test_repo import WebTestRunRepository
from app.schemas.test_run import (
    TestRunCreate,
    TestRunPatchUpdate,
    TestRunFullReplace,
    TestRunInfo,
    TestRunListInfo,
    TestRunMinifiedInfo,
    TestRunTestCaseInfo,
    TestRunTestCaseMinifiedInfo,
    TestRunLinks,
    OverallProgress,
    AddTestCasesRequest,
    RemoveTestCasesRequest,
    TestRunAssignRequest,
    CloseTestRunRequest,
    ConfigurationMapping,
    TestPlanRef,
    TestStepBrief,
    IssueTracker,
    TestCaseFilter,
    TestRunScriptJobInfo,
    TestRunScriptJobCreate,
    TestRunScheduleInfo,
    TestRunScheduleCreate,
    TestRunScheduleUpdate,
)
from app.schemas.enums import (
    TestRunActiveState,
    TestRunState,
    TestResultStatus,
    FilterScope,
    ExecutionMode,
    TriggerType,
    ScriptType,
    JobStatus,
    FailurePolicy,
)
from app.utils.exceptions import NotFoundException, BadRequestException
from app.config.settings import settings
from app.config.database import async_session_factory


logger = logging.getLogger(__name__)

# 模块级后台任务集合：持有 asyncio.create_task 的引用，避免事件循环仅持弱引用导致
# 任务被 GC（"Task was destroyed but it is pending"）而遗留 IN_PROGRESS 僵尸运行。
_background_tasks: set[asyncio.Task] = set()


def _spawn_tracked(coro, label: str) -> asyncio.Task:
    """创建并跟踪一个后台任务。

    - 持有任务引用，防止被垃圾回收；
    - 任务结束时自动从集合移除；
    - 任务异常时记录日志，避免静默失败（异常仍由协程内部兜底处理）。
    """
    task = asyncio.create_task(coro, name=label)
    _background_tasks.add(task)

    def _on_done(t: asyncio.Task) -> None:
        _background_tasks.discard(t)
        # 取回异常以标记为"已检索"，同时记录，便于排查后台执行失败
        if t.cancelled():
            logger.warning("[TestRunService] 后台任务被取消: %s", label)
            return
        exc = t.exception()
        if exc is not None:
            logger.error("[TestRunService] 后台任务异常 %s: %s", label, exc)

    task.add_done_callback(_on_done)
    return task


class TestRunService:
    """测试运行服务类"""

    def __init__(self, session: AsyncSession, mongodb=None):
        self.session = session
        self.mongodb = mongodb
        self.repo = TestRunRepository(session)
        self.tc_repo = TestRunTestCaseRepository(session)
        self.script_job_repo = TestRunScriptJobRepository(session)
        self.schedule_repo = TestRunScheduleRepository(session)
        self.project_repo = ProjectRepository(session)
        self.test_case_repo = TestCaseRepository(session)
        self.test_plan_repo = TestPlanRepository(session)

    # ============ 内部工具 ============

    async def _get_project_by_identifier(self, project_identifier: str):
        """根据标识符获取项目"""
        project = await self.project_repo.get_by_identifier(project_identifier)
        if not project:
            raise NotFoundException(
                resource_type="项目", resource_id=project_identifier
            )
        return project

    async def _require_test_run(
        self, project_id: UUID, test_run_identifier: str
    ) -> TestRun:
        test_run = await self.repo.get_by_identifier(test_run_identifier)
        if not test_run or test_run.project_id != project_id:
            raise NotFoundException(
                resource_type="测试运行", resource_id=test_run_identifier
            )
        return test_run
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1doaFV3PT06MzhkMDVhYzE=

    async def _resolve_test_plan_id(
        self, identifier: Optional[str], project_id: UUID
    ) -> Optional[UUID]:
        """把 TP-x / STP-x identifier 解析为 test_plans.id"""
        if not identifier:
            return None
        tp = await self.test_plan_repo.get_by_identifier(identifier)
        if not tp or tp.project_id != project_id:
            raise BadRequestException(
                message=f"测试计划 '{identifier}' 不存在或不属于该项目"
            )
        return tp.id

    async def _resolve_environment_id(
        self, environment_id: Optional[str], project_id: UUID
    ) -> Optional[UUID]:
        """校验 environment_id 属于该项目，返回 UUID 或 None"""
        if not environment_id:
            return None
        from app.repositories.environment_repo import EnvironmentRepository

        env_repo = EnvironmentRepository(self.session)
        try:
            env_uuid = UUID(environment_id)
        except ValueError:
            raise BadRequestException(
                message=f"环境 ID '{environment_id}' 格式不正确"
            )
        env = await env_repo.get_by_id(env_uuid)
        if not env or env.project_id != project_id:
            raise BadRequestException(
                message=f"环境 '{environment_id}' 不存在或不属于该项目"
            )
        return env_uuid

    async def _resolve_schedule_id(
        self, schedule_id: Optional[str], project_id: UUID
    ) -> Optional[UUID]:
        """校验 scheduled_by 属于该项目，返回 UUID 或 None"""
        if not schedule_id:
            return None
        try:
            schedule_uuid = UUID(schedule_id)
        except ValueError:
            raise BadRequestException(
                message=f"来源调度 ID '{schedule_id}' 格式不正确"
            )
        schedule = await self.schedule_repo.get_by_id(schedule_uuid)
        if not schedule or schedule.project_id != project_id:
            raise BadRequestException(
                message=f"来源调度 '{schedule_id}' 不存在或不属于该项目"
            )
        return schedule_uuid

    def _overall_progress(self, test_run: TestRun) -> OverallProgress:
        """从模型字段构造 BS 7 字段进度"""
        return OverallProgress(
            untested=test_run.untested_count or 0,
            passed=test_run.passed_count or 0,
            retest=test_run.retest_count or 0,
            failed=test_run.failed_count or 0,
            blocked=test_run.blocked_count or 0,
            skipped=test_run.skipped_count or 0,
            in_progress=test_run.in_progress_count or 0,
        )

    def _links(
        self, project_identifier: str, test_run_identifier: str
    ) -> TestRunLinks:
        base = (
            f"{settings.api_prefix}/projects/{project_identifier}"
            f"/test-runs/{test_run_identifier}"
        )
        return TestRunLinks(self=base, test_cases=f"{base}/test-cases")

    async def _batch_schedule_names(
        self, schedule_ids: set[UUID]
    ) -> dict[UUID, str]:
        """批量获取调度名称，用于列表/详情展示"""
        if not schedule_ids:
            return {}
        schedules = await self.schedule_repo.get_by_ids(list(schedule_ids))
        return {s.id: s.name for s in schedules if s.id}

    def _test_plan_ref(self, plan) -> Optional[TestPlanRef]:
        if not plan:
            return None
        return TestPlanRef(identifier=plan.identifier, name=plan.name)

    def _configuration_map_to_schema(
        self, raw: Optional[list[dict]]
    ) -> Optional[list[ConfigurationMapping]]:
        if not raw:
            return None
        return [ConfigurationMapping(**item) for item in raw]

    def _issue_tracker_to_schema(
        self, raw: Optional[dict]
    ) -> Optional[IssueTracker]:
        if not raw:
            return None
        return IssueTracker(**raw)

    def _filter_test_cases_to_schema(
        self, raw: Optional[dict]
    ) -> Optional[TestCaseFilter]:
        if not raw:
            return None
        return TestCaseFilter(**raw)

    async def _to_test_run_test_case_info(
        self, item: TestRunTestCase, *, fetch_steps: bool = False
    ) -> TestRunTestCaseInfo:
        tc = item.test_case
        steps: Optional[list[TestStepBrief]] = None
        if fetch_steps and tc and tc.steps:
            steps = [
                TestStepBrief(
                    id=s.id,
                    order=s.step_number,
                    description=s.action,
                    result=s.expected_result,
                )
                for s in tc.steps[:30]
            ]

        return TestRunTestCaseInfo(
            id=item.id,
            test_run_id=item.test_run_id,
            test_case_id=item.test_case_id,
            identifier=tc.identifier if tc else "",
            name=tc.name if tc else "",
            description=tc.description if tc else None,
            case_type=tc.test_case_type if tc else None,
            priority=tc.priority if tc else None,
            status=str(tc.state.value) if tc and tc.state else None,
            folder_id=tc.folder_id if tc else None,
            folder_path=None,
            configuration_id=item.configuration_id,
            assignee=item.assignee,
            latest_status=item.latest_status,
            latest_result_id=item.latest_result_id,
            dataset=tc.dataset if tc else None,
            steps=steps,
            created_at=item.created_at,
            last_updated_at=item.updated_at,
            created_by=tc.created_by if tc else None,
            last_updated_by=tc.last_updated_by if tc else None,
        )

    def _to_minified_test_case(
        self, item: TestRunTestCase
    ) -> TestRunTestCaseMinifiedInfo:
        tc = item.test_case
        return TestRunTestCaseMinifiedInfo(
            identifier=tc.identifier if tc else "",
            name=tc.name if tc else "",
            description=tc.description if tc else None,
            latest_status=item.latest_status,
        )

    def _to_script_job_info(self, job: TestRunScriptJob) -> TestRunScriptJobInfo:
        return TestRunScriptJobInfo(
            id=job.id,
            test_run_id=job.test_run_id,
            script_type=job.script_type,
            script_id=job.script_id,
            script_identifier=job.script_identifier,
            script_name=job.script_name,
            execution_order=job.execution_order,
            execution_mode=job.execution_mode,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            duration_ms=job.duration_ms,
            result_summary=job.result_summary,
            error_message=job.error_message,
            stdout=job.stdout,
            stderr=job.stderr,
            report_path=job.report_path,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    def _to_schedule_info(self, schedule: TestRunSchedule) -> TestRunScheduleInfo:
        return TestRunScheduleInfo(
            id=schedule.id,
            project_id=schedule.project_id,
            name=schedule.name,
            description=schedule.description,
            trigger_type=schedule.trigger_type,
            trigger_config=schedule.trigger_config,
            is_enabled=schedule.is_enabled,
            next_run_at=schedule.next_run_at,
            last_run_at=schedule.last_run_at,
            test_run_template=schedule.test_run_template,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )

    async def _to_info(
        self,
        test_run: TestRun,
        project_identifier: str,
        *,
        include_inline_test_cases: bool = True,
        include_script_jobs: bool = True,
    ) -> TestRunInfo:
        # 关联计划
        plan = None
        sub_plan = None
        if test_run.test_plan_id:
            plan = await self.test_plan_repo.get_by_id(test_run.test_plan_id)
        if test_run.sub_test_plan_id:
            sub_plan = await self.test_plan_repo.get_by_id(
                test_run.sub_test_plan_id
            )

        # 来源调度名称
        schedule_name: Optional[str] = None
        if test_run.scheduled_by:
            schedule = await self.schedule_repo.get_by_id(test_run.scheduled_by)
            schedule_name = schedule.name if schedule else None

        inline_cases: Optional[list[TestRunTestCaseInfo]] = None
        if include_inline_test_cases:
            items = await self.tc_repo.get_all_for_run(
                test_run.id, with_steps=False
            )
            inline_cases = [
                await self._to_test_run_test_case_info(i) for i in items
            ]

        script_jobs: Optional[list[TestRunScriptJobInfo]] = None
        if include_script_jobs:
            jobs, _ = await self.script_job_repo.get_by_test_run(test_run.id)
            script_jobs = [self._to_script_job_info(j) for j in jobs]

        return TestRunInfo(
            id=test_run.id,
            identifier=test_run.identifier,
            name=test_run.name,
            description=test_run.description,
            run_state=test_run.run_state,
            active_state=test_run.active_state,
            assignee=test_run.assignee,
            test_case_assignee=test_run.test_case_assignee,
            project_id=test_run.project_id,
            test_plan=self._test_plan_ref(plan),
            sub_test_plan=self._test_plan_ref(sub_plan),
            test_cases_count=test_run.test_cases_count or 0,
            passed_count=test_run.passed_count or 0,
            failed_count=test_run.failed_count or 0,
            customstatus_count=test_run.custom_status_count or 0,
            tags=test_run.tags or [],
            issues=test_run.issues or [],
            issue_tracker=self._issue_tracker_to_schema(test_run.issue_tracker),
            configurations=test_run.configurations or [],
            configuration_map=self._configuration_map_to_schema(
                test_run.configuration_map
            ),
            folder_ids=test_run.folder_ids,
            include_all=test_run.include_all,
            filter_scope=test_run.filter_scope or FilterScope.GLOBAL,
            filter_test_cases=self._filter_test_cases_to_schema(
                test_run.filter_test_cases
            ),
            overall_progress=self._overall_progress(test_run),
            test_cases=inline_cases,
            execution_mode=test_run.execution_mode or ExecutionMode.SEQUENTIAL,
            max_concurrency=test_run.max_concurrency or 5,
            failure_policy=test_run.failure_policy or FailurePolicy.CONTINUE,
            trigger_type=test_run.trigger_type or TriggerType.MANUAL,
            script_jobs=script_jobs,
            environment_id=str(test_run.environment_id) if test_run.environment_id else None,
            scheduled_by=test_run.scheduled_by,
            schedule_name=schedule_name,
            created_at=test_run.created_at,
            updated_at=test_run.updated_at,
            closed_at=test_run.closed_at,
            links=self._links(project_identifier, test_run.identifier),
        )

    def _to_minified_info(
        self, test_run: TestRun, project_identifier: str
    ) -> TestRunMinifiedInfo:
        return TestRunMinifiedInfo(
            id=test_run.id,
            identifier=test_run.identifier,
            name=test_run.name,
            description=test_run.description,
            run_state=test_run.run_state,
            active_state=test_run.active_state,
            assignee=test_run.assignee,
            project_id=test_run.project_id,
            tags=test_run.tags or [],
            configurations=test_run.configurations or [],
            overall_progress=self._overall_progress(test_run),
            failure_policy=test_run.failure_policy or FailurePolicy.CONTINUE,
            created_at=test_run.created_at,
            updated_at=test_run.updated_at,
            links=self._links(project_identifier, test_run.identifier),
        )

    def _to_list_info(
        self,
        test_run: TestRun,
        *,
        schedule_names: Optional[dict[UUID, str]] = None,
    ) -> TestRunListInfo:
        schedule_names = schedule_names or {}
        return TestRunListInfo(
            id=test_run.id,
            identifier=test_run.identifier,
            name=test_run.name,
            description=test_run.description,
            run_state=test_run.run_state,
            active_state=test_run.active_state,
            assignee=test_run.assignee,
            test_case_assignee=test_run.test_case_assignee,
            project_id=test_run.project_id,
            test_cases_count=test_run.test_cases_count or 0,
            configurations=test_run.configurations or [],
            overall_progress=self._overall_progress(test_run),
            created_at=test_run.created_at,
            closed_at=test_run.closed_at,
            tags=test_run.tags or [],
            issues=test_run.issues or [],
            execution_mode=test_run.execution_mode or ExecutionMode.SEQUENTIAL,
            max_concurrency=test_run.max_concurrency or 5,
            failure_policy=test_run.failure_policy or FailurePolicy.CONTINUE,
            trigger_type=test_run.trigger_type or TriggerType.MANUAL,
            environment_id=str(test_run.environment_id) if test_run.environment_id else None,
            scheduled_by=test_run.scheduled_by,
            schedule_name=schedule_names.get(test_run.scheduled_by) if test_run.scheduled_by else None,
        )

    # ============ 测试用例解析 (BS 优先级) ============

    async def _resolve_test_cases_for_create(
        self,
        project_id: UUID,
        data: Union[TestRunCreate, TestRunFullReplace],
    ) -> list[TestCase]:
        """
        按 BS 规范的 5 级优先级解析最终用例集合:
        1. include_all=True
        2. folder_ids + filter_test_cases + filter_scope=within_folders
        3. folder_ids only
        4. filter_test_cases + filter_scope=global
        5. 显式 test_cases identifier 列表
        """
        if data.include_all:
            return await self.test_case_repo.get_by_project_with_filters(
                project_id=project_id,
                offset=0,
                limit=100000,
            )

        folder_ids_str: Optional[list[str]] = None
        if data.folder_ids:
            folder_ids_str = [str(fid) for fid in data.folder_ids]

        filt = data.filter_test_cases
        filter_scope = data.filter_scope or FilterScope.GLOBAL

        # 2: 文件夹 + 过滤 (within_folders)
        if folder_ids_str and filt and filter_scope == FilterScope.WITHIN_FOLDERS:
            return await self.test_case_repo.get_by_project_with_filters(
                project_id=project_id,
                offset=0,
                limit=100000,
                folder_ids=folder_ids_str,
                statuses=filt.status,
                priorities=filt.priority,
                case_types=filt.case_type,
                owners=filt.owner,
                tags=filt.tags,
                custom_fields=filt.custom_fields,
            )

        # 3: 仅文件夹
        if folder_ids_str:
            return await self.test_case_repo.get_by_project_with_filters(
                project_id=project_id,
                offset=0,
                limit=100000,
                folder_ids=folder_ids_str,
            )

        # 4: 全局过滤
        if filt:
            return await self.test_case_repo.get_by_project_with_filters(
                project_id=project_id,
                offset=0,
                limit=100000,
                statuses=filt.status,
                priorities=filt.priority,
                case_types=filt.case_type,
                owners=filt.owner,
                tags=filt.tags,
                custom_fields=filt.custom_fields,
            )

        # 5: 显式列表
        if data.test_cases:
            resolved: list[TestCase] = []
            seen: set[UUID] = set()
            for ident in data.test_cases:
                tc = await self.test_case_repo.get_by_identifier(ident)
                if tc and tc.project_id == project_id and tc.id not in seen:
                    resolved.append(tc)
                    seen.add(tc.id)
            return resolved

        return []

    @staticmethod
    def _build_configuration_lookup(
        configuration_map: Optional[list[ConfigurationMapping]],
    ) -> dict[str, list[int]]:
        """把 ConfigurationMapping 列表展开为 {tc_identifier: [config_ids]}"""
        lookup: dict[str, list[int]] = {}
        if not configuration_map:
            return lookup
        for entry in configuration_map:
            ids = entry.configuration_ids or []
            keys = (
                [entry.test_case_id]
                if isinstance(entry.test_case_id, str)
                else list(entry.test_case_id)
            )
            for key in keys:
                lookup.setdefault(key, []).extend(ids)
        return lookup

    async def _materialize_test_run_test_cases(
        self,
        test_run_id: UUID,
        cases: list[TestCase],
        *,
        global_configurations: Optional[list[int]],
        configuration_map: Optional[list[ConfigurationMapping]],
        default_assignee: Optional[str],
    ) -> list[TestRunTestCase]:
        """根据用例集合 + 配置映射创建关联 (configuration_map 覆盖全局 configurations)"""
        per_case_map = self._build_configuration_lookup(configuration_map)
        created: list[TestRunTestCase] = []

        for tc in cases:
            config_ids = per_case_map.get(tc.identifier)
            if config_ids is None:
                config_ids = list(global_configurations or [])

            if config_ids:
                for cid in config_ids:
                    created.append(
                        TestRunTestCase(
                            test_run_id=test_run_id,
                            test_case_id=tc.id,
                            configuration_id=cid,
                            assignee=default_assignee,
                            latest_status=TestResultStatus.UNTESTED,
                        )
                    )
            else:
                created.append(
                    TestRunTestCase(
                        test_run_id=test_run_id,
                        test_case_id=tc.id,
                        assignee=default_assignee,
                        latest_status=TestResultStatus.UNTESTED,
                    )
                )

        if created:
            await self.tc_repo.add_test_cases(test_run_id, created)
        return created

    # ============ 公共服务 ============

    async def get_list(
        self,
        project_identifier: str,
        *,
        run_states: Optional[list[TestRunState]] = None,
        assignees: Optional[list[str]] = None,
        test_plan_id: Optional[str] = None,
        include_closed: bool = False,
        closed_before=None,
        closed_after=None,
        created_before=None,
        created_after=None,
        search: Optional[str] = None,
        trigger_types: Optional[list[TriggerType]] = None,
        scheduled_by: Optional[UUID] = None,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[list[TestRunListInfo], int]:
        project = await self._get_project_by_identifier(project_identifier)

        resolved_plan_id: Optional[UUID] = None
        if test_plan_id:
            tp = await self.test_plan_repo.get_by_identifier(test_plan_id)
            if tp and tp.project_id == project.id:
                resolved_plan_id = tp.id

        test_runs, total = await self.repo.get_list(
            project_id=project.id,
            run_states=run_states,
            assignees=assignees,
            test_plan_id=resolved_plan_id,
            include_closed=include_closed,
            closed_before=closed_before,
            closed_after=closed_after,
            created_before=created_before,
            created_after=created_after,
            search=search,
            trigger_types=trigger_types,
            scheduled_by=scheduled_by,
            offset=offset,
            limit=limit,
        )

        # 批量获取来源调度名称
        schedule_ids = {
            tr.scheduled_by for tr in test_runs if tr.scheduled_by
        }
        schedule_names = await self._batch_schedule_names(schedule_ids)

        return [
            self._to_list_info(tr, schedule_names=schedule_names)
            for tr in test_runs
        ], total

    async def get_detail(
        self,
        project_identifier: str,
        test_run_identifier: str,
        *,
        minify: bool = False,
    ) -> Union[TestRunInfo, TestRunMinifiedInfo]:
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        if minify:
            return self._to_minified_info(test_run, project_identifier)
        return await self._to_info(test_run, project_identifier)

    # 兼容别名
    async def get_by_identifier(
        self, project_identifier: str, test_run_identifier: str
    ) -> TestRunInfo:
        return await self.get_detail(
            project_identifier, test_run_identifier, minify=False
        )

    async def create(
        self,
        project_identifier: str,
        data: TestRunCreate,
    ) -> TestRunInfo:
        project = await self._get_project_by_identifier(project_identifier)
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1doaFV3PT06MzhkMDVhYzE=

        # 互斥校验已在 schema 层，但是 service 再校验一次以确保稳健
        if data.test_plan_id and data.sub_test_plan_id:
            raise BadRequestException(
                message="test_plan_id 与 sub_test_plan_id 不能同时提供"
            )

        plan_id = await self._resolve_test_plan_id(data.test_plan_id, project.id)
        sub_plan_id = await self._resolve_test_plan_id(
            data.sub_test_plan_id, project.id
        )
        environment_id = await self._resolve_environment_id(
            data.environment_id, project.id
        )
        scheduled_by_id = await self._resolve_schedule_id(
            data.scheduled_by, project.id
        )

        # 生成唯一标识符并创建 TestRun；带重试以应对并发/定时调度导致的主键冲突
        max_retries = 3
        test_run: TestRun | None = None
        for attempt in range(max_retries):
            identifier = await self.repo.generate_identifier()
            test_run = TestRun(
                project_id=project.id,
                identifier=identifier,
                name=data.name,
                description=data.description,
                run_state=data.run_state,
                active_state=TestRunActiveState.ACTIVE,
                assignee=data.assignee,
                test_case_assignee=data.test_case_assignee,
                test_plan_id=plan_id,
                sub_test_plan_id=sub_plan_id,
                environment_id=environment_id,
                scheduled_by=scheduled_by_id,
                tags=data.tags or [],
                issues=data.issues or [],
                issue_tracker=data.issue_tracker.model_dump()
                if data.issue_tracker
                else None,
                configurations=data.configurations or [],
                configuration_map=[
                    m.model_dump() for m in data.configuration_map
                ]
                if data.configuration_map
                else None,
                folder_ids=data.folder_ids,
                include_all=bool(data.include_all),
                filter_scope=data.filter_scope or FilterScope.GLOBAL,
                filter_test_cases=data.filter_test_cases.model_dump()
                if data.filter_test_cases
                else None,
                execution_mode=data.execution_mode or ExecutionMode.SEQUENTIAL,
                max_concurrency=data.max_concurrency or 5,
                failure_policy=data.failure_policy or FailurePolicy.CONTINUE,
                trigger_type=data.trigger_type or TriggerType.MANUAL,
            )
            try:
                test_run = await self.repo.create(test_run)
                break
            except IntegrityError as exc:
                if "ix_test_runs_identifier" in str(exc) and attempt < max_retries - 1:
                    await self.session.rollback()
                    await asyncio.sleep(0.05 * (2 ** attempt))
                    continue
                raise

        if test_run is None:
            raise BadRequestException(message="生成测试运行标识符失败，请重试")

        # 解析用例并创建关联（兼容旧模式）
        cases = await self._resolve_test_cases_for_create(project.id, data)
        await self._materialize_test_run_test_cases(
            test_run.id,
            cases,
            global_configurations=data.configurations,
            configuration_map=data.configuration_map,
            default_assignee=data.test_case_assignee or data.assignee,
        )

        # 创建脚本作业（新方式：直接脚本选择）
        if data.scripts:
            jobs: list[TestRunScriptJob] = []
            for i, sel in enumerate(data.scripts):
                jobs.append(
                    TestRunScriptJob(
                        test_run_id=test_run.id,
                        script_type=sel.script_type,
                        script_id=UUID(sel.script_id),
                        script_identifier=sel.script_identifier or "",
                        script_name=sel.script_name,
                        execution_order=sel.execution_order or i,
                        execution_mode=sel.execution_mode
                        or (data.execution_mode or ExecutionMode.SEQUENTIAL),
                        execution_config=sel.execution_config,
                        status=JobStatus.PENDING,
                        max_retries=0,
                    )
                )
            await self.script_job_repo.create_many(jobs)
            # 新方式基于 script_jobs 统计未测/进行中数量
            await self.repo.update_counts_from_jobs(test_run.id)
        else:
            await self.repo.update_counts(test_run.id)
        # update_counts* 直接执行 UPDATE 会使当前 session 中的 test_run 对象过期，
        # 重新查询获取干净对象再返回，避免 async session 中访问过期属性触发 MissingGreenlet。
        test_run = await self.repo.get_by_id(test_run.id)
        return await self._to_info(test_run, project_identifier)

    async def patch_update(
        self,
        project_identifier: str,
        test_run_identifier: str,
        data: TestRunPatchUpdate,
    ) -> TestRunInfo:
        """PATCH /test-runs/{id}/update - 部分更新"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        payload = data.model_dump(exclude_unset=True)

        # test_plan_id / sub_test_plan_id (identifier → UUID)
        if "test_plan_id" in payload:
            ident = payload.pop("test_plan_id")
            test_run.test_plan_id = (
                await self._resolve_test_plan_id(ident, project.id)
                if ident
                else None
            )
        if "sub_test_plan_id" in payload:
            ident = payload.pop("sub_test_plan_id")
            test_run.sub_test_plan_id = (
                await self._resolve_test_plan_id(ident, project.id)
                if ident
                else None
            )

        # configuration_map serialize
        if "configuration_map" in payload:
            cm = payload.pop("configuration_map")
            test_run.configuration_map = (
                [m.model_dump() if hasattr(m, "model_dump") else m for m in cm]
                if cm is not None
                else None
            )

        # filter_test_cases serialize
        if "filter_test_cases" in payload:
            ftc = payload.pop("filter_test_cases")
            test_run.filter_test_cases = (
                ftc.model_dump() if hasattr(ftc, "model_dump") else ftc
            )

        # issue_tracker serialize
        if "issue_tracker" in payload:
            it = payload.pop("issue_tracker")
            test_run.issue_tracker = (
                it.model_dump() if hasattr(it, "model_dump") else it
            )

        # environment_id 校验并转换
        if "environment_id" in payload:
            env_id = payload.pop("environment_id")
            test_run.environment_id = await self._resolve_environment_id(
                env_id, project.id
            )

        # active_state 关闭/打开时同步 closed_at 与 run_state
        if "active_state" in payload:
            active_state = payload["active_state"]
            if isinstance(active_state, TestRunActiveState):
                active_state = active_state.value
            if active_state == TestRunActiveState.CLOSED.value:
                if test_run.closed_at is None:
                    test_run.closed_at = datetime.now(timezone.utc)
                test_run.run_state = TestRunState.CLOSED
            elif active_state == TestRunActiveState.ACTIVE.value:
                test_run.closed_at = None

        # run_state 设为 closed 时同步 active_state 与 closed_at
        if "run_state" in payload:
            run_state = payload["run_state"]
            if isinstance(run_state, TestRunState):
                run_state = run_state.value
            if run_state == TestRunState.CLOSED.value:
                test_run.active_state = TestRunActiveState.CLOSED
                if test_run.closed_at is None:
                    test_run.closed_at = datetime.now(timezone.utc)

        # scripts: 替换脚本作业（新增/清空直接脚本选择）
        scripts_updated = False
        if "scripts" in payload:
            scripts = payload.pop("scripts")
            await self.script_job_repo.delete_by_test_run(test_run.id)
            if scripts:
                scripts_updated = True
                jobs: list[TestRunScriptJob] = []
                for i, sel in enumerate(scripts):
                    jobs.append(
                        TestRunScriptJob(
                            test_run_id=test_run.id,
                            script_type=sel["script_type"],
                            script_id=UUID(sel["script_id"]),
                            script_identifier=sel.get("script_identifier") or "",
                            script_name=sel.get("script_name"),
                            execution_order=sel.get("execution_order")
                            if sel.get("execution_order") is not None
                            else i,
                            execution_mode=sel.get("execution_mode")
                            or test_run.execution_mode,
                            execution_config=sel.get("execution_config"),
                            status=JobStatus.PENDING,
                            max_retries=0,
                        )
                    )
                await self.script_job_repo.create_many(jobs)

        # 平铺字段
        for key, value in payload.items():
            if hasattr(test_run, key):
                setattr(test_run, key, value)

        # 关闭状态以 active_state 为准，强制联动 run_state
        if test_run.active_state == TestRunActiveState.CLOSED:
            test_run.run_state = TestRunState.CLOSED

        test_run = await self.repo.update(test_run)

        # 根据是否存在脚本作业选择正确的计数方式
        if scripts_updated:
            await self.repo.update_counts_from_jobs(test_run.id)
        else:
            existing_jobs, _ = await self.script_job_repo.get_by_test_run(test_run.id)
            if existing_jobs:
                await self.repo.update_counts_from_jobs(test_run.id)
            else:
                await self.repo.update_counts(test_run.id)

        # update_counts* 直接执行 UPDATE 会使当前 session 中的 test_run 对象过期，
        # 在 async session 中访问过期属性可能报 MissingGreenlet。
        # 重新查询获取干净对象，避免依赖 refresh 处理过期状态。
        test_run = await self.repo.get_by_id(test_run.id)
        return await self._to_info(test_run, project_identifier)

    async def full_replace(
        self,
        project_identifier: str,
        test_run_identifier: str,
        data: TestRunFullReplace,
    ) -> TestRunInfo:
        """POST /test-runs/{id}/update - 全量替换 (保留 identifier/created_at)"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        if data.test_plan_id and data.sub_test_plan_id:
            raise BadRequestException(
                message="test_plan_id 与 sub_test_plan_id 不能同时提供"
            )

        plan_id = await self._resolve_test_plan_id(data.test_plan_id, project.id)
        sub_plan_id = await self._resolve_test_plan_id(
            data.sub_test_plan_id, project.id
        )
        environment_id = await self._resolve_environment_id(
            data.environment_id, project.id
        )

        test_run.name = data.name
        test_run.description = data.description
        test_run.run_state = data.run_state
        test_run.assignee = data.assignee
        test_run.test_case_assignee = data.test_case_assignee
        test_run.test_plan_id = plan_id
        test_run.sub_test_plan_id = sub_plan_id
        test_run.environment_id = environment_id
        test_run.tags = data.tags or []
        test_run.issues = data.issues or []
        test_run.issue_tracker = (
            data.issue_tracker.model_dump() if data.issue_tracker else None
        )
        test_run.configurations = data.configurations or []
        test_run.configuration_map = (
            [m.model_dump() for m in data.configuration_map]
            if data.configuration_map
            else None
        )
        test_run.folder_ids = data.folder_ids
        test_run.include_all = bool(data.include_all)
        test_run.filter_scope = data.filter_scope or FilterScope.GLOBAL
        test_run.filter_test_cases = (
            data.filter_test_cases.model_dump()
            if data.filter_test_cases
            else None
        )

        await self.repo.update(test_run)

        # 重建关联用例
        await self.tc_repo.remove_all_for_run(test_run.id)
        cases = await self._resolve_test_cases_for_create(project.id, data)
        await self._materialize_test_run_test_cases(
            test_run.id,
            cases,
            global_configurations=data.configurations,
            configuration_map=data.configuration_map,
            default_assignee=data.test_case_assignee or data.assignee,
        )

        # 重建脚本作业
        if data.scripts:
            jobs: list[TestRunScriptJob] = []
            for i, sel in enumerate(data.scripts):
                jobs.append(
                    TestRunScriptJob(
                        test_run_id=test_run.id,
                        script_type=sel.script_type,
                        script_id=UUID(sel.script_id),
                        script_identifier=sel.script_identifier or "",
                        script_name=sel.script_name,
                        execution_order=sel.execution_order or i,
                        execution_mode=sel.execution_mode
                        or (data.execution_mode or ExecutionMode.SEQUENTIAL),
                        execution_config=sel.execution_config,
                        status=JobStatus.PENDING,
                        max_retries=0,
                    )
                )
            await self.script_job_repo.create_many(jobs)
            await self.repo.update_counts_from_jobs(test_run.id)
        else:
            await self.repo.update_counts(test_run.id)
        # update_counts* 直接执行 UPDATE 会使当前 session 中的 test_run 对象过期，
        # 重新查询获取干净对象再返回，避免 async session 中访问过期属性触发 MissingGreenlet。
        test_run = await self.repo.get_by_id(test_run.id)
        return await self._to_info(test_run, project_identifier)

    async def delete(
        self,
        project_identifier: str,
        test_run_identifier: str,
    ) -> None:
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)
        await self.repo.delete(test_run)

    async def close_test_run(
        self,
        project_identifier: str,
        test_run_identifier: str,
        data: CloseTestRunRequest,
    ) -> TestRunInfo:
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        test_run.active_state = data.active_state or TestRunActiveState.CLOSED
        if test_run.active_state == TestRunActiveState.CLOSED:
            test_run.closed_at = datetime.now(timezone.utc)
            test_run.run_state = TestRunState.CLOSED
        else:
            test_run.closed_at = None

        test_run = await self.repo.update(test_run)
        return await self._to_info(test_run, project_identifier)

    async def get_test_cases(
        self,
        project_identifier: str,
        test_run_identifier: str,
        *,
        status: Optional[TestResultStatus] = None,
        assignee: Optional[str] = None,
        search: Optional[str] = None,
        minify: bool = False,
        fetch_steps: bool = False,
        offset: int = 0,
        limit: int = 30,
    ) -> tuple[
        list[Union[TestRunTestCaseInfo, TestRunTestCaseMinifiedInfo]], int
    ]:
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        # fetch_steps 优先于 minify;按 BS 行为禁用分页
        if fetch_steps:
            items = await self.tc_repo.get_all_for_run(
                test_run.id, with_steps=True
            )
            total = len(items)
            result = [
                await self._to_test_run_test_case_info(i, fetch_steps=True)
                for i in items
            ]
            return result, total

        items, total = await self.tc_repo.get_list(
            test_run_id=test_run.id,
            status=status,
            assignee=assignee,
            search=search,
            with_steps=False,
            offset=offset,
            limit=limit,
        )

        if minify:
            return [self._to_minified_test_case(i) for i in items], total

        result = [
            await self._to_test_run_test_case_info(i) for i in items
        ]
        return result, total

    async def add_test_cases(
        self,
        project_identifier: str,
        test_run_identifier: str,
        data: AddTestCasesRequest,
    ) -> TestRunInfo:
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        resolved: list[TestCase] = []
        for ident in data.test_cases:
            tc = await self.test_case_repo.get_by_identifier(ident)
            if tc and tc.project_id == project.id:
                resolved.append(tc)

        await self._materialize_test_run_test_cases(
            test_run.id,
            resolved,
            global_configurations=data.configuration_ids,
            configuration_map=None,
            default_assignee=(
                data.assignee
                or test_run.test_case_assignee
                or test_run.assignee
            ),
        )

        await self.repo.update_counts(test_run.id)
        # update_counts 直接执行 UPDATE 会使当前 session 中的 test_run 对象过期，
        # 重新查询获取干净对象再返回，避免 async session 中访问过期属性触发 MissingGreenlet。
        test_run = await self.repo.get_by_id(test_run.id)
        return await self._to_info(test_run, project_identifier)

    async def remove_test_cases(
        self,
        project_identifier: str,
        test_run_identifier: str,
        data: RemoveTestCasesRequest,
    ) -> TestRunInfo:
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        test_case_ids: list[UUID] = []
        for ident in data.test_cases:
            tc = await self.test_case_repo.get_by_identifier(ident)
            if tc and tc.project_id == project.id:
                test_case_ids.append(tc.id)

        if test_case_ids:
            await self.tc_repo.remove_test_cases(
                test_run.id,
                test_case_ids,
                data.configuration_ids,
            )

        await self.repo.update_counts(test_run.id)
        # update_counts 直接执行 UPDATE 会使当前 session 中的 test_run 对象过期，
        # 重新查询获取干净对象再返回，避免 async session 中访问过期属性触发 MissingGreenlet。
        test_run = await self.repo.get_by_id(test_run.id)
        return await self._to_info(test_run, project_identifier)

    async def assign(
        self,
        project_identifier: str,
        test_run_identifier: str,
        data: TestRunAssignRequest,
    ) -> TestRunInfo:
        """POST /test-runs/{id}/assign"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        assignments: list[dict] = []
        for item in data.assign_to:
            tc = await self.test_case_repo.get_by_identifier(item.test_case_id)
            if tc and tc.project_id == project.id:
                assignments.append(
                    {
                        "test_case_id": tc.id,
                        "configuration_id": item.configuration_id,
                        "assignee": item.assignee,
                    }
                )

        if assignments:
            await self.tc_repo.update_assignees(test_run.id, assignments)

        await self.session.refresh(test_run)
        return await self._to_info(test_run, project_identifier)

    # 兼容旧名
    async def update_assignees(
        self,
        project_identifier: str,
        test_run_identifier: str,
        data: TestRunAssignRequest,
    ) -> TestRunInfo:
        return await self.assign(
            project_identifier, test_run_identifier, data
        )

    # ============ 脚本作业管理 ============

    async def get_script_jobs(
        self,
        project_identifier: str,
        test_run_identifier: str,
        script_type: Optional[ScriptType] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """获取测试运行的脚本作业列表"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        offset = (page - 1) * page_size
        jobs, total = await self.script_job_repo.get_by_test_run(
            test_run.id,
            script_type=script_type,
            offset=offset,
            limit=page_size,
        )

        return {
            "items": [self._to_script_job_info(j) for j in jobs],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def add_script_jobs(
        self,
        project_identifier: str,
        test_run_identifier: str,
        jobs_data: list[TestRunScriptJobCreate],
    ) -> TestRunInfo:
        """添加脚本作业到测试运行"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        # 获取当前最大执行顺序
        existing_jobs, _ = await self.script_job_repo.get_by_test_run(test_run.id)
        max_order = max((j.execution_order for j in existing_jobs), default=-1)

        jobs: list[TestRunScriptJob] = []
        for i, data in enumerate(jobs_data):
            jobs.append(
                TestRunScriptJob(
                    test_run_id=test_run.id,
                    script_type=data.script_type,
                    script_id=UUID(data.script_id),
                    script_identifier=data.script_identifier or "",
                    script_name=data.script_name,
                    execution_order=data.execution_order or (max_order + 1 + i),
                    execution_mode=data.execution_mode
                    or test_run.execution_mode
                    or ExecutionMode.SEQUENTIAL,
                    execution_config=data.execution_config,
                    status=JobStatus.PENDING,
                    max_retries=data.max_retries,
                )
            )

        await self.script_job_repo.create_many(jobs)
        await self.session.refresh(test_run)
        return await self._to_info(test_run, project_identifier)

    async def remove_script_job(
        self,
        project_identifier: str,
        test_run_identifier: str,
        job_id: str,
    ) -> TestRunInfo:
        """从测试运行移除脚本作业"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        job = await self.script_job_repo.get_by_id(UUID(job_id))
        if not job or job.test_run_id != test_run.id:
            raise NotFoundException(resource_type="脚本作业", resource_id=job_id)

        await self.script_job_repo.delete(job)
        await self.session.refresh(test_run)
        return await self._to_info(test_run, project_identifier)

    async def get_job_report_url(
        self,
        project_identifier: str,
        test_run_identifier: str,
        job_id: str,
    ) -> dict:
        """获取脚本作业报告的预签名 URL"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        job = await self.script_job_repo.get_by_id(UUID(job_id))
        if not job or job.test_run_id != test_run.id:
            raise NotFoundException(resource_type="脚本作业", resource_id=job_id)

        if not job.report_path:
            raise NotFoundException(
                resource_type="报告", resource_id=job_id,
                message="该作业暂无报告"
            )

        from app.config.minio_client import MinIOClient
        url = MinIOClient.get_presigned_url(job.report_path, expires=timedelta(hours=1))
        return {"url": url, "expires_in": 3600}

    async def retry_job(
        self,
        project_identifier: str,
        test_run_identifier: str,
        job_id: str,
    ) -> TestRunScriptJobInfo:
        """重试单个脚本作业：重置为 pending 并在后台真正重新执行该作业。"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        job = await self.script_job_repo.get_by_id(UUID(job_id))
        if not job or job.test_run_id != test_run.id:
            raise NotFoundException(resource_type="脚本作业", resource_id=job_id)

        # 只允许重试 failed / skipped / cancelled 状态的作业
        if job.status not in (JobStatus.FAILED, JobStatus.SKIPPED, JobStatus.CANCELLED):
            raise BadRequestException(
                message=f"当前作业状态为 {job.status.value}，不允许重试"
            )

        # 原子抢占执行权：运行正在执行中时拒绝重试，避免并发执行互相覆盖
        acquired = await self.repo.try_mark_in_progress(test_run.id)
        if not acquired:
            raise BadRequestException(
                message="测试运行正在执行中，请等待当前执行结束后再重试"
            )

        # 重置状态为 pending
        await self.script_job_repo.update_status(
            job.id,
            JobStatus.PENDING,
            retry_count=job.retry_count + 1,
            error_message=None,
            result_summary=None,
            report_path=None,
            duration_ms=None,
            started_at=None,
            completed_at=None,
        )
        await self.session.commit()

        # 后台真正重新执行该作业（任务纳入跟踪，防止被 GC）
        _spawn_tracked(
            self._retry_jobs_background(
                project_identifier=project_identifier,
                test_run_identifier=test_run_identifier,
                job_ids=[job.id],
            ),
            label=f"retry-job-{test_run.identifier}-{job_id}",
        )

        return self._to_script_job_info(job)

    async def _retry_jobs_background(
        self,
        project_identifier: str,
        test_run_identifier: str,
        job_ids: list[UUID],
    ) -> None:
        """后台重新执行指定的脚本作业（重试场景）。

        使用独立数据库会话；执行完成后由引擎基于全部作业重新定案。
        """
        async with async_session_factory() as session:
            service = TestRunService(session, self.mongodb)
            try:
                project = await service._get_project_by_identifier(project_identifier)
                test_run = await service._require_test_run(
                    project.id, test_run_identifier
                )
                execution_service = TestExecutionService(service.mongodb)
                await execution_service.execute_jobs(test_run.id, job_ids)
            except asyncio.CancelledError:
                logger.warning(
                    "[TestRunService] 后台重试执行被取消: %s", test_run_identifier
                )
                await self._mark_run_rejected(
                    service, project_identifier, test_run_identifier, session,
                    reason="重试执行被取消",
                )
                raise
            except Exception:
                logger.exception("[TestRunService] 后台重试执行失败")
                await self._mark_run_rejected(
                    service, project_identifier, test_run_identifier, session,
                    reason="重试执行异常",
                )

    async def get_job_logs(
        self,
        project_identifier: str,
        test_run_identifier: str,
        job_id: str,
    ) -> dict:
        """获取脚本作业的 stdout/stderr 日志"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        job = await self.script_job_repo.get_by_id(UUID(job_id))
        if not job or job.test_run_id != test_run.id:
            raise NotFoundException(resource_type="脚本作业", resource_id=job_id)

        return {
            "stdout": job.stdout or "",
            "stderr": job.stderr or "",
        }

    async def batch_retry_jobs(
        self,
        project_identifier: str,
        test_run_identifier: str,
        job_ids: list[str],
    ) -> list[TestRunScriptJobInfo]:
        """批量重试脚本作业：重置为 pending 并在后台真正重新执行这些作业。"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        # 先筛选出可重试的作业
        retryable: list[TestRunScriptJob] = []
        for job_id in job_ids:
            job = await self.script_job_repo.get_by_id(UUID(job_id))
            if not job or job.test_run_id != test_run.id:
                continue
            if job.status not in (
                JobStatus.FAILED,
                JobStatus.SKIPPED,
                JobStatus.CANCELLED,
            ):
                continue
            retryable.append(job)

        if not retryable:
            return []

        # 原子抢占执行权：运行正在执行中时拒绝批量重试
        acquired = await self.repo.try_mark_in_progress(test_run.id)
        if not acquired:
            raise BadRequestException(
                message="测试运行正在执行中，请等待当前执行结束后再重试"
            )

        retried: list[TestRunScriptJobInfo] = []
        for job in retryable:
            await self.script_job_repo.update_status(
                job.id,
                JobStatus.PENDING,
                retry_count=job.retry_count + 1,
                error_message=None,
                result_summary=None,
                report_path=None,
                stdout=None,
                stderr=None,
                duration_ms=None,
                started_at=None,
                completed_at=None,
            )
            retried.append(self._to_script_job_info(job))

        await self.session.commit()

        # 后台统一重新执行这批作业（任务纳入跟踪，防止被 GC）
        _spawn_tracked(
            self._retry_jobs_background(
                project_identifier=project_identifier,
                test_run_identifier=test_run_identifier,
                job_ids=[job.id for job in retryable],
            ),
            label=f"batch-retry-{test_run.identifier}",
        )

        return retried

    async def get_script_history(
        self,
        project_identifier: str,
        script_type: ScriptType,
        script_id: str,
        limit: int = 30,
    ) -> dict:
        """获取脚本执行历史趋势（成功率统计）"""
        await self._get_project_by_identifier(project_identifier)

        runs: list[Any] = []
        total_attr = "total_tests"
        passed_attr = "passed_tests"
        failed_attr = "failed_tests"
        skipped_attr = "skipped_tests"

        if script_type == ScriptType.API_TEST:
            api_run_repo = APITestRunRepository(self.session)
            runs, _ = await api_run_repo.get_by_api_test(
                UUID(script_id), offset=0, limit=limit
            )
        elif script_type == ScriptType.WEB_TEST:
            web_run_repo = WebTestRunRepository(self.session)
            runs, _ = await web_run_repo.get_by_web_test(
                UUID(script_id), offset=0, limit=limit
            )
        elif script_type == ScriptType.SCENARIO:
            stmt = (
                select(ScenarioRun)
                .where(ScenarioRun.scenario_id == UUID(script_id))
                .order_by(ScenarioRun.created_at.desc())
                .offset(0)
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            runs = list(result.scalars().all())
            total_attr = "total_steps"
            passed_attr = "passed_steps"
            failed_attr = "failed_steps"
            skipped_attr = "skipped_steps"
        else:
            # 兜底：按 TestRunScriptJob 查询
            jobs = await self.script_job_repo.get_history_by_script(
                script_type=script_type,
                script_id=UUID(script_id),
                limit=limit,
            )
            history = []
            for job in jobs:
                history.append({
                    "job_id": str(job.id),
                    "test_run_id": str(job.test_run_id),
                    "status": job.status.value,
                    "result_summary": job.result_summary,
                    "duration_ms": job.duration_ms,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                })

            total = len(jobs)
            passed = sum(1 for j in jobs if j.status == JobStatus.COMPLETED)
            failed = sum(1 for j in jobs if j.status == JobStatus.FAILED)
            skipped = sum(1 for j in jobs if j.status == JobStatus.SKIPPED)
            cancelled = sum(1 for j in jobs if j.status == JobStatus.CANCELLED)
            success_rate = round((passed / total) * 100, 1) if total > 0 else 0

            return {
                "script_type": script_type.value,
                "script_id": script_id,
                "total_runs": total,
                "success_rate": success_rate,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "cancelled": cancelled,
                "history": history,
            }

        history = []
        for run in runs:
            started_at = getattr(run, "started_at", None) or getattr(run, "created_at", None)
            completed_at = getattr(run, "completed_at", None) or getattr(run, "updated_at", None)
            history.append({
                "job_id": str(run.id),
                "test_run_id": None,
                "status": run.status,
                "result_summary": {
                    "total": getattr(run, total_attr) or 0,
                    "passed": getattr(run, passed_attr) or 0,
                    "failed": getattr(run, failed_attr) or 0,
                    "skipped": getattr(run, skipped_attr) or 0,
                },
                "duration_ms": getattr(run, "duration_ms", None),
                "started_at": started_at.isoformat() if started_at else None,
                "completed_at": completed_at.isoformat() if completed_at else None,
            })

        total = len(history)
        passed = sum(1 for h in history if h["status"] == "completed")
        failed = sum(1 for h in history if h["status"] == "failed")
        skipped = 0
        cancelled = sum(1 for h in history if h["status"] == "cancelled")
        success_rate = round((passed / total) * 100, 1) if total > 0 else 0

        return {
            "script_type": script_type.value,
            "script_id": script_id,
            "total_runs": total,
            "success_rate": success_rate,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "cancelled": cancelled,
            "history": history,
        }

    async def get_script_benchmark(
        self,
        project_identifier: str,
        script_type: ScriptType,
        script_id: str,
        limit: int = 30,
    ) -> dict:
        """获取脚本性能基准（耗时趋势）"""
        await self._get_project_by_identifier(project_identifier)

        jobs = await self.script_job_repo.get_history_by_script(
            script_type=script_type,
            script_id=UUID(script_id),
            limit=limit,
        )

        runs = []
        durations = []
        for job in jobs:
            if job.duration_ms is not None:
                runs.append({
                    "job_id": str(job.id),
                    "status": job.status.value,
                    "duration_ms": job.duration_ms,
                    "date": job.completed_at.isoformat() if job.completed_at else (
                        job.started_at.isoformat() if job.started_at else None
                    ),
                })
                durations.append(job.duration_ms)

        avg = round(sum(durations) / len(durations), 0) if durations else 0
        min_d = min(durations) if durations else 0
        max_d = max(durations) if durations else 0
        median = sorted(durations)[len(durations) // 2] if durations else 0

        return {
            "script_type": script_type.value,
            "script_id": script_id,
            "total_runs": len(runs),
            "avg_duration_ms": avg,
            "min_duration_ms": min_d,
            "max_duration_ms": max_d,
            "median_duration_ms": median,
            "runs": runs,
        }

    async def get_job_report_preview(
        self,
        project_identifier: str,
        test_run_identifier: str,
        job_id: str,
    ) -> str:
        """获取脚本作业 HTML 报告的内嵌预览内容（解压 ZIP 返回 index.html）"""
        import zipfile
        import tempfile

        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        job = await self.script_job_repo.get_by_id(UUID(job_id))
        if not job or job.test_run_id != test_run.id:
            raise NotFoundException(resource_type="脚本作业", resource_id=job_id)

        if not job.report_path:
            raise NotFoundException(
                resource_type="报告", resource_id=job_id, message="该作业暂无报告"
            )

        # 从 MinIO 下载 ZIP
        zip_bytes = MinIOClient.download_file(job.report_path)

        # 解压到临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            zip_file = tmp_path / "report.zip"
            zip_file.write_bytes(zip_bytes)

            with zipfile.ZipFile(zip_file, 'r') as zf:
                zf.extractall(tmp_path)

            # 查找 index.html
            index_html = tmp_path / "index.html"
            if not index_html.exists():
                # 可能在子目录中
                for subdir in tmp_path.iterdir():
                    if subdir.is_dir():
                        candidate = subdir / "index.html"
                        if candidate.exists():
                            index_html = candidate
                            break

            if not index_html.exists():
                raise NotFoundException(
                    resource_type="报告", resource_id=job_id, message="报告中未找到 index.html"
                )

            html = index_html.read_text(encoding="utf-8")

            # 根据 index.html 在 ZIP 包中的实际位置计算 base href。
            # 当前 ZIP 把 playwright-report 目录打包为 html/ 前缀，因此 index.html
            # 位于 html/index.html；若 base href 仍指向 report-preview/，浏览器解析
            # 相对路径 data/xxx.png 时会落到 report-preview/data/，而实际资源在
            # report-preview/html/data/，导致截图/视频/trace 404。
            try:
                rel_index_dir = index_html.relative_to(tmp_path).parent.as_posix()
            except ValueError:
                rel_index_dir = ""

            base_href = (
                f"/api/v2/projects/{project_identifier}"
                f"/test-runs/{test_run_identifier}"
                f"/script-jobs/{job_id}/report-preview/"
            )
            if rel_index_dir:
                base_href += f"{rel_index_dir}/"

            if "<head>" in html:
                html = html.replace("<head>", f'<head><base href="{base_href}">', 1)
            elif "<HEAD>" in html:
                html = html.replace("<HEAD>", f'<HEAD><base href="{base_href}">', 1)
            else:
                html = f'<!DOCTYPE html><base href="{base_href}">' + html

            return html

    async def get_job_report_resource(
        self,
        project_identifier: str,
        test_run_identifier: str,
        job_id: str,
        resource_path: str,
    ) -> tuple[bytes, str]:
        """从 ZIP 报告中解压指定资源文件返回"""
        import zipfile
        import tempfile
        import mimetypes

        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        job = await self.script_job_repo.get_by_id(UUID(job_id))
        if not job or job.test_run_id != test_run.id:
            raise NotFoundException(resource_type="脚本作业", resource_id=job_id)

        if not job.report_path:
            raise NotFoundException(
                resource_type="报告", resource_id=job_id, message="该作业暂无报告"
            )

        zip_bytes = MinIOClient.download_file(job.report_path)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            zip_file = tmp_path / "report.zip"
            zip_file.write_bytes(zip_bytes)

            with zipfile.ZipFile(zip_file, 'r') as zf:
                # 查找匹配的资源文件（支持子目录）
                resource_file = None
                for name in zf.namelist():
                    if name.endswith('/') :
                        continue
                    # 去除可能的顶级目录前缀
                    clean_name = name.split('/', 1)[1] if '/' in name else name
                    if clean_name == resource_path or name == resource_path:
                        resource_file = zf.read(name)
                        break

                if resource_file is None:
                    raise NotFoundException(
                        resource_type="报告资源", resource_id=resource_path
                    )

                content_type = mimetypes.guess_type(resource_path)[0] or "application/octet-stream"
                return resource_file, content_type

    async def map_jobs_to_test_cases(
        self,
        project_identifier: str,
        test_run_identifier: str,
    ) -> TestRunInfo:
        """将 script_job 的执行结果反向映射到 test_run_cases 的状态"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        # 获取所有脚本作业
        jobs, _ = await self.script_job_repo.get_by_test_run(test_run.id)

        # 汇总 job 结果
        overall_failed = any(j.status == JobStatus.FAILED for j in jobs)
        overall_passed = all(j.status == JobStatus.COMPLETED for j in jobs)

        # 更新所有关联的 test_run_cases
        cases = await self.tc_repo.get_all_for_run(test_run.id, with_steps=False)
        for case in cases:
            if overall_failed:
                await self.tc_repo.update_status(case.id, TestResultStatus.FAILED)
            elif overall_passed:
                await self.tc_repo.update_status(case.id, TestResultStatus.PASSED)
            else:
                # 部分成功部分失败 → 根据具体情况判断
                # 如果有 running/pending 的 job，设为 IN_PROGRESS
                has_running = any(j.status == JobStatus.RUNNING for j in jobs)
                if has_running:
                    await self.tc_repo.update_status(case.id, TestResultStatus.IN_PROGRESS)
                else:
                    await self.tc_repo.update_status(case.id, TestResultStatus.SKIPPED)

        # 更新 TestRun 统计
        await self.repo.update_counts_from_jobs(test_run.id)
        # update_counts_from_jobs 直接执行 UPDATE 会使当前 session 中的 test_run 对象过期，
        # 重新查询获取干净对象再返回，避免 async session 中访问过期属性触发 MissingGreenlet。
        test_run = await self.repo.get_by_id(test_run.id)
        return await self._to_info(test_run, project_identifier)

    # ============ 调度管理 ============

    async def get_schedules(
        self,
        project_identifier: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取项目的定时调度列表"""
        project = await self._get_project_by_identifier(project_identifier)
        offset = (page - 1) * page_size
        schedules, total = await self.schedule_repo.get_by_project(
            project.id, offset=offset, limit=page_size
        )
        return {
            "items": [self._to_schedule_info(s) for s in schedules],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_schedule(
        self,
        project_identifier: str,
        schedule_id: str,
    ) -> TestRunScheduleInfo:
        """获取定时调度详情"""
        project = await self._get_project_by_identifier(project_identifier)
        schedule = await self.schedule_repo.get_by_id(UUID(schedule_id))
        if not schedule or schedule.project_id != project.id:
            raise NotFoundException(resource_type="定时调度", resource_id=schedule_id)
        return self._to_schedule_info(schedule)

    async def create_schedule(
        self,
        project_identifier: str,
        data: TestRunScheduleCreate,
    ) -> TestRunScheduleInfo:
        """创建定时调度"""
        project = await self._get_project_by_identifier(project_identifier)

        schedule = TestRunSchedule(
            project_id=project.id,
            name=data.name,
            description=data.description,
            test_run_template=data.test_run_template,
            trigger_type=data.trigger_type,
            trigger_config=data.trigger_config,
            is_enabled=data.is_enabled,
        )

        # 计算下次执行时间
        if schedule.is_enabled:
            from app.services.scheduler_service import get_scheduler_service

            scheduler = get_scheduler_service()
            schedule.next_run_at = scheduler.compute_next_run_at(
                schedule.trigger_type.value,
                schedule.trigger_config,
            )

        schedule = await self.schedule_repo.create(schedule)
        await self.session.commit()

        # 同步到 APScheduler
        from app.services.scheduler_service import get_scheduler_service
        get_scheduler_service().add_schedule(schedule)

        return self._to_schedule_info(schedule)

    async def update_schedule(
        self,
        project_identifier: str,
        schedule_id: str,
        data: TestRunScheduleUpdate,
    ) -> TestRunScheduleInfo:
        """更新定时调度"""
        project = await self._get_project_by_identifier(project_identifier)
        schedule = await self.schedule_repo.get_by_id(UUID(schedule_id))
        if not schedule or schedule.project_id != project.id:
            raise NotFoundException(resource_type="定时调度", resource_id=schedule_id)

        payload = data.model_dump(exclude_unset=True)
        for key, value in payload.items():
            if hasattr(schedule, key):
                setattr(schedule, key, value)

        # 触发器或启用状态变更后，重新计算下次执行时间
        trigger_changed = (
            "trigger_type" in payload or "trigger_config" in payload
        )
        enabled_changed = "is_enabled" in payload
        if trigger_changed or enabled_changed:
            from app.services.scheduler_service import get_scheduler_service

            scheduler = get_scheduler_service()
            if schedule.is_enabled:
                schedule.next_run_at = scheduler.compute_next_run_at(
                    schedule.trigger_type.value,
                    schedule.trigger_config,
                )
            else:
                schedule.next_run_at = None

        schedule = await self.schedule_repo.update(schedule)
        await self.session.commit()

        # 同步到 APScheduler
        from app.services.scheduler_service import get_scheduler_service
        svc = get_scheduler_service()
        if schedule.is_enabled:
            svc.add_schedule(schedule)
        else:
            svc.pause_schedule(str(schedule.id))

        return self._to_schedule_info(schedule)

    async def delete_schedule(
        self,
        project_identifier: str,
        schedule_id: str,
    ) -> None:
        """删除定时调度"""
        project = await self._get_project_by_identifier(project_identifier)
        schedule = await self.schedule_repo.get_by_id(UUID(schedule_id))
        if not schedule or schedule.project_id != project.id:
            raise NotFoundException(resource_type="定时调度", resource_id=schedule_id)
        await self.schedule_repo.delete(schedule)
        await self.session.commit()

        # 从 APScheduler 移除
        from app.services.scheduler_service import get_scheduler_service
        get_scheduler_service().remove_schedule(schedule_id)

    async def trigger_schedule(
        self,
        project_identifier: str,
        schedule_id: str,
    ) -> dict:
        """立即手动触发一次调度，生成 TestRun 并执行"""
        project = await self._get_project_by_identifier(project_identifier)
        schedule = await self.schedule_repo.get_by_id(UUID(schedule_id))
        if not schedule or schedule.project_id != project.id:
            raise NotFoundException(resource_type="定时调度", resource_id=schedule_id)

        if not schedule.is_enabled:
            raise BadRequestException(message="调度已禁用，无法触发")

        # 幂等：最近 1 分钟内已触发过则返回已有 run
        recent_run = await self.repo.get_recent_by_schedule(schedule.id, seconds=60)
        if recent_run:
            return {
                "status": "skipped",
                "reason": "recent_run_exists",
                "test_run_id": str(recent_run.id),
                "identifier": recent_run.identifier,
                "message": "最近 1 分钟内已触发过该调度",
            }

        # 幂等：有执行中的 run 则跳过
        in_progress_run = await self.repo.get_in_progress_by_schedule(schedule.id)
        if in_progress_run:
            return {
                "status": "skipped",
                "reason": "in_progress",
                "test_run_id": str(in_progress_run.id),
                "identifier": in_progress_run.identifier,
                "message": "该调度存在执行中的测试运行",
            }

        template = schedule.test_run_template or {}
        test_run = await self.create(
            project_identifier,
            TestRunCreate(
                name=template.get("name", f"定时执行 - {schedule.name}"),
                description=template.get("description", schedule.description),
                execution_mode=template.get("execution_mode", "sequential"),
                max_concurrency=template.get("max_concurrency", 5),
                failure_policy=template.get("failure_policy", "continue"),
                environment_id=template.get("environment_id"),
                scripts=template.get("scripts", []),
                trigger_type=TriggerType.SCHEDULED,
                scheduled_by=str(schedule.id),
            ),
        )

        await self.execute_test_run(project_identifier, test_run.identifier)

        # 更新调度上次执行时间，并重新计算下次执行时间
        schedule.last_run_at = datetime.now(timezone.utc)
        from app.services.scheduler_service import get_scheduler_service

        scheduler = get_scheduler_service()
        schedule.next_run_at = scheduler.compute_next_run_at(
            schedule.trigger_type.value,
            schedule.trigger_config,
        )
        await self.session.commit()

        return {
            "status": "triggered",
            "test_run_id": str(test_run.id),
            "identifier": test_run.identifier,
            "message": "调度已触发",
        }

    async def get_schedule_runs(
        self,
        project_identifier: str,
        schedule_id: str,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取某调度产生的执行历史"""
        project = await self._get_project_by_identifier(project_identifier)
        schedule = await self.schedule_repo.get_by_id(UUID(schedule_id))
        if not schedule or schedule.project_id != project.id:
            raise NotFoundException(resource_type="定时调度", resource_id=schedule_id)

        offset = (page - 1) * page_size
        test_runs, total = await self.repo.get_list(
            project_id=project.id,
            scheduled_by=schedule.id,
            include_closed=True,
            offset=offset,
            limit=page_size,
        )

        schedule_ids = {tr.scheduled_by for tr in test_runs if tr.scheduled_by}
        schedule_names = await self._batch_schedule_names(schedule_ids)

        return {
            "items": [
                self._to_list_info(tr, schedule_names=schedule_names)
                for tr in test_runs
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ============ 测试运行执行 ============

    async def execute_test_run(
        self,
        project_identifier: str,
        test_run_identifier: str,
    ) -> dict:
        """
        执行测试运行：使用统一执行引擎协调所有脚本作业的执行。
        支持 script_jobs（新方式）和 test_case 关联（旧方式）两种模式。

        采用 fire-and-forget 模式：立即更新状态为 IN_PROGRESS 并返回，
        实际执行在后台任务中完成，前端通过轮询获取最新状态。
        """
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self._require_test_run(project.id, test_run_identifier)

        # 原子抢占执行权：仅当运行不在进行中且处于活跃状态时成功。
        # 用单条带条件 UPDATE 消除"读状态→判断→写状态"之间的并发竞态；
        # 已关闭（active_state=closed）的运行也会被拦截，无法在 API 层执行。
        acquired = await self.repo.try_mark_in_progress(test_run.id)
        await self.session.commit()
        if not acquired:
            return {
                "status": "in_progress",
                "test_run_id": str(test_run.id),
                "identifier": test_run.identifier,
                "message": "测试运行已在执行中或已关闭",
            }

        # 在后台执行测试，不阻塞 HTTP 响应（任务纳入跟踪，防止被 GC）
        _spawn_tracked(
            self._execute_test_run_background(
                project_identifier=project_identifier,
                test_run_identifier=test_run_identifier,
            ),
            label=f"execute-run-{test_run.identifier}",
        )

        return {
            "status": "in_progress",
            "test_run_id": str(test_run.id),
            "identifier": test_run.identifier,
            "message": "测试运行已提交到后台执行",
        }

    async def _execute_test_run_background(
        self,
        project_identifier: str,
        test_run_identifier: str,
    ) -> None:
        """
        后台执行测试运行。

        使用独立的数据库会话，避免 HTTP 请求结束后会话被关闭导致的问题。
        """
        async with async_session_factory() as session:
            service = TestRunService(session, self.mongodb)
            try:
                project = await service._get_project_by_identifier(project_identifier)
                test_run = await service._require_test_run(project.id, test_run_identifier)

                # 检查是否有脚本作业
                jobs, _ = await service.script_job_repo.get_by_test_run(test_run.id)

                if jobs:
                    # 新方式：使用统一执行引擎执行脚本作业
                    execution_service = TestExecutionService(service.mongodb)
                    await execution_service.execute_run(test_run.id)
                else:
                    # 旧方式：遍历 test_case 关联执行（兼容模式）
                    await service._execute_legacy(test_run)
            except asyncio.CancelledError:
                # 任务被取消（如服务关闭）：CancelledError 是 BaseException，
                # 不会被下面的 except Exception 接住，需单独处理并置为终态，
                # 避免运行永远停留在 IN_PROGRESS。
                logger.warning(
                    "[TestRunService] 后台执行被取消: %s", test_run_identifier
                )
                await self._mark_run_rejected(
                    service, project_identifier, test_run_identifier, session,
                    reason="执行被取消",
                )
                raise
            except Exception:
                logger.exception("[TestRunService] 后台执行测试运行失败")
                await self._mark_run_rejected(
                    service, project_identifier, test_run_identifier, session,
                )

    async def _mark_run_rejected(
        self,
        service: "TestRunService",
        project_identifier: str,
        test_run_identifier: str,
        session: AsyncSession,
        reason: str = "后台执行异常",
    ) -> None:
        """将测试运行置为 REJECTED 终态（后台执行失败/取消时的兜底）。"""
        try:
            project = await service._get_project_by_identifier(project_identifier)
            test_run = await service._require_test_run(project.id, test_run_identifier)
            test_run.run_state = TestRunState.REJECTED
            await service.repo.update(test_run)
            await service.repo.update_counts_from_jobs(test_run.id)
            await session.commit()
        except Exception as inner_e:
            logger.error(
                "[TestRunService] 置为失败状态也失败了(%s): %s", reason, inner_e
            )

    async def _execute_legacy(self, test_run: TestRun) -> dict:
        """旧模式执行：遍历 test_case 关联执行 API/Web 测试"""
        from app.services.api_test_executor import APITestExecutor
        from app.repositories.api_test_repo import APITestRunRepository

        # 更新测试运行状态为进行中
        test_run.run_state = TestRunState.IN_PROGRESS
        await self.repo.update(test_run)
        await self.session.commit()

        # 获取所有关联的测试用例
        cases = await self.tc_repo.get_all_for_run(test_run.id, with_steps=False)

        executed_count = 0
        passed_count = 0
        failed_count = 0
        skipped_count = 0
        infra_error_count = 0

        for case in cases:
            # 加载测试用例的 api_tests 和 web_tests 关系
            await self.session.refresh(case, ["test_case"])
            await self.session.refresh(case.test_case, ["api_tests", "web_tests"])

            case_status = TestResultStatus.PASSED
            has_automated_tests = False
            any_failed = False
            case_infra_error = False

            # 执行关联的 API 测试
            for api_test in case.test_case.api_tests:
                has_automated_tests = True
                try:
                    executor = APITestExecutor(self.session, self.mongodb)
                    run_id = await executor.execute_test(api_test.id)
                    api_run = await self._wait_for_api_test_run(UUID(run_id))

                    if api_run.status == "completed":
                        if api_run.failed_tests > 0:
                            any_failed = True
                        elif api_run.passed_tests > 0:
                            pass  # passed
                        else:
                            case_status = TestResultStatus.SKIPPED
                            skipped_count += 1
                    else:
                        any_failed = True
                        case_infra_error = True

                    executed_count += 1
                except Exception:
                    any_failed = True
                    case_infra_error = True
                    executed_count += 1

            # TODO: Web 测试执行（Phase 4 实现）
            for _web_test in case.test_case.web_tests:
                has_automated_tests = True

            if has_automated_tests:
                if any_failed:
                    case_status = TestResultStatus.FAILED
                    failed_count += 1
                elif case_status != TestResultStatus.SKIPPED:
                    passed_count += 1
                else:
                    skipped_count += 1

                if case_infra_error:
                    infra_error_count += 1

                await self.tc_repo.update_status(case.id, case_status)
            else:
                case_status = TestResultStatus.SKIPPED
                skipped_count += 1
                await self.tc_repo.update_status(case.id, case_status)

        # 更新 TestRun 计数
        await self.repo.update_counts(test_run.id)

        # 执行完成后更新状态
        test_run = await self.repo.get_by_id(test_run.id)
        if infra_error_count > 0:
            test_run.run_state = TestRunState.REJECTED
        elif failed_count > 0:
            test_run.run_state = TestRunState.DONE_WITH_FAILURES
        else:
            test_run.run_state = TestRunState.DONE
        await self.repo.update(test_run)
        await self.session.commit()

        return {
            "test_run_id": str(test_run.id),
            "identifier": test_run.identifier,
            "executed": executed_count,
            "passed": passed_count,
            "failed": failed_count,
            "skipped": skipped_count,
        }

    async def _wait_for_api_test_run(
        self,
        run_id: UUID,
        timeout: int = 300,
        interval: float = 2.0,
    ) -> APITestRun:
        """轮询等待 API 测试运行完成"""
        repo = APITestRunRepository(self.session)
        for _ in range(int(timeout / interval)):
            run = await repo.get_by_id(run_id)
            if run and run.status in ("completed", "failed", "cancelled"):
                return run
            await asyncio.sleep(interval)
        raise TimeoutError(f"API 测试运行 {run_id} 执行超时")
