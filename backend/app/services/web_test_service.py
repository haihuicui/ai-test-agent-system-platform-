"""
Web 测试服务

处理 Web 测试相关的业务逻辑
"""

import asyncio
import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.storage_state_job import StorageStateJob
from app.models.web_test import WebTest, WebTestRun, WebTestResult
from app.models.web_function import WebFunction, WebSubFunction
from app.repositories.web_test_repo import (
    WebTestRepository,
    WebTestRunRepository,
    WebTestResultRepository,
)
from app.repositories.project_repo import ProjectRepository
from app.schemas.enums import TestResultStatus
from app.utils.exceptions import NotFoundException
from app.utils.playwright_report import map_playwright_status, parse_playwright_json
from app.utils.shell_env import ensure_playwright_mcp_project
from app.utils.sync_executor import run_sync
from app.config.minio_client import MinIOClient
from app.config.settings import settings
from app.config.database import async_session_factory


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


class WebTestService:
    """Web 测试服务类"""

    def __init__(self, session: AsyncSession, mongodb=None):
        self.session = session
        self.mongodb = mongodb
        self.web_test_repo = WebTestRepository(session)
        self.web_test_run_repo = WebTestRunRepository(session)
        self.web_test_result_repo = WebTestResultRepository(session)
        self.project_repo = ProjectRepository(session)

    async def _get_project_by_identifier(self, identifier: str):
        """获取项目，不存在则抛出异常"""
        project = await self.project_repo.get_by_identifier(identifier)
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=identifier)
        return project

    # ==================== Web 测试管理 ====================

    async def create_web_test(
        self,
        project_identifier: str,
        name: str,
        base_url: str,
        script_path: str,
        script_format: str = "playwright",
        script_language: str = "typescript",
        description: Optional[str] = None,
        test_config: Optional[dict] = None,
        folder_id: Optional[str] = None,
        target_pages: Optional[list] = None,
        test_flows: Optional[list] = None,
    ) -> dict:
        """创建 Web 测试"""
        project = await self._get_project_by_identifier(project_identifier)

        # 生成标识符 (简化版本，实际应该用序列)
        identifier = f"WT-{uuid4().hex[:8].upper()}"

        web_test = await self.web_test_repo.create(
            project_id=project.id,
            identifier=identifier,
            name=name,
            base_url=base_url,
            script_path=script_path,
            script_format=script_format,
            script_language=script_language,
            description=description,
            test_config=test_config or {},
            target_pages=target_pages,
            test_flows=test_flows,
            generated_by_agent="web_agent",
            total_pages=len(target_pages) if target_pages else 0,
            total_flows=len(test_flows) if test_flows else 0,
        )
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZGtSSVRRPT06MjUwZjQ4ZDM=

        return {
            "id": str(web_test.id),
            "identifier": web_test.identifier,
            "name": web_test.name,
            "base_url": web_test.base_url,
            "description": web_test.description,
            "script_format": web_test.script_format,
            "script_language": web_test.script_language,
            "total_pages": web_test.total_pages,
            "total_flows": web_test.total_flows,
            "created_at": web_test.created_at.isoformat(),
        }

    async def get_web_test(
        self,
        project_identifier: str,
        web_test_id: str,
    ) -> dict:
        """获取 Web 测试详情"""
        project = await self._get_project_by_identifier(project_identifier)
        web_test = await self.web_test_repo.get_by_id_with_relations(UUID(web_test_id))

        if not web_test or web_test.project_id != project.id:
            raise NotFoundException(resource_type="Web 测试", resource_id=web_test_id)

        return {
            "id": str(web_test.id),
            "identifier": web_test.identifier,
            "name": web_test.name,
            "base_url": web_test.base_url,
            "description": web_test.description,
            "script_path": web_test.script_path,
            "script_format": web_test.script_format,
            "script_language": web_test.script_language,
            "test_config": web_test.test_config,
            "target_pages": web_test.target_pages,
            "test_flows": web_test.test_flows,
            "total_pages": web_test.total_pages,
            "total_flows": web_test.total_flows,
            "created_at": web_test.created_at.isoformat(),
            "updated_at": web_test.updated_at.isoformat() if web_test.updated_at else None,
        }

    async def list_web_tests(
        self,
        project_identifier: str,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        script_format: Optional[str] = None,
    ) -> dict:
        """获取 Web 测试列表"""
        project = await self._get_project_by_identifier(project_identifier)
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZGtSSVRRPT06MjUwZjQ4ZDM=

        offset = (page - 1) * page_size
        items, total = await self.web_test_repo.get_by_project(
            project.id,
            offset=offset,
            limit=page_size,
            search=search,
            script_format=script_format,
        )

        return {
            "items": [
                {
                    "id": str(item.id),
                    "identifier": item.identifier,
                    "name": item.name,
                    "base_url": item.base_url,
                    "description": item.description,
                    "script_format": item.script_format,
                    "script_language": item.script_language,
                    "total_pages": item.total_pages,
                    "total_flows": item.total_flows,
                    "created_at": item.created_at.isoformat(),
                    "updated_at": item.updated_at.isoformat() if item.updated_at else None,
                }
                for item in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def update_web_test(
        self,
        project_identifier: str,
        web_test_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        test_config: Optional[dict] = None,
    ) -> dict:
        """更新 Web 测试"""
        project = await self._get_project_by_identifier(project_identifier)
        web_test = await self.web_test_repo.get_by_id(UUID(web_test_id))

        if not web_test or web_test.project_id != project.id:
            raise NotFoundException(resource_type="Web 测试", resource_id=web_test_id)

        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if test_config is not None:
            update_data["test_config"] = test_config

        updated = await self.web_test_repo.update(web_test, **update_data)

        return {
            "id": str(updated.id),
            "identifier": updated.identifier,
            "name": updated.name,
            "description": updated.description,
            "test_config": updated.test_config,
            "updated_at": updated.updated_at.isoformat() if updated.updated_at else None,
        }

    async def delete_web_test(
        self,
        project_identifier: str,
        web_test_id: str,
    ) -> None:
        """删除 Web 测试"""
        project = await self._get_project_by_identifier(project_identifier)
        web_test = await self.web_test_repo.get_by_id(UUID(web_test_id))

        if not web_test or web_test.project_id != project.id:
            raise NotFoundException(resource_type="Web 测试", resource_id=web_test_id)

        await self.web_test_repo.delete(web_test)

    async def get_test_script(
        self,
        project_identifier: str,
        web_test_id: str,
    ) -> str:
        """获取测试脚本内容"""
        project = await self._get_project_by_identifier(project_identifier)
        web_test = await self.web_test_repo.get_by_id(UUID(web_test_id))
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZGtSSVRRPT06MjUwZjQ4ZDM=

        if not web_test or web_test.project_id != project.id:
            raise NotFoundException(resource_type="Web 测试", resource_id=web_test_id)

        # 从 MinIO 下载脚本
        content_bytes = MinIOClient.download_file(web_test.script_path)
        return content_bytes.decode('utf-8')

    async def update_test_script(
        self,
        project_identifier: str,
        web_test_id: str,
        script_content: str,
    ) -> None:
        """更新测试脚本内容"""
        project = await self._get_project_by_identifier(project_identifier)
        web_test = await self.web_test_repo.get_by_id(UUID(web_test_id))

        if not web_test or web_test.project_id != project.id:
            raise NotFoundException(resource_type="Web 测试", resource_id=web_test_id)

        # 上传到 MinIO
        script_bytes = script_content.encode('utf-8')
        MinIOClient.upload_bytes(
            object_name=web_test.script_path,
            data=script_bytes,
            content_type="text/plain"
        )

    async def run_web_test(
        self,
        project_identifier: str,
        web_test_id: str,
        execution_config: Optional[dict] = None,
    ) -> dict:
        """执行 Web 测试"""
        project = await self._get_project_by_identifier(project_identifier)
        web_test = await self.web_test_repo.get_by_id(UUID(web_test_id))

        if not web_test or web_test.project_id != project.id:
            raise NotFoundException(resource_type="Web 测试", resource_id=web_test_id)

        # 创建测试运行记录
        identifier = f"WTR-{datetime.now().strftime('%Y%m%d')}-{uuid4().hex[:6]}"
        test_run = await self.web_test_run_repo.create(
            project_id=project.id,
            web_test_id=web_test.id,
            identifier=identifier,
            status="pending",
            execution_config=execution_config or {},
        )
        await self.session.commit()

        # 在后台异步执行测试
        asyncio.create_task(
            self._execute_in_background(
                run_id=test_run.id,
                web_test=web_test,
                execution_config=execution_config or {},
            )
        )

        return {
            "run_id": str(test_run.id),
            "identifier": test_run.identifier,
            "status": test_run.status,
        }

    async def _execute_in_background(
        self,
        run_id: UUID,
        web_test: WebTest,
        execution_config: dict,
    ) -> None:
        """在后台执行 Web 测试"""
        async with async_session_factory() as session:
            run_repo = WebTestRunRepository(session)
            try:
                # 1. 更新状态为 running
                await run_repo.update(
                    await run_repo.get_by_id(run_id),
                    status="running",
                )
                await session.commit()

                # 2. 从 MinIO 下载脚本
                script_content = MinIOClient.download_file(web_test.script_path)
                script_content = script_content.decode("utf-8")

                # 3. 准备执行环境
                # 复用已安装 @playwright/test 的 web_mcp 工作区，在其下创建按 run_id
                # 隔离的子目录，避免临时目录缺少 Playwright 依赖而重复 npm install。
                workspace_root = Path(settings.web_mcp_workspace_root).resolve()
                storage_state_path = await self._resolve_storage_state_path(web_test.project_id)
                await ensure_playwright_mcp_project(
                    str(workspace_root),
                    headless=execution_config.get("headless", True),
                    storage_state=storage_state_path,
                )
                exec_root = workspace_root / ".web_test_runs" / str(run_id)
                await run_sync(lambda: exec_root.mkdir(parents=True, exist_ok=True))
                temp_path = exec_root

                # 写入测试脚本
                script_file = temp_path / "web-test.spec.ts"
                await run_sync(script_file.write_text, script_content, encoding="utf-8")

                # 创建 Playwright 配置
                playwright_config = self._generate_playwright_config(
                    web_test, execution_config, storage_state_path=storage_state_path
                )
                config_file = temp_path / "playwright.config.ts"
                await run_sync(config_file.write_text, playwright_config, encoding="utf-8")

                try:
                    # 4. 执行测试（在 workspace_root 下运行 npx，避免临时目录缺少 node_modules）
                    result = await self._run_playwright_test(
                        workspace_root=str(workspace_root),
                        config_path=str(config_file),
                        execution_config=execution_config,
                    )

                    # 5. 解析结果并更新
                    total = result.get("total", 0)
                    passed = result.get("passed", 0)
                    failed = result.get("failed", 0)
                    skipped = result.get("skipped", 0)
                    error = result.get("error")

                    # 截断日志，防止数据库/前端过载
                    _MAX_LOG_LENGTH = 100_000
                    stdout_text = result.get("stdout", "") or ""
                    stderr_text = result.get("stderr", "") or ""
                    # 兜底：stderr 为空但 error 有内容时，把 error 也放进 stderr，
                    # 保证前端日志弹窗一定能看到失败原因。
                    if not stderr_text and error:
                        stderr_text = error
                    if len(stdout_text) > _MAX_LOG_LENGTH:
                        stdout_text = stdout_text[:_MAX_LOG_LENGTH] + "\n...[truncated]"
                    if len(stderr_text) > _MAX_LOG_LENGTH:
                        stderr_text = stderr_text[:_MAX_LOG_LENGTH] + "\n...[truncated]"

                    # 上传报告产物（HTML 报告 + 截图/video/trace）到 MinIO。
                    report_object_name, screenshots_prefix = await self._upload_run_artifacts(
                        temp_path=temp_path,
                        web_test=web_test,
                        run_id=run_id,
                    )

                    await run_repo.update(
                        await run_repo.get_by_id(run_id),
                        status="completed" if result.get("success") else "failed",
                        total_tests=total,
                        passed_tests=passed,
                        failed_tests=failed,
                        skipped_tests=skipped,
                        error_message=error,
                        duration_ms=result.get("duration_ms"),
                        report_path=report_object_name,
                        screenshots_path=screenshots_prefix,
                        stdout=stdout_text,
                        stderr=stderr_text,
                    )

                    # 逐用例写 WebTestResult（用例级趋势分析数据源；与 agent 链路口径一致）
                    cases = result.get("cases") or []
                    for c in cases:
                        case_error = c.get("error")
                        session.add(WebTestResult(
                            test_run_id=run_id,
                            web_test_id=web_test.id,
                            scenario_name=(c.get("title") or "未命名用例")[:500],
                            page_url=(web_test.base_url or "")[:2048],
                            test_type="functional",
                            status=map_playwright_status(c.get("status")),
                            test_summary={
                                "file": c.get("file"),
                                "duration_ms": c.get("duration_ms"),
                                "retries": c.get("retries"),
                            },
                            error_details={"error_message": case_error} if case_error else None,
                            error_message=case_error,
                            duration_ms=c.get("duration_ms"),
                            retry_count=c.get("retries") or 0,
                        ))
                    await session.commit()
                finally:
                    # 清理隔离执行目录，避免占用磁盘。
                    def _cleanup() -> None:
                        if exec_root.exists():
                            shutil.rmtree(exec_root, ignore_errors=True)
                    await run_sync(_cleanup)

            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                print(f"Web 测试执行失败: {e}\n{tb}")
                try:
                    run = await run_repo.get_by_id(run_id)
                    if run:
                        await run_repo.update(
                            run,
                            status="failed",
                            error_message=str(e) or tb[:4000],
                            stdout="",
                            stderr=tb,
                        )
                        await session.commit()
                except Exception as inner:
                    print(f"Web 测试失败状态写入也失败了: {inner}")

    async def _resolve_storage_state_path(self, project_id: UUID) -> Optional[str]:
        """查询项目最近一次成功生成的 storageState 本地路径。

        直接查 storage_state_jobs 表，避免引入 StorageStateService 造成服务循环依赖。
        """
        result = await self.session.execute(
            select(StorageStateJob)
            .where(
                StorageStateJob.project_id == project_id,
                StorageStateJob.status == "completed",
                StorageStateJob.output_path.isnot(None),
            )
            .order_by(StorageStateJob.completed_at.desc())
            .limit(1)
        )
        job = result.scalar_one_or_none()
        return job.output_path if job else None

    def _generate_playwright_config(
        self,
        web_test: WebTest,
        execution_config: dict,
        storage_state_path: Optional[str] = None,
    ) -> str:
        """生成 Playwright 配置文件"""
        headless = execution_config.get("headless", True)
        browser = execution_config.get("browser", "chromium")
        viewport = execution_config.get("viewport", {"width": 1280, "height": 720})
        slow_mo = execution_config.get("slow_mo", 0)

        # 注入全局登录态（storageState）：文件存在时才写入，避免 Playwright 因缺失文件报错退出
        storage_state_line = ""
        if storage_state_path:
            ss_path = Path(storage_state_path)
            if ss_path.exists():
                storage_state_line = f"    storageState: {json.dumps(ss_path.as_posix())},\n"

        return f"""
import {{ defineConfig, devices }} from '@playwright/test';

export default defineConfig({{
  testDir: './',
  fullyParallel: false,
  forbidOnly: false,
  retries: 0,
  use: {{
    baseURL: '{web_test.base_url or ''}',
    headless: {'true' if headless else 'false'},
    launchOptions: {{
      slowMo: {slow_mo},
    }},
    viewport: {{ width: {viewport['width']}, height: {viewport['height']} }},
{storage_state_line}    // 始终保留现场，供 HTML 报告与自愈诊断（与 agent 链路口径一致）
    trace: 'on',
    video: 'on',
    screenshot: 'on',
  }},
  projects: [
    {{
      name: 'web-tests',
      use: {{ ...devices['Desktop {browser.capitalize()}'] }},
    }},
  ],
}});
"""

    async def _upload_run_artifacts(
        self,
        temp_path: Path,
        web_test: WebTest,
        run_id: UUID,
    ) -> tuple[Optional[str], Optional[str]]:
        """在临时目录删除前，把报告产物上传到 MinIO。

        把 HTML 报告与 test-results（截图/video/trace）打成一个 zip 设到 report_path
        （保持目录结构，HTML 内的 trace/video 引用不断）；截图再单独上传一份设到
        screenshots_path，供前端列表直接浏览。同步 IO 经 run_sync 入线程池，避免阻塞事件循环。

        Returns:
            (report_object_name, screenshots_prefix)；无产物或上传失败时为 None。
            任何异常都不阻断主流程（仅记录日志）。
        """
        report_object_name: Optional[str] = None
        screenshots_prefix: Optional[str] = None
        try:
            html_report_dir = temp_path / "playwright-report"
            test_results_dir = temp_path / "test-results"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_prefix = f"web-tests/{web_test.project_id}/runs/{run_id}"

            # 1. HTML 报告 + test-results 打包 zip（保持结构，HTML 内 trace/video 引用不断）
            if html_report_dir.exists():
                zip_path = temp_path / f"report-{timestamp}.zip"

                def _make_zip() -> None:
                    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                        for root_dir, arc_prefix in ((html_report_dir, "html"), (test_results_dir, "test-results")):
                            if root_dir.exists():
                                for fp in root_dir.rglob("*"):
                                    if fp.is_file():
                                        zipf.write(fp, f"{arc_prefix}/{fp.relative_to(root_dir)}")

                await run_sync(_make_zip)
                zip_bytes = await run_sync(zip_path.read_bytes)
                report_object_name = f"{base_prefix}/report-{timestamp}.zip"
                await run_sync(
                    MinIOClient.upload_bytes,
                    object_name=report_object_name,
                    data=zip_bytes,
                    content_type="application/zip",
                )

            # 2. 截图单独上传一份（retain-on-failure 才产出，量小），供前端列表浏览
            if test_results_dir.exists():
                images = [p for p in test_results_dir.rglob("*")
                          if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg")]
                if images:
                    screenshots_prefix = f"{base_prefix}/screenshots"
                    for img in images:
                        img_bytes = await run_sync(img.read_bytes)
                        await run_sync(
                            MinIOClient.upload_bytes,
                            object_name=f"{screenshots_prefix}/{img.name}",
                            data=img_bytes,
                            content_type="image/png",
                        )
        except Exception as e:
            print(f"[Web Test Run] 上传报告产物失败（不影响主流程）: {e}")
        return report_object_name, screenshots_prefix

    async def _run_playwright_test(
        self,
        workspace_root: str,
        config_path: str,
        execution_config: dict,
    ) -> dict:
        """运行 Playwright 测试。

        在 workspace_root（含 node_modules）下执行 npx，但通过 --config 指定
        隔离目录中的 playwright.config.ts，使输出与依赖分离。
        """
        start_time = datetime.now()
        timeout = execution_config.get("timeout", 300)
        work_dir = os.path.dirname(config_path)

        # 准备环境变量：确保 PATH 包含 Node.js
        env = _ensure_node_in_path({**os.environ})
        env_vars = execution_config.get("env") or execution_config.get("environment_variables")
        if env_vars:
            env.update(env_vars)

        npx_cmd = _get_npx_cmd()

        try:
            # 检查 npx 是否可用
            npx_check = await asyncio.create_subprocess_exec(
                *npx_cmd, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=workspace_root,
            )
            await asyncio.wait_for(npx_check.communicate(), timeout=10)
            if npx_check.returncode != 0:
                raise Exception("npx 不可用，请确保 Node.js 已安装")

            # 同时产出 JSON（机器解析）与 HTML（人读报告）。JSON 写入文件而非读 stdout，
            # 因为多 reporter 时 stdout 会被 html reporter 的进度/提示污染，导致解析失败。
            json_output_file = os.path.join(work_dir, "results.json")
            html_report_dir = os.path.join(work_dir, "playwright-report")
            env["CI"] = "1"  # 禁止 html reporter 执行后自动打开浏览器
            env["PLAYWRIGHT_JSON_OUTPUT_FILE"] = json_output_file
            env["PLAYWRIGHT_HTML_REPORT"] = html_report_dir

            # 运行 Playwright 测试
            proc = await asyncio.create_subprocess_exec(
                *npx_cmd, "playwright", "test",
                "--config", config_path,
                "--reporter=json,html",
                cwd=workspace_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # 尝试解析 JSON 结果（从文件读，而非可能被 html reporter 污染的 stdout）
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")
            try:
                with open(json_output_file, encoding="utf-8", errors="replace") as f:
                    result_data = json.load(f)
                # 解析逻辑与 agent 链路共用（app.utils.playwright_report），保证口径一致。
                parsed = parse_playwright_json(result_data)
                stats = parsed["stats"]

                # Playwright 失败时，错误信息通常在每个 case 的 error 字段里，
                # stderr 可能为空。提取失败用例错误，既用于 error_message，
                # 也回填到 stderr，确保前端日志弹窗有内容可看。
                failure_messages = []
                for c in parsed["cases"]:
                    if c.get("status") == "unexpected" and c.get("error"):
                        failure_messages.append(f"{c['title']}: {c['error']}")
                failure_summary = "\n".join(failure_messages)

                if proc.returncode != 0:
                    effective_error = stderr_text or failure_summary
                    # stderr 为空时，把失败用例错误写进去，避免日志弹窗"暂无日志"
                    effective_stderr = stderr_text or failure_summary
                else:
                    effective_error = None
                    effective_stderr = stderr_text

                return {
                    "success": proc.returncode == 0,
                    "total": stats["total"],
                    "passed": stats["passed"],
                    "failed": stats["failed"],
                    "skipped": stats["skipped"],
                    "duration_ms": duration_ms,
                    "cases": parsed["cases"],
                    "error": effective_error,
                    "stdout": stdout_text,
                    "stderr": effective_stderr,
                }
            except (json.JSONDecodeError, OSError):  # OSError 涵盖 results.json 未生成（如执行崩溃）
                # JSON 解析失败，使用简化结果。同时兜底：stderr 为空时尝试用 stdout 填充，
                # 避免前端日志弹窗完全没有内容。
                fallback_error = stderr_text or (
                    stdout_text if proc.returncode != 0 else None
                )
                fallback_stderr = stderr_text or fallback_error or ""
                return {
                    "success": proc.returncode == 0,
                    "total": 1,
                    "passed": 1 if proc.returncode == 0 else 0,
                    "failed": 0 if proc.returncode == 0 else 1,
                    "skipped": 0,
                    "duration_ms": duration_ms,
                    "cases": [],
                    "error": fallback_error,
                    "stdout": stdout_text,
                    "stderr": fallback_stderr,
                }
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZGtSSVRRPT06MjUwZjQ4ZDM=

        except asyncio.TimeoutError:
            timeout_msg = f"测试执行超时（{timeout}秒）"
            return {
                "success": False,
                "total": 0,
                "passed": 0,
                "failed": 1,
                "skipped": 0,
                "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                "cases": [],
                "error": timeout_msg,
                "stdout": "",
                "stderr": timeout_msg,
            }
        except Exception as e:
            err_msg = str(e)
            return {
                "success": False,
                "total": 0,
                "passed": 0,
                "failed": 1,
                "skipped": 0,
                "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                "cases": [],
                "error": err_msg,
                "stdout": "",
                "stderr": err_msg,
            }

    async def get_test_runs(
        self,
        project_identifier: str,
        web_test_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取测试运行历史"""
        project = await self._get_project_by_identifier(project_identifier)
        web_test = await self.web_test_repo.get_by_id(UUID(web_test_id))

        if not web_test or web_test.project_id != project.id:
            raise NotFoundException(resource_type="Web 测试", resource_id=web_test_id)

        offset = (page - 1) * page_size
        items, total = await self.web_test_run_repo.get_by_web_test(
            web_test.id,
            offset=offset,
            limit=page_size,
        )

        return {
            "items": [
                {
                    "id": str(item.id),
                    "identifier": item.identifier,
                    "status": item.status,
                    "total_tests": item.total_tests,
                    "passed_tests": item.passed_tests,
                    "failed_tests": item.failed_tests,
                    "skipped_tests": item.skipped_tests,
                    "duration_ms": item.duration_ms,
                    "error_message": item.error_message,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_folder_web_tests(
        self,
        project_identifier: str,
        folder_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取文件夹下的 Web 测试列表"""
        from sqlalchemy import select, func

        project = await self._get_project_by_identifier(project_identifier)

        query = select(WebTest).where(
            WebTest.project_id == project.id,
            WebTest.folder_id == UUID(folder_id)
        )

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        query = query.order_by(WebTest.created_at.desc())
        query = query.offset(offset).limit(page_size)

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return {
            "items": [
                {
                    "id": str(item.id),
                    "identifier": item.identifier,
                    "name": item.name,
                    "base_url": item.base_url,
                    "description": item.description,
                    "script_format": item.script_format,
                    "total_pages": item.total_pages,
                    "total_flows": item.total_flows,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
