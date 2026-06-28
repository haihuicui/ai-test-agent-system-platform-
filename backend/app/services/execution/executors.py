"""
脚本执行器注册表与具体实现

支持 Playwright、场景测试、Web 测试等执行器，按 ScriptType 自动分发。
"""

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from app.config.database import async_session_factory
from app.config.minio_client import MinIOClient
from app.config.settings import settings
from app.repositories.api_test_repo import APITestRepository, APITestRunRepository
from app.schemas.enums import JobStatus
from app.services.execution.models import ExecutionResult
from app.services.execution.runner import PlaywrightRunner

import asyncio
import tempfile
import zipfile
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.test_scenario import ScenarioRun, ScenarioStepResult, TestScenario
from app.services.execution.scenario_report import generate_scenario_report
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VFZZMk53PT06N2NmYjQwOGI=

logger = logging.getLogger(__name__)


class ScriptExecutor(ABC):
    """脚本执行器抽象基类"""

    @abstractmethod
    async def execute(self, script_id: UUID, config: Dict[str, Any]) -> ExecutionResult:
        """执行单个脚本"""
        ...

    @abstractmethod
    async def cancel(self) -> None:
        """取消当前执行"""
        ...


class PlaywrightExecutor(ScriptExecutor):
    """Playwright API 测试执行器"""

    def __init__(self, mongodb=None):
        self.mongodb = mongodb
        self._cancelled = False
        self.workspace_dir = Path(settings.api_workspace_root).resolve()
        self.runner = PlaywrightRunner(self.workspace_dir)

    async def execute(self, script_id: UUID, config: Dict[str, Any]) -> ExecutionResult:
        """
        执行 Playwright API 测试脚本。

        流程：
        1. 加载 APITest 并创建 APITestRun
        2. 从 MinIO 下载脚本到 workspace/tests/
        3. 使用 PlaywrightRunner 异步执行
        4. 更新 APITestRun 状态并返回结果
        """
        start_time = datetime.now(timezone.utc)
        run_id: Optional[UUID] = None

        # 1. 加载 APITest 并创建运行记录
        async with async_session_factory() as session:
            api_test_repo = APITestRepository(session)
            run_repo = APITestRunRepository(session)

            api_test = await api_test_repo.get_by_id(script_id)
            if not api_test:
                return ExecutionResult(
                    success=False,
                    status=JobStatus.FAILED.value,
                    error_message=f"API 测试不存在: {script_id}",
                )

            identifier = await run_repo.get_next_identifier(script_id)
            test_run = await run_repo.create(
                project_id=api_test.project_id,
                api_test_id=script_id,
                identifier=identifier,
                status="pending",
                execution_config=config,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
            )
            run_id = test_run.id
            await session.commit()

        # 2. 更新为 RUNNING（独立 session，避免长事务）
        if run_id:
            try:
                async with async_session_factory() as session:
                    run_repo = APITestRunRepository(session)
                    run_record = await run_repo.get_by_id(run_id)
                    if run_record:
                        await run_repo.update(run_record, status="running")
                        await session.commit()
            except Exception as e:
                logger.warning("[PlaywrightExecutor] 更新运行状态为 running 失败: %s", e)

        # 3. 下载脚本
        script_file_path: Optional[Path] = None
        try:
            script_content = MinIOClient.download_file(api_test.script_path)
            script_content = script_content.decode("utf-8")
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VFZZMk53PT06N2NmYjQwOGI=

            # 写入 workspace/tests/，使用唯一文件名避免冲突
            safe_name = f"run_{run_id}_{uuid.uuid4().hex[:8]}.spec.ts"
            script_file_path = self.workspace_dir / "tests" / safe_name
            script_file_path.write_text(script_content, encoding="utf-8")
            logger.info(
                "[PlaywrightExecutor] 脚本已下载: %s", script_file_path
            )
        except Exception as e:
            logger.exception("[PlaywrightExecutor] 下载脚本失败")
            await self._update_run_failed(run_id, f"下载脚本失败: {e}")
            return ExecutionResult(
                success=False,
                status=JobStatus.FAILED.value,
                error_message=f"下载脚本失败: {e}",
            )

        # 4. 执行测试（同时生成 list + html 报告）
        config_with_reporter = {**config, "reporter": "list,html"}
        runner_result = await self.runner.run(
            script_path=script_file_path,
            config=config_with_reporter,
            timeout=config.get("timeout", 300),
        )

        # 5. 将 HTML 报告打包上传到 MinIO
        report_path = runner_result.report_path
        if report_path and Path(report_path).exists():
            try:
                import zipfile
                report_dir = Path(report_path)
                zip_path = report_dir.parent / f"report-{run_id}.zip"
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file in report_dir.rglob('*'):
                        if file.is_file():
                            zipf.write(file, file.relative_to(report_dir))
                minio_path = f"playwright-reports/{run_id}/report.zip"
                with open(zip_path, 'rb') as f:
                    MinIOClient.upload_bytes(
                        object_name=minio_path,
                        data=f.read(),
                        content_type="application/zip",
                    )
                report_path = minio_path
                try:
                    zip_path.unlink()
                except Exception:
                    pass
            except Exception as e:
                logger.warning("[PlaywrightExecutor] 上传报告失败: %s", e)

        # 6. 清理临时脚本文件
        if script_file_path and script_file_path.exists():
            try:
                script_file_path.unlink()
            except Exception as e:
                logger.warning("[PlaywrightExecutor] 清理临时脚本失败: %s", e)

        # 7. 更新 APITestRun 结果
        duration_ms = runner_result.duration_ms
        if self._cancelled:
            await self._update_run_status(
                run_id, "cancelled", duration_ms=duration_ms
            )
            return ExecutionResult(
                success=False,
                status=JobStatus.CANCELLED.value,
                duration_ms=duration_ms,
                error_message="执行已被取消",
            )

        if runner_result.success:
            await self._update_run_completed(
                run_id,
                duration_ms=duration_ms,
                total=runner_result.result_summary.get("total", 0),
                passed=runner_result.result_summary.get("passed", 0),
                failed=runner_result.result_summary.get("failed", 0),
                skipped=runner_result.result_summary.get("skipped", 0),
                report_path=report_path,
            )
            return ExecutionResult(
                success=True,
                status=JobStatus.COMPLETED.value,
                duration_ms=duration_ms,
                stdout=runner_result.stdout[:50000] if runner_result.stdout else "",
                stderr=runner_result.stderr[:50000] if runner_result.stderr else "",
                report_path=report_path,
                result_summary=runner_result.result_summary,
                detail_run_id=str(run_id),
            )
        else:
            await self._update_run_failed(
                run_id,
                error_message=runner_result.error_message,
                duration_ms=duration_ms,
                report_path=report_path,
            )
            return ExecutionResult(
                success=False,
                status=JobStatus.FAILED.value,
                duration_ms=duration_ms,
                error_message=runner_result.error_message,
                stdout=runner_result.stdout[:50000] if runner_result.stdout else "",
                stderr=runner_result.stderr[:50000] if runner_result.stderr else "",
                report_path=report_path,
                detail_run_id=str(run_id),
            )

    async def cancel(self) -> None:
        self._cancelled = True

    async def _update_run_status(
        self,
        run_id: Optional[UUID],
        status: str,
        duration_ms: Optional[int] = None,
    ) -> None:
        if not run_id:
            return
        try:
            async with async_session_factory() as session:
                run_repo = APITestRunRepository(session)
                run_record = await run_repo.get_by_id(run_id)
                if run_record:
                    kwargs: Dict[str, Any] = {"status": status}
                    if duration_ms is not None:
                        kwargs["duration_ms"] = duration_ms
                    await run_repo.update(run_record, **kwargs)
                    await session.commit()
        except Exception as e:
            logger.warning("[PlaywrightExecutor] 更新运行状态失败: %s", e)

    async def _update_run_completed(
        self,
        run_id: Optional[UUID],
        duration_ms: int,
        total: int,
        passed: int,
        failed: int,
        skipped: int,
        report_path: Optional[str] = None,
    ) -> None:
        if not run_id:
            return
        try:
            async with async_session_factory() as session:
                run_repo = APITestRunRepository(session)
                run_record = await run_repo.get_by_id(run_id)
                if run_record:
                    await run_repo.update(
                        run_record,
                        status="completed",
                        duration_ms=duration_ms,
                        total_tests=total,
                        passed_tests=passed,
                        failed_tests=failed,
                        skipped_tests=skipped,
                        report_path=report_path,
                    )
                    await session.commit()
        except Exception as e:
            logger.warning("[PlaywrightExecutor] 更新运行完成状态失败: %s", e)

    async def _update_run_failed(
        self,
        run_id: Optional[UUID],
        error_message: Optional[str],
        duration_ms: Optional[int] = None,
        report_path: Optional[str] = None,
    ) -> None:
        if not run_id:
            return
        try:
            async with async_session_factory() as session:
                run_repo = APITestRunRepository(session)
                run_record = await run_repo.get_by_id(run_id)
                if run_record:
                    kwargs: Dict[str, Any] = {
                        "status": "failed",
                        "error_message": error_message,
                    }
                    if duration_ms is not None:
                        kwargs["duration_ms"] = duration_ms
                    if report_path is not None:
                        kwargs["report_path"] = report_path
                    await run_repo.update(run_record, **kwargs)
                    await session.commit()
        except Exception as e:
            logger.warning("[PlaywrightExecutor] 更新运行失败状态失败: %s", e)


