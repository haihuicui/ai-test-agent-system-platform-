"""
API 测试脚本执行工具

提供在测试目录中执行 API 测试脚本的功能
"""

import os
import sys
import json
import uuid
import zipfile
import shutil
import asyncio
import socket
import re
import logging
import subprocess
from urllib.parse import urlparse
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timezone
from uuid import UUID

logger = logging.getLogger(__name__)

from langchain_core.tools import tool
from langgraph.config import get_config
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.api.runtime_context import get_conversation_id as get_ctx_conversation_id
from app.utils.sync_executor import run_sync
from app.config import settings
from app.config.database import async_session_factory
from app.models.attachment import Attachment, AttachmentEntityType
from app.models.api_endpoint import APIEndpoint
from app.models.api_test import APITest, APITestRun, APITestResult
from app.repositories.api_test_repo import (
    APITestRepository,
    APITestRunRepository,
    APITestResultRepository,
)
from app.schemas.enums import TestResultStatus
from app.services.api_test_executor import (
    APITestExecutor,
    _ensure_trace_helper,
    _get_business_code_env_value,
    _parse_api_trace,
    _rewrite_script_imports,
)
from app.config.minio_client import MinIOClient
from app.services.environment_service import EnvironmentService
from app.utils.exceptions import BadRequestException

print(f"[TRACE-DEBUG] execution_tools loaded from {__file__}")


def _get_conversation_id() -> Optional[str]:
    """
    获取当前 AI 会话 ID。

    优先从 LangGraph 运行配置读取（工具调用上下文内最可靠），
    读取不到时回退到 contextvar。
    """
    try:
        config = get_config()
        if config and isinstance(config.get("configurable"), dict):
            conversation_id = config["configurable"].get("conversation_id")
            if conversation_id:
                return conversation_id
    except Exception:
        pass
    return get_ctx_conversation_id()


# ============================================================================
# 测试目录配置
# ============================================================================

# 测试服务器根目录
WORKSPACE_TESTS_ROOT = Path(settings.api_workspace_root) / "tests"
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TkUxcll3PT06ZGQyYmExYzM=


def get_workspace_tests_dir() -> Path:
    """
    获取 workspace 测试目录路径

    Returns:
        workspace 测试目录的绝对路径
    """
    return WORKSPACE_TESTS_ROOT


def get_project_root() -> Path:
    """
    获取项目根目录（用于在 workspace 测试目录中找到 package.json）

    Returns:
        项目根目录的绝对路径
    """
    return Path(settings.api_workspace_root)


def _ensure_node_in_path(env: Dict[str, str]) -> Dict[str, str]:
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


