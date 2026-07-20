"""
Web 登录态（storageState）生成服务

通过 Node.js Playwright 在后台执行表单登录，导出 storageState.json，
并归档到 MinIO。
"""

import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import async_session_factory
from app.config.minio_client import MinIOClient
from app.config.settings import settings
from app.models.attachment import Attachment, AttachmentEntityType
from app.models.environment import ProjectEnvironment
from app.models.project import Project
from app.models.storage_state_job import StorageStateJob
from app.repositories.environment_repo import EnvironmentRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.storage_state import LoginSelectors, StorageStateJobInfo
from app.utils.exceptions import BadRequestException, NotFoundException
from app.utils.shell_env import ensure_playwright_mcp_project
from app.utils.sync_executor import run_sync

logger = logging.getLogger(__name__)


class StorageStateService:
    """Web 登录态生成服务"""

    _locks: dict[tuple[UUID, Optional[UUID]], asyncio.Lock] = {}
    _locks_guard = asyncio.Lock()

    def __init__(self, session: AsyncSession):
        self.session = session
        self.project_repo = ProjectRepository(session)
        self.env_repo = EnvironmentRepository(session)

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    async def create_job(
        self,
        project_identifier: str,
        env_id: Optional[UUID | str],
        username: Optional[str],
        password: str,
        captcha: Optional[str],
        selectors: Optional[LoginSelectors],
        headless: bool,
        save_attachment: bool,
    ) -> tuple[StorageStateJob, str, Optional[str], LoginSelectors, Project, Optional[ProjectEnvironment]]:
        """创建生成任务并合并配置。

        返回: (job, effective_username, effective_captcha, effective_selectors, project, env)
        """
        if not password:
            raise BadRequestException("密码不能为空")

        project = await self._resolve_project(project_identifier)
        env = await self._resolve_environment(project.id, env_id)
        effective_username, effective_captcha, effective_selectors = self._merge_config(
            env, username, captcha, selectors
        )

        output_path = self._resolve_output_path()

        job = StorageStateJob(
            project_id=project.id,
            environment_id=env.id if env else None,
            status="pending",
            output_path=output_path,
        )
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)

        logger.info(
            "[StorageState] 已创建任务 job=%s project=%s env=%s output=%s headless=%s save_attachment=%s",
            job.id,
            project.identifier,
            env.id if env else None,
            output_path,
            headless,
            save_attachment,
        )

        return job, effective_username, effective_captcha, effective_selectors, project, env

    async def execute_generation(
        self,
        job_id: UUID,
        username: str,
        password: str,
        captcha: Optional[str],
        selectors: LoginSelectors,
        headless: bool,
        save_attachment: bool,
        project_identifier: str,
    ) -> None:
        """执行生成（可在后台任务中调用）。"""
        async with async_session_factory() as session:
            service = StorageStateService(session)
            await service._execute_generation(
                job_id=job_id,
                username=username,
                password=password,
                captcha=captcha,
                selectors=selectors,
                headless=headless,
                save_attachment=save_attachment,
                project_identifier=project_identifier,
            )

    async def get_job(self, project_identifier: str, job_id: UUID) -> StorageStateJobInfo:
        """查询任务详情。"""
        project = await self._resolve_project(project_identifier)
        job = await self.session.get(StorageStateJob, job_id)
        if not job or job.project_id != project.id:
            raise NotFoundException(resource_type="登录态生成任务", resource_id=str(job_id))
        return self.to_info(job)

    async def get_latest_success(self, project_identifier: str) -> Optional[StorageStateJobInfo]:
        """查询项目最近一次成功的生成记录。"""
        from sqlalchemy import select

        project = await self._resolve_project(project_identifier)
        result = await self.session.execute(
            select(StorageStateJob)
            .where(
                StorageStateJob.project_id == project.id,
                StorageStateJob.status == "completed",
            )
            .order_by(StorageStateJob.completed_at.desc())
            .limit(1)
        )
        job = result.scalar_one_or_none()
        return self.to_info(job) if job else None

    async def generate_and_wait(
        self,
        project_identifier: str,
        env_id: Optional[UUID | str],
        username: Optional[str],
        password: str,
        captcha: Optional[str],
        selectors: Optional[LoginSelectors],
        headless: bool,
        save_attachment: bool,
    ) -> StorageStateJobInfo:
        """创建并同步等待任务完成（供 CLI 使用）。"""
        job, effective_username, effective_captcha, effective_selectors, project, _ = await self.create_job(
            project_identifier=project_identifier,
            env_id=env_id,
            username=username,
            password=password,
            captcha=captcha,
            selectors=selectors,
            headless=headless,
            save_attachment=save_attachment,
        )
        await self._execute_generation(
            job_id=job.id,
            username=effective_username,
            password=password,
            captcha=effective_captcha,
            selectors=effective_selectors,
            headless=headless,
            save_attachment=save_attachment,
            project_identifier=project.identifier,
        )
        # 避免 commit 后对象过期触发同步懒加载
        await self.session.refresh(job)
        return self.to_info(job)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _resolve_project(self, project_identifier: str) -> Project:
        project = await self.project_repo.get_by_identifier(project_identifier)
        if not project:
            try:
                project_id = UUID(project_identifier)
                project = await self.project_repo.get_by_id(project_id)
            except ValueError:
                pass
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=project_identifier)
        return project

    async def _resolve_environment(
        self,
        project_id: UUID,
        env_id: Optional[UUID | str],
    ) -> Optional[ProjectEnvironment]:
        if env_id:
            env = await self.env_repo.get_by_id(UUID(str(env_id)))
            if not env or env.project_id != project_id:
                raise NotFoundException(resource_type="环境", resource_id=str(env_id))
            return env
        return await self.env_repo.get_default_by_project(project_id)

    def _merge_config(
        self,
        env: Optional[ProjectEnvironment],
        username: Optional[str],
        captcha: Optional[str],
        selectors: Optional[LoginSelectors],
    ) -> tuple[str, Optional[str], LoginSelectors]:
        """合并请求参数与环境配置中的 form_login 信息。"""
        effective_username = username
        effective_captcha = captcha
        effective_selectors = selectors

        if env and env.auth_type == "form_login":
            cfg = (env.auth_config or {}).get("form_login", {})
            if not effective_username:
                effective_username = cfg.get("username")
            if effective_selectors is None:
                stored_selectors = cfg.get("selectors", {})
                effective_selectors = LoginSelectors(
                    login_url=cfg.get("login_url", ""),
                    username_selector=stored_selectors.get(
                        "username_selector", "input[name='username']"
                    ),
                    password_selector=stored_selectors.get(
                        "password_selector", "input[name='password']"
                    ),
                    captcha_selector=stored_selectors.get("captcha_selector") or None,
                    submit_selector=stored_selectors.get(
                        "submit_selector", "button[type='submit']"
                    ),
                    success_selector=stored_selectors.get(
                        "success_selector", ".dashboard"
                    ),
                )
            elif effective_selectors.captcha_selector is None:
                stored_captcha_selector = (
                    cfg.get("selectors", {}).get("captcha_selector") or None
                )
                if stored_captcha_selector:
                    effective_selectors.captcha_selector = stored_captcha_selector

            # 将非空的验证码选择器回写到环境配置，方便下次预填充
            if (
                effective_selectors is not None
                and effective_selectors.captcha_selector
            ):
                env.auth_config = env.auth_config or {}
                env.auth_config.setdefault("form_login", {})
                env.auth_config["form_login"].setdefault("selectors", {})
                env.auth_config["form_login"]["selectors"][
                    "captcha_selector"
                ] = effective_selectors.captcha_selector

        if not effective_username:
            raise BadRequestException("用户名不能为空，请在请求或环境配置 auth_config.form_login.username 中提供")

        if effective_selectors is None or not effective_selectors.login_url:
            raise BadRequestException(
                "登录 URL 不能为空，请在请求 selectors 或环境配置 auth_config.form_login 中提供"
            )

        if bool(effective_captcha) != bool(effective_selectors.captcha_selector):
            raise BadRequestException("验证码和验证码选择器需同时填写或同时留空")

        return effective_username, effective_captcha, effective_selectors

    def _resolve_output_path(self) -> str:
        ss = getattr(settings, "web_mcp_storage_state", None)
        if ss:
            return str(Path(ss).resolve())
        # 未配置全局路径时回退到工作区默认位置，并给出提示
        default = Path(settings.web_mcp_root).resolve() / "storage-state" / "global.json"
        logger.warning(
            "[StorageState] settings.web_mcp_storage_state 未配置，生成结果将写入默认路径: %s",
            default,
        )
        return str(default)

    async def _acquire_lock(self, project_id: UUID, env_id: Optional[UUID]) -> asyncio.Lock:
        async with self._locks_guard:
            key = (project_id, env_id)
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    async def _execute_generation(
        self,
        job_id: UUID,
        username: str,
        password: str,
        captcha: Optional[str],
        selectors: LoginSelectors,
        headless: bool,
        save_attachment: bool,
        project_identifier: str,
    ) -> None:
        job = await self.session.get(StorageStateJob, job_id)
        if not job:
            logger.error("[StorageState] 任务 %s 不存在", job_id)
            return

        project = await self.project_repo.get_by_id(job.project_id)
        env = await self.env_repo.get_by_id(job.environment_id) if job.environment_id else None

        tmp_dir: Optional[Path] = None

        async with await self._acquire_lock(job.project_id, job.environment_id):
            try:
                job.status = "running"
                job.started_at = datetime.now(timezone.utc)
                await self.session.commit()

                output_path = Path(job.output_path)
                await run_sync(output_path.parent.mkdir, parents=True, exist_ok=True)

                web_mcp_root = Path(settings.web_mcp_root).resolve()
                tmp_dir = web_mcp_root / ".storage-state-jobs" / str(job_id)
                await run_sync(tmp_dir.mkdir, parents=True, exist_ok=True)

                config_path, _ = await self._write_setup_project(
                    tmp_dir, output_path, headless
                )

                env_vars = os.environ.copy()
                env_vars.update({
                    "LOGIN_URL": selectors.login_url,
                    "LOGIN_USERNAME": username,
                    "LOGIN_PASSWORD": password,
                    "CAPTCHA": captcha or "",
                    "CAPTCHA_SELECTOR": selectors.captcha_selector or "",
                    "USERNAME_SELECTOR": selectors.username_selector,
                    "PASSWORD_SELECTOR": selectors.password_selector,
                    "SUBMIT_SELECTOR": selectors.submit_selector,
                    "SUCCESS_SELECTOR": selectors.success_selector,
                    "STORAGE_STATE_PATH": str(output_path),
                    "PLAYWRIGHT_HEADLESS": "true" if headless else "false",
                })

                npx = "npx.cmd" if os.name == "nt" else "npx"
                logger.info(
                    "[StorageState] 开始执行 Playwright 登录脚本: job=%s url=%s",
                    job_id,
                    selectors.login_url,
                )

                proc = await asyncio.create_subprocess_exec(
                    npx,
                    "playwright",
                    "test",
                    "--config",
                    str(config_path),
                    "--project=setup",
                    cwd=str(web_mcp_root),
                    env=env_vars,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=settings.web_exec_timeout_seconds
                )
                stdout = stdout_b.decode("utf-8", errors="replace")
                stderr = stderr_b.decode("utf-8", errors="replace")

                if proc.returncode != 0:
                    raise RuntimeError(
                        f"Playwright 登录脚本执行失败（返回码 {proc.returncode}）:\n{stderr}\n{stdout}"
                    )

                if not await run_sync(output_path.exists):
                    raise RuntimeError(f"storageState 文件未生成: {output_path}")

                # 激活：更新 playwright.config.js 注入 storageState
                await ensure_playwright_mcp_project(
                    str(web_mcp_root),
                    headless=headless,
                    storage_state=str(output_path),
                )

                attachment_id: Optional[UUID] = None
                if save_attachment and project:
                    object_name = f"web-tests/{project_identifier}/storage-state/{job_id}.json"
                    data = await run_sync(output_path.read_bytes)
                    await run_sync(
                        MinIOClient.upload_bytes,
                        object_name=object_name,
                        data=data,
                        content_type="application/json",
                    )

                    attachment = Attachment(
                        entity_type=AttachmentEntityType.STORAGE_STATE,
                        entity_id=job.environment_id or job.project_id,
                        project_id=job.project_id,
                        file_name="storage-state.json",
                        file_size=len(data),
                        content_type="application/json",
                        object_name=object_name,
                        description=f"Web 登录态 storageState（项目 {project.name}）",
                        created_by="storage-state-service",
                    )
                    self.session.add(attachment)
                    await self.session.flush()
                    await self.session.refresh(attachment)
                    attachment_id = attachment.id

                job.status = "completed"
                job.attachment_id = attachment_id
                job.completed_at = datetime.now(timezone.utc)
                job.stdout = stdout[:100_000]
                job.stderr = stderr[:100_000]
                await self.session.commit()

                logger.info(
                    "[StorageState] 任务完成 job=%s output=%s attachment=%s",
                    job_id,
                    output_path,
                    attachment_id,
                )

            except Exception as e:
                error_msg = str(e)
                logger.exception("[StorageState] 任务失败 job=%s: %s", job_id, error_msg)
                job.status = "failed"
                job.error_message = error_msg[:4000]
                job.completed_at = datetime.now(timezone.utc)
                await self.session.commit()
            finally:
                if tmp_dir is not None:
                    try:
                        await run_sync(shutil.rmtree, tmp_dir, ignore_errors=True)
                    except Exception as cleanup_err:
                        logger.warning(
                            "[StorageState] 清理临时目录失败 %s: %s",
                            tmp_dir,
                            cleanup_err,
                        )

    async def _write_setup_project(
        self,
        tmp_dir: Path,
        output_path: Path,
        headless: bool,
    ) -> tuple[Path, Path]:
        def _write() -> tuple[Path, Path]:
            config_path = tmp_dir / "playwright.config.js"
            spec_path = tmp_dir / "setup.spec.ts"

            config_path.write_text(
                f"""module.exports = {{
  testDir: './',
  timeout: 60000,
  retries: 0,
  workers: 1,
  use: {{
    headless: {'true' if headless else 'false'},
    viewport: {{ width: 1280, height: 720 }},
  }},
  projects: [
    {{ name: 'setup', use: {{ browserName: 'chromium' }} }}
  ],
}};
""",
                encoding="utf-8",
            )

            spec_path.write_text(
                """import { test } from '@playwright/test';

test('login and save storage state', async ({ page }) => {
  const loginUrl = process.env.LOGIN_URL;
  const username = process.env.LOGIN_USERNAME;
  const password = process.env.LOGIN_PASSWORD;
  const captcha = process.env.CAPTCHA;
  const captchaSelector = process.env.CAPTCHA_SELECTOR;
  const outputPath = process.env.STORAGE_STATE_PATH;

  if (!loginUrl || !username || !password || !outputPath) {
    throw new Error('Missing LOGIN_URL, LOGIN_USERNAME, LOGIN_PASSWORD or STORAGE_STATE_PATH');
  }

  await page.goto(loginUrl);
  await page.waitForLoadState('networkidle');

  await page.locator(process.env.USERNAME_SELECTOR).fill(username);
  await page.locator(process.env.PASSWORD_SELECTOR).fill(password);
  if (captcha && captchaSelector) {
    await page.locator(captchaSelector).fill(captcha);
  }
  await page.locator(process.env.SUBMIT_SELECTOR).click();

  await page.waitForSelector(process.env.SUCCESS_SELECTOR, {
    state: 'visible',
    timeout: 30000,
  });

  await page.context().storageState({ path: outputPath });
});
""",
                encoding="utf-8",
            )
            return config_path, spec_path

        return await run_sync(_write)

    def to_info(self, job: StorageStateJob) -> StorageStateJobInfo:
        return StorageStateJobInfo(
            job_id=job.id,
            project_id=job.project_id,
            environment_id=job.environment_id,
            status=job.status,
            output_path=job.output_path,
            attachment_id=job.attachment_id,
            error_message=job.error_message,
            stdout=job.stdout,
            stderr=job.stderr,
            started_at=job.started_at,
            completed_at=job.completed_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
