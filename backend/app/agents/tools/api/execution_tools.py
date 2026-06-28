"""
API 测试脚本执行工具

提供在测试目录中执行 API 测试脚本的功能
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

from app.utils.sync_executor import run_sync
from app.config import settings
from app.config.database import async_session_factory
from app.models.attachment import Attachment, AttachmentEntityType
from app.models.api_endpoint import APIEndpoint
from app.config.minio_client import MinIOClient


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


@tool
async def execute_api_script(
    local_script_path: str,
    framework: str = "playwright",
    reporter: str = "html",
    project_identifier: str = "PR-1",
    endpoint_id: Optional[str] = None
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

    Returns:
        JSON 格式的执行结果，包含：
        - success: 是否成功
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
        ...     endpoint_id="5ea81a5f-c97b-4a36-a680-13637f1b9eed"
        ... )
    """
    try:
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
            return json.dumps({
                "success": False,
                "error": f"脚本文件不存在: {script_path}"
            }, ensure_ascii=False, indent=2)

        script_filename = script_path.name

        print(f"[API Script Execution] 准备执行脚本: {script_path}")

        # 4. 计算相对路径（相对于 project_root）
        try:
            relative_path = script_path.resolve().relative_to(project_root)
        except ValueError:
            # 如果无法计算相对路径，使用文件名
            relative_path = script_path.name

        print(f"[API Script Execution] 项目根目录: {project_root}")
        print(f"[API Script Execution] 相对脚本路径: {relative_path}")

        # 5. 执行脚本
        execution_result = await _execute_script_internal(
            script_path=str(relative_path),
            script_filename=script_filename,
            framework=framework,
            reporter=reporter,
            project_root=str(project_root)
        )

        # 6. 保存测试报告到 MinIO（如果生成了 HTML 报告）
        report_attachment_id = None
        if endpoint_id and reporter == "html" and execution_result.get("report_path"):
            # 获取端点信息
            async with async_session_factory() as db:
                endpoint_result = await db.execute(
                    select(APIEndpoint).where(APIEndpoint.id == UUID(endpoint_id))
                )
                endpoint = endpoint_result.scalar_one_or_none()

            if endpoint:
                report_attachment_id = await _save_test_report(
                    endpoint_id=endpoint_id,
                    project_identifier=project_identifier,
                    endpoint=endpoint,
                    report_path=execution_result["report_path"],
                    execution_result=execution_result,
                    project_root=str(project_root)
                )
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TkUxcll3PT06ZGQyYmExYzM=

                # 7. 更新端点的测试运行次数
                try:
                    async with async_session_factory() as db:
                        endpoint_result = await db.execute(
                            select(APIEndpoint).where(APIEndpoint.id == UUID(endpoint_id))
                        )
                        endpoint = endpoint_result.scalar_one_or_none()

                        if endpoint:
                            # 递增测试运行次数
                            endpoint.total_test_runs = (endpoint.total_test_runs or 0) + 1

                            # 更新最后运行状态
                            if execution_result.get("success"):
                                endpoint.last_run_status = "success"
                            else:
                                endpoint.last_run_status = "failed"

                            await db.commit()
                            print(f"[API Script Execution] 已更新端点 {endpoint_id} 的测试运行次数")
                except Exception as e:
                    print(f"[API Script Execution] 更新端点测试运行次数失败: {e}")

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

        if endpoint_id:
            result["endpoint_id"] = endpoint_id

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return json.dumps({
            "success": False,
            "error": f"执行脚本时发生错误: {str(e)}"
        }, ensure_ascii=False, indent=2)


async def _execute_script_internal(
    script_path: str,
    script_filename: str,
    framework: str,
    reporter: str,
    project_root: str
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

        if framework == "playwright":
            if reporter == "html":
                # HTML 报告需要指定输出目录
                if is_windows:
                    cmd = f'npx playwright test {script_filename} --reporter=html'
                else:
                    cmd = ["npx", "playwright", "test", script_filename, "--reporter=html"]
            else:
                if is_windows:
                    cmd = f'npx playwright test {script_filename} --reporter={reporter}'
                else:
                    cmd = ["npx", "playwright", "test", script_filename, f"--reporter={reporter}"]
        elif framework == "jest":
            if reporter == "html":
                if is_windows:
                    cmd = f'npm test -- {script_filename} --reporter=html'
                else:
                    cmd = ["npm", "test", "--", script_filename, "--reporter=html"]
            else:
                if is_windows:
                    cmd = f"npm test -- {script_filename} --reporter={reporter}"
                else:
                    cmd = ["npm", "test", "--", script_filename, f"--reporter={reporter}"]
        elif framework == "pytest":
            if is_windows:
                cmd = f"pytest {script_filename} --reporter={reporter}"
            else:
                cmd = ["pytest", script_filename, f"--reporter={reporter}"]
        else:
            return {
                "success": False,
                "error": f"不支持的测试框架: {framework}"
            }

        print(f"[API Script Execution] 执行命令: {cmd if is_windows else ' '.join(cmd)}")
        print(f"[API Script Execution] 工作目录: {project_root}")
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TkUxcll3PT06ZGQyYmExYzM=

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

        print(f"[API Script Execution] 执行完成，返回码: {return_code}")
        print(f"[API Script Execution] 执行时间: {duration:.2f}s")

        # 检查是否生成了 HTML 报告
        report_path = None
        if reporter == "html":
            report_dir = Path(project_root) / "playwright-report"
            index_html = report_dir / "index.html"
            if await run_sync(index_html.exists):
                report_path = str(report_dir)
                print(f"[API Script Execution] HTML 报告已生成: {report_path}")

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
    endpoint_id: str,
    project_identifier: str,
    endpoint: APIEndpoint,
    report_path: str,
    execution_result: Dict[str, Any],
    project_root: str
) -> Optional[str]:
    """
    保存测试报告到 MinIO 并创建附件记录

    Args:
        endpoint_id: 端点 ID
        project_identifier: 项目标识符
        endpoint: 端点对象
        report_path: 报告目录路径
        execution_result: 执行结果
        project_root: 项目根目录

    Returns:
        附件 ID，如果保存失败则返回 None
    """
    try:
        # 1. 将报告目录打包成 ZIP
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
        object_name = f"api-tests/{project_identifier}/endpoints/{endpoint_id}/test-report-{timestamp}.zip"
        await run_sync(
            MinIOClient.upload_bytes,
            object_name=object_name,
            data=zip_bytes,
            content_type="application/zip"
        )
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TkUxcll3PT06ZGQyYmExYzM=

        print(f"[API Report] 报告已上传到 MinIO: {object_name}")

        # 4. 创建附件记录
        async with async_session_factory() as session:
            # 生成报告描述
            duration = execution_result.get("duration", 0)
            stdout = execution_result.get("stdout", "")

            # 尝试解析测试结果
            passed_count = stdout.count("✓") + stdout.count("passed")
            failed_count = stdout.count("✘") + stdout.count("failed")

            description = f"API 测试报告 - {endpoint.display_name}\n"
            description += f"执行时间: {duration:.2f}秒\n"
            if passed_count > 0 or failed_count > 0:
                description += f"通过: {passed_count} | 失败: {failed_count}"

            # 创建附件
            attachment = Attachment(
                entity_type=AttachmentEntityType.API_TEST_REPORT,
                entity_id=UUID(endpoint_id),
                project_id=endpoint.project_id,
                file_name=f"api-test-report-{timestamp}.zip",
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

            return str(attachment.id)

    except Exception as e:
        print(f"[API Report] 保存测试报告失败: {e}")
        import traceback
        traceback.print_exc()
        return None


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