@tool
async def execute_api_script(
    local_script_path: str,
    framework: str = "playwright",
    reporter: str = "html",
    project_identifier: str = "PR-1",
    endpoint_id: Optional[str] = None,
    execution_config: Optional[Dict[str, Any]] = None
) -> str:
    """
    执行已下载到测试目录的 API 测试脚本

    此工具会：
    1. 验证脚本文件存在于 workspace 测试目录
    2. 执行测试（Playwright/Jest/Pytest）
    3. 生成测试报告（HTML/JSON）
    4. 将测试报告保存到 MinIO
    5. 在数据库中创建测试报告附件记录
    6. 更新端点的测试运行次数
    7. 清理临时报告文件

    Args:
        local_script_path: 本地脚本文件的完整路径（相对或绝对路径）
        framework: 测试框架 (playwright, jest, pytest)
        reporter: 报告格式 (html, json, list)
        project_identifier: 项目标识符，用于保存测试报告
        endpoint_id: 端点 ID（可选，用于更新测试统计）
        execution_config: 执行配置（可选）
            - env_id: 项目环境 ID，后端会自动解析该环境的 base_url、auth、headers（推荐）
            - base_url: API Base URL，会注入为环境变量 API_BASE_URL（仅当用户明确要求时直接使用）
            - env: 额外环境变量字典，如 {"AUTH_TOKEN": "..."}，会覆盖后端自动注入的值
            - environment_variables: env 的别名，兼容旧调用

    环境注入说明：
        - 静态认证（bearer/api_key/oauth2）：后端从环境的 auth_secret 注入 AUTH_TOKEN / Authorization 等变量
        - 动态认证（dynamic_bearer）：后端会根据环境的 auth_config.token_url 自动获取 token 并注入 AUTH_TOKEN
        - 脚本里应只读取 process.env.AUTH_TOKEN / process.env.API_BASE_URL，禁止写 fallback 默认值

    Returns:
        JSON 格式的执行结果，包含：
        - success: 是否成功
        - exit_code: 语义化退出码
            0=全部通过, 1=有失败, 2=环境不可达, 3=超时, 4=脚本/执行错误
        - preflight_status: 执行前环境探针状态
        - script_path: 执行的脚本路径
        - execution_result: 执行结果（stdout, stderr, duration, return_code）
        - report_attachment_id: 测试报告附件 ID（如果生成了报告）
        - error: 错误信息（如果有）

    Example:
        >>> result = await execute_api_script(
        ...     local_script_path="backend/workspace/api/tests/login_test.spec.ts",
        ...     framework="playwright",
        ...     reporter="html",
        ...     project_identifier="PR-3",
        ...     endpoint_id="5ea81a5f-c97b-4a36-a680-13637f1b9eed",
        ...     execution_config={
        ...         "env_id": "550e8400-e29b-41d4-a716-446655440000",
        ...         "env": {"OPTIONAL_HEADER": "value"}
        ...     }
        ... )
    """
    try:
        # 用于诊断的上下文，最终随结果返回
        diagnostics: Dict[str, Any] = {
            "received_execution_config": execution_config,
            "resolved_env_id": None,
            "resolved_base_url": None,
            "resolved_env_keys": [],
            "script_path": None,
            "working_directory": None,
            "command": None,
        }

        # 读取当前 AI 会话 ID（优先从 LangGraph 运行配置读取）
        conversation_id = _get_conversation_id()
        diagnostics["conversation_id"] = conversation_id

        # 1. 解析脚本路径
        # 清理路径：去除开头的斜杠或反斜杠，标准化分隔符
        cleaned_path = local_script_path.strip().strip('/').strip('\\')
        script_path = Path(cleaned_path)
        project_root = Path(settings.api_workspace_root).resolve()
        workspace_tests_dir = get_workspace_tests_dir()

        # 2. 标准化路径：如果是绝对路径，直接使用；如果是相对路径，在 workspace_tests_dir 中查找
        if script_path.is_absolute():
            # 绝对路径：直接使用
            pass
        else:
            # 相对路径：尝试多种解析方式
            # 方式1: 路径已经是相对于 project_root 的格式 (如: "tests/test.spec.ts")
            test_path_full = project_root / script_path
            if await run_sync(test_path_full.exists):
                script_path = test_path_full
            # 方式2: 只在 workspace_tests_dir 中查找文件名
            else:
                test_path = workspace_tests_dir / script_path.name
                if await run_sync(test_path.exists):
                    script_path = test_path
                # 方式3: 尝试添加 .spec.ts 扩展名
                elif not script_path.suffix:
                    test_path_with_ext = workspace_tests_dir / f"{script_path.name}.spec.ts"
                    if await run_sync(test_path_with_ext.exists):
                        script_path = test_path_with_ext

        # 3. 验证脚本文件存在
        if not await run_sync(script_path.exists):
            diagnostics["script_path"] = str(script_path)
            return json.dumps({
                "success": False,
                "exit_code": 4,
                "error": f"脚本文件不存在: {script_path}",
                "diagnostics": diagnostics,
            }, ensure_ascii=False, indent=2)

        script_filename = script_path.name

        print(f"[API Script Execution] 准备执行脚本: {script_path}")

        # 4. 计算相对路径（相对于 project_root）
        try:
            relative_path = script_path.resolve().relative_to(project_root)
        except ValueError:
            # 如果无法计算相对路径，使用文件名
            relative_path = script_path.name

        diagnostics["script_path"] = relative_path.as_posix()
        diagnostics["working_directory"] = str(project_root)

        print(f"[API Script Execution] 项目根目录: {project_root}")
        print(f"[API Script Execution] 相对脚本路径: {relative_path}")

        # 5. 解析执行环境变量（支持 execution_config + 项目环境 fallback）
        resolved_base_url, resolved_env, env_resolution_error = await _resolve_execution_env(
            project_identifier=project_identifier,
            endpoint_id=endpoint_id,
            execution_config=execution_config
        )

        diagnostics["resolved_env_id"] = (
            execution_config.get("env_id") if isinstance(execution_config, dict) else None
        )
        diagnostics["resolved_base_url"] = resolved_base_url
        diagnostics["resolved_env_keys"] = list(resolved_env.keys())
        diagnostics["env_resolution_error"] = env_resolution_error

        # 6. 执行脚本
        execution_result = await _execute_script_internal(
            script_path=relative_path.as_posix(),
            script_filename=script_filename,
            framework=framework,
            reporter=reporter,
            project_root=str(project_root),
            base_url=resolved_base_url,
            env_vars=resolved_env,
            script_abs_path=str(script_path),
        )

        diagnostics["command"] = execution_result.get("command")

        # 把内部错误也暴露到 stderr，方便前端/Agent 直接读取
        if execution_result.get("error") and not execution_result.get("stderr"):
            execution_result["stderr"] = execution_result["error"]

        # 6. 保存测试报告到 MinIO（如果生成了 HTML 报告）
        report_attachment_id = None
        report_object_name = None
        if endpoint_id and reporter == "html" and execution_result.get("report_path"):
            try:
                # 获取端点信息
                async with async_session_factory() as db:
                    endpoint_result = await db.execute(
                        select(APIEndpoint).where(APIEndpoint.id == UUID(endpoint_id))
                    )
                    endpoint = endpoint_result.scalar_one_or_none()

                if endpoint:
                    save_result = await _save_test_report(
                        endpoint_id=endpoint_id,
                        project_identifier=project_identifier,
                        endpoint=endpoint,
                        report_path=execution_result["report_path"],
                        execution_result=execution_result,
                        project_root=str(project_root),
                        conversation_id=conversation_id,
                    )
                    if save_result:
                        report_attachment_id, report_object_name = save_result
            except Exception as e:
                logger.exception("[execute_api_script] 保存测试报告失败: %s", e)
                execution_result["stderr"] = (
                    execution_result.get("stderr", "") + f"\n[警告] 保存测试报告失败: {e}"
                ).strip()

        # 7. 写入 api_test_runs / api_test_results（执行历史核心修复）
        if endpoint_id:
            try:
                async with async_session_factory() as db:
                    endpoint_result = await db.execute(
                        select(APIEndpoint).where(APIEndpoint.id == UUID(endpoint_id))
                    )
                    endpoint = endpoint_result.scalar_one_or_none()

                    if endpoint:
                        script_language = _infer_script_language(script_path)
                        api_test = await _find_or_create_api_test_for_endpoint(
                            session=db,
                            endpoint_id=endpoint_id,
                            endpoint=endpoint,
                            project_identifier=project_identifier,
                            script_format=framework,
                            script_language=script_language,
                        )
                        if api_test:
                            test_run = await _create_test_run(
                                session=db,
                                api_test=api_test,
                                execution_result=execution_result,
                                execution_config=execution_config,
                                report_object_name=report_object_name,
                            )
                            await _create_test_results(
                                session=db,
                                test_run_id=test_run.id,
                                api_test=api_test,
                                execution_result=execution_result,
                            )

                            # 更新端点统计
                            endpoint.total_test_runs = (endpoint.total_test_runs or 0) + 1
                            endpoint.last_run_status = "success" if execution_result.get("success") else "failed"

                            await db.commit()
                            print(f"[API Script Execution] 已创建测试运行记录: {test_run.id}")
            except Exception as e:
                logger.exception("[execute_api_script] 写入测试运行记录失败: %s", e)
                execution_result["stderr"] = (
                    execution_result.get("stderr", "") + f"\n[警告] 写入测试运行记录失败: {e}"
                ).strip()

        # 8. 返回结果
        result = {
            "success": execution_result.get("success", False),
            "exit_code": execution_result.get("exit_code", 4),
            "preflight_status": execution_result.get("preflight_status", "unknown"),
            "script_path": str(script_path),
            "script_filename": script_filename,
            "execution_result": execution_result,
            "diagnostics": diagnostics,
        }

        if report_attachment_id:
            result["report_attachment_id"] = report_attachment_id
            result["message"] = "脚本执行完成，测试报告已保存"

        if endpoint_id:
            result["endpoint_id"] = endpoint_id

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        traceback.print_exc()
        try:
            error_msg = str(e) or e.__class__.__name__
        except Exception:
            error_msg = repr(e)
        return json.dumps({
            "success": False,
            "exit_code": 4,
            "preflight_status": "unknown",
            "error": f"执行脚本时发生错误: {error_msg}",
            "traceback": tb,
            "diagnostics": {"received_execution_config": execution_config},
        }, ensure_ascii=False, indent=2)


