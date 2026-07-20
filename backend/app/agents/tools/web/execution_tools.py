"""
Web 测试脚本执行工具

提供在 测试目录中执行 Playwright 脚本的功能
"""

import asyncio
import os
import sys
import json
import subprocess
import zipfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID, uuid4

from langchain_core.tools import tool
from sqlalchemy import select
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TVhwMk9RPT06MTE1M2I2M2M=

from app.utils.sync_executor import run_sync
from app.utils.shell_env import resolve_effective_headless
from app.config import settings
from app.config.database import async_session_factory
from app.models.attachment import Attachment, AttachmentEntityType
from app.models.web_function import WebFunction, WebSubFunction
from app.models.web_test import WebTest, WebTestRun, WebTestResult
from app.utils.playwright_report import map_playwright_status, parse_playwright_json
from app.config.minio_client import MinIOClient


# ============================================================================
# 测试目录配置
# ============================================================================

# 测试服务器根目录
WORKSPACE_TESTS_ROOT = Path(settings.web_mcp_workspace_root) / "tests"

# ============================================================================
# 并发控制
# ============================================================================
# 多个执行共享同一 project_root（node_modules / tests 目录）。报告与输出目录虽已按
# execution_id 隔离，但并发跑 playwright 仍会争抢浏览器与 node 资源，因此用信号量限制
# 全局并发上限；在信号量允许范围内，不同子功能可安全并行（目录已隔离）。
_execution_semaphore = asyncio.Semaphore(settings.web_exec_max_concurrency)

# 同一子功能（或同一脚本）的执行串行，防止同一脚本被并发触发导致报告相互覆盖。
_sub_function_locks: Dict[str, asyncio.Lock] = {}
_sub_function_locks_guard = asyncio.Lock()


async def _acquire_exec_lock(key: str) -> asyncio.Lock:
    """获取某个执行键（子功能 ID 或脚本文件名）对应的串行锁。"""
    async with _sub_function_locks_guard:
        lock = _sub_function_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _sub_function_locks[key] = lock
        return lock


def get_workspace_tests_dir() -> Path:
    """
    获取 WORKSPACE 测试目录路径

    Returns:
        WORKSPACE 测试目录的绝对路径
    """
    return WORKSPACE_TESTS_ROOT


def get_project_root() -> Path:
    """
    获取项目根目录（用于在 测试目录中找到 package.json）

    Returns:
        项目根目录的绝对路径
    """
    # 需要往上找到项目根目录
    return Path(settings.web_mcp_workspace_root)


