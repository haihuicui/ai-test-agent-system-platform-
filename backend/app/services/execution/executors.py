"""
脚本执行器注册表与具体实现

支持 Playwright、场景测试、Web 测试等执行器，按 ScriptType 自动分发。
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from app.config.database import async_session_factory
from app.config.minio_client import MinIOClient
from app.repositories.api_test_repo import APITestRunRepository
from app.schemas.enums import JobStatus
from app.services.execution.models import ExecutionResult

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

    async def execute(self, script_id: UUID, config: Dict[str, Any]) -> ExecutionResult:
        """
        执行 Playwright API 测试脚本。

        不再自己下载脚本、拼 npx 命令，而是复用已经成熟的
        APITestExecutor，以获得：
        - 项目环境变量 / auth token 注入
        - api-trace-helper 捕获真实请求/响应
        - 脱敏、大响应体截断与 MinIO 上传
        - 按用例生成 APITestResult
        - 独立的 per-run 报告目录（避免并发覆盖）
        """
        from app.services.api_test_executor import APITestExecutor
        from app.repositories.api_test_repo import APITestRunRepository

        start_time = datetime.now(timezone.utc)
        run_id: Optional[UUID] = None

        # 1. 复用 APITestExecutor 启动执行（内部会解析环境、复制 trace helper、
        #    重写 import、生成报告并创建 APITestResult）
        try:
            async with async_session_factory() as session:
                executor = APITestExecutor(session, self.mongodb)
                run_id_str = await executor.execute_test(script_id, config or {})
                run_id = UUID(run_id_str)
        except Exception as e:
            logger.exception("[PlaywrightExecutor] 启动 API 测试执行失败")
            return ExecutionResult(
                success=False,
                status=JobStatus.FAILED.value,
                error_message=f"启动 API 测试执行失败: {e}",
            )

        # 2. 轮询等待后台执行完成
        timeout = (config or {}).get("timeout", 300)
        interval = 2.0
        try:
            async with async_session_factory() as session:
                run_repo = APITestRunRepository(session)
                for _ in range(int(timeout / interval)):
                    if self._cancelled:
                        return ExecutionResult(
                            success=False,
                            status=JobStatus.CANCELLED.value,
                            error_message="执行已被取消",
                        )
                    run = await run_repo.get_by_id(run_id)
                    if run and run.status in ("completed", "failed", "cancelled"):
                        break
                    await asyncio.sleep(interval)
                else:
                    return ExecutionResult(
                        success=False,
                        status=JobStatus.FAILED.value,
                        error_message=f"API 测试执行超时（超过 {timeout} 秒）",
                    )

                duration_ms = int(
                    (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                )
                success = run.status == "completed"
                result_summary = {
                    "total": run.total_tests or 0,
                    "passed": run.passed_tests or 0,
                    "failed": run.failed_tests or 0,
                    "skipped": run.skipped_tests or 0,
                }

                return ExecutionResult(
                    success=success,
                    status=JobStatus.COMPLETED.value
                    if success
                    else JobStatus.FAILED.value,
                    duration_ms=duration_ms,
                    error_message=run.error_message if not success else None,
                    report_path=run.report_path,
                    result_summary=result_summary,
                    detail_run_id=str(run_id),
                )
        except Exception as e:
            logger.exception("[PlaywrightExecutor] 等待 API 测试执行结果失败")
            return ExecutionResult(
                success=False,
                status=JobStatus.FAILED.value,
                error_message=f"等待 API 测试执行结果失败: {e}",
            )

    async def cancel(self) -> None:
        self._cancelled = True


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
                env_id = config.get("env_id")
                env_uuid = UUID(env_id) if env_id else None

                scenario_run = await engine.execute(
                    scenario_id=script_id,
                    variables=variables,
                    base_url=base_url,
                    env_id=env_uuid,
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
