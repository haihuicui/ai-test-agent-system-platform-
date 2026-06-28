"""
API 测试执行器

负责异步执行 API 测试并收集结果
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.api_test import APITest, APITestRun, APITestResult
from app.repositories.api_test_repo import (
    APITestRepository,
    APITestRunRepository,
    APITestResultRepository,
)
from app.config.minio_client import MinIOClient
from app.config.database import async_session_factory
from app.schemas.enums import TestResultStatus
from app.models.mongodb.api_test_log import APITestDetailLog

logger = logging.getLogger(__name__)


def _get_npx_cmd() -> list[str]:
    """获取平台相关的 npx 命令。"""
    if os.name == "nt":  # Windows
        return ["npx.cmd"]
    return ["npx"]


def _ensure_node_in_path(env: dict[str, str]) -> dict[str, str]:
    """确保 PATH 包含常见的 Node.js 安装目录。"""
    node_paths = [
        r"C:\Program Files\nodejs",
        r"C:\Program Files (x86)\nodejs",
        os.path.expanduser(r"~\AppData\Roaming\npm"),
        "/usr/local/bin",
        "/usr/bin",
    ]
    current_path = env.get("PATH", "")
    paths_to_add = [p for p in node_paths if p not in current_path]
    if paths_to_add:
        env = {**env, "PATH": os.pathsep.join(paths_to_add + [current_path])}
    return env

# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW1wNk1BPT06ZWUzYTIzYTg=

class APITestExecutor:
    """
    API 测试执行器

    负责执行 Playwright API 测试并收集结果
    """

    def __init__(self, session: AsyncSession, mongodb=None):
        self.session = session
        self.mongodb = mongodb
        self.api_test_repo = APITestRepository(session)
        self.api_test_run_repo = APITestRunRepository(session)
        self.api_test_result_repo = APITestResultRepository(session)

    async def execute_test(
        self,
        api_test_id: UUID,
        execution_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        执行 API 测试（异步）

        Args:
            api_test_id: API 测试 ID
            execution_config: 执行配置

        Returns:
            str: 测试运行 ID
        """
        # 1. 获取 API 测试
        api_test = await self.api_test_repo.get_by_id(api_test_id)
        if not api_test:
            raise ValueError(f"API 测试不存在: {api_test_id}")

        # 2. 创建测试运行记录
        identifier = await self.api_test_run_repo.get_next_identifier(api_test_id)
        test_run = await self.api_test_run_repo.create(
            project_id=api_test.project_id,
            api_test_id=api_test_id,
            identifier=identifier,
            status="pending",
            execution_config=execution_config or {},
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            skipped_tests=0,
        )

        run_id = test_run.id

        # 3. 立即提交，确保后台任务的新 session 能读取到这条记录
        await self.session.commit()

        # 4. 在后台执行测试（只传递 primitive ID，不传递 ORM 实例）
        asyncio.create_task(
            self._execute_in_background(
                run_id=run_id,
                api_test_id=api_test_id,
                execution_config=execution_config or {},
            )
        )

        return str(run_id)
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW1wNk1BPT06ZWUzYTIzYTg=

    async def _execute_in_background(
        self,
        run_id: UUID,
        api_test_id: UUID,
        execution_config: Dict[str, Any],
    ):
        """
        Execute test in background with a new DB session.

        Workflow:
        1. Update status to RUNNING
        2. Fetch APITest by ID (avoid detached instance issues)
        3. Download test script from MinIO
        4. Prepare execution environment in workspace
        5. Run Playwright test (async subprocess, non-blocking)
        6. Parse test results
        7. Save results to database
        8. Update run status
        """
        async with async_session_factory() as session:
            run_repo = APITestRunRepository(session)
            result_repo = APITestResultRepository(session)
            api_test_repo = APITestRepository(session)

            try:
                # 1. 更新状态为 RUNNING
                run_record = await run_repo.get_by_id(run_id)
                if run_record is None:
                    raise ValueError(f"测试运行记录不存在: {run_id}")
                await run_repo.update(run_record, status="running")
                await session.commit()

                # 2. 重新加载 APITest（避免跨 session 的 ORM 实例问题）
                api_test = await api_test_repo.get_by_id(api_test_id)
                if api_test is None:
                    raise ValueError(f"API 测试不存在: {api_test_id}")

                # 3. 下载测试脚本
                script_content = MinIOClient.download_file(api_test.script_path)
                script_content = script_content.decode("utf-8")

                # 4. 准备执行环境：使用 workspace 目录而非临时目录
                workspace_dir = Path(settings.api_workspace_root).resolve()
                tests_dir = workspace_dir / "tests"
                tests_dir.mkdir(parents=True, exist_ok=True)

                # 使用唯一文件名避免冲突
                script_file = tests_dir / f"run_{run_id}_{uuid4().hex[:8]}.spec.ts"
                script_file.write_text(script_content, encoding="utf-8")
                logger.info("[APITestExecutor] 脚本已写入: %s", script_file)

                try:
                    # 5. 执行测试（非阻塞异步子进程）
                    result = await self._run_playwright_test(
                        script_path=script_file,
                        execution_config=execution_config,
                    )

                    # 6. 解析结果并保存
                    await self._process_test_results(
                        run_repo=run_repo,
                        result_repo=result_repo,
                        run_id=run_id,
                        api_test=api_test,
                        test_result=result,
                    )
                    await session.commit()

                    # 7. 更新为完成状态
                    run_record = await run_repo.get_by_id(run_id)
                    if run_record:
                        await run_repo.update(
                            run_record,
                            status="completed",
                        )
                        await session.commit()

                finally:
                    # 清理临时脚本文件
                    if script_file.exists():
                        try:
                            script_file.unlink()
                            logger.info("[APITestExecutor] 已清理临时脚本: %s", script_file)
                        except Exception as e:
                            logger.warning("[APITestExecutor] 清理临时脚本失败: %s", e)

            except Exception as e:
                logger.exception("[APITestExecutor] 后台执行失败")
                # 更新为失败状态
                try:
                    run_record = await run_repo.get_by_id(run_id)
                    if run_record:
                        await run_repo.update(
                            run_record,
                            status="failed",
                            error_message=str(e)
                        )
                        await session.commit()
                except Exception as inner_e:
                    logger.error("[APITestExecutor] 更新失败状态也失败了: %s", inner_e)

    async def _run_playwright_test(
        self,
        script_path: Path,
        execution_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        运行 Playwright 测试（非阻塞异步子进程）

        Args:
            script_path: 测试脚本路径
            execution_config: 执行配置

        Returns:
            dict: 测试结果
        """
        workspace_dir = Path(settings.api_workspace_root).resolve()
        proc: Optional[asyncio.subprocess.Process] = None

        try:
            # 准备环境变量：确保 PATH 包含 Node.js
            env = _ensure_node_in_path({**os.environ})
            env_vars = execution_config.get("env") or execution_config.get("environment_variables")
            if env_vars:
                env.update(env_vars)
            if execution_config.get("base_url"):
                env["API_BASE_URL"] = execution_config["base_url"]
            env["CI"] = "1"

            npx_cmd = _get_npx_cmd()

            # 检查 npx 是否可用
            npx_proc = await asyncio.create_subprocess_exec(
                *npx_cmd, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(npx_proc.communicate(), timeout=10)
            if npx_proc.returncode != 0:
                raise Exception(f"npx 不可用: {stderr.decode('utf-8', errors='replace')}")

            # 计算相对路径
            relative_path = script_path.relative_to(workspace_dir)

            # 运行 Playwright 测试
            proc = await asyncio.create_subprocess_exec(
                *npx_cmd, "playwright", "test",
                relative_path.as_posix(),
                "--reporter=list",
                cwd=str(workspace_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=execution_config.get("timeout", 300),
            )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            return {
                "status": "passed" if proc.returncode == 0 else "failed",
                "error": stderr if proc.returncode != 0 else None,
                "stdout": stdout,
                "returncode": proc.returncode,
            }
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW1wNk1BPT06ZWUzYTIzYTg=

        except asyncio.TimeoutError:
            logger.warning("[APITestExecutor] Playwright 执行超时，正在终止...")
            if proc and proc.returncode is None:
                try:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except Exception:
                    pass
            return {
                "status": "failed",
                "error": f"测试执行超时（超过 {execution_config.get('timeout', 300)} 秒）",
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": f"测试执行失败: {str(e)}",
            }

    async def _process_test_results(
        self,
        run_id: UUID,
        api_test: APITest,
        test_result: Dict[str, Any],
        *,
        run_repo: Optional[APITestRunRepository] = None,
        result_repo: Optional[APITestResultRepository] = None,
    ):
        """
        处理测试结果

        Args:
            run_id: 测试运行 ID
            api_test: API 测试
            test_result: Playwright 测试结果
        """
        try:
            # 解析 Playwright 结果
            suites = test_result.get("suites", [])
            total_tests = 0
            passed_tests = 0
            failed_tests = 0
            skipped_tests = 0

            for suite in suites:
                specs = suite.get("specs", [])
                for spec in specs:
                    tests = spec.get("tests", [])
                    for test in tests:
                        total_tests += 1

                        status = TestResultStatus.PASSED
                        if test.get("ok", False):
                            passed_tests += 1
                        else:
                            failed_tests += 1
                            status = TestResultStatus.FAILED

                        # 保存测试结果
                        await self._save_test_result(
                            run_id=run_id,
                            api_test=api_test,
                            test_name=test.get("title", ""),
                            status=status,
                            results=test.get("results", []),
                            result_repo=result_repo,
                        )

            # 更新运行统计
            _run_repo = run_repo or self.api_test_run_repo
            run_record = await _run_repo.get_by_id(run_id)
            if run_record:
                await _run_repo.update(
                    run_record,
                    total_tests=total_tests,
                    passed_tests=passed_tests,
                    failed_tests=failed_tests,
                    skipped_tests=skipped_tests,
                )

        except Exception as e:
            logger.error("[APITestExecutor] 处理测试结果失败: %s", e)

    async def _save_test_result(
        self,
        run_id: UUID,
        api_test: APITest,
        test_name: str,
        status: TestResultStatus,
        _results: List[Dict[str, Any]],
        *,
        result_repo: Optional[APITestResultRepository] = None,
    ):
        """
        保存单个测试结果

        Args:
            run_id: 测试运行 ID
            api_test: API 测试
            test_name: 测试名称
            status: 测试状态
            _results: 测试结果详情（预留，用于提取断言和执行时间）
            result_repo: 可选的结果仓储（后台任务使用新 session）
        """
        try:
            # 提取端点和 HTTP 方法（从测试名称中解析）
            endpoint, method = self._parse_endpoint_from_test_name(test_name)

            # 创建测试结果记录
            _result_repo = result_repo or self.api_test_result_repo
            await _result_repo.create(
                test_run_id=run_id,
                api_test_id=api_test.id,
                scenario_name=test_name,
                endpoint=endpoint,
                method=method,
                status=status,
                request_summary={
                    "url": api_test.test_config.get("base_url", ""),
                    "method": method,
                },
                response_summary={
                    "status_code": 200 if status == TestResultStatus.PASSED else 500,
                },
                error_message=None if status == TestResultStatus.PASSED else "测试失败",
                duration_ms=0,  # TODO: 从测试结果中提取
                retry_count=0,
            )

        except Exception as e:
            logger.error("[APITestExecutor] 保存测试结果失败: %s", e)

    def _parse_endpoint_from_test_name(self, test_name: str) -> tuple[str, str]:
        """
        Parse endpoint and HTTP method from test name.

        Input:  "GET /api/v1/users"
        Output: ("/api/v1/users", "GET")
        """
        import re

        # Try to match pattern: "METHOD /path" or "METHOD path"
        match = re.match(r'^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(.+)$', test_name)
        if match:
            method = match.group(1)
            endpoint = match.group(2)
            return endpoint, method

        # Default to GET if no explicit method found
        return test_name, "GET"

    async def _generate_allure_report(
        self,
        run_id: UUID,
        work_dir: Path,
    ) -> Optional[str]:
        """
        生成 Allure 测试报告

        Args:
            run_id: 测试运行 ID
            work_dir: 工作目录（包含 allure-results）

        Returns:
            str: 报告目录路径 (MinIO)
        """
        try:
            allure_results_dir = work_dir / "allure-results"

            # 检查 Allure 结果是否存在
            if not allure_results_dir.exists():
                logger.info("[APITestExecutor] 未找到 Allure 测试结果")
                return None

            # 生成 HTML 报告到临时目录
            allure_report_dir = work_dir / "allure-report"
            proc = await asyncio.create_subprocess_exec(
                "allure", "generate", str(allure_results_dir), "-o", str(allure_report_dir), "--clean",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=30)

            # 将报告打包为 ZIP 并上传到 MinIO
            import zipfile
            zip_path = work_dir / "allure-report.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in allure_report_dir.rglob('*'):
                    if file.is_file():
                        arcname = file.relative_to(allure_report_dir)
                        zipf.write(file, arcname)

            # 上传到 MinIO
            report_path = f"api-test-reports/{run_id}/allure-report.zip"
            with open(zip_path, 'rb') as f:
                MinIOClient.upload_bytes(
                    object_name=report_path,
                    data=f.read(),
                    content_type="application/zip",
                )
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YW1wNk1BPT06ZWUzYTIzYTg=

            return report_path

        except Exception as e:
            logger.error("[APITestExecutor] 生成 Allure 报告失败: %s", e)
            return None

    async def save_detail_log(
        self,
        test_result_id: UUID,
        test_run_id: UUID,
        api_test_id: UUID,
        scenario_name: str,
        endpoint: str,
        method: str,
        request: Dict[str, Any],
        response: Dict[str, Any],
        status: str,
        duration_ms: int,
    ) -> str:
        """
        保存详细日志到 MongoDB

        Args:
            test_result_id: 测试结果 ID
            test_run_id: 测试运行 ID
            api_test_id: API 测试 ID
            scenario_name: 场景名称
            endpoint: 端点
            method: HTTP 方法
            request: 请求数据
            response: 响应数据
            status: 状态
            duration_ms: 执行时长

        Returns:
            str: MongoDB 日志 ID
        """
        if not self.mongodb:
            return None

        try:
            log = APITestDetailLog(
                log_id=str(uuid4()),
                test_result_id=test_result_id,
                test_run_id=test_run_id,
                api_test_id=api_test_id,
                scenario_name=scenario_name,
                endpoint=endpoint,
                method=method,
                request=request,
                response=response,
                assertions=[],  # TODO: 从测试结果中提取断言
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                status=status,
                error=None if status == "passed" else {"message": "测试失败"},
            )

            # 保存到 MongoDB
            collection = self.mongodb.db.get_collection("api_test_logs")
            result = await collection.insert_one(log.to_document())

            return str(result.inserted_id)

        except Exception as e:
            logger.error("[APITestExecutor] 保存详细日志失败: %s", e)
            return None

    async def generate_test_report(
        self,
        run_id: UUID,
    ) -> Optional[str]:
        """
        生成测试报告（已废弃，使用 _generate_allure_report 代替）

        Args:
            run_id: 测试运行 ID

        Returns:
            str: 报告文件路径 (MinIO)
        """
        # 此方法已集成到 _execute_in_background 中
        # 保留是为了向后兼容
        test_run = await self.api_test_run_repo.get_by_id(run_id)
        if test_run and test_run.report_path:
            return test_run.report_path
        return None
