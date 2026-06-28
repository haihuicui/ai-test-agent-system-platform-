"""
Android 测试脚本执行工具（企业级执行层）

提供在本地测试目录中执行 Android 测试脚本的功能，支持：
- 失败重试与可重试错误识别
- AndroidTestRun / AndroidTestResult 完整持久化
- Midscene 报告解析与结构化结果提取
- 批量执行的错误隔离
"""

import os
import sys
import json
import re
import subprocess
import zipfile
import shutil
import traceback
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select

from app.utils.sync_executor import run_sync
from app.config import settings
from app.config.database import async_session_factory
from app.models.attachment import Attachment, AttachmentEntityType
from app.models.project import Project
from app.models.android_test import AndroidTest, AndroidTestRun, AndroidTestRunStatus
from app.repositories.android_test_repo import (
    AndroidTestRepository,
    AndroidTestRunRepository,
    AndroidTestResultRepository,
)
from app.schemas.enums import TestResultStatus
from app.config.minio_client import MinIOClient


WORKSPACE_TESTS_ROOT = Path(settings.android_workspace_root) / "tests"


def get_workspace_tests_dir() -> Path:
    """获取 workspace 测试目录路径"""
    return WORKSPACE_TESTS_ROOT


# =============================================================================
# 重试策略
# =============================================================================

RETRYABLE_PATTERNS = [
    re.compile(r"element\s+not\s+found", re.IGNORECASE),
    re.compile(r"timed?\s*out", re.IGNORECASE),
    re.compile(r"ai\s+(?:plan|think|action)\s+(?:fail|timeout)", re.IGNORECASE),
    re.compile(r"INJECT_EVENTS", re.IGNORECASE),
    re.compile(r"screenshot\s+fail", re.IGNORECASE),
    re.compile(r"could\s+not\s+locate", re.IGNORECASE),
    re.compile(r"no\s+android\s+device\s+connected", re.IGNORECASE),
    re.compile(r"device\s+offline", re.IGNORECASE),
]

NON_RETRYABLE_PATTERNS = [
    re.compile(r"SyntaxError"),
    re.compile(r"ReferenceError"),
    re.compile(r"TypeError"),
    re.compile(r"MODULE_NOT_FOUND"),
    re.compile(r"Cannot\s+find\s+module", re.IGNORECASE),
    re.compile(r"app\s+not\s+installed", re.IGNORECASE),
]
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2V0ZoeE5nPT06OTk1MDg3OTE=


def _is_retryable_error(stdout: str, stderr: str, return_code: int) -> bool:
    """
    判断错误是否可重试。

    可重试：视觉定位抖动、AI 规划超时、设备瞬断、弹窗干扰等
    不可重试：脚本语法错误、模块缺失、App 未安装等
    """
    combined = f"{stdout}\n{stderr}"

    if any(p.search(combined) for p in NON_RETRYABLE_PATTERNS):
        return False

    if return_code != 0 and any(p.search(combined) for p in RETRYABLE_PATTERNS):
        return True

    # 未知错误默认不重试，避免无限消耗资源
    return False


def _build_retry_context(attempt: int) -> str:
    """生成重试时注入的额外上下文提示"""
    if attempt == 1:
        return "如果因弹窗或页面未加载导致失败，请增加 aiWaitFor 等待。"
    return "已连续失败，建议降低截图缩放因子或增加 replanningCycleLimit。"


# =============================================================================
# 报告解析
# =============================================================================

def _find_midscene_report_dir(project_root: Path, report_file_name: Optional[str] = None) -> Optional[Path]:
    """定位 Midscene 报告目录"""
    report_root = project_root / "midscene_run" / "report"
    if report_root.exists() and any(report_root.iterdir()):
        return report_root
    return None
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2V0ZoeE5nPT06OTk1MDg3OTE=