@tool
async def execute_web_script(
    local_script_path: str,
    framework: str = "playwright",
    reporter: str = "html",
    project_identifier: str = "PR-1",
    sub_function_id: Optional[str] = None,
    headless: Optional[bool] = None,
) -> str:
    """
    执行已下载到 MCP 测试目录的 Web 测试脚本

    此工具会：
    1. 验证脚本文件存在于 workspace 测试目录
    2. 静态校验脚本可被收集（--list，不起浏览器）
    3. 执行 Playwright 测试（输出按 execution_id 隔离，互不覆盖）
    4. 解析 JSON 结构化结果（用例级 pass/fail/时长）
    5. 将测试报告打包保存到 MinIO 并创建附件记录
    6. 更新子功能的测试运行次数与最近状态

    Args:
        local_script_path: 本地脚本文件的完整路径（相对或绝对路径）
        framework: 测试框架 (playwright, jest, pytest)
        reporter: 报告格式 (html, json, list)
        project_identifier: 项目标识符，用于保存测试报告
        sub_function_id: 子功能 ID（可选，用于更新测试统计）
        headless: 是否以无头模式运行浏览器（可选，默认读取 settings.web_mcp_headless）

    Returns:
        JSON 格式的执行结果，包含：
        - success: 是否成功
        - script_path: 执行的脚本路径
        - execution_result: 执行结果（stdout, stderr, duration, return_code, stats, cases）
        - report_attachment_id: 测试报告附件 ID（如果生成了报告）
        - error: 错误信息（如果有）
    """
    try:
        # 1. 解析脚本路径（健壮：支持绝对路径 / 相对路径 / 纯文件名）
        #    历史上这里直接 script_path.relative_to(project_root)，当传入相对路径或
        #    纯文件名时会抛 ValueError 并被外层兜底成笼统错误，导致 agent 无法定位脚本、
        #    被迫改用 test_run，测试报告也就无法自动保存到 MinIO。
        project_root = Path(settings.web_mcp_workspace_root).resolve()
        script_path = Path(local_script_path)

        if not script_path.is_absolute():
            # 相对路径或纯文件名：优先从 workspace tests 目录解析，其次从 project_root 解析
            candidate_in_tests = (get_workspace_tests_dir() / script_path).resolve()
            if await run_sync(candidate_in_tests.exists):
                script_path = candidate_in_tests
            else:
                script_path = (project_root / script_path).resolve()
        else:
            script_path = script_path.resolve()

        # 2. 验证脚本文件存在
        if not await run_sync(script_path.exists):
            return json.dumps({
                "success": False,
                "error": (
                    f"脚本文件不存在: {script_path}。"
                    f"支持绝对路径，或相对于 {get_workspace_tests_dir()} 的文件名/相对路径。"
                )
            }, ensure_ascii=False, indent=2)

        script_filename = script_path.name

        # 3. 同一子功能（或脚本）串行 + 全局并发上限
        exec_lock_key = sub_function_id or script_filename
        exec_lock = await _acquire_exec_lock(exec_lock_key)
        async with exec_lock:
            async with _execution_semaphore:
                return await _execute_and_report(
                    script_path=script_path,
                    script_filename=script_filename,
                    project_root=project_root,
                    framework=framework,
                    reporter=reporter,
                    project_identifier=project_identifier,
                    sub_function_id=sub_function_id,
                    headless=headless,
                )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return json.dumps({
            "success": False,
            "error": f"执行脚本时发生错误: {str(e)}"
        }, ensure_ascii=False, indent=2)