class ScenarioExecutor(ScriptExecutor):
    """场景测试执行器（委托给现有 ScenarioExecutionEngine）"""

    def __init__(self):
        self._cancelled = False

    async def execute(self, script_id: UUID, config: Dict[str, Any]) -> ExecutionResult:
        from app.services.scenario_execution_engine import ScenarioExecutionEngine

        start_time = datetime.now(timezone.utc)

        async with async_session_factory() as session:
            engine = ScenarioExecutionEngine(session)
            try:
                variables = config.get("variables", {})
                base_url = config.get("base_url", "")

                scenario_run = await engine.execute(
                    scenario_id=script_id,
                    variables=variables,
                    base_url=base_url,
                )

                duration_ms = int(
                    (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                )
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VFZZMk53PT06N2NmYjQwOGI=

                if self._cancelled:
                    return ExecutionResult(
                        success=False,
                        status=JobStatus.CANCELLED.value,
                        duration_ms=duration_ms,
                        error_message="执行已被取消",
                    )

                success = getattr(scenario_run, "status", "failed") == "completed"
                run_status = JobStatus.COMPLETED.value if success else JobStatus.FAILED.value

                # 加载场景名称
                scenario = await session.get(TestScenario, scenario_run.scenario_id)
                scenario_name = scenario.name if scenario else "未知场景"

                # 加载步骤结果
                step_results_stmt = (
                    select(ScenarioStepResult)
                    .where(ScenarioStepResult.run_id == scenario_run.id)
                    .order_by(ScenarioStepResult.step_order)
                    .options(selectinload(ScenarioStepResult.step))
                )
                step_results_raw = await session.execute(step_results_stmt)
                step_results_orm = step_results_raw.scalars().all()

                step_results_data = []
                for sr in step_results_orm:
                    step_results_data.append({
                        "step_order": sr.step_order,
                        "step_name": sr.step.name if sr.step else None,
                        "status": sr.status,
                        "duration_ms": sr.duration_ms,
                        "error_message": sr.error_message,
                        "request_data": sr.request_data,
                        "response_data": sr.response_data,
                        "extracted_data": sr.extracted_data,
                        "assertion_results": sr.assertion_results,
                    })

                result_summary = {
                    "total": getattr(scenario_run, "total_steps", 0),
                    "passed": getattr(scenario_run, "passed_steps", 0),
                    "failed": getattr(scenario_run, "failed_steps", 0),
                    "skipped": getattr(scenario_run, "skipped_steps", 0),
                }

                # 生成 HTML 报告并上传
                report_path: Optional[str] = None
                try:
                    report_html = generate_scenario_report(
                        scenario_name=scenario_name,
                        run_identifier=scenario_run.identifier,
                        run_status=scenario_run.status,
                        total_steps=result_summary["total"],
                        passed_steps=result_summary["passed"],
                        failed_steps=result_summary["failed"],
                        skipped_steps=result_summary["skipped"],
                        duration_ms=getattr(scenario_run, "duration_ms", duration_ms),
                        error_message=scenario_run.error_message,
                        step_results=step_results_data,
                    )

                    with tempfile.TemporaryDirectory() as tmpdir:
                        report_dir = Path(tmpdir) / "scenario-report"
                        report_dir.mkdir()
                        index_path = report_dir / "index.html"
                        index_path.write_text(report_html, encoding="utf-8")

                        zip_path = Path(tmpdir) / f"scenario-report-{scenario_run.id}.zip"
                        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                            for file in report_dir.rglob('*'):
                                if file.is_file():
                                    zf.write(file, file.relative_to(report_dir))

                        minio_path = f"scenario-reports/{scenario_run.id}/report.zip"
                        with open(zip_path, 'rb') as f:
                            MinIOClient.upload_bytes(
                                object_name=minio_path,
                                data=f.read(),
                                content_type="application/zip",
                            )
                        report_path = minio_path

                    # 更新 ScenarioRun 的报告路径
                    from sqlalchemy import update as sa_update
                    await session.execute(
                        sa_update(ScenarioRun)
                        .where(ScenarioRun.id == scenario_run.id)
                        .values(report_path=report_path)
                    )
                    await session.commit()
                except Exception as e:
                    logger.warning("[ScenarioExecutor] 生成/上传报告失败: %s", e)

                return ExecutionResult(
                    success=success,
                    status=run_status,
                    duration_ms=duration_ms,
                    error_message=scenario_run.error_message if not success else None,
                    report_path=report_path,
                    result_summary=result_summary,
                    detail_run_id=str(scenario_run.id),
                )

            except asyncio.CancelledError:
                duration_ms = int(
                    (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                )
                return ExecutionResult(
                    success=False,
                    status=JobStatus.CANCELLED.value,
                    duration_ms=duration_ms,
                    error_message="执行被取消",
                )
            except Exception as e:
                duration_ms = int(
                    (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                )
                return ExecutionResult(
                    success=False,
                    status=JobStatus.FAILED.value,
                    duration_ms=duration_ms,
                    error_message=str(e),
                )

    async def cancel(self) -> None:
        self._cancelled = True


class WebTestExecutor(ScriptExecutor):
    """Web 测试执行器（委托给现有 WebTestService）"""

    def __init__(self):
        self._cancelled = False

    async def execute(self, script_id: UUID, config: Dict[str, Any]) -> ExecutionResult:
        from app.repositories.project_repo import ProjectRepository
        from app.repositories.web_test_repo import WebTestRepository
        from app.services.web_test_service import WebTestService

        start_time = datetime.now(timezone.utc)

        async with async_session_factory() as session:
            web_test_repo = WebTestRepository(session)
            project_repo = ProjectRepository(session)

            web_test = await web_test_repo.get_by_id(script_id)
            if not web_test:
                return ExecutionResult(
                    success=False,
                    status=JobStatus.FAILED.value,
                    error_message=f"Web 测试不存在: {script_id}",
                )

            project = await project_repo.get_by_id(web_test.project_id)
            if not project:
                return ExecutionResult(
                    success=False,
                    status=JobStatus.FAILED.value,
                    error_message=f"项目不存在: {web_test.project_id}",
                )

            service = WebTestService(session)
            try:
                result = await service.run_web_test(
                    project_identifier=project.identifier,
                    web_test_id=str(script_id),
                    execution_config=config,
                )
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VFZZMk53PT06N2NmYjQwOGI=

                if self._cancelled:
                    return ExecutionResult(
                        success=False,
                        status=JobStatus.CANCELLED.value,
                        error_message="执行已被取消",
                    )

                run_id = result.get("run_id")
                # WebTestService 已内部创建 WebTestRun 并执行
                # 这里直接按返回结果判断
                success = result.get("status") != "failed"
                duration_ms = int(
                    (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                )
                return ExecutionResult(
                    success=success,
                    status=JobStatus.COMPLETED.value if success else JobStatus.FAILED.value,
                    duration_ms=duration_ms,
                    error_message=None if success else result.get("error"),
                    detail_run_id=str(run_id) if run_id else None,
                )

            except asyncio.CancelledError:
                return ExecutionResult(
                    success=False,
                    status=JobStatus.CANCELLED.value,
                    error_message="执行被取消",
                )
            except Exception as e:
                duration_ms = int(
                    (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                )
                return ExecutionResult(
                    success=False,
                    status=JobStatus.FAILED.value,
                    duration_ms=duration_ms,
                    error_message=str(e),
                )

    async def cancel(self) -> None:
        self._cancelled = True


class ExecutorRegistry:
    """执行器注册表：按 ScriptType 分发给具体执行器"""

    _executors: Dict[str, Any] = {}

    @classmethod
    def get(cls, script_type: str, mongodb: Any = None) -> ScriptExecutor:
        """获取对应类型的执行器实例"""
        if script_type == "api_test":
            return PlaywrightExecutor(mongodb=mongodb)
        elif script_type == "scenario":
            return ScenarioExecutor()
        elif script_type == "web_test":
            return WebTestExecutor()
        else:
            raise ValueError(f"不支持的脚本类型: {script_type}")