def _parse_midscene_results(
    project_root: Path,
    report_file_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    解析 Midscene 执行结果。

    优先查找 persistExecutionDump 生成的 JSON dump，
    否则尝试从报告目录的 HTML 文件名和 stdout 推断。
    """
    results: List[Dict[str, Any]] = []

    # 1. 查找 JSON dump
    dump_candidates = [
        project_root / "midscene_run" / "dump" / f"{report_file_name}.json",
        project_root / "midscene_run" / "dump" / "execution-dump.json",
        project_root / "midscene_run" / "dump.json",
    ]
    for dump_path in dump_candidates:
        if dump_path.exists():
            try:
                with open(dump_path, "r", encoding="utf-8") as f:
                    dump = json.load(f)
                # Midscene dump 结构推测：包含 tasks/actions/assertions
                return _normalize_dump_results(dump)
            except Exception:
                pass

    # 2. 查找 HTML 报告文件，按文件名推断用例
    report_dir = _find_midscene_report_dir(project_root, report_file_name)
    if report_dir:
        html_files = sorted(report_dir.glob("*.html"))
        for html_file in html_files:
            results.append({
                "case_id": html_file.stem,
                "scenario_name": html_file.stem,
                "status": "unknown",
                "duration_ms": None,
                "error_message": None,
                "screenshot_path": None,
                "test_summary": {"report_file": html_file.name},
            })

    return results


def _normalize_dump_results(dump: Any) -> List[Dict[str, Any]]:
    """将 Midscene dump 归一化为内部结果格式"""
    results: List[Dict[str, Any]] = []
    if not isinstance(dump, dict):
        return results

    tasks = dump.get("tasks") or dump.get("actions") or []
    for idx, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue
        status = "passed" if task.get("success") or task.get("status") == "success" else "failed"
        error = task.get("error") or task.get("errorMessage") or task.get("thought")
        results.append({
            "case_id": task.get("name") or task.get("id") or f"step_{idx+1}",
            "scenario_name": task.get("name") or f"Step {idx+1}",
            "status": status,
            "duration_ms": task.get("durationMs") or task.get("duration") or task.get("time"),
            "error_message": error if status == "failed" else None,
            "screenshot_path": task.get("screenshot") or task.get("screenshotAfter"),
            "test_summary": task,
        })
    return results


def _extract_results_from_stdout(stdout: str) -> List[Dict[str, Any]]:
    """stdout 降级解析：用于没有 dump 的情况"""
    results: List[Dict[str, Any]] = []

    # 匹配 "=== Test: xxx ===" 或 "Step N: xxx"
    step_pattern = re.compile(r"(?:===\s*Test:\s*(.+?)\s*===|Step\s+(\d+)\s*:\s*(.+))", re.IGNORECASE)
    error_pattern = re.compile(r"(?:Error|❌|Test failed):?\s*(.+)", re.IGNORECASE)

    steps = step_pattern.findall(stdout)
    errors = error_pattern.findall(stdout)

    if not steps:
        # 整体作为一条结果
        has_error = bool(errors)
        results.append({
            "case_id": "main",
            "scenario_name": "Main Test",
            "status": "failed" if has_error else "passed",
            "duration_ms": None,
            "error_message": errors[0] if errors else None,
            "screenshot_path": None,
            "test_summary": {"stdout_steps": 0},
        })
        return results

    for name_from_test, step_num, name_from_step in steps:
        scenario_name = (name_from_test or name_from_step or f"Step {step_num}").strip()
        case_id = f"step_{step_num or 0}"
        results.append({
            "case_id": case_id,
            "scenario_name": scenario_name,
            "status": "passed",  # 默认通过，后续根据错误覆盖
            "duration_ms": None,
            "error_message": None,
            "screenshot_path": None,
            "test_summary": {"source": "stdout"},
        })

    # 如果有错误但未定位到具体步骤，标记最后一步失败
    if errors and results:
        results[-1]["status"] = "failed"
        results[-1]["error_message"] = errors[0]
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2V0ZoeE5nPT06OTk1MDg3OTE=

    return results


# =============================================================================
# 执行核心
# =============================================================================

async def _execute_once(
    script_path: str,
    script_filename: str,
    framework: str,
    project_root: str,
    extra_env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """单次执行脚本"""
    start_time = datetime.now(timezone.utc)
    is_windows = sys.platform == "win32"

    if framework == "midscene":
        if is_windows:
            cmd = f'npx tsx "{script_filename}"'
        else:
            cmd = ["npx", "tsx", script_filename]
    elif framework == "appium":
        if is_windows:
            cmd = f'npx wdio run "{script_filename}"'
        else:
            cmd = ["npx", "wdio", "run", script_filename]
    else:
        return {"success": False, "error": f"不支持的测试框架: {framework}"}

    env = os.environ.copy()
    env["CI"] = "1"
    if extra_env:
        env.update(extra_env)

    result = await run_sync(
        subprocess.run,
        cmd,
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        shell=is_windows,
        env=env,
    )

    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()

    report_dir = Path(project_root) / "midscene_run" / "report"
    report_exists = await run_sync(lambda d: d.exists() and any(d.iterdir()), report_dir)
    report_path = str(report_dir) if report_exists else None

    return {
        "success": result.returncode == 0,
        "return_code": result.returncode,
        "duration": duration,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "report_path": report_path,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
    }


async def _execute_android_script_internal(
    script_path: str,
    script_filename: str,
    framework: str,
    project_root: str,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """内部执行：支持重试"""
    last_result: Optional[Dict[str, Any]] = None
    attempt = 0

    while attempt <= max_retries:
        attempt += 1
        print(f"[Android Script Execution] 执行尝试 {attempt}/{max_retries + 1}: {script_filename}")
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2V0ZoeE5nPT06OTk1MDg3OTE=

        extra_env = {}
        if attempt > 1:
            extra_env["MIDSCENE_RETRY_ATTEMPT"] = str(attempt)
            extra_env["MIDSCENE_RETRY_HINT"] = _build_retry_context(attempt - 1)

        last_result = await _execute_once(
            script_path=script_path,
            script_filename=script_filename,
            framework=framework,
            project_root=project_root,
            extra_env=extra_env,
        )

        if last_result.get("success"):
            last_result["attempts"] = attempt
            last_result["retried"] = attempt > 1
            return last_result

        if attempt <= max_retries and _is_retryable_error(
            last_result.get("stdout", ""),
            last_result.get("stderr", ""),
            last_result.get("return_code", -1),
        ):
            print(f"[Android Script Execution] 检测到可重试错误，准备第 {attempt + 1} 次尝试")
            continue
        else:
            print("[Android Script Execution] 错误不可重试或已达最大重试次数")
            break

    last_result = last_result or {"success": False, "error": "未执行"}
    last_result["attempts"] = attempt
    last_result["retried"] = attempt > 1
    return last_result


# =============================================================================
# 测试运行持久化
# =============================================================================

async def _create_test_run(
    session,
    android_test_id: UUID,
    execution_config: Dict[str, Any],
) -> AndroidTestRun:
    """创建 AndroidTestRun 记录"""
    repo = AndroidTestRunRepository(session)
    test_repo = AndroidTestRepository(session)

    android_test = await test_repo.get_by_id(android_test_id)
    if not android_test:
        raise ValueError(f"AndroidTest {android_test_id} not found")

    identifier = await repo.get_next_identifier(android_test_id)
    run = AndroidTestRun(
        project_id=android_test.project_id,
        android_test_id=android_test_id,
        identifier=identifier,
        status=AndroidTestRunStatus.RUNNING,
        execution_config=execution_config,
    )
    session.add(run)
    await session.flush()
    await session.refresh(run)
    return run


async def _finalize_test_run(
    session,
    run: AndroidTestRun,
    execution_result: Dict[str, Any],
    parsed_results: List[Dict[str, Any]],
    report_path: Optional[str],
    report_object_name: Optional[str],
) -> None:
    """更新 AndroidTestRun 并写入 AndroidTestResult"""
    duration_sec = execution_result.get("duration", 0)
    run.duration_ms = int(duration_sec * 1000)
    run.status = (
        AndroidTestRunStatus.COMPLETED
        if execution_result.get("success")
        else AndroidTestRunStatus.FAILED
    )

    # 统计
    passed = sum(1 for r in parsed_results if r.get("status") == "passed")
    failed = sum(1 for r in parsed_results if r.get("status") == "failed")
    skipped = sum(1 for r in parsed_results if r.get("status") == "skipped")
    total = len(parsed_results)

    run.total_tests = total or (1 if execution_result.get("success") else 0)
    run.passed_tests = passed
    run.failed_tests = failed
    run.skipped_tests = skipped

    if report_object_name:
        run.report_path = report_object_name

    if not execution_result.get("success") and not parsed_results:
        run.error_message = (
            execution_result.get("stderr", "")[:2000]
            or execution_result.get("error", "")
            or "执行失败"
        )

    await session.flush()
    await session.refresh(run)

    # 写入详细结果
    result_repo = AndroidTestResultRepository(session)
    if parsed_results:
        for item in parsed_results:
            result = AndroidTestResult(
                test_run_id=run.id,
                android_test_id=run.android_test_id,
                scenario_name=item.get("scenario_name", "Unknown")[:500],
                case_id=item.get("case_id", "unknown"),
                test_type=item.get("test_type", "interaction"),
                status=_map_status(item.get("status", "failed")),
                test_summary=item.get("test_summary"),
                error_details=item.get("error_details"),
                error_message=item.get("error_message"),
                screenshot_path=item.get("screenshot_path"),
                duration_ms=item.get("duration_ms"),
                retry_count=item.get("retry_count", 0),
            )
            session.add(result)
    elif execution_result.get("success"):
        # 没有解析到步骤，但整体成功，记录一条汇总结果
        result = AndroidTestResult(
            test_run_id=run.id,
            android_test_id=run.android_test_id,
            scenario_name="Main Test",
            case_id="main",
            test_type="interaction",
            status=TestResultStatus.PASSED,
            test_summary={"source": "execution_summary"},
            duration_ms=int(duration_sec * 1000),
        )
        session.add(result)

    await session.flush()


def _map_status(status: str) -> TestResultStatus:
    mapping = {
        "passed": TestResultStatus.PASSED,
        "failed": TestResultStatus.FAILED,
        "skipped": TestResultStatus.SKIPPED,
        "blocked": TestResultStatus.BLOCKED,
        "unknown": TestResultStatus.FAILED,
    }
    return mapping.get(status.lower(), TestResultStatus.FAILED)


# =============================================================================
# 报告上传
# =============================================================================

async def _save_android_test_report(
    project_identifier: str,
    project: Project,
    report_path: str,
    execution_result: Dict[str, Any],
    project_root: str,
) -> Optional[str]:
    """保存 Android 测试报告到 MinIO 并创建附件记录"""
    try:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        zip_filename = f"android_test_report_{timestamp}.zip"
        zip_path = Path(project_root) / zip_filename

        print(f"[Android Report] 打包测试报告: {report_path} -> {zip_path}")

        def _create_zip(zip_path: Path, report_path: str) -> None:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                report_dir = Path(report_path)
                for file_path in report_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(report_dir)
                        zipf.write(file_path, arcname)

        await run_sync(_create_zip, zip_path, report_path)

        zip_bytes = await run_sync(
            lambda p: open(p, "rb").read(),
            zip_path
        )

        object_name = f"android-tests/{project_identifier}/reports/test-report-{timestamp}.zip"
        await run_sync(
            MinIOClient.upload_bytes,
            object_name=object_name,
            data=zip_bytes,
            content_type="application/zip",
        )

        print(f"[Android Report] 报告已上传到 MinIO: {object_name}")

        duration = execution_result.get("duration", 0)
        stdout = execution_result.get("stdout", "")
        passed_count = stdout.count("Test passed") + stdout.count("passed")
        failed_count = stdout.count("Test failed") + stdout.count("failed")

        description = "Android 测试报告\n"
        description += f"执行时间: {duration:.2f}秒\n"
        if passed_count > 0 or failed_count > 0:
            description += f"通过: {passed_count} | 失败: {failed_count}"

        async with async_session_factory() as session:
            attachment = Attachment(
                entity_type=AttachmentEntityType.ANDROID_TEST_REPORT,
                entity_id=project.id,
                project_id=project.id,
                file_name=f"android-test-report-{timestamp}.zip",
                file_size=len(zip_bytes),
                content_type="application/zip",
                object_name=object_name,
                description=description,
                created_by="android-agent",
            )
            session.add(attachment)
            await session.commit()
            await session.refresh(attachment)

        try:
            await run_sync(zip_path.unlink)
        except Exception as e:
            print(f"[Android Report] 清理临时 ZIP 文件失败: {e}")

        return object_name

    except Exception as e:
        print(f"[Android Report] 保存测试报告失败: {e}")
        traceback.print_exc()
        return None


# =============================================================================
# 对外工具
# =============================================================================

@tool
async def execute_android_script(
    local_script_path: str,
    framework: str = "midscene",
    reporter: str = "html",
    project_identifier: str = "",
    android_test_id: Optional[str] = None,
    max_retries: int = 2,
) -> str:
    """
    执行已下载到本地测试目录的 Android 测试脚本（企业级）

    能力：
    1. 可重试错误自动重试（默认最多 2 次重试）
    2. 创建 AndroidTestRun 并更新执行状态
    3. 解析 Midscene 报告，生成 AndroidTestResult
    4. 将测试报告打包上传到 MinIO

    Args:
        local_script_path: 本地脚本文件路径（相对或绝对）
        framework: 测试框架 (midscene, appium, espresso)
        reporter: 报告格式
        project_identifier: 项目标识符，用于保存测试报告
        android_test_id: Android 测试 ID（必填，用于创建运行记录）
        max_retries: 最大重试次数（默认 2）

    Returns:
        JSON 格式的执行结果
    """
    run_id_str: Optional[str] = None
    try:
        # 1. 解析脚本路径
        cleaned_path = local_script_path.strip().strip("/").strip("\\")
        script_path = Path(cleaned_path)
        project_root = Path(settings.android_workspace_root).resolve()
        workspace_tests_dir = get_workspace_tests_dir()

        if script_path.is_absolute():
            pass
        else:
            test_path_full = project_root / script_path
            if await run_sync(test_path_full.exists):
                script_path = test_path_full
            else:
                test_path = workspace_tests_dir / script_path
                if await run_sync(test_path.exists):
                    script_path = test_path
                elif not script_path.suffix:
                    test_path_with_ext = workspace_tests_dir / f"{script_path.name}.ts"
                    if await run_sync(test_path_with_ext.exists):
                        script_path = test_path_with_ext

        if not await run_sync(script_path.exists):
            return json.dumps(
                {"success": False, "error": f"脚本文件不存在: {script_path}"},
                ensure_ascii=False,
                indent=2,
            )

        try:
            relative_path = script_path.resolve().relative_to(project_root)
        except ValueError:
            relative_path = script_path.name

        script_filename = script_path.name
        print(f"[Android Script Execution] 准备执行脚本: {script_path}")

        # 2. 创建 AndroidTestRun（如果提供了 android_test_id）
        run: Optional[AndroidTestRun] = None
        if android_test_id:
            try:
                test_uuid = UUID(android_test_id)
                async with async_session_factory() as session:
                    run = await _create_test_run(
                        session,
                        test_uuid,
                        {
                            "script_path": str(relative_path),
                            "framework": framework,
                            "reporter": reporter,
                            "project_identifier": project_identifier,
                        },
                    )
                    await session.commit()
                    run_id_str = str(run.id)
                    print(f"[Android Script Execution] 已创建运行记录: {run_id_str}")
            except Exception as e:
                print(f"[Android Script Execution] 创建运行记录失败: {e}")

        # 3. 执行脚本（带重试）
        execution_result = await _execute_android_script_internal(
            script_path=str(relative_path),
            script_filename=script_filename,
            framework=framework,
            project_root=str(project_root),
            max_retries=max_retries,
        )

        # 4. 解析结果
        parsed_results = await run_sync(_parse_midscene_results, project_root)
        if not parsed_results:
            parsed_results = await run_sync(_extract_results_from_stdout, execution_result.get("stdout", ""))

        # 5. 上传报告
        report_object_name: Optional[str] = None
        report_attachment_id: Optional[str] = None
        if reporter == "html" and execution_result.get("report_path") and project_identifier:
            async with async_session_factory() as db:
                project_result = await db.execute(
                    select(Project).where(Project.identifier == project_identifier)
                )
                project = project_result.scalar_one_or_none()

                if project:
                    report_object_name = await _save_android_test_report(
                        project_identifier=project_identifier,
                        project=project,
                        report_path=execution_result["report_path"],
                        execution_result=execution_result,
                        project_root=str(project_root),
                    )
                    # 查询刚创建的 attachment id
                    if report_object_name:
                        attachment_result = await db.execute(
                            select(Attachment).where(Attachment.object_name == report_object_name)
                        )
                        attachment = attachment_result.scalar_one_or_none()
                        if attachment:
                            report_attachment_id = str(attachment.id)

        # 6. 更新 AndroidTestRun 与 AndroidTestResult
        if run_id_str:
            try:
                async with async_session_factory() as session:
                    run = await session.get(AndroidTestRun, UUID(run_id_str))
                    if run:
                        await _finalize_test_run(
                            session,
                            run,
                            execution_result,
                            parsed_results,
                            execution_result.get("report_path"),
                            report_object_name,
                        )
                        await session.commit()
                        print(f"[Android Script Execution] 已更新运行记录及 {len(parsed_results)} 条结果")
            except Exception as e:
                print(f"[Android Script Execution] 更新运行记录失败: {e}")
                traceback.print_exc()

        # 7. 更新 AndroidTest 统计
        if android_test_id:
            try:
                async with async_session_factory() as db:
                    test_result = await db.execute(
                        select(AndroidTest).where(AndroidTest.id == UUID(android_test_id))
                    )
                    android_test = test_result.scalar_one_or_none()
                    if android_test:
                        android_test.total_scenarios = (android_test.total_scenarios or 0) + max(
                            len(parsed_results), 1
                        )
                        android_test.updated_at = datetime.now(timezone.utc)
                        await db.commit()
            except Exception as e:
                print(f"[Android Script Execution] 更新 Android 测试记录失败: {e}")

        # 8. 返回结果
        result_payload = {
            "success": execution_result.get("success", False),
            "script_path": str(script_path),
            "script_filename": script_filename,
            "run_id": run_id_str,
            "report_attachment_id": report_attachment_id,
            "attempts": execution_result.get("attempts", 1),
            "retried": execution_result.get("retried", False),
            "execution_result": {
                "return_code": execution_result.get("return_code"),
                "duration": execution_result.get("duration"),
                "stdout": execution_result.get("stdout", "")[-4000:],
                "stderr": execution_result.get("stderr", "")[-2000:],
                "report_path": execution_result.get("report_path"),
            },
            "parsed_results": [
                {
                    "case_id": r.get("case_id"),
                    "scenario_name": r.get("scenario_name"),
                    "status": r.get("status"),
                    "error_message": r.get("error_message"),
                }
                for r in parsed_results
            ],
        }

        return json.dumps(result_payload, ensure_ascii=False, indent=2)

    except Exception as e:
        traceback.print_exc()

        # 尽量标记运行失败
        if run_id_str:
            try:
                async with async_session_factory() as session:
                    run = await session.get(AndroidTestRun, UUID(run_id_str))
                    if run:
                        run.status = AndroidTestRunStatus.FAILED
                        run.error_message = f"执行异常: {str(e)[:2000]}"
                        await session.commit()
            except Exception:
                pass

        return json.dumps(
            {"success": False, "run_id": run_id_str, "error": f"执行脚本时发生错误: {str(e)}"},
            ensure_ascii=False,
            indent=2,
        )


@tool
async def get_android_execution_status(
    execution_id: str,
) -> str:
    """
    获取 Android 测试执行状态

    Args:
        execution_id: AndroidTestRun ID

    Returns:
        JSON 格式的执行状态及结果摘要
    """
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(AndroidTestRun).where(AndroidTestRun.id == UUID(execution_id))
            )
            run = result.scalar_one_or_none()

            if not run:
                return json.dumps(
                    {"success": False, "error": f"未找到运行记录: {execution_id}"},
                    ensure_ascii=False,
                    indent=2,
                )

            results_result = await db.execute(
                select(AndroidTestResult).where(AndroidTestResult.test_run_id == run.id)
            )
            results = results_result.scalars().all()

            return json.dumps(
                {
                    "success": True,
                    "execution_id": execution_id,
                    "identifier": run.identifier,
                    "status": run.status,
                    "duration_ms": run.duration_ms,
                    "total_tests": run.total_tests,
                    "passed_tests": run.passed_tests,
                    "failed_tests": run.failed_tests,
                    "skipped_tests": run.skipped_tests,
                    "report_path": run.report_path,
                    "error_message": run.error_message,
                    "created_at": run.created_at.isoformat() if run.created_at else None,
                    "results": [
                        {
                            "case_id": r.case_id,
                            "scenario_name": r.scenario_name,
                            "status": r.status.value,
                            "duration_ms": r.duration_ms,
                            "error_message": r.error_message,
                        }
                        for r in results
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )

    except Exception as e:
        return json.dumps(
            {"success": False, "error": f"查询执行状态时发生错误: {str(e)}"},
            ensure_ascii=False,
            indent=2,
        )


@tool
async def run_all_android_scripts(
    project_identifier: str,
    script_pattern: str = "tests/android/test_*.ts",
    max_retries: int = 2,
) -> str:
    """
    批量执行 Android 测试目录中匹配的所有脚本

    特性：
    - 每个脚本独立执行，单个失败不影响其他脚本
    - 每个脚本自动创建 AndroidTestRun
    - 汇总执行统计

    Args:
        project_identifier: 项目标识符
        script_pattern: 脚本匹配模式（glob）
        max_retries: 每个脚本最大重试次数

    Returns:
        JSON 格式的批量执行结果
    """
    try:
        project_root = Path(settings.android_workspace_root).resolve()
        tests_dir = project_root / "tests" / "android"
        scripts = sorted(tests_dir.glob(Path(script_pattern).name))

        if not scripts:
            return json.dumps(
                {
                    "success": True,
                    "message": "未找到匹配脚本",
                    "matched_pattern": script_pattern,
                    "results": [],
                },
                ensure_ascii=False,
                indent=2,
            )

        results: List[Dict[str, Any]] = []
        overall_success = True

        for script in scripts:
            script_result: Dict[str, Any] = {
                "script": script.name,
                "success": False,
                "run_id": None,
                "return_code": None,
                "duration": None,
                "report_attachment_id": None,
                "error": None,
            }
            try:
                result_json = await execute_android_script(
                    local_script_path=str(script),
                    framework="midscene",
                    reporter="html",
                    project_identifier=project_identifier,
                    max_retries=max_retries,
                )
                parsed = json.loads(result_json)
                script_result["success"] = parsed.get("success", False)
                script_result["run_id"] = parsed.get("run_id")
                script_result["return_code"] = parsed.get("execution_result", {}).get("return_code")
                script_result["duration"] = parsed.get("execution_result", {}).get("duration")
                script_result["report_attachment_id"] = parsed.get("report_attachment_id")
                script_result["attempts"] = parsed.get("attempts", 1)
                script_result["retried"] = parsed.get("retried", False)
            except Exception as e:
                script_result["error"] = str(e)
                traceback.print_exc()

            if not script_result["success"]:
                overall_success = False
            results.append(script_result)

        return json.dumps(
            {
                "success": overall_success,
                "total": len(results),
                "passed": sum(1 for r in results if r["success"]),
                "failed": sum(1 for r in results if not r["success"]),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        traceback.print_exc()
        return json.dumps(
            {"success": False, "error": f"批量执行时发生错误: {str(e)}"},
            ensure_ascii=False,
            indent=2,
        )