async def _execute_and_report(
    script_path: Path,
    script_filename: str,
    project_root: Path,
    framework: str,
    reporter: str,
    project_identifier: str,
    sub_function_id: Optional[str],
    headless: Optional[bool],
) -> str:
    """在并发锁内执行脚本、解析结构化结果并保存报告。返回给 agent 的 JSON。"""
    print(f"[Web Script Execution] 准备执行脚本: {script_path}")

    # 3. 确定相对路径（相对于项目根目录，playwright 以 project_root 为工作目录）
    try:
        relative_path = script_path.relative_to(project_root)
    except ValueError:
        relative_path = Path(script_filename)

    print(f"[Web Script Execution] 项目根目录: {project_root}")
    print(f"[Web Script Execution] 相对脚本路径: {relative_path}")

    # 4. 静态校验：先用 --list 确认脚本可被收集（不起浏览器），挡掉语法/import 类错误。
    #    注意：与实际执行保持一致，只传文件名（script_filename），让 Playwright 在
    #    playwright.config.js 的 testDir 下自动匹配，避免 tests/xxx 这种相对路径在
    #    --list 阶段因 testDir 前缀重复而找不到文件。
    static_check = await _static_check_script(
        script_path=script_filename,
        project_root=str(project_root),
    )
    if not static_check.get("success"):
        return json.dumps({
            "success": False,
            "stage": "static_check",
            "error": static_check.get("error"),
            "detail": (static_check.get("output") or "")[-4000:],
            "hint": "脚本存在语法/import/收集期错误。此错误不起浏览器即可复现，请修复后重试。",
        }, ensure_ascii=False, indent=2)

    # 5. 生成本次执行的隔离目录（报告 / JSON 结果 / test-results 均按 execution_id 隔离，
    #    避免多次执行或与历史残留互相覆盖）。
    execution_id = f"{sub_function_id or 'adhoc'}-{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    exec_root = project_root / ".exec_runs" / execution_id
    html_report_dir = exec_root / "html"
    json_report_file = exec_root / "results.json"
    test_output_dir = exec_root / "test-results"
    await run_sync(lambda: test_output_dir.mkdir(parents=True, exist_ok=True))

    # 6. 执行脚本
    resolved_headless = settings.web_mcp_headless if headless is None else headless
    execution_result = await _execute_script_internal(
        script_path=str(relative_path),
        script_filename=script_filename,
        framework=framework,
        reporter=reporter,
        project_root=str(project_root),
        html_report_dir=str(html_report_dir),
        json_report_file=str(json_report_file),
        test_output_dir=str(test_output_dir),
        headless=resolved_headless,
    )

    # 7. 解析 JSON 结构化结果（用例级 pass/fail/时长），失败时回退到 return_code 判定
    structured = await _parse_json_report(json_report_file)
    if structured:
        execution_result["stats"] = structured["stats"]
        execution_result["cases"] = structured["cases"]
        # 以结构化结果为准修正 success（比 return_code 更精确）
        execution_result["success"] = structured["stats"]["failed"] == 0 and structured["stats"]["total"] > 0

    # 8. 报告 + 结构化落库 + 统计（均需先拿到 sub_function）
    report_attachment_id = None
    test_run_id = None
    if sub_function_id:
        async with async_session_factory() as db:
            sub_function_result = await db.execute(
                select(WebSubFunction).where(WebSubFunction.id == UUID(sub_function_id))
            )
            sub_function = sub_function_result.scalar_one_or_none()

        if sub_function:
            # 8a. 打包报告上传 MinIO 并建附件（仅 html 报告时），同时取回 object_name
            report_object_name = None
            if reporter == "html" and execution_result.get("report_path"):
                report_info = await _save_test_report(
                    sub_function_id=sub_function_id,
                    project_identifier=project_identifier,
                    sub_function=sub_function,
                    exec_root=str(exec_root),
                    execution_id=execution_id,
                    execution_result=execution_result,
                    project_root=str(project_root)
                )
                if report_info:
                    report_attachment_id = report_info["attachment_id"]
                    report_object_name = report_info["object_name"]

            # 8b. 结构化结果落库 WebTestRun/WebTestResult（用例级趋势分析；无 stats 则跳过）
            test_run_id = await _persist_structured_run(
                sub_function=sub_function,
                project_identifier=project_identifier,
                execution_id=execution_id,
                execution_result=execution_result,
                report_object_name=report_object_name,
                headless=resolved_headless,
                framework=framework,
                reporter=reporter,
            )

            # 8c. 更新子功能的测试运行次数与最近状态
            try:
                async with async_session_factory() as db:
                    sub_function_result = await db.execute(
                        select(WebSubFunction).where(WebSubFunction.id == UUID(sub_function_id))
                    )
                    sub_function = sub_function_result.scalar_one_or_none()

                    if sub_function:
                        sub_function.total_test_runs = (sub_function.total_test_runs or 0) + 1
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TVhwMk9RPT06MTE1M2I2M2M=
                        sub_function.last_run_status = "passed" if execution_result.get("success") else "failed"

                        await db.commit()
                        print(f"[Web Script Execution] 已更新子功能 {sub_function_id} 的测试运行次数")
            except Exception as e:
                print(f"[Web Script Execution] 更新子功能测试运行次数失败: {e}")

    # 10. 返回结果
    result = {
        "success": True,
        "script_path": str(script_path),
        "script_filename": script_filename,
        "execution_id": execution_id,
        "execution_result": execution_result
    }

    if report_attachment_id:
        result["report_attachment_id"] = report_attachment_id
        result["message"] = "脚本执行完成，测试报告已保存"

    if test_run_id:
        result["test_run_id"] = test_run_id

    if sub_function_id:
        result["sub_function_id"] = sub_function_id

    return json.dumps(result, ensure_ascii=False, indent=2)


