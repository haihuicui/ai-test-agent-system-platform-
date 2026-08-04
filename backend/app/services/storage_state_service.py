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
import subprocess
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import async_session_factory
from app.config.minio_client import MinIOClient
from app.config.settings import settings
from app.models.attachment import Attachment, AttachmentEntityType
from app.models.environment import AuthType, ProjectEnvironment
from app.models.project import Project
from app.models.storage_state_job import StorageStateJob
from app.repositories.environment_repo import EnvironmentRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.storage_state import LoginSelectors, StorageStateJobInfo
from app.utils.exceptions import BadRequestException, NotFoundException
from app.utils.shell_env import ensure_playwright_mcp_project
from app.utils.storage_state_validator import validate_storage_state
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
        login_mode: str = "form_login",
        token_inject: Optional[dict] = None,
    ) -> tuple[StorageStateJob, str, Optional[str], LoginSelectors, Project, Optional[ProjectEnvironment]]:
        """创建生成任务并合并配置。

        返回: (job, effective_username, effective_captcha, effective_selectors, project, env)
        """
        if login_mode == "form_login" and not password:
            raise BadRequestException("密码不能为空")

        project = await self._resolve_project(project_identifier)
        env = await self._resolve_environment(project.id, env_id)
        effective_username, effective_captcha, effective_selectors = self._merge_config(
            env, username, captcha, selectors, login_mode=login_mode
        )

        # 先创建 job 以获取 job.id，再用 job.id 生成隔离输出路径
        job = StorageStateJob(
            project_id=project.id,
            environment_id=env.id if env else None,
            status="pending",
        )
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)

        job.output_path = self._resolve_output_path(
            project.id, env.id if env else None, job.id
        )

        logger.info(
            "[StorageState] 已创建任务 job=%s project=%s env=%s output=%s headless=%s save_attachment=%s login_mode=%s",
            job.id,
            project.identifier,
            env.id if env else None,
            job.output_path,
            headless,
            save_attachment,
            login_mode,
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
        login_mode: str = "form_login",
        token_inject: Optional[dict] = None,
    ) -> None:
        """执行生成（可在后台任务中调用）。"""
        async with async_session_factory() as session:
            service = StorageStateService(session)
            try:
                await service._execute_generation(
                    job_id=job_id,
                    username=username,
                    password=password,
                    captcha=captcha,
                    selectors=selectors,
                    headless=headless,
                    save_attachment=save_attachment,
                    project_identifier=project_identifier,
                    login_mode=login_mode,
                    token_inject=token_inject,
                )
            except Exception as e:
                logger.exception(
                    "[StorageState] 后台任务未捕获异常 job=%s: %s", job_id, e
                )
                try:
                    job = await session.get(StorageStateJob, job_id)
                    if job:
                        error_msg = str(e)
                        if isinstance(e, asyncio.TimeoutError):
                            error_msg = (
                                f"Playwright 登录脚本执行超时（超过 "
                                f"{settings.web_exec_timeout_seconds} 秒）"
                            )
                        elif not error_msg:
                            error_msg = f"{type(e).__name__}: 未知异常"
                        job.status = "failed"
                        job.error_message = error_msg[:4000]
                        job.stderr = f"{error_msg}\n\n{traceback.format_exc()}"[:100_000]
                        job.completed_at = datetime.now(timezone.utc)
                        await session.commit()
                except Exception as inner:
                    logger.error(
                        "[StorageState] 无法更新任务失败状态 job=%s: %s",
                        job_id,
                        inner,
                    )

    async def get_job(self, project_identifier: str, job_id: UUID) -> StorageStateJobInfo:
        """查询任务详情。"""
        project = await self._resolve_project(project_identifier)
        job = await self.session.get(StorageStateJob, job_id)
        if not job or job.project_id != project.id:
            raise NotFoundException(resource_type="登录态生成任务", resource_id=str(job_id))
        return self.to_info(job)

    async def get_latest_success(
        self,
        project_identifier: str,
        environment_id: Optional[UUID | str] = None,
    ) -> Optional[StorageStateJobInfo]:
        """查询项目最近一次成功的生成记录。

        优先匹配指定环境；无匹配时回退到项目级（environment_id IS NULL）记录。
        """
        from sqlalchemy import select

        project = await self._resolve_project(project_identifier)
        env_id_value = UUID(str(environment_id)) if environment_id else None

        query = (
            select(StorageStateJob)
            .where(
                StorageStateJob.project_id == project.id,
                StorageStateJob.status == "completed",
            )
            .order_by(StorageStateJob.completed_at.desc())
        )

        if env_id_value:
            # 先查环境隔离记录
            result = await self.session.execute(
                query.where(StorageStateJob.environment_id == env_id_value).limit(1)
            )
            job = result.scalar_one_or_none()
            if job:
                return self.to_info(job)

        # 回退：项目级记录或显式环境为 None 的记录
        result = await self.session.execute(
            query.where(StorageStateJob.environment_id.is_(None)).limit(1)
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
        login_mode: str = "form_login",
        token_inject: Optional[dict] = None,
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
            login_mode=login_mode,
            token_inject=token_inject,
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
            login_mode=login_mode,
            token_inject=token_inject,
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
        login_mode: str = "form_login",
    ) -> tuple[str, Optional[str], LoginSelectors]:
        """合并请求参数与环境配置中的登录态信息。

        支持两个来源：
        - auth_type == "form_login" 时读取 auth_config.form_login；
        - 其他 auth_type 时读取 auth_config.storage_state（不改动主认证类型）。
        token_inject 模式下 selectors 可为空，返回默认 LoginSelectors。
        """
        if login_mode == "token_inject":
            # token 注入模式不需要 selectors，返回默认值即可
            effective_username = username
            effective_captcha = captcha
            if env:
                auth_config = env.auth_config or {}
                token_cfg = auth_config.get("token_inject", {})
                token_body = token_cfg.get("token_body", {})
                if not effective_username:
                    effective_username = token_body.get("username")
                if not effective_captcha:
                    effective_captcha = token_body.get("captcha")
            # username/captcha 均可从 token_body 读取，不再强制要求单独提供
            return effective_username, effective_captcha, LoginSelectors(login_url="")

        effective_username = username
        effective_captcha = captcha
        effective_selectors = selectors

        cfg: Optional[dict] = None
        target_key = "form_login"
        if env:
            auth_config = env.auth_config or {}
            if env.auth_type == "form_login":
                cfg = auth_config.get("form_login", {})
            elif "storage_state" in auth_config:
                cfg = auth_config["storage_state"]
                target_key = "storage_state"

        if cfg:
            if not effective_username:
                effective_username = cfg.get("username")
            if not effective_captcha:
                effective_captcha = cfg.get("captcha")
            if effective_selectors is None:
                stored_selectors = cfg.get("selectors", {})
                effective_selectors = LoginSelectors(
                    pre_click_selector=stored_selectors.get("pre_click_selector") or None,
                    login_url=cfg.get("login_url", ""),
                    username_selector=stored_selectors.get("username_selector", ""),
                    password_selector=stored_selectors.get("password_selector", ""),
                    captcha_selector=stored_selectors.get("captcha_selector") or None,
                    submit_selector=stored_selectors.get("submit_selector", ""),
                    success_selector=stored_selectors.get("success_selector", ""),
                )
            elif effective_selectors.captcha_selector is None:
                stored_captcha_selector = (
                    cfg.get("selectors", {}).get("captcha_selector") or None
                )
                if stored_captcha_selector:
                    effective_selectors.captcha_selector = stored_captcha_selector

            # 将非空的 pre_click_selector / captcha_selector 回写到环境配置
            if effective_selectors is not None and effective_selectors.pre_click_selector:
                auth_config = env.auth_config or {}
                auth_config.setdefault(target_key, {})
                auth_config[target_key].setdefault("selectors", {})
                auth_config[target_key]["selectors"][
                    "pre_click_selector"
                ] = effective_selectors.pre_click_selector
                env.auth_config = auth_config

            # 将非空的验证码选择器回写到环境配置，方便下次预填充
            if (
                effective_selectors is not None
                and effective_selectors.captcha_selector
            ):
                auth_config = env.auth_config or {}
                auth_config.setdefault(target_key, {})
                auth_config[target_key].setdefault("selectors", {})
                auth_config[target_key]["selectors"][
                    "captcha_selector"
                ] = effective_selectors.captcha_selector
                env.auth_config = auth_config

            # 将非空的验证码值回写到环境配置，方便自动化测试复用
            if effective_captcha:
                auth_config = env.auth_config or {}
                auth_config.setdefault(target_key, {})
                auth_config[target_key]["captcha"] = effective_captcha
                env.auth_config = auth_config

        if not effective_username:
            raise BadRequestException(
                "用户名不能为空，请在请求或环境配置 auth_config.form_login.username 或 auth_config.storage_state.username 中提供"
            )

        if login_mode == "form_login" and (effective_selectors is None or not effective_selectors.login_url):
            raise BadRequestException(
                "登录 URL 不能为空，请在请求 selectors 或环境配置 auth_config.form_login / auth_config.storage_state 中提供"
            )

        if bool(effective_captcha) != bool(effective_selectors.captcha_selector):
            raise BadRequestException("验证码和验证码选择器需同时填写或同时留空")

        return effective_username, effective_captcha, effective_selectors

    def _resolve_output_path(
        self,
        project_id: Optional[UUID] = None,
        environment_id: Optional[UUID] = None,
        job_id: Optional[UUID] = None,
    ) -> str:
        """生成按项目+环境隔离的 storageState 输出文件路径。

        优先级：
        1. 有 project_id 和 job_id 时，使用项目/环境隔离路径
        2. 否则回退到 settings.web_mcp_storage_state（全局配置，保持旧行为）
        3. 再回退到 web_mcp_root/storage-state/global.json
        """
        root = Path(settings.web_mcp_root).resolve()
        if project_id is not None and job_id is not None:
            parts = ["storage-state", str(project_id)]
            if environment_id is not None:
                parts.append(str(environment_id))
            parts.append(f"{job_id}.json")
            return str(root / "/".join(parts))

        ss = getattr(settings, "web_mcp_storage_state", None)
        if ss:
            return str(Path(ss).resolve())

        # 未配置全局路径且无足够信息时回退到工作区默认位置
        default = root / "storage-state" / "global.json"
        logger.warning(
            "[StorageState] 未提供 project_id/job_id 且未配置全局路径，生成结果将写入默认路径: %s",
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
        login_mode: str = "form_login",
        token_inject: Optional[dict] = None,
    ) -> None:
        job = await self.session.get(StorageStateJob, job_id)
        if not job:
            logger.error("[StorageState] 任务 %s 不存在", job_id)
            return

        tmp_dir: Optional[Path] = None
        screenshot_path: Optional[Path] = None

        async with await self._acquire_lock(job.project_id, job.environment_id):
            try:
                job.status = "running"
                job.started_at = datetime.now(timezone.utc)
                await self.session.commit()

                project = await self.project_repo.get_by_id(job.project_id)
                env = await self.env_repo.get_by_id(job.environment_id) if job.environment_id else None

                output_path = Path(job.output_path)
                await run_sync(output_path.parent.mkdir, parents=True, exist_ok=True)

                stdout = ""
                stderr = ""
                if login_mode == "token_inject":
                    if not token_inject:
                        raise BadRequestException("token_inject 模式必须提供 token_inject 配置")
                    await self._generate_by_token_inject(
                        job_id=job_id,
                        token_inject=token_inject,
                        output_path=output_path,
                        headless=headless,
                    )
                else:
                    if not selectors.submit_selector or not selectors.submit_selector.strip():
                        raise BadRequestException("提交按钮选择器 SUBMIT_SELECTOR 不能为空")
                    if not selectors.success_selector or not selectors.success_selector.strip():
                        raise BadRequestException("成功页面元素选择器 SUCCESS_SELECTOR 不能为空")

                    web_mcp_root = Path(settings.web_mcp_root).resolve()
                    tmp_dir = web_mcp_root / ".storage-state-jobs" / str(job_id)
                    screenshot_path = tmp_dir / "failure-screenshot.png"
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
                        "PRE_CLICK_SELECTOR": selectors.pre_click_selector or "",
                        "USERNAME_SELECTOR": selectors.username_selector,
                        "PASSWORD_SELECTOR": selectors.password_selector,
                        "SUBMIT_SELECTOR": selectors.submit_selector,
                        "SUCCESS_SELECTOR": selectors.success_selector,
                        "STORAGE_STATE_PATH": str(output_path),
                        "FAILURE_SCREENSHOT_PATH": str(screenshot_path),
                        "PLAYWRIGHT_HEADLESS": "true" if headless else "false",
                    })

                    npx = "npx.cmd" if os.name == "nt" else "npx"
                    logger.info(
                        "[StorageState] 开始执行 Playwright 登录脚本: job=%s url=%s",
                        job_id,
                        selectors.login_url,
                    )

                    cmd = [
                        npx,
                        "playwright",
                        "test",
                        "--config",
                        str(config_path),
                        "--project=setup",
                    ]
                    stdout, stderr, returncode = await self._run_playwright_subprocess(
                        cmd=cmd,
                        cwd=str(web_mcp_root),
                        env=env_vars,
                        timeout=settings.web_exec_timeout_seconds,
                    )

                    if returncode != 0:
                        raise RuntimeError(
                            f"Playwright 登录脚本执行失败（返回码 {returncode}）:\n{stderr}\n{stdout}"
                        )

                if not await run_sync(output_path.exists):
                    raise RuntimeError(f"storageState 文件未生成: {output_path}")

                # 静态校验：解析 cookie expires / JWT exp，记录到任务元数据
                validation = validate_storage_state(output_path)
                job.is_valid = validation.is_valid
                job.expires_at = validation.earliest_expiry
                job.validation_reason = validation.reason
                logger.info(
                    "[StorageState] 生成完成并校验 job=%s is_valid=%s reason=%s",
                    job_id,
                    validation.is_valid,
                    validation.reason,
                )

                # 运行时探针：用生成的 storageState 访问需登录 API，401/403 判定失效并尝试重新生成
                probe_ok = True
                probe_reason = ""
                if settings.web_mcp_storage_state_probe_enabled and env is not None:
                    probe_ok, probe_reason = await self._probe_storage_state(
                        output_path, env, token_inject if login_mode == "token_inject" else None
                    )
                    if not probe_ok:
                        logger.warning(
                            "[StorageState] 运行时探针判定失效 job=%s env=%s reason=%s",
                            job_id,
                            env.id,
                            probe_reason,
                        )
                        # 如果当前是 token 注入模式且配置了 token_inject，立即重新生成一次
                        if login_mode == "token_inject" and token_inject:
                            logger.info(
                                "[StorageState] 探针失效，立即重新生成 token 注入登录态 job=%s",
                                job_id,
                            )
                            await self._generate_by_token_inject(
                                job_id=job_id,
                                token_inject=token_inject,
                                output_path=output_path,
                                headless=headless,
                            )
                            # 重新校验
                            validation = validate_storage_state(output_path)
                            job.is_valid = validation.is_valid
                            job.expires_at = validation.earliest_expiry
                            job.validation_reason = (
                                f"{validation.reason}（探针失效后重新生成）"
                            )
                            probe_ok, probe_reason = await self._probe_storage_state(
                                output_path, env, token_inject
                            )
                            if not probe_ok:
                                raise RuntimeError(
                                    f"storageState 运行时探针二次判定失效: {probe_reason}"
                                )
                        else:
                            raise RuntimeError(
                                f"storageState 运行时探针判定失效: {probe_reason}"
                            )

                # 激活：更新 playwright.config.js 注入 storageState
                web_mcp_root = Path(settings.web_mcp_root).resolve()
                await ensure_playwright_mcp_project(
                    str(web_mcp_root),
                    headless=headless,
                    storage_state=str(output_path),
                )

                # 更新环境认证配置与凭据：测试环境下密码作为普通字段保存到 auth_secret，
                # 与 username/selectors 一起写入 auth_config.form_login，供后续自动续期使用。
                if env is not None:
                    auth_config = env.auth_config or {}
                    if login_mode == "token_inject":
                        # token 注入模式：保存 token_inject 配置，password 从 token_body 提取写入 auth_secret
                        auth_config["token_inject"] = token_inject
                        token_body = (token_inject or {}).get("token_body", {})
                        env.auth_secret = token_body.get("password") or password or ""
                        env.auth_config = auth_config
                        if env.auth_type == AuthType.NONE.value:
                            env.auth_type = AuthType.FORM_LOGIN.value
                            logger.info(
                                "[StorageState] 环境 %s auth_type 自动切换为 form_login",
                                env.id,
                            )
                        logger.info(
                            "[StorageState] 环境 %s token 注入配置已更新", env.id
                        )
                    else:
                        form_login_selectors = {
                            "pre_click_selector": selectors.pre_click_selector,
                            "username_selector": selectors.username_selector,
                            "password_selector": selectors.password_selector,
                            "captcha_selector": selectors.captcha_selector,
                            "submit_selector": selectors.submit_selector,
                            "success_selector": selectors.success_selector,
                        }
                        # 过滤掉 None 值，保持配置简洁
                        form_login_selectors = {
                            k: v for k, v in form_login_selectors.items() if v
                        }
                        form_login = {
                            "username": username,
                            "login_url": selectors.login_url,
                            "selectors": form_login_selectors,
                        }
                        if captcha:
                            form_login["captcha"] = captcha

                        # 向后兼容：若之前仅有 auth_config.storage_state，先同步到 form_login
                        storage_cfg = auth_config.get("storage_state")
                        if storage_cfg and "form_login" not in auth_config:
                            auth_config["form_login"] = storage_cfg

                        existing_form_login = auth_config.get("form_login", {})
                        existing_form_login.update(form_login)
                        auth_config["form_login"] = existing_form_login

                        # 测试环境：密码作为普通字段明文保存
                        env.auth_secret = password
                        env.auth_config = auth_config

                        if env.auth_type == AuthType.NONE.value:
                            env.auth_type = AuthType.FORM_LOGIN.value
                            logger.info(
                                "[StorageState] 环境 %s auth_type 自动切换为 form_login",
                                env.id,
                            )
                        logger.info(
                            "[StorageState] 环境 %s 登录凭据已更新", env.id
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

                # 生成成功后，若环境已保存密码，则注册到期前自动续期调度
                if (
                    settings.web_mcp_storage_state_auto_renew_enabled
                    and job.expires_at
                    and env is not None
                    and env.auth_secret
                ):
                    # 延迟导入避免与 scheduler_service 循环依赖
                    from app.services.scheduler_service import get_scheduler_service

                    buffer = timedelta(
                        minutes=settings.web_mcp_storage_state_auto_renew_buffer_minutes
                    )
                    run_at = job.expires_at - buffer
                    if run_at > datetime.now(timezone.utc):
                        scheduler = get_scheduler_service()
                        scheduler.schedule_storage_state_renewal(
                            env_id=str(env.id),
                            run_at=run_at,
                        )
                        logger.info(
                            "[StorageState] 已注册自动续期: env=%s run_at=%s",
                            env.id,
                            run_at.isoformat(),
                        )

                logger.info(
                    "[StorageState] 任务完成 job=%s output=%s attachment=%s",
                    job_id,
                    output_path,
                    attachment_id,
                )

            except Exception as e:
                error_msg = str(e)
                if isinstance(e, asyncio.TimeoutError):
                    error_msg = (
                        f"Playwright 登录脚本执行超时（超过 "
                        f"{settings.web_exec_timeout_seconds} 秒）"
                    )
                elif not error_msg:
                    error_msg = f"{type(e).__name__}: 未知异常"
                logger.exception("[StorageState] 任务失败 job=%s: %s", job_id, error_msg)

                _MAX_LOG_LENGTH = 100_000
                stdout_local = locals().get("stdout", "")
                stderr_local = locals().get("stderr", "")
                tb = traceback.format_exc()
                if not stderr_local:
                    stderr_local = f"{error_msg}\n\n{tb}"
                else:
                    stderr_local = f"{stderr_local}\n\nTraceback:\n{tb}"
                if len(stdout_local) > _MAX_LOG_LENGTH:
                    stdout_local = stdout_local[:_MAX_LOG_LENGTH] + "\n...[truncated]"
                if len(stderr_local) > _MAX_LOG_LENGTH:
                    stderr_local = stderr_local[:_MAX_LOG_LENGTH] + "\n...[truncated]"

                failure_screenshot_attachment_id: Optional[UUID] = None
                project = locals().get("project")
                project_name = project.name if project else "未知项目"
                if screenshot_path and await run_sync(screenshot_path.exists):
                    try:
                        img_bytes = await run_sync(screenshot_path.read_bytes)
                        object_name = f"web-tests/{project_identifier}/storage-state/{job_id}/failure-screenshot.png"
                        await run_sync(
                            MinIOClient.upload_bytes,
                            object_name=object_name,
                            data=img_bytes,
                            content_type="image/png",
                        )
                        att = Attachment(
                            entity_type=AttachmentEntityType.STORAGE_STATE_JOB,
                            entity_id=job_id,
                            project_id=job.project_id,
                            file_name="failure-screenshot.png",
                            file_size=len(img_bytes),
                            content_type="image/png",
                            object_name=object_name,
                            description=f"登录态生成失败截图（项目 {project_name}）",
                            created_by="storage-state-service",
                        )
                        self.session.add(att)
                        await self.session.flush()
                        await self.session.refresh(att)
                        failure_screenshot_attachment_id = att.id
                    except Exception as upload_err:
                        logger.warning(
                            "[StorageState] 上传失败截图失败 job=%s: %s",
                            job_id,
                            upload_err,
                        )

                job.status = "failed"
                job.error_message = error_msg[:4000]
                job.stdout = stdout_local
                job.stderr = stderr_local
                job.failure_screenshot_attachment_id = failure_screenshot_attachment_id
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

    async def _run_playwright_subprocess(
        self,
        cmd: list[str],
        cwd: str,
        env: dict[str, str],
        timeout: float,
    ) -> tuple[str, str, int]:
        """在线程池中执行 Playwright 子进程。

        不直接使用 asyncio 子进程，避免 Windows 下 SelectorEventLoop / 某些 uvicorn
        配置不支持 subprocess 而抛出 NotImplementedError。
        """
        try:
            result = await run_sync(
                subprocess.run,
                cmd,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            raise asyncio.TimeoutError

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
    trace: 'on',
    screenshot: 'on',
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
  const preClickSelector = process.env.PRE_CLICK_SELECTOR;
  const outputPath = process.env.STORAGE_STATE_PATH;
  const submitSelector = process.env.SUBMIT_SELECTOR;
  const successSelector = process.env.SUCCESS_SELECTOR;

  if (!loginUrl || !username || !password || !outputPath) {
    throw new Error('Missing LOGIN_URL, LOGIN_USERNAME, LOGIN_PASSWORD or STORAGE_STATE_PATH');
  }
  if (!submitSelector || !successSelector) {
    throw new Error(`Missing SUBMIT_SELECTOR or SUCCESS_SELECTOR: submit=${submitSelector}, success=${successSelector}`);
  }

  try {
    await page.goto(loginUrl);
    await page.waitForLoadState('networkidle');

    if (preClickSelector) {
      await page.locator(preClickSelector).waitFor({ state: 'visible', timeout: 10000 });
      await page.locator(preClickSelector).click();
      await page.waitForTimeout(500);
    }

    await page.locator(process.env.USERNAME_SELECTOR).waitFor({ state: 'visible', timeout: 15000 });
    await page.locator(process.env.USERNAME_SELECTOR).fill(username);
    await page.locator(process.env.PASSWORD_SELECTOR).waitFor({ state: 'visible', timeout: 15000 });
    await page.locator(process.env.PASSWORD_SELECTOR).fill(password);
    if (captcha && captchaSelector) {
      await page.locator(captchaSelector).waitFor({ state: 'visible', timeout: 10000 });
      await page.locator(captchaSelector).fill(captcha);
    }

    await page.locator(submitSelector).waitFor({ state: 'visible', timeout: 15000 });
    await page.locator(submitSelector).click();

    await page.waitForSelector(successSelector, {
      state: 'visible',
      timeout: 30000,
    });

    await page.context().storageState({ path: outputPath });
  } catch (e) {
    const screenshotPath = process.env.FAILURE_SCREENSHOT_PATH;
    if (screenshotPath) {
      try {
        await page.screenshot({ path: screenshotPath, fullPage: true });
      } catch (screenshotErr) {
        console.error('Failed to take failure screenshot:', screenshotErr);
      }
    }
    throw e;
  }
});
""",
                encoding="utf-8",
            )
            return config_path, spec_path

        return await run_sync(_write)

    async def _generate_by_token_inject(
        self,
        job_id: UUID,
        token_inject: dict,
        output_path: Path,
        headless: bool,
    ) -> None:
        """通过 API 获取 token 并注入浏览器生成 storageState。"""
        import httpx
        from jsonpath_ng import parse as jsonpath_parse

        token_url = token_inject.get("token_url")
        if not token_url:
            raise BadRequestException("token_inject 配置缺少 token_url")
        token_method = (token_inject.get("token_method") or "POST").upper()
        token_body = token_inject.get("token_body") or {}
        token_path = token_inject.get("token_path") or "$.data.token"
        inject_localstorage = token_inject.get("inject_localstorage") or {
            "token": "{token}",
            "userStatus": "login",
        }
        inject_cookies = token_inject.get("inject_cookies") or [
            {"name": "Authorization", "value": "{token}"}
        ]
        target_domains = token_inject.get("target_domains") or []
        if not target_domains:
            raise BadRequestException("token_inject 配置缺少 target_domains")

        # 1. 调用 token 接口获取 token
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if token_method == "GET":
                    resp = await client.get(token_url, params=token_body)
                else:
                    resp = await client.request(
                        token_method,
                        token_url,
                        json=token_body if isinstance(token_body, dict) else None,
                        content=token_body if isinstance(token_body, str) else None,
                    )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            raise RuntimeError(f"获取 token 失败: {e}") from e

        # 2. 提取 token
        try:
            if token_path.startswith("$"):
                jsonpath_expr = jsonpath_parse(token_path)
                matches = jsonpath_expr.find(data)
                if not matches:
                    raise RuntimeError(f"JSONPath '{token_path}' 未匹配到任何值")
                token = matches[0].value
            else:
                current = data
                for part in token_path.split("."):
                    current = current[part]
                token = current
            if not isinstance(token, str) or not token:
                raise RuntimeError(f"提取到的 token 无效: {token!r}")
        except Exception as e:
            raise RuntimeError(f"提取 token 失败: {e}") from e

        logger.info("[StorageState] token 获取成功 job=%s token=%s...", job_id, token[:20])

        # 3. 用 Playwright 注入每个目标域
        web_mcp_root = Path(settings.web_mcp_root).resolve()
        tmp_dir = web_mcp_root / ".storage-state-jobs" / str(job_id)
        await run_sync(tmp_dir.mkdir, parents=True, exist_ok=True)

        spec_path = tmp_dir / "token-inject.spec.ts"
        config_path = tmp_dir / "playwright.config.js"

        # 生成注入脚本
        localstorage_js = "\n".join(
            f"    localStorage.setItem({json.dumps(k)}, {json.dumps(v.replace('{token}', token))});"
            for k, v in inject_localstorage.items()
        )
        cookies_json = json.dumps([
            {
                "name": c.get("name", "Authorization"),
                "value": c.get("value", "{token}").replace("{token}", token),
                "domain": domain,
                "path": c.get("path", "/"),
                "expires": int(datetime.now(timezone.utc).timestamp()) + token_inject.get("token_ttl_seconds", 604800),
            }
            for domain in target_domains
            for c in inject_cookies
        ])

        config_content = f"""module.exports = {{
  testDir: './',
  timeout: 120000,
  retries: 0,
  workers: 1,
  use: {{
    headless: {'true' if headless else 'false'},
    viewport: {{ width: 1280, height: 720 }},
    trace: 'on',
    screenshot: 'on',
  }},
  projects: [
    {{ name: 'token-inject', use: {{ browserName: 'chromium' }} }}
  ],
}};
"""
        await run_sync(config_path.write_text, config_content, encoding="utf-8")

        spec_content = f"""import {{ test }} from '@playwright/test';

