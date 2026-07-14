"""
Web 测试脚本执行工具

提供在 测试目录中执行 Playwright 脚本的功能
"""

import os
import sys
import json
import subprocess
import tempfile
import zipfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TVhwMk9RPT06MTE1M2I2M2M=

from app.utils.sync_executor import run_sync
from app.utils.shell_env import resolve_effective_headless
from app.config import settings
from app.config.database import async_session_factory
from app.models.attachment import Attachment, AttachmentEntityType
from app.models.web_function import WebSubFunction
from app.config.minio_client import MinIOClient


# ============================================================================
# 测试目录配置
# ============================================================================

# 测试服务器根目录
WORKSPACE_TESTS_ROOT = Path(settings.web_mcp_workspace_root) / "tests"


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
    2. 执行 Playwright 测试
    3. 生成测试报告（HTML/JSON）
    4. 将测试报告保存到 MinIO
    5. 在数据库中创建测试报告附件记录
    6. 更新子功能的测试运行次数
    7. 清理临时报告文件

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
        - execution_result: 执行结果（stdout, stderr, duration, return_code）
        - report_attachment_id: 测试报告附件 ID（如果生成了报告）
        - error: 错误信息（如果有）

    Example:
        >>> result = await execute_web_script(
        ...     local_script_path="backend/workspace/web/tests/login_test.spec.ts",
        ...     framework="playwright",
        ...     reporter="html",
        ...     project_identifier="PR-3",
        ...     sub_function_id="5ea81a5f-c97b-4a36-a680-13637f1b9eed"
        ... )
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

        print(f"[Web Script Execution] 准备执行脚本: {script_path}")

        # 3. 确定相对路径（相对于项目根目录，playwright 以 project_root 为工作目录）
        #    脚本通常位于 project_root/tests 下；若不在 project_root 内，退用文件名
        try:
            relative_path = script_path.relative_to(project_root)
        except ValueError:
            relative_path = Path(script_filename)

        print(f"[Web Script Execution] 项目根目录: {project_root}")
        print(f"[Web Script Execution] 相对脚本路径: {relative_path}")

        # 4.5 静态校验：先用 --list 确认脚本可被收集（不起浏览器），挡掉语法/import 类错误
        static_check = await _static_check_script(
            script_path=str(relative_path),
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

        # 5. 执行脚本
        resolved_headless = settings.web_mcp_headless if headless is None else headless
        execution_result = await _execute_script_internal(
            script_path=str(relative_path),
            script_filename=script_filename,
            framework=framework,
            reporter=reporter,
            project_root=str(project_root),
            headless=resolved_headless,
        )

        # 6. 保存测试报告到 MinIO（如果生成了 HTML 报告）
        report_attachment_id = None
        if sub_function_id and reporter == "html" and execution_result.get("report_path"):
            # 获取子功能信息
            async with async_session_factory() as db:
                sub_function_result = await db.execute(
                    select(WebSubFunction).where(WebSubFunction.id == UUID(sub_function_id))
                )
                sub_function = sub_function_result.scalar_one_or_none()

            if sub_function:
                report_attachment_id = await _save_test_report(
                    sub_function_id=sub_function_id,
                    project_identifier=project_identifier,
                    sub_function=sub_function,
                    report_path=execution_result["report_path"],
                    execution_result=execution_result,
                    project_root=str(project_root)
                )

                # 7. 更新子功能的测试运行次数
                try:
                    async with async_session_factory() as db:
                        sub_function_result = await db.execute(
                            select(WebSubFunction).where(WebSubFunction.id == UUID(sub_function_id))
                        )
                        sub_function = sub_function_result.scalar_one_or_none()

                        if sub_function:
                            # 递增测试运行次数
                            sub_function.total_test_runs = (sub_function.total_test_runs or 0) + 1
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TVhwMk9RPT06MTE1M2I2M2M=

                            # 更新最后运行状态
                            if execution_result.get("success"):
                                sub_function.last_run_status = "passed"
                            else:
                                sub_function.last_run_status = "failed"

                            await db.commit()
                            print(f"[Web Script Execution] 已更新子功能 {sub_function_id} 的测试运行次数")
                except Exception as e:
                    print(f"[Web Script Execution] 更新子功能测试运行次数失败: {e}")

        # 8. 返回结果
        result = {
            "success": True,
            "script_path": str(script_path),
            "script_filename": script_filename,
            "execution_result": execution_result
        }

        if report_attachment_id:
            result["report_attachment_id"] = report_attachment_id
            result["message"] = "脚本执行完成，测试报告已保存"

        if sub_function_id:
            result["sub_function_id"] = sub_function_id

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return json.dumps({
            "success": False,
            "error": f"执行脚本时发生错误: {str(e)}"
        }, ensure_ascii=False, indent=2)


async def _static_check_script(script_path: str, project_root: str) -> Dict[str, Any]:
    """
    静态校验：用 `playwright test --list` 确认脚本可被收集（语法 / import / 收集期错误），
    不启动浏览器。通过后才进入真实执行，避免为毫秒级就能发现的错误付出一次最长 300s 的浏览器执行。

    选择 --list 而非 tsc --noEmit 的原因：workspace 没有 tsconfig.json，tsc 开箱即用会误报；
    --list 依赖已有的 playwright.config.js（testDir=./tests），能捕获语法/缺 import/收集错误且不起浏览器。

    Args:
        script_path: 相对 project_root 的脚本路径
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
            timeout=120,  # 收集阶段不应超过 2 分钟
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
        return {"success": False, "error": "静态校验超时（--list 超过 120s）", "output": ""}
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
    headless: bool = True,
) -> Dict[str, Any]:
    """
    内部执行脚本函数

    Args:
        script_path: 脚本文件相对路径（相对于 project_root）
        script_filename: 脚本文件名
        framework: 测试框架
        reporter: 报告格式
        project_root: 项目根目录

    Returns:
        执行结果字典
    """
    try:
        start_time = datetime.now()

        # 确定测试命令
        is_windows = sys.platform == "win32"
        effective_headless = resolve_effective_headless(headless)
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TVhwMk9RPT06MTE1M2I2M2M=

        if framework == "playwright":
            headed_flag = "--headed" if not effective_headless else ""
            if reporter == "html":
                # HTML 报告需要指定输出目录
                if is_windows:
                    cmd = f'npx playwright test "{script_filename}" --reporter=html {headed_flag}'
                else:
                    cmd = ["npx", "playwright", "test", script_filename, "--reporter=html"]
                    if headed_flag:
                        cmd.append("--headed")
            else:
                if is_windows:
                    cmd = f'npx playwright test "{script_filename}" --reporter={reporter} {headed_flag}'
                else:
                    cmd = ["npx", "playwright", "test", script_filename, f"--reporter={reporter}"]
                    if headed_flag:
                        cmd.append("--headed")
        else:
            return {
                "success": False,
                "error": f"不支持的测试框架: {framework}，Web 测试仅支持 playwright"
            }

        print(f"[Web Script Execution] 执行命令: {cmd if is_windows else ' '.join(cmd)}")
        print(f"[Web Script Execution] 工作目录: {project_root}")

        # 准备环境变量（设置 CI=1 禁用 Playwright HTML reporter 自动打开浏览器）
        env = os.environ.copy()
        if reporter == "html":
            env['CI'] = '1'

        # 执行测试
        result = await run_sync(
            subprocess.run,
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=300,  # 5分钟超时
            shell=is_windows,
            env=env
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 解析输出
        stdout = result.stdout
        stderr = result.stderr
        return_code = result.returncode

        print(f"[Web Script Execution] 执行完成，返回码: {return_code}")
        print(f"[Web Script Execution] 执行时间: {duration:.2f}s")

        # 检查是否生成了 HTML 报告
        report_path = None
        if reporter == "html":
            report_dir = Path(project_root) / "playwright-report"
            index_html = report_dir / "index.html"
            if await run_sync(index_html.exists):
                report_path = str(report_dir)
                print(f"[Web Script Execution] HTML 报告已生成: {report_path}")

        return {
            "success": return_code == 0,
            "return_code": return_code,
            "duration": duration,
            "stdout": stdout,
            "stderr": stderr,
            "report_path": report_path,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "脚本执行超时（超过5分钟）"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"执行脚本时发生错误: {str(e)}"
        }


async def _save_test_report(
    sub_function_id: str,
    project_identifier: str,
    sub_function: WebSubFunction,
    report_path: str,
    execution_result: Dict[str, Any],
    project_root: str
) -> Optional[str]:
    """
    保存测试报告到 MinIO 并创建附件记录

    Args:
        sub_function_id: 子功能 ID
        project_identifier: 项目标识符
        sub_function: 子功能对象
        report_path: 报告目录路径
        execution_result: 执行结果
        project_root: 项目根目录

    Returns:
        附件 ID，如果保存失败则返回 None
    """
    try:
        # 1. 将报告目录打包成 ZIP
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"web_test_report_{timestamp}.zip"
        zip_path = Path(project_root) / zip_filename
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TVhwMk9RPT06MTE1M2I2M2M=

        print(f"[Web Report] 打包测试报告: {report_path} -> {zip_path}")

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
        object_name = f"web-tests/{project_identifier}/sub-functions/{sub_function_id}/test-report-{timestamp}.zip"
        await run_sync(
            MinIOClient.upload_bytes,
            object_name=object_name,
            data=zip_bytes,
            content_type="application/zip"
        )

        print(f"[Web Report] 报告已上传到 MinIO: {object_name}")

        # 4. 创建附件记录
        async with async_session_factory() as session:
            # 生成报告描述
            duration = execution_result.get("duration", 0)
            stdout = execution_result.get("stdout", "")

            # 尝试解析测试结果
            passed_count = stdout.count("✓") + stdout.count("passed")
            failed_count = stdout.count("✘") + stdout.count("failed")

            description = f"Web 测试报告 - {sub_function.display_name}\n"
            description += f"执行时间: {duration:.2f}秒\n"
            if passed_count > 0 or failed_count > 0:
                description += f"通过: {passed_count} | 失败: {failed_count}"

            # 创建附件
            attachment = Attachment(
                entity_type=AttachmentEntityType.WEB_TEST_REPORT,
                entity_id=UUID(sub_function_id),
                project_id=sub_function.project_id,
                file_name=f"web-test-report-{timestamp}.zip",
                file_size=len(zip_bytes),
                content_type="application/zip",
                object_name=object_name,
                description=description,
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

            # 6. 清理报告目录
            try:
                await run_sync(shutil.rmtree, report_path)
                print(f"[Web Report] 报告目录已清理: {report_path}")
            except Exception as e:
                print(f"[Web Report] 清理报告目录失败: {e}")

            return str(attachment.id)

    except Exception as e:
        print(f"[Web Report] 保存测试报告失败: {e}")
        import traceback
        traceback.print_exc()
        return None