async def _static_check_script(script_path: str, project_root: str) -> Dict[str, Any]:
    """
    静态校验：用 `playwright test --list` 确认脚本可被收集（语法 / import / 收集期错误），
    不启动浏览器。通过后才进入真实执行，避免为毫秒级就能发现的错误付出一次最长执行超时的浏览器运行。

    选择 --list 而非 tsc --noEmit 的原因：workspace 没有 tsconfig.json，tsc 开箱即用会误报；
    --list 依赖已有的 playwright.config.js（testDir=./tests），能捕获语法/缺 import/收集错误且不起浏览器。

    Args:
        script_path: 脚本文件名或相对 project_root 的路径。推荐只传文件名，
                     让 Playwright 按 playwright.config.js 的 testDir 自动查找。
        project_root: 项目根目录（含 package.json / playwright.config.js）

    Returns:
        {"success": bool, "error": str|None, "output": str}
    """
    try:
        is_windows = sys.platform == "win32"
        if is_windows:
            cmd = f'npx playwright test "{script_path}" --list'
        else:
            npx = shutil.which("npx") or "npx"
            cmd = [npx, "playwright", "test", script_path, "--list"]

        env = os.environ.copy()
        env['CI'] = '1'

        result = await run_sync(
            subprocess.run,
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=settings.web_exec_static_check_timeout,
            shell=is_windows,
            env=env,
        )

        if result.returncode == 0:
            return {"success": True, "error": None, "output": result.stdout}

        return {
            "success": False,
            "error": "脚本静态校验失败（语法/import/收集期错误），未启动浏览器执行",
            "output": (result.stdout or "") + "\n" + (result.stderr or ""),
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"静态校验超时（--list 超过 {settings.web_exec_static_check_timeout}s）", "output": ""}
    except Exception as e:
        # 校验工具本身异常（如 npx 不可用）时 fail-open 放行，由真实执行自行报错，
        # 避免因环境问题误判而阻断主流程。
        print(f"[Web Script Execution] 静态校验异常，跳过校验继续执行: {e}")
        return {"success": True, "error": None, "output": ""}