const token = {json.dumps(token)};
const targetDomains = {json.dumps(target_domains)};
const cookies = {cookies_json};

test('token inject and save storage state', async ({{ context, page }}) => {{
  // 注入 cookies
  await context.addCookies(cookies);

  for (const domain of targetDomains) {{
    const url = `https://${{domain}}`;
    await page.goto(url);
    await page.waitForLoadState('networkidle');

    // 注入 localStorage
    await page.evaluate(() => {{
{localstorage_js}
    }});

    // 刷新使 localStorage 生效
    await page.reload();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
  }}

  // 保存 storageState
  await context.storageState({{ path: {json.dumps(str(output_path))} }});
}});
"""
        await run_sync(spec_path.write_text, spec_content, encoding="utf-8")

        # 4. 执行 Playwright 脚本
        npx = "npx.cmd" if os.name == "nt" else "npx"
        cmd = [
            npx,
            "playwright",
            "test",
            "--config",
            str(config_path),
            "--project=token-inject",
        ]
        stdout, stderr, returncode = await self._run_playwright_subprocess(
            cmd=cmd,
            cwd=str(web_mcp_root),
            env=os.environ.copy(),
            timeout=settings.web_exec_timeout_seconds,
        )
        if returncode != 0:
            raise RuntimeError(
                f"Playwright token 注入脚本执行失败（返回码 {returncode}）:\n{stderr}\n{stdout}"
            )

        logger.info("[StorageState] token 注入完成 job=%s", job_id)

    async def _probe_storage_state(
        self,
        output_path: Path,
        env: ProjectEnvironment,
        token_inject: Optional[dict] = None,
    ) -> tuple[bool, str]:
        """运行时探针：用生成的 storageState 访问需登录 API，判定是否失效。

        返回 (是否有效, 原因说明)。
        """
        import json as json_module

        try:
            # 读取 storageState 提取 Authorization cookie 或 localStorage token
            ss_data = json_module.loads(await run_sync(output_path.read_text, encoding="utf-8"))
            token: Optional[str] = None

            # 优先从 localStorage 取 token
            for origin_entry in ss_data.get("origins", []):
                for item in origin_entry.get("localStorage", []):
                    if item.get("name") == "token":
                        token = item.get("value")
                        break
                if token:
                    break

            # 其次从 cookies 取 Authorization
            if not token:
                for cookie in ss_data.get("cookies", []):
                    if cookie.get("name") == "Authorization":
                        token = cookie.get("value")
                        break

            if not token:
                return False, "storageState 中未找到 token/Authorization"

            # 确定探针目标 URL
            probe_path = settings.web_mcp_storage_state_probe_path
            if token_inject and token_inject.get("target_domains"):
                # token 注入模式：优先用第一个目标域
                domain = token_inject["target_domains"][0]
                probe_url = f"https://{domain}{probe_path}"
            else:
                # form_login 模式：用环境 base_url
                base_url = (env.base_url or "").rstrip("/")
                if not base_url:
                    return False, "环境 base_url 为空，无法执行运行时探针"
                probe_url = f"{base_url}{probe_path}"

            # 发起探针请求
            import httpx
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
                resp = await client.get(
                    probe_url,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code in (401, 403):
                    return False, f"探针返回 {resp.status_code}: {resp.text[:200]}"
                if resp.status_code >= 500:
                    return False, f"探针返回服务端错误 {resp.status_code}"
                # 2xx/3xx/404 都视为通过（404 可能只是接口不存在，但 token 本身有效）
                return True, f"探针通过: {probe_url} status={resp.status_code}"
        except Exception as e:
            logger.warning("[StorageState] 运行时探针异常: %s", e)
            return False, f"探针异常: {type(e).__name__}: {e}"

    def to_info(self, job: StorageStateJob) -> StorageStateJobInfo:
        return StorageStateJobInfo(
            job_id=job.id,
            project_id=job.project_id,
            environment_id=job.environment_id,
            status=job.status,
            output_path=job.output_path,
            attachment_id=job.attachment_id,
            failure_screenshot_attachment_id=job.failure_screenshot_attachment_id,
            error_message=job.error_message,
            stdout=job.stdout,
            stderr=job.stderr,
            is_valid=job.is_valid,
            expires_at=job.expires_at,
            validation_reason=job.validation_reason,
            probe_status=job.probe_status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