async def _resolve_execution_env(
    project_identifier: str,
    endpoint_id: Optional[str],
    execution_config: Optional[Dict[str, Any]]
) -> tuple[Optional[str], Dict[str, str], Optional[str]]:
    """
    解析执行环境变量

    优先级：
    1. execution_config.base_url / execution_config.env
    2. 项目默认环境配置
    3. OpenAPI servers

    Args:
        project_identifier: 项目标识符
        endpoint_id: 端点 ID
        execution_config: 执行配置

    Returns:
        (base_url, env_vars, resolution_error)
    """
    execution_config = execution_config or {}
    if isinstance(execution_config, str):
        try:
            execution_config = json.loads(execution_config)
        except json.JSONDecodeError:
            execution_config = {}
    env_vars: Dict[str, str] = {}
    resolution_error: Optional[str] = None

    # 统一从项目环境配置读取（支持 env_id 指定环境）。
    # 注意：之前这里在 execution_config 提供 base_url 时会提前返回，导致
    # EnvironmentService 中的 bearer token / headers 不会被注入，造成认证丢失。
    async with async_session_factory() as db:
        service = EnvironmentService(db)
        try:
            env_id = execution_config.get("env_id")
            logger.info(
                "[execute_api_script] 解析执行环境: project=%s env_id=%s endpoint=%s",
                project_identifier,
                env_id,
                endpoint_id,
            )
            env_vars = await service.get_execution_env_vars(
                project_identifier=project_identifier,
                execution_config=execution_config,
                endpoint_id=UUID(endpoint_id) if endpoint_id else None,
                env_id=env_id if env_id else None,
            )
            logger.info(
                "[execute_api_script] 环境变量已解析: keys=%s",
                list(env_vars.keys()),
            )
        except BadRequestException as e:
            resolution_error = f"环境配置错误: {e.message}"
            logger.warning("[execute_api_script] %s", resolution_error)
            # 未配置项目环境时，降级为只使用 execution_config 中的 base_url/env
            if execution_config.get("base_url"):
                env_vars["API_BASE_URL"] = str(execution_config["base_url"])
            extra_env = execution_config.get("env") or execution_config.get("environment_variables") or {}
            for key, value in extra_env.items():
                env_vars[key] = str(value)
        except Exception as e:
            resolution_error = f"解析执行环境失败: {e}"
            logger.exception("[execute_api_script] %s", resolution_error)
            # 数据库连接失败等其他异常，记录日志并降级处理
            if execution_config.get("base_url"):
                env_vars["API_BASE_URL"] = str(execution_config["base_url"])
            extra_env = execution_config.get("env") or execution_config.get("environment_variables") or {}
            for key, value in extra_env.items():
                env_vars[key] = str(value)

    base_url = env_vars.pop("API_BASE_URL", None)
    return base_url, env_vars, resolution_error