async def _execute_script_internal(
    script_path: str,
    script_filename: str,
    framework: str,
    reporter: str,
    project_root: str,
    html_report_dir: str,
    json_report_file: str,
    test_output_dir: str,
    headless: bool = True,
) -> Dict[str, Any]:
    """
    内部执行脚本函数

    所有输出（HTML 报告 / JSON 结果 / trace / video / screenshot）均写入按 execution_id
    隔离的目录，避免多次执行互相覆盖。通过 `--reporter=html,json` 同时产出人类可读的
    HTML 报告与机器可读的 JSON 结果，并用 `--output` 隔离 test-results。

    Args:
        script_path: 脚本文件相对路径（相对于 project_root）
        script_filename: 脚本文件名
        framework: 测试框架
        reporter: 报告格式
        project_root: 项目根目录
        html_report_dir: 隔离的 HTML 报告输出目录
        json_report_file: 隔离的 JSON 结果文件路径
        test_output_dir: 隔离的 test-results 输出目录
        headless: 是否无头运行

    Returns:
        执行结果字典
    """
    try:
        start_time = datetime.now()

        is_windows = sys.platform == "win32"
        effective_headless = resolve_effective_headless(headless)
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TVhwMk9RPT06MTE1M2I2M2M=

        if framework != "playwright":
            return {
                "success": False,
                "error": f"不支持的测试框架: {framework}，Web 测试仅支持 playwright"
            }

        # 统一超时/重试预算：单用例超时与自动重试次数由 settings 集中控制，通过命令行
        # 覆盖 config，避免与 healer 的修复重跑叠加放大。
        test_timeout = settings.web_exec_test_timeout_ms
        retries = settings.web_exec_retries
        # reporter 同时产出 html（人读）+ json（机读）；即便调用方只要 json 也保留 html 便于排查。
        reporter_spec = "html,json" if reporter == "html" else f"{reporter},json"
        headed_flag = "--headed" if not effective_headless else ""

        if is_windows:
            cmd = (
                f'npx playwright test "{script_filename}" --reporter={reporter_spec} '
                f'--output="{test_output_dir}" --timeout={test_timeout} --retries={retries} {headed_flag}'
            )
        else:
            cmd = [
                "npx", "playwright", "test", script_filename,
                f"--reporter={reporter_spec}",
                f"--output={test_output_dir}",
                f"--timeout={test_timeout}",
                f"--retries={retries}",
            ]
            if headed_flag:
                cmd.append("--headed")

        print(f"[Web Script Execution] 执行命令: {cmd if is_windows else ' '.join(cmd)}")
        print(f"[Web Script Execution] 工作目录: {project_root}")

        # 环境变量：
        # - CI=1 禁用 Playwright HTML reporter 自动打开浏览器
        # - PLAYWRIGHT_HTML_REPORT 指向隔离的 HTML 目录
        # - PLAYWRIGHT_JSON_OUTPUT_FILE 指向隔离的 JSON 结果文件
        env = os.environ.copy()
        env['CI'] = '1'
        env['PLAYWRIGHT_HTML_REPORT'] = html_report_dir
        env['PLAYWRIGHT_JSON_OUTPUT_FILE'] = json_report_file

        result = await run_sync(
            subprocess.run,
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=settings.web_exec_timeout_seconds,
            shell=is_windows,
            env=env
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        stdout = result.stdout
        stderr = result.stderr
        return_code = result.returncode

        print(f"[Web Script Execution] 执行完成，返回码: {return_code}")
        print(f"[Web Script Execution] 执行时间: {duration:.2f}s")

        # HTML 报告是否生成（隔离目录下的 index.html）
        report_path = None
        if reporter == "html":
            index_html = Path(html_report_dir) / "index.html"
            if await run_sync(index_html.exists):
                report_path = html_report_dir
                print(f"[Web Script Execution] HTML 报告已生成: {report_path}")

        # 收集 test-results 产出的截图与视频路径，便于下游 save_web_test_report
        # 直接内联到执行摘要中展示。
        screenshots: list[str] = []
        videos: list[str] = []
        test_output_path = Path(test_output_dir)
        if await run_sync(test_output_path.exists):
            for fp in await run_sync(lambda: list(test_output_path.rglob("*"))):
                if not await run_sync(fp.is_file):
                    continue
                suffix = fp.suffix.lower()
                if suffix in (".png", ".jpg", ".jpeg"):
                    screenshots.append(str(fp))
                elif suffix in (".webm", ".mp4", ".mov"):
                    videos.append(str(fp))

        return {
            "success": return_code == 0,
            "return_code": return_code,
            "duration": duration,
            "stdout": stdout,
            "stderr": stderr,
            "report_path": report_path,
            "exec_root": str(Path(html_report_dir).parent),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "screenshots": screenshots,
            "videos": videos,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"脚本执行超时（超过{settings.web_exec_timeout_seconds}秒）"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"执行脚本时发生错误: {str(e)}"
        }


async def _parse_json_report(json_report_file: Path) -> Optional[Dict[str, Any]]:
    """
    解析 Playwright JSON reporter 产出的结构化结果。

    Returns:
        None 表示解析失败（文件缺失/格式异常），调用方应回退到 return_code 判定；
        否则返回 {"stats": {...}, "cases": [...]}，cases 为用例级结果。
    """
    try:
        if not await run_sync(json_report_file.exists):
            return None
        raw = await run_sync(json_report_file.read_text, encoding="utf-8", errors="replace")
        data = json.loads(raw)
        # 解析逻辑与服务端链路共用（app.utils.playwright_report），保证口径一致
        return parse_playwright_json(data)
    except Exception as e:
        print(f"[Web Script Execution] 解析 JSON 报告失败，回退到返回码判定: {e}")
        return None


async def _persist_structured_run(
    sub_function: WebSubFunction,
    project_identifier: str,
    execution_id: str,
    execution_result: Dict[str, Any],
    report_object_name: Optional[str],
    headless: bool,
    framework: str,
    reporter: str,
) -> Optional[str]:
    """把结构化执行结果写入 WebTestRun / WebTestResult 表（用例级趋势分析的数据源）。

    与附件报告（_save_test_report）互补：附件存 HTML/zip 供人查看，这里把每个用例的
    pass/fail/duration/retries 落库，供前端做通过率趋势、失败聚类与 flaky 分析。

    设计要点：
    - WebTestRun.web_test_id 为 NOT NULL，因此先按 sub_function_id upsert 一条 WebTest。
    - 仅在拿到结构化 stats 时落库；静态校验失败/超时等无 stats 的场景跳过。
    - 任何异常都不影响主流程：只记录日志并返回 None。

    Returns:
        创建的 WebTestRun ID；未落库或失败返回 None。
    """
    stats = execution_result.get("stats")
    if not stats:
        return None

    try:
        async with async_session_factory() as session:
            sub_function_uuid = sub_function.id

            # 所属功能的基础 URL（WebSubFunction 本身无 base_url，取自所属 WebFunction）
            base_url = None
            function_row = (await session.execute(
                select(WebFunction).where(WebFunction.id == sub_function.function_id)
            )).scalar_one_or_none()
            if function_row:
                base_url = function_row.base_url

            # 1. upsert WebTest（一个子功能对应一条脚本记录）
            web_test = (await session.execute(
                select(WebTest).where(WebTest.sub_function_id == sub_function_uuid)
            )).scalar_one_or_none()
            if web_test is None:
                web_test = WebTest(
                    project_id=sub_function.project_id,
                    folder_id=sub_function.folder_id,
                    function_id=sub_function.function_id,
                    sub_function_id=sub_function_uuid,
                    identifier=f"WT-{uuid4().hex[:8].upper()}",
                    name=sub_function.display_name,
                    base_url=base_url,
                    script_path=f"web-tests/{project_identifier}/sub-functions/{sub_function_uuid}/test-script.ts",
                    script_format="playwright",
                    script_language="typescript",
                    generated_by_agent="web_agent",
                )
                session.add(web_test)
                await session.flush()

            # 2. 创建 WebTestRun（截断日志防止数据库/前端过载，沿用服务端链路口径）
            cases = execution_result.get("cases") or []
            first_error = next((c.get("error") for c in cases if c.get("error")), None)
            duration_ms = stats.get("duration_ms") or int((execution_result.get("duration") or 0) * 1000)
            stdout_text = (execution_result.get("stdout") or "")[:100_000]
            stderr_text = (execution_result.get("stderr") or "")[:100_000]

            test_run = WebTestRun(
                project_id=sub_function.project_id,
                web_test_id=web_test.id,
                identifier=f"WTR-{datetime.now().strftime('%Y%m%d')}-{uuid4().hex[:6]}",
                status="completed" if execution_result.get("success") else "failed",
                execution_config={
                    "execution_id": execution_id,
                    "headless": headless,
                    "framework": framework,
                    "reporter": reporter,
                },
                total_tests=stats.get("total", 0),
                passed_tests=stats.get("passed", 0),
                failed_tests=stats.get("failed", 0),
                skipped_tests=stats.get("skipped", 0),
                duration_ms=duration_ms,
                report_path=report_object_name,
                stdout=stdout_text,
                stderr=stderr_text,
                error_message=first_error,
            )
            session.add(test_run)
            await session.flush()

            # 3. 逐用例创建 WebTestResult
            for c in cases:
                case_error = c.get("error")
                session.add(WebTestResult(
                    test_run_id=test_run.id,
                    web_test_id=web_test.id,
                    scenario_name=(c.get("title") or "未命名用例")[:500],
                    page_url=(base_url or "")[:2048],
                    test_type=sub_function.test_type or "functional",
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
            print(f"[Web Script Execution] 结构化结果已落库: test_run_id={test_run.id}, 用例数={len(cases)}")
            return str(test_run.id)
    except Exception as e:
        print(f"[Web Script Execution] 写入 WebTestRun/WebTestResult 失败（不影响主流程）: {e}")
        import traceback
        traceback.print_exc()
        return None


async def _save_test_report(
    sub_function_id: str,
    project_identifier: str,
    sub_function: WebSubFunction,
    exec_root: str,
    execution_id: str,
    execution_result: Dict[str, Any],
    project_root: str
) -> Optional[Dict[str, str]]:
    """
    保存测试报告到 MinIO 并创建附件记录

    打包整个隔离执行目录（html 报告 + results.json + test-results），并在附件描述中
    写入结构化结果摘要（用例级 pass/fail），便于前端与后续分析直接消费。

    Args:
        sub_function_id: 子功能 ID
        project_identifier: 项目标识符
        sub_function: 子功能对象
        exec_root: 本次执行的隔离根目录
        execution_id: 本次执行的唯一标识
        execution_result: 执行结果（含 stats / cases）
        project_root: 项目根目录

    Returns:
        {"attachment_id": ..., "object_name": ...}；保存失败返回 None。
        object_name 供 WebTestRun.report_path 引用。
    """
    try:
        # 1. 将隔离执行目录打包成 ZIP
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"web_test_report_{timestamp}.zip"
        zip_path = Path(project_root) / zip_filename
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TVhwMk9RPT06MTE1M2I2M2M=

        print(f"[Web Report] 打包测试报告: {exec_root} -> {zip_path}")

        def _create_zip(zip_path: Path, exec_root: str) -> None:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                root = Path(exec_root)
                for file_path in root.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(root)
                        zipf.write(file_path, arcname)

        await run_sync(_create_zip, zip_path, exec_root)

        # 2. 读取 ZIP 文件内容
        zip_bytes = await run_sync(
            lambda p: open(p, 'rb').read(),
            zip_path
        )

        # 3. 上传到 MinIO
        object_name = f"web-tests/{project_identifier}/sub-functions/{sub_function_id}/test-report-{timestamp}.zip"
        await run_sync(
            MinIOClient.upload_bytes,
            object_name=object_name,
            data=zip_bytes,
            content_type="application/zip"
        )

        print(f"[Web Report] 报告已上传到 MinIO: {object_name}")

        # 4. 创建附件记录（描述使用结构化结果，而非脆弱的 stdout 字符串计数）
        async with async_session_factory() as session:
            duration = execution_result.get("duration", 0)
            stats = execution_result.get("stats") or {}
            cases = execution_result.get("cases") or []

            description = f"Web 测试报告 - {sub_function.display_name}\n"
            description += f"执行标识: {execution_id}\n"
            description += f"执行时间: {duration:.2f}秒\n"
            if stats:
                description += (
                    f"结果: 通过 {stats.get('passed', 0)} | 失败 {stats.get('failed', 0)} | "
                    f"跳过 {stats.get('skipped', 0)} | 共 {stats.get('total', 0)}\n"
                )
                failed_cases = [c for c in cases if c.get("status") in ("unexpected", "failed", "timedOut")]
                for c in failed_cases[:5]:
                    description += f"  ✘ {c.get('title')} ({int(c.get('duration_ms', 0))}ms)\n"
            else:
                # 无结构化结果时退化为基础描述
                description += f"返回码: {execution_result.get('return_code')}\n"

            attachment = Attachment(
                entity_type=AttachmentEntityType.WEB_TEST_REPORT,
                entity_id=UUID(sub_function_id),
                project_id=sub_function.project_id,
                file_name=f"web-test-report-{timestamp}.zip",
                file_size=len(zip_bytes),
                content_type="application/zip",
                object_name=object_name,
                description=description.strip(),
                created_by="web-agent"
            )

            session.add(attachment)
            await session.commit()
            await session.refresh(attachment)

            print(f"[Web Report] 附件记录已创建: {attachment.id}")

            # 5. 清理临时 ZIP 文件
            try:
                await run_sync(zip_path.unlink)
                print(f"[Web Report] 临时 ZIP 文件已清理: {zip_path}")
            except Exception as e:
                print(f"[Web Report] 清理临时 ZIP 文件失败: {e}")

            # 6. 清理隔离执行目录
            try:
                await run_sync(shutil.rmtree, exec_root, True)
                print(f"[Web Report] 执行目录已清理: {exec_root}")
            except Exception as e:
                print(f"[Web Report] 清理执行目录失败: {e}")

            return {"attachment_id": str(attachment.id), "object_name": object_name}

    except Exception as e:
        print(f"[Web Report] 保存测试报告失败: {e}")
        import traceback
        traceback.print_exc()
        return None
