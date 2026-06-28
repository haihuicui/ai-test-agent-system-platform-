"""
Web 测试服务

处理 Web 测试相关的业务逻辑
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

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
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)

                    # 写入测试脚本
                    script_file = temp_path / "web-test.spec.ts"
                    script_file.write_text(script_content, encoding="utf-8")

                    # 创建 Playwright 配置
                    playwright_config = self._generate_playwright_config(
                        web_test, execution_config
                    )
                    config_file = temp_path / "playwright.config.ts"
                    config_file.write_text(playwright_config, encoding="utf-8")

                    # 4. 执行测试
                    result = await self._run_playwright_test(
                        temp_dir, execution_config
                    )

                    # 5. 解析结果并更新
                    total = result.get("total", 0)
                    passed = result.get("passed", 0)
                    failed = result.get("failed", 0)
                    skipped = result.get("skipped", 0)
                    error = result.get("error")

                    await run_repo.update(
                        await run_repo.get_by_id(run_id),
                        status="completed" if result.get("success") else "failed",
                        total_tests=total,
                        passed_tests=passed,
                        failed_tests=failed,
                        skipped_tests=skipped,
                        error_message=error,
                        duration_ms=result.get("duration_ms"),
                    )
                    await session.commit()

            except Exception as e:
                await run_repo.update(
                    await run_repo.get_by_id(run_id),
                    status="failed",
                    error_message=str(e),
                )
                await session.commit()
                print(f"Web 测试执行失败: {e}")

    def _generate_playwright_config(
        self, web_test: WebTest, execution_config: dict
    ) -> str:
        """生成 Playwright 配置文件"""
        headless = execution_config.get("headless", True)
        browser = execution_config.get("browser", "chromium")
        viewport = execution_config.get("viewport", {"width": 1280, "height": 720})
        slow_mo = execution_config.get("slow_mo", 0)

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
  }},
  projects: [
    {{
      name: 'web-tests',
      use: {{ ...devices['Desktop {browser.capitalize()}'] }},
    }},
  ],
}});
"""

    async def _run_playwright_test(
        self,
        work_dir: str,
        execution_config: dict,
    ) -> dict:
        """运行 Playwright 测试"""
        start_time = datetime.now()
        timeout = execution_config.get("timeout", 300)

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
            )
            await asyncio.wait_for(npx_check.communicate(), timeout=10)
            if npx_check.returncode != 0:
                raise Exception("npx 不可用，请确保 Node.js 已安装")

            # 运行 Playwright 测试
            proc = await asyncio.create_subprocess_exec(
                *npx_cmd, "playwright", "test",
                "--reporter=json",
                cwd=work_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # 尝试解析 JSON 结果
            try:
                result_data = json.loads(stdout.decode("utf-8"))
                stats = result_data.get("stats", {})
                return {
                    "success": proc.returncode == 0,
                    "total": stats.get("tests", 0),
                    "passed": stats.get("expected", 0),
                    "failed": stats.get("unexpected", 0),
                    "skipped": stats.get("skipped", 0),
                    "duration_ms": duration_ms,
                    "error": stderr.decode("utf-8") if proc.returncode != 0 else None,
                }
            except json.JSONDecodeError:
                # JSON 解析失败，使用简化结果
                return {
                    "success": proc.returncode == 0,
                    "total": 1,
                    "passed": 1 if proc.returncode == 0 else 0,
                    "failed": 0 if proc.returncode == 0 else 1,
                    "skipped": 0,
                    "duration_ms": duration_ms,
                    "error": stderr.decode("utf-8") if proc.returncode != 0 else None,
                }
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZGtSSVRRPT06MjUwZjQ4ZDM=

        except asyncio.TimeoutError:
            return {
                "success": False,
                "total": 0,
                "passed": 0,
                "failed": 1,
                "skipped": 0,
                "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                "error": f"测试执行超时（{timeout}秒）",
            }
        except Exception as e:
            return {
                "success": False,
                "total": 0,
                "passed": 0,
                "failed": 1,
                "skipped": 0,
                "duration_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                "error": str(e),
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