async def _execute_script_internal(
    script_path: str,
    script_filename: str,
    framework: str,
    reporter: str,
    project_root: str,
    base_url: Optional[str] = None,
    env_vars: Optional[Dict[str, str]] = None,
    script_abs_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    内部执行脚本函数

    Args:
        script_path: 脚本文件相对路径（相对于 project_root）
        script_filename: 脚本文件名
        framework: 测试框架
        reporter: 报告格式
        project_root: 项目根目录
        base_url: 已解析的 API Base URL
        env_vars: 已解析的环境变量字典
        script_abs_path: 脚本文件绝对路径（用于注入 trace helper）

    Returns:
        执行结果字典
    """
    start_time = datetime.now()
    env_vars = env_vars or {}
    cmd: Any = ""

    # 为每次执行生成独立的 HTML 报告目录，避免并发冲突
    report_dir_name = f"playwright-report-{uuid.uuid4().hex[:8]}"
    report_dir = Path(project_root) / report_dir_name

    # 执行前环境探针
    preflight = await _preflight_check(base_url)
    if not preflight["ok"]:
        return {
            "success": False,
            "exit_code": 2,
            "preflight_status": preflight["status"],
            "duration": 0,
            "stdout": "",
            "stderr": "",
            "error": preflight["message"],
            "report_path": None,
            "start_time": start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "result_summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
        }

    try:
        is_windows = sys.platform == "win32"

        # 准备环境变量（设置 CI=1 禁用 Playwright HTML reporter 自动打开浏览器）
        env = _ensure_node_in_path(os.environ.copy())
        if reporter == "html":
            env['CI'] = '1'
            env["PLAYWRIGHT_HTML_OUTPUT_DIR"] = str(report_dir)
            env["PLAYWRIGHT_HTML_OUTPUT_FILE"] = "index.html"

        # 注入 API_BASE_URL 和额外环境变量（强制转换为字符串，避免 Windows CreateProcess 失败）
        if base_url:
            base_url = str(base_url).strip()
            if base_url:
                env["API_BASE_URL"] = base_url
                print(f"[API Script Execution] 注入 API_BASE_URL: {env['API_BASE_URL']}")
        if env_vars:
            for key, value in env_vars.items():
                env[key] = str(value)
            print(f"[API Script Execution] 注入环境变量: {list(env_vars.keys())}")

        # 为 Playwright 注入 trace helper，捕获真实请求/响应明细
        actual_script_path: Optional[Path] = None
        executed_script_path: Optional[Path] = None
        trace_file: Optional[Path] = None
        if framework == "playwright":
            try:
                project_root_path = Path(project_root)
                helper_file = _ensure_trace_helper(project_root_path)
                trace_file = project_root_path / f"api-trace-{uuid.uuid4().hex}.jsonl"
                env["API_TRACE_OUTPUT_FILE"] = str(trace_file)
                env["API_TEST_SUCCESS_CODES"] = _get_business_code_env_value()

                # 确定脚本的绝对路径
                if script_abs_path:
                    actual_script_path = Path(script_abs_path).resolve()
                else:
                    candidate = project_root_path / script_path
                    if await run_sync(candidate.exists):
                        actual_script_path = candidate
                    else:
                        candidate = project_root_path / "tests" / script_path
                        if await run_sync(candidate.exists):
                            actual_script_path = candidate

                # 将 @playwright/test 导入替换为相对路径的 api-trace-helper
                if actual_script_path and await run_sync(actual_script_path.exists):
                    # Windows 下原文件常被占用，先复制到临时文件再修改，避免读写原文件
                    temp_script_path = project_root_path / "tests" / f"tmp-trace-{uuid.uuid4().hex}.spec.ts"
                    await run_sync(shutil.copy2, actual_script_path, temp_script_path)
                    helper_relpath = os.path.relpath(
                        helper_file.parent, temp_script_path.parent
                    ).replace(os.sep, "/")
                    helper_path = f"{helper_relpath}/{helper_file.stem}"
                    original_script = await run_sync(
                        temp_script_path.read_text, encoding="utf-8"
                    )
                    rewritten_script = _rewrite_script_imports(
                        original_script, helper_path=helper_path
                    )
                    if rewritten_script != original_script:
                        await run_sync(temp_script_path.write_text, rewritten_script, encoding="utf-8")
                        executed_script_path = temp_script_path
                        print(f"[API Script Execution] 已注入 trace helper（临时副本）: {temp_script_path}")
                    else:
                        executed_script_path = temp_script_path
                        print(f"[API Script Execution] 无需替换 import，使用临时副本执行: {temp_script_path}")
            except Exception as e:
                print(f"[API Script Execution] 注入 trace helper 失败，继续执行原脚本: {e}")

        # 确定实际执行的脚本路径（可能是临时副本）
        if executed_script_path:
            run_script_path = executed_script_path.relative_to(Path(project_root)).as_posix()
        else:
            run_script_path = script_path

        # 确定测试命令
        if framework == "playwright":
            if reporter == "html":
                # HTML 报告需要指定输出目录；同时使用 list reporter 输出到 stdout，
                # 便于后续解析每个用例的通过/失败状态。
                if is_windows:
                    cmd = f'npx playwright test "{run_script_path}" --reporter=list,html'
                else:
                    cmd = ["npx", "playwright", "test", run_script_path, "--reporter=list,html"]
            else:
                if is_windows:
                    cmd = f'npx playwright test "{run_script_path}" --reporter={reporter}'
                else:
                    cmd = ["npx", "playwright", "test", run_script_path, f"--reporter={reporter}"]
        elif framework == "jest":
            if reporter == "html":
                if is_windows:
                    cmd = f'npm test -- "{run_script_path}" --reporter=html'
                else:
                    cmd = ["npm", "test", "--", run_script_path, "--reporter=html"]
            else:
                if is_windows:
                    cmd = f'npm test -- "{run_script_path}" --reporter={reporter}'
                else:
                    cmd = ["npm", "test", "--", run_script_path, f"--reporter={reporter}"]
        elif framework == "pytest":
            if is_windows:
                cmd = f'pytest "{run_script_path}" --reporter={reporter}'
            else:
                cmd = ["pytest", run_script_path, f"--reporter={reporter}"]
        else:
            return {
                "success": False,
                "exit_code": 4,
                "preflight_status": "ok",
                "error": f"不支持的测试框架: {framework}",
                "duration": 0,
                "stdout": "",
                "stderr": "",
                "report_path": None,
                "start_time": start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "result_summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
            }

        print(f"[API Script Execution] 执行命令: {cmd if is_windows else ' '.join(cmd)}")
        print(f"[API Script Execution] 工作目录: {project_root}")

        # 执行测试（优先 asyncio 子进程；Windows SelectorEventLoop 不支持子进程，降级到线程池同步执行）
        stdout = ""
        stderr = ""
        return_code = -1
        try:
            if is_windows:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    cwd=project_root,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=project_root,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=300,  # 5分钟超时
                )
            except asyncio.TimeoutError:
                if proc.returncode is None:
                    try:
                        proc.kill()
                        await asyncio.wait_for(proc.wait(), timeout=5)
                    except Exception:
                        pass
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                return {
                    "success": False,
                    "exit_code": 3,
                    "preflight_status": "ok",
                    "error": "脚本执行超时（超过5分钟）",
                    "duration": duration,
                    "stdout": "",
                    "stderr": "",
                    "report_path": None,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "result_summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
                    "command": cmd if is_windows else ' '.join(cmd),
                }

            stdout = stdout_bytes.decode('utf-8', errors='replace')
            stderr = stderr_bytes.decode('utf-8', errors='replace')
            return_code = proc.returncode

        except NotImplementedError:
            # Windows SelectorEventLoop 不支持 asyncio 子进程，降级到线程池执行同步 subprocess
            print("[API Script Execution] 当前 EventLoop 不支持 asyncio 子进程，降级到同步 subprocess")
            try:
                result = await run_sync(
                    subprocess.run,
                    cmd,
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=300,
                    shell=is_windows,
                    env=env,
                )
                stdout = result.stdout
                stderr = result.stderr
                return_code = result.returncode
            except subprocess.TimeoutExpired:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                return {
                    "success": False,
                    "exit_code": 3,
                    "preflight_status": "ok",
                    "error": "脚本执行超时（超过5分钟）",
                    "duration": duration,
                    "stdout": "",
                    "stderr": "",
                    "report_path": None,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "result_summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
                    "command": cmd if is_windows else ' '.join(cmd),
                }
            except Exception as e:
                err_detail = str(e).strip() or e.__class__.__name__
                return {
                    "success": False,
                    "exit_code": 4,
                    "preflight_status": "ok",
                    "error": f"同步子进程执行失败: {err_detail}",
                    "duration": 0,
                    "stdout": "",
                    "stderr": f"同步子进程执行失败: {err_detail}",
                    "report_path": None,
                    "start_time": start_time.isoformat(),
                    "end_time": datetime.now().isoformat(),
                    "result_summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
                    "command": cmd if is_windows else ' '.join(cmd),
                }

        except Exception as e:
            err_detail = str(e).strip() or e.__class__.__name__
            return {
                "success": False,
                "exit_code": 4,
                "preflight_status": "ok",
                "error": f"启动测试子进程失败: {err_detail}",
                "duration": 0,
                "stdout": "",
                "stderr": f"启动测试子进程失败: {err_detail}",
                "report_path": None,
                "start_time": start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "result_summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
                "command": cmd if is_windows else ' '.join(cmd),
            }

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print(f"[API Script Execution] 执行完成，返回码: {return_code}")
        print(f"[API Script Execution] 执行时间: {duration:.2f}s")

        # 检查是否生成了 HTML 报告
        report_path = None
        if reporter == "html":
            index_html = report_dir / "index.html"
            if await run_sync(index_html.exists):
                report_path = str(report_dir)
                print(f"[API Script Execution] HTML 报告已生成: {report_path}")

        # 解析测试结果摘要
        result_summary = _parse_test_summary(stdout)

        # 解析真实请求/响应 trace，并清理临时 trace 文件和临时脚本文件
        trace_entries: List[Dict[str, Any]] = []
        if trace_file and await run_sync(trace_file.exists):
            try:
                trace_entries = _parse_api_trace(trace_file)
                print(f"[API Script Execution] 已解析 trace 条目: {len(trace_entries)}")
            except Exception as e:
                print(f"[API Script Execution] 解析 trace 文件失败: {e}")
            finally:
                try:
                    await run_sync(trace_file.unlink)
                except Exception:
                    pass
        if executed_script_path and executed_script_path != actual_script_path:
            try:
                if await run_sync(executed_script_path.exists):
                    await run_sync(executed_script_path.unlink)
                    print(f"[API Script Execution] 已清理临时脚本: {executed_script_path}")
            except Exception:
                pass

        return {
            "success": return_code == 0,
            "exit_code": 0 if return_code == 0 else 1,
            "preflight_status": "ok",
            "return_code": return_code,
            "duration": duration,
            "stdout": stdout,
            "stderr": stderr,
            "report_path": report_path,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "result_summary": result_summary,
            "trace_entries": trace_entries,
            "command": cmd if is_windows else ' '.join(cmd),
        }

    except Exception as e:
        err_detail = str(e).strip() or e.__class__.__name__
        return {
            "success": False,
            "exit_code": 4,
            "preflight_status": "ok",
            "error": f"执行脚本时发生错误: {err_detail}",
            "duration": 0,
            "stdout": "",
            "stderr": f"执行脚本时发生错误: {err_detail}",
            "report_path": None,
            "start_time": start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "result_summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
            "command": cmd if is_windows else ' '.join(cmd),
        }


async def _preflight_check(base_url: Optional[str]) -> Dict[str, Any]:
    """
    执行前环境探针：DNS 解析、TCP 连通、HTTP 可达性

    Args:
        base_url: API Base URL

    Returns:
        {"ok": bool, "status": str, "message": str}
    """
    if not base_url:
        return {
            "ok": False,
            "status": "MISSING_BASE_URL",
            "message": "未配置 API_BASE_URL。请在 execution_config 中传入 base_url，或前往项目设置 > 环境管理配置默认环境。"
        }

    try:
        parsed = urlparse(base_url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return {
                "ok": False,
                "status": "INVALID_BASE_URL",
                "message": f"无法解析 base_url 的主机名: {base_url}"
            }

        # 1. DNS 解析
        try:
            await run_sync(socket.getaddrinfo, host, port)
        except socket.gaierror as e:
            return {
                "ok": False,
                "status": "DNS_FAILED",
                "message": f"域名解析失败 [{host}]: {str(e)}"
            }

        # 2. TCP 连通性
        try:
            await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5
            )
        except asyncio.TimeoutError:
            return {
                "ok": False,
                "status": "TCP_TIMEOUT",
                "message": f"TCP 连接超时 [{host}:{port}]"
            }
        except OSError as e:
            return {
                "ok": False,
                "status": "TCP_FAILED",
                "message": f"TCP 连接失败 [{host}:{port}]: {str(e)}"
            }

        # 3. HTTP 预检（P0 暂不实现，避免引入新依赖；P1 通过统一 runner 补齐）
        # TODO: P1 中使用 aiohttp/httpx 发送 GET /health 或 OPTIONS 预检请求

        return {"ok": True, "status": "ok", "message": ""}

    except Exception as e:
        return {
            "ok": False,
            "status": "PREFLIGHT_ERROR",
            "message": f"环境探针异常: {str(e)}"
        }


def _parse_test_summary(stdout: str) -> Dict[str, int]:
    """
    从 Playwright list reporter 输出解析测试统计

    Args:
        stdout: 测试标准输出

    Returns:
        {"total": int, "passed": int, "failed": int, "skipped": int}
    """
    result = {"total": 0, "passed": 0, "failed": 0, "skipped": 0}

    passed_match = re.search(r"(\d+)\s+passed", stdout)
    if passed_match:
        result["passed"] = int(passed_match.group(1))

    failed_match = re.search(r"(\d+)\s+failed", stdout)
    if failed_match:
        result["failed"] = int(failed_match.group(1))

    skipped_match = re.search(r"(\d+)\s+skipped", stdout)
    if skipped_match:
        result["skipped"] = int(skipped_match.group(1))

    total_match = re.search(r"Total:\s+(\d+)\s+test", stdout)
    if total_match:
        result["total"] = int(total_match.group(1))
    else:
        result["total"] = result["passed"] + result["failed"] + result["skipped"]

    return result


async def _save_test_report(
    endpoint_id: str,
    project_identifier: str,
    endpoint: APIEndpoint,
    report_path: str,
    execution_result: Dict[str, Any],
    project_root: str,
    conversation_id: Optional[str] = None,
) -> Optional[Tuple[str, str]]:
    """
    保存测试报告到 MinIO 并创建/更新附件记录

    在同一 AI 对话（conversation_id）内，同一端点的报告使用固定对象名，
    多次执行只保留一条附件记录；没有会话上下文时保留历史版本行为。

    Args:
        endpoint_id: 端点 ID
        project_identifier: 项目标识符
        endpoint: 端点对象
        report_path: 报告目录路径
        execution_result: 执行结果
        project_root: 项目根目录
        conversation_id: AI 会话 ID（可选，未提供时尝试从 LangGraph 配置/contextvar 读取）

    Returns:
        (附件 ID, MinIO 对象名)，如果保存失败则返回 None
    """
    try:
        # 优先使用显式传入的 conversation_id，否则从 LangGraph 配置/contextvar 读取
        conversation_id = conversation_id or _get_conversation_id()

        # 1. 将报告目录打包成 ZIP（本地临时文件名仍使用时间戳，避免并发冲突）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"api_test_report_{timestamp}.zip"
        zip_path = Path(project_root) / zip_filename

        print(f"[API Report] 打包测试报告: {report_path} -> {zip_path}")

        def _create_zip(zip_path: Path, report_path: str) -> None:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                report_dir = Path(report_path)
                for file_path in report_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(report_dir)
                        zipf.write(file_path, arcname)

        await run_sync(_create_zip, zip_path, report_path)

        # 2. 读取 ZIP 文件内容
        zip_bytes = await run_sync(
            lambda p: open(p, 'rb').read(),
            zip_path
        )

        # 3. 上传到 MinIO
        if conversation_id:
            # 同一会话内使用固定对象名，多次执行只保留一份报告
            object_name = (
                f"api-tests/{project_identifier}/endpoints/{endpoint_id}"
                f"/conversations/{conversation_id}/test-report.zip"
            )
        else:
            # 没有会话上下文时，按时间戳生成独立报告（保留历史版本）
            object_name = f"api-tests/{project_identifier}/endpoints/{endpoint_id}/test-report-{timestamp}.zip"

        await run_sync(
            MinIOClient.upload_bytes,
            object_name=object_name,
            data=zip_bytes,
            content_type="application/zip"
        )
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TkUxcll3PT06ZGQyYmExYzM=

        print(f"[API Report] 报告已上传到 MinIO: {object_name}")

        # 4. 创建或更新附件记录
        async with async_session_factory() as session:
            # 生成报告描述
            duration = execution_result.get("duration", 0)
            stdout = execution_result.get("stdout", "")

            # 尝试解析测试结果
            result_summary = execution_result.get("result_summary", {})
            passed_count = result_summary.get("passed", 0)
            failed_count = result_summary.get("failed", 0)
            skipped_count = result_summary.get("skipped", 0)

            description = f"API 测试报告 - {endpoint.display_name}\n"
            description += f"执行时间: {duration:.2f}秒\n"
            description += f"通过: {passed_count} | 失败: {failed_count} | 跳过: {skipped_count}"

            file_name = f"api-test-report-{timestamp}.zip"

            if conversation_id:
                # 同一 conversation_id 内 upsert，保证只保留一条报告附件
                upsert_stmt = pg_insert(Attachment).values(
                    entity_type=AttachmentEntityType.API_TEST_REPORT,
                    entity_id=UUID(endpoint_id),
                    project_id=endpoint.project_id,
                    file_name=file_name,
                    file_size=len(zip_bytes),
                    content_type="application/zip",
                    object_name=object_name,
                    description=description,
                    created_by="api-agent",
                    updated_at=func.now(),
                ).on_conflict_do_update(
                    index_elements=["object_name"],
                    set_=dict(
                        file_size=len(zip_bytes),
                        content_type="application/zip",
                        file_name=file_name,
                        description=description,
                        updated_at=func.now(),
                    ),
                )
                await session.execute(upsert_stmt)
                await session.commit()

                # 查询并返回附件 ID
                result = await session.execute(
                    select(Attachment).where(Attachment.object_name == object_name)
                )
                attachment = result.scalar_one()
                await session.refresh(attachment)
                print(f"[API Report] 附件记录已创建/更新: {attachment.id}")
            else:
                # 无会话上下文时，创建新附件记录
                attachment = Attachment(
                    entity_type=AttachmentEntityType.API_TEST_REPORT,
                    entity_id=UUID(endpoint_id),
                    project_id=endpoint.project_id,
                    file_name=file_name,
                    file_size=len(zip_bytes),
                    content_type="application/zip",
                    object_name=object_name,
                    description=description,
                    created_by="api-agent"
                )

                session.add(attachment)
                await session.commit()
                await session.refresh(attachment)
                print(f"[API Report] 附件记录已创建: {attachment.id}")

            # 5. 清理临时 ZIP 文件
            try:
                await run_sync(zip_path.unlink)
                print(f"[API Report] 临时 ZIP 文件已清理: {zip_path}")
            except Exception as e:
                print(f"[API Report] 清理临时 ZIP 文件失败: {e}")

            # 6. 清理报告目录
            try:
                await run_sync(shutil.rmtree, report_path)
                print(f"[API Report] 报告目录已清理: {report_path}")
            except Exception as e:
                print(f"[API Report] 清理报告目录失败: {e}")

            return str(attachment.id), object_name

    except Exception as e:
        print(f"[API Report] 保存测试报告失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def _infer_script_language(path: Path) -> str:
    """
    根据脚本文件扩展名推断脚本语言
    """
    ext = path.suffix.lower().lstrip(".")
    return {"ts": "typescript", "js": "javascript", "py": "python"}.get(ext, "typescript")


async def _find_or_create_api_test_for_endpoint(
    session: AsyncSession,
    endpoint_id: str,
    endpoint: APIEndpoint,
    project_identifier: str,
    script_format: str = "playwright",
    script_language: str = "typescript",
    script_object_name: Optional[str] = None,
) -> Optional[APITest]:
    """
    查找或创建与端点关联的 APITest 记录

    逻辑复用 save_test_script 中的 find-or-create 模式：
    1. 先验证 endpoint.api_test_ids 中现有的 APITest；
    2. 兜底通过 script_path 中的 endpoint_id 匹配；
    3. 仍找不到则新建一个 APITest。
    """
    api_test_repo = APITestRepository(session)
    api_test: Optional[APITest] = None

    # 1. 清理并验证 endpoint.api_test_ids
    valid_test_ids: list[str] = []
    if endpoint.api_test_ids:
        parsed_ids: list[UUID] = []
        for tid in endpoint.api_test_ids:
            try:
                parsed_ids.append(UUID(tid))
            except ValueError:
                continue
        if parsed_ids:
            stmt = select(APITest).where(APITest.id.in_(parsed_ids))
            result = await session.execute(stmt)
            existing_tests = result.scalars().all()
            valid_test_ids = [str(t.id) for t in existing_tests]
            api_test = existing_tests[0] if existing_tests else None

    # 2. 兜底查找：通过 script_path 中的 endpoint_id 匹配
    if api_test is None:
        fallback_stmt = select(APITest).where(
            APITest.project_id == endpoint.project_id,
            APITest.script_path.like(f"%/endpoints/{endpoint_id}/test-script.%"),
        )
        fallback_result = await session.execute(fallback_stmt)
        api_test = fallback_result.scalar_one_or_none()
        if api_test:
            valid_test_ids = [str(api_test.id)]

    # 3. 仍找不到则创建新的 APITest
    if api_test is None:
        extension = {"typescript": "ts", "javascript": "js", "python": "py"}.get(script_language, "ts")
        object_name = script_object_name or f"api-tests/{project_identifier}/endpoints/{endpoint_id}/test-script.{extension}"
        identifier = await api_test_repo.get_next_identifier(endpoint.project_id)
        api_test = APITest(
            project_id=endpoint.project_id,
            folder_id=endpoint.folder_id,
            identifier=identifier,
            name=endpoint.display_name or f"API Test {identifier}",
            script_path=object_name,
            script_format=script_format,
            script_language=script_language,
            schema_type="openapi",
            generated_by_agent="api_agent",
        )
        session.add(api_test)
        valid_test_ids = []

    # 4. 同步 endpoint.api_test_ids
    current_ids = set(valid_test_ids)
    current_ids.add(str(api_test.id))
    endpoint.api_test_ids = list(current_ids)
    endpoint.updated_at = datetime.now(timezone.utc)

    return api_test


async def _create_test_run(
    session: AsyncSession,
    api_test: APITest,
    execution_result: Dict[str, Any],
    execution_config: Optional[Dict[str, Any]],
    report_object_name: Optional[str],
) -> APITestRun:
    """
    根据执行结果创建 APITestRun 记录
    """
    run_repo = APITestRunRepository(session)
    identifier = await run_repo.get_next_identifier(api_test.id)

    # 规范化执行配置
    config = execution_config
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except json.JSONDecodeError:
            config = None

    # 状态映射
    preflight_status = execution_result.get("preflight_status", "ok")
    if preflight_status != "ok":
        status = "failed"
    elif execution_result.get("success"):
        status = "completed"
    else:
        status = "failed"

    # 统计
    result_summary = execution_result.get("result_summary", {})
    total_tests = result_summary.get("total", 0)
    passed_tests = result_summary.get("passed", 0)
    failed_tests = result_summary.get("failed", 0)
    skipped_tests = result_summary.get("skipped", 0)

    # 时长
    duration = execution_result.get("duration")
    duration_ms = int(duration * 1000) if isinstance(duration, (int, float)) else None

    error_message = execution_result.get("error") if status == "failed" else None

    test_run = await run_repo.create(
        project_id=api_test.project_id,
        api_test_id=api_test.id,
        identifier=identifier,
        status=status,
        execution_config=config,
        total_tests=total_tests,
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        skipped_tests=skipped_tests,
        duration_ms=duration_ms,
        report_path=report_object_name,
        error_message=error_message,
    )
    return test_run


async def _create_test_results(
    session: AsyncSession,
    test_run_id: UUID,
    api_test: APITest,
    execution_result: Dict[str, Any],
) -> None:
    """
    从 Playwright list reporter stdout 解析用例结果并写入 APITestResult。

    如果执行过程中通过 trace helper 捕获到真实请求/响应，会一并回填到
    request_summary / response_summary / request_data / response_data /
    assertion_results / duration_ms 字段；否则仅保留从用例标题推断的信息。
    """
    stdout = execution_result.get("stdout", "")
    if not stdout:
        return

    try:
        parsed_items = APITestExecutor._parse_playwright_list_output(stdout)
    except Exception as e:
        logger.warning("[execute_api_script] 解析 Playwright stdout 失败: %s", e)
        return

    if not parsed_items:
        return

    result_repo = APITestResultRepository(session)
    status_map = {
        "passed": TestResultStatus.PASSED,
        "failed": TestResultStatus.FAILED,
        "skipped": TestResultStatus.SKIPPED,
    }

    trace_entries = execution_result.get("trace_entries", [])

    for item in parsed_items:
        status = status_map.get(item["status"], TestResultStatus.FAILED)
        title = item["title"]
        endpoint, method = APITestExecutor._parse_endpoint_from_test_name(title)

        # 匹配当前用例的 trace 条目并构建请求/响应摘要
        matched_traces = APITestExecutor._match_trace_entries(title, trace_entries)
        request_data, response_data, assertion_results, duration_ms = APITestExecutor._build_trace_summary(
            matched_traces, status, stdout=stdout,
        )

        # trace 未命中时回退到简单推断
        if request_data is None:
            request_data = {"method": method, "url": endpoint}
        if response_data is None:
            response_data = {"status": 200 if status == TestResultStatus.PASSED else 500}
        if assertion_results is None:
            assertion_results = [
                {
                    "assertion": {"type": "test"},
                    "passed": status == TestResultStatus.PASSED,
                    "actual": status.value,
                    "expected": TestResultStatus.PASSED.value,
                    "message": f"测试执行{'通过' if status == TestResultStatus.PASSED else '失败'}: {title}",
                }
            ]

        # 根据断言结果修正用例整体状态：如果断言中有失败的，应覆盖为 FAILED
        # 解决 HTTP 200 + 业务错误码假阳性（body.code=3001 等）时用例仍显示"通过"的问题
        if status == TestResultStatus.PASSED and assertion_results:
            if any(a.get("passed") is False for a in assertion_results):
                status = TestResultStatus.FAILED

        # 当断言反假阳性检测到失败时，生成更有意义的 error_message
        if status == TestResultStatus.FAILED:
            failed_assertions = [
                a.get("message", "") for a in assertion_results
                if a.get("passed") is False
            ]
            error_message = "; ".join(failed_assertions) if failed_assertions else "测试失败（断言未通过）"
        else:
            error_message = None

        await result_repo.create(
            test_run_id=test_run_id,
            api_test_id=api_test.id,
            scenario_name=title,
            endpoint=endpoint,
            method=method,
            status=status,
            request_summary=request_data,
            response_summary=response_data,
            request_data=request_data,
            response_data=response_data,
            assertion_results=assertion_results,
            error_message=error_message,
            duration_ms=duration_ms,
            retry_count=0,
        )


@tool
async def execute_api_script_by_artifact_id(
    attachment_id: str,
    endpoint_id: str,
    project_identifier: str,
    execution_config: Optional[Dict[str, Any]] = None,
    framework: str = "playwright",
) -> str:
    """
    通过附件 ID 执行已保存的 API 测试脚本

    此工具会自动：
    1. 从 MinIO 下载附件中的脚本内容
    2. 将脚本写入 workspace 测试目录
    3. 执行测试（默认 Playwright）
    4. 生成 HTML 测试报告并保存到 MinIO
    5. 创建测试报告附件记录

    Args:
        attachment_id: 测试脚本附件 ID
        endpoint_id: 关联的 API 端点 ID（用于保存测试报告附件）
        project_identifier: 项目标识符
        execution_config: 执行配置（可选）
            - env_id: 项目环境 ID，后端自动解析 base_url、auth、headers
            - env: 额外环境变量字典
        framework: 测试框架，默认 playwright

    Returns:
        JSON 格式的执行结果
    """
    try:
        diagnostics: Dict[str, Any] = {
            "attachment_id": attachment_id,
            "endpoint_id": endpoint_id,
            "project_identifier": project_identifier,
            "execution_config": execution_config,
        }

        # 读取当前 AI 会话 ID（优先从 LangGraph 运行配置读取）
        conversation_id = _get_conversation_id()
        diagnostics["conversation_id"] = conversation_id

        # 1. 查询附件
        async with async_session_factory() as db:
            attachment_result = await db.execute(
                select(Attachment).where(Attachment.id == UUID(attachment_id))
            )
            attachment = attachment_result.scalar_one_or_none()

            if not attachment:
                return json.dumps({
                    "success": False,
                    "exit_code": 4,
                    "error": f"附件不存在: {attachment_id}",
                    "diagnostics": diagnostics,
                }, ensure_ascii=False, indent=2)

            if attachment.entity_type != AttachmentEntityType.API_TEST_SCRIPT:
                return json.dumps({
                    "success": False,
                    "exit_code": 4,
                    "error": f"附件类型不是测试脚本: {attachment.entity_type}",
                    "diagnostics": diagnostics,
                }, ensure_ascii=False, indent=2)

            # 2. 查询端点
            endpoint_result = await db.execute(
                select(APIEndpoint).where(APIEndpoint.id == UUID(endpoint_id))
            )
            endpoint = endpoint_result.scalar_one_or_none()

            if not endpoint:
                return json.dumps({
                    "success": False,
                    "exit_code": 4,
                    "error": f"端点不存在: {endpoint_id}",
                    "diagnostics": diagnostics,
                }, ensure_ascii=False, indent=2)

        # 3. 下载脚本内容
        script_content_bytes = await run_sync(MinIOClient.download_file, attachment.object_name)
        script_content = script_content_bytes.decode("utf-8")

        # 4. 写入 workspace 测试目录
        project_root = Path(settings.api_workspace_root).resolve()
        tests_dir = project_root / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)

        script_filename = attachment.file_name or f"script_{attachment_id}.spec.ts"
        # Playwright 配置 testMatch 只识别 *.spec.ts；如果附件名不符合，强制修正扩展名
        if framework == "playwright" and not script_filename.endswith(".spec.ts"):
            if script_filename.endswith(".ts") or script_filename.endswith(".js"):
                script_filename = script_filename[:-3]
            script_filename = f"{script_filename}.spec.ts"

        # 使用唯一本地文件名，避免并发执行冲突
        local_filename = f"{attachment_id}_{script_filename}"
        local_script_path = tests_dir / local_filename
        await run_sync(local_script_path.write_text, script_content, encoding="utf-8")
        diagnostics["local_script_path"] = str(local_script_path)

        try:
            # 5. 解析执行环境
            resolved_base_url, resolved_env, env_resolution_error = await _resolve_execution_env(
                project_identifier=project_identifier,
                endpoint_id=endpoint_id,
                execution_config=execution_config
            )

            diagnostics["resolved_base_url"] = resolved_base_url
            diagnostics["resolved_env_keys"] = list(resolved_env.keys())
            diagnostics["env_resolution_error"] = env_resolution_error

            # 6. 执行脚本（强制使用 html reporter 以生成报告）
            execution_result = await _execute_script_internal(
                script_path=local_filename,
                script_filename=local_filename,
                framework=framework,
                reporter="html",
                project_root=str(project_root),
                base_url=resolved_base_url,
                env_vars=resolved_env,
                script_abs_path=str(local_script_path),
            )

            # 把内部错误暴露到 stderr
            if execution_result.get("error") and not execution_result.get("stderr"):
                execution_result["stderr"] = execution_result["error"]

            diagnostics["command"] = execution_result.get("command")

            # 7. 保存测试报告
            report_attachment_id = None
            report_object_name = None
            if execution_result.get("report_path"):
                try:
                    save_result = await _save_test_report(
                        endpoint_id=endpoint_id,
                        project_identifier=project_identifier,
                        endpoint=endpoint,
                        report_path=execution_result["report_path"],
                        execution_result=execution_result,
                        project_root=str(project_root),
                        conversation_id=conversation_id,
                    )
                    if save_result:
                        report_attachment_id, report_object_name = save_result
                except Exception as e:
                    logger.exception("[execute_api_script_by_artifact_id] 保存测试报告失败: %s", e)
                    execution_result["stderr"] = (
                        execution_result.get("stderr", "") + f"\n[警告] 保存测试报告失败: {e}"
                    ).strip()

            # 8. 写入 api_test_runs / api_test_results（执行历史核心修复）
            try:
                async with async_session_factory() as db:
                    endpoint_result = await db.execute(
                        select(APIEndpoint).where(APIEndpoint.id == UUID(endpoint_id))
                    )
                    endpoint_for_run = endpoint_result.scalar_one_or_none()

                    if endpoint_for_run:
                        script_language = _infer_script_language(Path(attachment.file_name))
                        api_test = await _find_or_create_api_test_for_endpoint(
                            session=db,
                            endpoint_id=endpoint_id,
                            endpoint=endpoint_for_run,
                            project_identifier=project_identifier,
                            script_format=framework,
                            script_language=script_language,
                            script_object_name=attachment.object_name,
                        )
                        if api_test:
                            test_run = await _create_test_run(
                                session=db,
                                api_test=api_test,
                                execution_result=execution_result,
                                execution_config=execution_config,
                                report_object_name=report_object_name,
                            )
                            await _create_test_results(
                                session=db,
                                test_run_id=test_run.id,
                                api_test=api_test,
                                execution_result=execution_result,
                            )

                            # 更新端点统计
                            endpoint_for_run.total_test_runs = (endpoint_for_run.total_test_runs or 0) + 1
                            endpoint_for_run.last_run_status = "success" if execution_result.get("success") else "failed"

                            await db.commit()
                            print(f"[execute_api_script_by_artifact_id] 已创建测试运行记录: {test_run.id}")
            except Exception as e:
                logger.exception("[execute_api_script_by_artifact_id] 写入测试运行记录失败: %s", e)
                execution_result["stderr"] = (
                    execution_result.get("stderr", "") + f"\n[警告] 写入测试运行记录失败: {e}"
                ).strip()

            # 9. 返回结果
            result = {
                "success": execution_result.get("success", False),
                "exit_code": execution_result.get("exit_code", 4),
                "preflight_status": execution_result.get("preflight_status", "unknown"),
                "script_path": str(local_script_path),
                "script_filename": script_filename,
                "execution_result": execution_result,
                "diagnostics": diagnostics,
            }

            if report_attachment_id:
                result["report_attachment_id"] = report_attachment_id
                result["message"] = "脚本执行完成，测试报告已保存"

            return json.dumps(result, ensure_ascii=False, indent=2)

        finally:
            # 清理临时脚本文件
            try:
                if await run_sync(local_script_path.exists):
                    await run_sync(local_script_path.unlink)
            except Exception as e:
                logger.warning("[execute_api_script_by_artifact_id] 清理临时脚本失败: %s", e)

    except Exception as e:
        logger.exception("[execute_api_script_by_artifact_id] 执行失败")
        return json.dumps({
            "success": False,
            "exit_code": 4,
            "error": f"执行脚本时发生错误: {str(e)}",
        }, ensure_ascii=False, indent=2)


@tool
async def get_test_execution_status(
    execution_id: str
) -> str:
    """
    获取测试执行状态（占位符，未来可扩展为异步执行查询）

    Args:
        execution_id: 执行 ID

    Returns:
        JSON 格式的执行状态
    """
    return json.dumps({
        "success": True,
        "execution_id": execution_id,
        "status": "completed",
        "message": "当前版本仅支持同步执行，不支持异步状态查询"
    }, ensure_ascii=False, indent=2)
