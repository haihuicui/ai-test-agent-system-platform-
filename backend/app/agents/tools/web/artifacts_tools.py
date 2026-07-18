"""
Web 测试成果物管理工具

用于保存和查询 Web 子功能相关的测试成果物：
- 测试计划 (test_plan)
- 测试用例 (test_case)
- 测试脚本 (test_script)
- 测试报告 (test_report)
"""

import json
import io
import os
from uuid import UUID, uuid4
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.sync_executor import run_sync
from app.models.attachment import Attachment, AttachmentEntityType
from app.models.web_function import WebSubFunction
from app.models.web_test import WebTest, WebTestRun
from app.config.minio_client import MinIOClient
from app.config.database import async_session_factory
from app.config.settings import settings


def _resolve_workspace_path(file_path: str) -> Path:
    """
    解析文件路径，支持 MCP workspace 中的相对路径

    Args:
        file_path: 文件路径（可以是绝对路径或相对路径）

    Returns:
        解析后的绝对路径
    """
    path = Path(file_path)

    # 获取 Web workspace 根目录
    workspace_root = Path(settings.web_mcp_workspace_root).resolve()

    # 在 Windows 上，以 / 开头的路径不是真正的绝对路径（没有盘符）
    # 应该被当作相对路径处理，避免解析到 C:\
    if os.name == 'nt':  # Windows
        # 将 / 开头的路径当作相对路径
        if file_path.startswith('/') or file_path.startswith('\\'):
            # 去掉开头的 / 或 \
            file_path = file_path.lstrip('/\\')
            path = Path(file_path)

    # 如果是绝对路径，直接返回
    if path.is_absolute():
        return path

    # 检查文件是否在当前工作目录存在
    if path.exists():
        return path.resolve()

    # 尝试在 workspace 目录中查找
    workspace_path = workspace_root / path
    if workspace_path.exists():
        return workspace_path

    # 尝试在 MCP 输出目录中查找（MCP 工具可能使用环境变量指定的目录）
    mcp_output_root = settings.web_mcp_root
    if mcp_output_root:
        mcp_path = Path(mcp_output_root) / path
        if mcp_path.exists():
            return mcp_path

    # 如果都找不到，返回 workspace 路径（让调用方处理错误）
    return workspace_root / path
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0hCRFZnPT06MWExMTY3YzY=


@tool
async def save_web_test_plan(
    sub_function_id: str,
    plan_path: Optional[str] = None,
    test_plan: Optional[dict] = None,
    plan_content: Optional[str] = None,
    plan_format: str = "markdown",
    project_identifier: str = ""
) -> dict:
    """
    保存 Web 子功能的测试计划到 MinIO

    支持三种方式提供测试计划内容：
    1. 通过 plan_path 指定由 web_planner 生成的测试计划文件路径
    2. 通过 test_plan 直接提供测试计划字典（JSON 格式）
    3. 通过 plan_content 直接提供测试计划内容（Markdown/字符串）

    Args:
        sub_function_id: Web 子功能 ID
        plan_path: 测试计划文件路径（由 web_planner 生成），如 "./web-test-plan.md"
        test_plan: 测试计划内容（字典格式），包含：
            - test_scenarios: 测试场景列表
            - coverage: 覆盖率分析
            - priority: 优先级评估
            - estimated_time: 预估测试时间
        plan_content: 测试计划内容（Markdown/字符串格式），可选
        plan_format: 计划格式（markdown, json），默认为 markdown
        project_identifier: 项目标识符

    Returns:
        dict: 包含 attachment_id 和 file_path 的字典
    """
    # 验证 sub_function_id 是否为有效的 UUID
    try:
        sub_function_uuid = UUID(sub_function_id)
    except (ValueError, AttributeError):
        return {"error": f"Invalid sub_function_id format: {sub_function_id}. Must be a valid UUID."}

    # 获取测试计划内容
    plan_bytes = None
    content_type = None
    file_extension = None

    if plan_path:
        # 从 web_planner 生成的文件读取
        try:
            # 使用智能路径解析
            plan_file = _resolve_workspace_path(plan_path)
            if not await run_sync(plan_file.exists):
                return {
                    "error": f"Test plan file not found: {plan_path}",
                    "hint": f"Resolved path: {plan_file}",
                    "tried_paths": [
                        f"Current: {Path(plan_path).resolve()}",
                        f"Workspace: {Path(settings.web_mcp_workspace_root).resolve() / plan_path}",
                        f"MCP: {os.environ.get('WEB_WORKSPACE_ROOT', 'Not set')}"
                    ]
                }
            plan_content = await run_sync(plan_file.read_text, encoding='utf-8')
            plan_bytes = plan_content.encode('utf-8')

            # 根据文件扩展名确定格式
            if plan_file.suffix in ['.md', '.markdown']:
                plan_format = "markdown"
                content_type = "text/markdown"
                file_extension = "md"
            elif plan_file.suffix == '.json':
                plan_format = "json"
                content_type = "application/json"
                file_extension = "json"
            else:
                # 默认使用 markdown
                content_type = "text/markdown"
                file_extension = "md"
        except Exception as e:
            return {"error": f"Failed to read test plan file: {str(e)}"}
    elif test_plan:
        # 从字典生成 JSON
        plan_json = json.dumps(test_plan, ensure_ascii=False, indent=2)
        plan_bytes = plan_json.encode('utf-8')
        content_type = "application/json"
        file_extension = "json"
        plan_format = "json"
    elif plan_content:
        # 直接使用提供的内容
        plan_bytes = plan_content.encode('utf-8')
        if plan_format == "json":
            content_type = "application/json"
            file_extension = "json"
        else:
            content_type = "text/markdown"
            file_extension = "md"
    else:
        return {"error": "Either plan_path, test_plan, or plan_content must be provided"}

    async with async_session_factory() as session:
        # 查询 sub_function
        sub_function_stmt = select(WebSubFunction).where(
            WebSubFunction.id == sub_function_uuid
        )
        sub_function_result = await session.execute(sub_function_stmt)
        sub_function = sub_function_result.scalar_one_or_none()

        if not sub_function:
            return {"error": f"Sub-function {sub_function_id} not found"}

        # 生成 MinIO 对象名称
        object_name = f"web-tests/{project_identifier}/sub-functions/{sub_function_id}/test-plan.{file_extension}"

        # 上传到 MinIO
        await run_sync(
            MinIOClient.upload_bytes,
            object_name=object_name,
            data=plan_bytes,
            content_type=content_type
        )

        # 检查是否已存在相同的附件
        existing_stmt = select(Attachment).where(
            Attachment.object_name == object_name
        )
        existing_result = await session.execute(existing_stmt)
        existing_attachment = existing_result.scalar_one_or_none()
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0hCRFZnPT06MWExMTY3YzY=

        # 生成文件名和描述
        file_name = f"test-plan-{sub_function.display_name}.{file_extension}"
        format_desc = "Markdown" if plan_format == "markdown" else "JSON"
        description = f"Web 子功能 {sub_function.display_name} 的测试计划 ({format_desc})"

        if existing_attachment:
            # 更新现有附件
            existing_attachment.file_size = len(plan_bytes)
            existing_attachment.content_type = content_type
            existing_attachment.file_name = file_name
            existing_attachment.description = description
            existing_attachment.updated_at = datetime.now()
            attachment = existing_attachment
        else:
            # 创建新附件记录
            attachment = Attachment(
                entity_type=AttachmentEntityType.WEB_TEST_PLAN,
                entity_id=sub_function_uuid,
                project_id=sub_function.project_id,
                file_name=file_name,
                file_size=len(plan_bytes),
                content_type=content_type,
                object_name=object_name,
                description=description,
                created_by="web-agent"
            )
            session.add(attachment)

        await session.commit()
        await session.refresh(attachment)

        return {
            "success": True,
            "attachment_id": str(attachment.id),
            "file_path": object_name,
            "format": plan_format,
            "file_extension": file_extension,
            "message": f"测试计划已保存 ({format_desc})"
        }


def _validate_test_cases(test_cases: list) -> Optional[str]:
    """
    宽松校验测试用例结构，只拦截会污染下游 generator 的承重字段问题。

    只校验 generator 真正消费的字段，其余字段（tags/page_elements/prerequisites 等）
    允许缺失，避免因校验过严导致 Agent 反复返工（"弹皮球"）。

    支持参数化用例：is_parameterized / data_variants / parameter_description。

    Returns:
        None 表示通过；否则返回错误描述字符串。
    """
    if not isinstance(test_cases, list) or not test_cases:
        return "test_cases 必须是非空列表"

    for i, tc in enumerate(test_cases):
        if not isinstance(tc, dict):
            return f"test_cases[{i}] 必须是对象(dict)，实际为 {type(tc).__name__}"

        name = tc.get("name")
        if not isinstance(name, str) or not name.strip():
            return f"test_cases[{i}].name 缺失或为空"

        steps = tc.get("steps")
        if not isinstance(steps, list) or not steps:
            return f"test_cases[{i}].steps 必须是非空列表"
        for j, step in enumerate(steps):
            if not isinstance(step, dict) or not step.get("action"):
                return f"test_cases[{i}].steps[{j}] 必须是含 action 字段的对象"

        vps = tc.get("verification_points")
        if not isinstance(vps, list) or not vps:
            return f"test_cases[{i}].verification_points 必须至少包含一个验证点"

        # 参数化用例校验
        is_parameterized = tc.get("is_parameterized")
        data_variants = tc.get("data_variants")
        if is_parameterized is True:
            if not isinstance(data_variants, list) or not data_variants:
                return f"test_cases[{i}] 标记为参数化用例，但 data_variants 为空或非列表"
        if data_variants is not None and not isinstance(data_variants, list):
            return f"test_cases[{i}].data_variants 必须是列表"

    return None


@tool
async def save_web_test_cases(
    sub_function_id: str,
    test_cases: list[dict],
    project_identifier: str
) -> dict:
    """
    保存 Web 子功能的测试用例到 MinIO

    Args:
        sub_function_id: Web 子功能 ID
        test_cases: 测试用例列表，每个用例包含：
            - name: 用例名称
            - description: 用例描述
            - steps: 测试步骤
            - expected_result: 预期结果
            - priority: 优先级
            - page_elements: 涉及的页面元素
            - is_parameterized: 是否为参数化用例（可选）
            - data_variants: 参数化数据变体列表（可选，对象或字符串）
            - parameter_description: 参数化维度说明（可选）
        project_identifier: 项目标识符

    Returns:
        dict: 包含 attachment_id 和 file_path 的字典
    """
    # 验证 sub_function_id 是否为有效的 UUID
    try:
        sub_function_uuid = UUID(sub_function_id)
    except (ValueError, AttributeError):
        return {"error": f"Invalid sub_function_id format: {sub_function_id}. Must be a valid UUID."}

    # 宽松结构校验：在访问 DB 之前拦截会污染下游生成的承重字段问题
    validation_error = _validate_test_cases(test_cases)
    if validation_error:
        return {"error": f"测试用例结构校验失败: {validation_error}"}

    async with async_session_factory() as session:
        # 查询 sub_function
        sub_function_stmt = select(WebSubFunction).where(
            WebSubFunction.id == sub_function_uuid
        )
        sub_function_result = await session.execute(sub_function_stmt)
        sub_function = sub_function_result.scalar_one_or_none()

        if not sub_function:
            return {"error": f"Sub-function {sub_function_id} not found"}

        # 序列化测试用例
        cases_json = json.dumps(test_cases, ensure_ascii=False, indent=2)
        cases_bytes = cases_json.encode('utf-8')

        # 生成 MinIO 对象名称
        object_name = f"web-tests/{project_identifier}/sub-functions/{sub_function_id}/test-cases.json"

        # 上传到 MinIO
        await run_sync(
            MinIOClient.upload_bytes,
            object_name=object_name,
            data=cases_bytes,
            content_type="application/json"
        )
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0hCRFZnPT06MWExMTY3YzY=

        # 检查是否已存在相同的附件
        existing_stmt = select(Attachment).where(
            Attachment.object_name == object_name
        )
        existing_result = await session.execute(existing_stmt)
        existing_attachment = existing_result.scalar_one_or_none()

        if existing_attachment:
            # 更新现有附件
            existing_attachment.file_size = len(cases_bytes)
            existing_attachment.description = f"Web 子功能 {sub_function.display_name} 的测试用例（共 {len(test_cases)} 个）"
            existing_attachment.updated_at = datetime.now()
            attachment = existing_attachment
        else:
            # 创建新附件记录
            attachment = Attachment(
                entity_type=AttachmentEntityType.WEB_TEST_CASE,
                entity_id=sub_function_uuid,
                project_id=sub_function.project_id,
                file_name=f"test-cases-{sub_function.display_name}.json",
                file_size=len(cases_bytes),
                content_type="application/json",
                object_name=object_name,
                description=f"Web 子功能 {sub_function.display_name} 的测试用例（共 {len(test_cases)} 个）",
                created_by="web-agent"
            )
            session.add(attachment)

        # 更新子功能的测试用例统计。
        # 每个子功能只有一份 test-cases.json 产物，每次保存都是整体替换，
        # 因此用例总数必须“赋值”而非“累加”，否则重新生成会导致计数翻倍
        # （父级 WebFunction.total_test_cases 为各子功能之和，也会被连带放大）。
        sub_function.total_test_cases = len(test_cases)
        sub_function.updated_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(attachment)

        return {
            "success": True,
            "attachment_id": str(attachment.id),
            "file_path": object_name,
            "test_cases_count": len(test_cases),
            "message": f"已保存 {len(test_cases)} 个测试用例"
        }


@tool
async def save_web_test_script(
    sub_function_id: str,
    script_path: Optional[str] = None,
    script_content: Optional[str] = None,
    script_language: str = "typescript",
    script_format: str = "playwright",
    project_identifier: str = ""
) -> dict:
    """
    保存 Web 子功能的测试脚本到 MinIO

    支持两种方式提供脚本内容：
    1. 通过 script_path 指定由 web_generator 生成的脚本文件路径
    2. 通过 script_content 直接提供脚本内容

    Args:
        sub_function_id: Web 子功能 ID
        script_path: 脚本文件路径（由 web_generator 生成）
        script_content: 脚本内容（代码），可选
        script_language: 脚本语言（如: typescript, javascript, python）
        script_format: 脚本格式（如: playwright, cypress, selenium）
        project_identifier: 项目标识符

    Returns:
        dict: 包含 attachment_id 和 file_path 的字典
    """
    # 验证 sub_function_id 是否为有效的 UUID
    try:
        sub_function_uuid = UUID(sub_function_id)
    except (ValueError, AttributeError):
        return {"error": f"Invalid sub_function_id format: {sub_function_id}. Must be a valid UUID."}

    # 获取脚本内容
    if script_path:
        # 从 web_generator 生成的文件读取
        try:
            # 使用智能路径解析
            script_file = _resolve_workspace_path(script_path)
            if not await run_sync(script_file.exists):
                return {
                    "error": f"Script file not found: {script_path}",
                    "hint": f"Resolved path: {script_file}",
                    "tried_paths": [
                        f"Current: {Path(script_path).resolve()}",
                        f"Workspace: {Path(settings.web_mcp_workspace_root).resolve() / script_path}",
                        f"MCP: {os.environ.get('WEB_WORKSPACE_ROOT', 'Not set')}"
                    ]
                }
            script_content = await run_sync(script_file.read_text, encoding='utf-8')
        except Exception as e:
            return {"error": f"Failed to read script file: {str(e)}"}
    elif not script_content:
        return {"error": "Either script_path or script_content must be provided"}

    async with async_session_factory() as session:
        # 查询 sub_function
        sub_function_stmt = select(WebSubFunction).where(
            WebSubFunction.id == sub_function_uuid
        )
        sub_function_result = await session.execute(sub_function_stmt)
        sub_function = sub_function_result.scalar_one_or_none()

        if not sub_function:
            return {"error": f"Sub-function {sub_function_id} not found"}

        # 确定文件扩展名
        extension = {
            "typescript": "ts",
            "javascript": "js",
            "python": "py",
            "java": "java",
        }.get(script_language, "txt")

        # 生成 MinIO 对象名称
        object_name = f"web-tests/{project_identifier}/sub-functions/{sub_function_id}/test-script.{extension}"

        # 上传到 MinIO
        script_bytes = script_content.encode('utf-8')
        await run_sync(
            MinIOClient.upload_bytes,
            object_name=object_name,
            data=script_bytes,
            content_type="text/plain"
        )

        # 检查是否已存在相同的附件
        existing_stmt = select(Attachment).where(
            Attachment.object_name == object_name
        )
        existing_result = await session.execute(existing_stmt)
        existing_attachment = existing_result.scalar_one_or_none()

        if existing_attachment:
            # 更新现有附件
            existing_attachment.file_size = len(script_bytes)
            existing_attachment.description = f"Web 子功能 {sub_function.display_name} 的测试脚本 ({script_format} - {script_language})"
            existing_attachment.updated_at = datetime.now()
            attachment = existing_attachment
        else:
            # 创建新附件记录
            attachment = Attachment(
                entity_type=AttachmentEntityType.WEB_TEST_SCRIPT,
                entity_id=sub_function_uuid,
                project_id=sub_function.project_id,
                file_name=f"test-script.{extension}",
                file_size=len(script_bytes),
                content_type="text/plain",
                object_name=object_name,
                description=f"Web 子功能 {sub_function.display_name} 的测试脚本 ({script_format} - {script_language})",
                created_by="web-agent"
            )
            session.add(attachment)

        await session.commit()
        await session.refresh(attachment)

        return {
            "success": True,
            "attachment_id": str(attachment.id),
            "file_path": object_name,
            "language": script_language,
            "format": script_format,
            "message": "测试脚本已保存"
        }

# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Y0hCRFZnPT06MWExMTY3YzY=

@tool
async def get_web_sub_function_artifacts(
    sub_function_id: str,
    artifact_type: Optional[str] = None
) -> dict:
    """
    获取 Web 子功能的测试成果物列表

    Args:
        sub_function_id: Web 子功能 ID
        artifact_type: 成果物类型过滤（可选）:
            - WEB_TEST_PLAN: 测试计划
            - WEB_TEST_CASE: 测试用例
            - WEB_TEST_SCRIPT: 测试脚本
            - WEB_TEST_REPORT: 测试报告

    Returns:
        dict: 成果物列表，包含类型、文件名、描述、创建时间等信息
    """
    # 验证 sub_function_id 是否为有效的 UUID
    try:
        sub_function_uuid = UUID(sub_function_id)
    except (ValueError, AttributeError) as e:
        return {"error": f"Invalid sub_function_id format: {sub_function_id}. Must be a valid UUID."}

    async with async_session_factory() as session:
        # 构建查询
        stmt = select(Attachment).where(
            Attachment.entity_id == sub_function_uuid
        )

        # 按类型过滤
        if artifact_type:
            try:
                entity_type = AttachmentEntityType[artifact_type]
                stmt = stmt.where(Attachment.entity_type == entity_type)
            except KeyError:
                return {"error": f"Invalid artifact_type: {artifact_type}"}

        # 执行查询
        result = await session.execute(stmt)
        attachments = result.scalars().all()

        # 格式化返回
        artifacts = []
        for attachment in attachments:
            artifacts.append({
                "id": str(attachment.id),
                "type": attachment.entity_type.value,
                "file_name": attachment.file_name,
                "description": attachment.description,
                "file_size": attachment.file_size,
                "content_type": attachment.content_type,
                "object_name": attachment.object_name,
                "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
            })

        return {
            "success": True,
            "sub_function_id": sub_function_id,
            "artifacts": artifacts,
            "total": len(artifacts)
        }


@tool
async def save_web_test_report(
    test_run_id: str,
    report_path: Optional[str] = None,
    report_content: Optional[str] = None,
    screenshots: Optional[list[str]] = None,
    project_identifier: str = ""
) -> dict:
    """
    保存 Web 测试执行报告到 MinIO

    Args:
        test_run_id: 测试运行 ID
        report_path: 报告文件路径（可选）
        report_content: 报告内容（HTML/JSON），可选
        screenshots: 截图文件路径列表，可选
        project_identifier: 项目标识符

    Returns:
        dict: 包含 attachment_id 和 file_path 的字典
    """
    # 验证 test_run_id 是否为有效的 UUID
    try:
        run_uuid = UUID(test_run_id)
    except (ValueError, AttributeError):
        return {"error": f"Invalid test_run_id format: {test_run_id}. Must be a valid UUID."}

    async with async_session_factory() as session:
        # 查询 test run
        run_stmt = select(WebTestRun).where(
            WebTestRun.id == run_uuid
        )
        run_result = await session.execute(run_stmt)
        test_run = run_result.scalar_one_or_none()

        if not test_run:
            return {"error": f"Test run {test_run_id} not found"}

        report_object_name = None
        screenshot_dir = None
        attachment_id = None

        # 保存报告
        if report_path or report_content:
            if report_path:
                try:
                    report_file = _resolve_workspace_path(report_path)
                    if not await run_sync(report_file.exists):
                        return {"error": f"Report file not found: {report_path}"}
                    report_content = await run_sync(report_file.read_text, encoding='utf-8')
                except Exception as e:
                    return {"error": f"Failed to read report file: {str(e)}"}

            report_bytes = report_content.encode('utf-8')
            report_object_name = f"web-tests/{project_identifier}/runs/{test_run_id}/report.html"

            await run_sync(
                MinIOClient.upload_bytes,
                object_name=report_object_name,
                data=report_bytes,
                content_type="text/html"
            )

            # 创建报告附件记录
            attachment = Attachment(
                entity_type=AttachmentEntityType.WEB_TEST_REPORT,
                entity_id=run_uuid,
                project_id=test_run.project_id,
                file_name=f"test-report-{test_run.identifier}.html",
                file_size=len(report_bytes),
                content_type="text/html",
                object_name=report_object_name,
                description=f"Web 测试运行 {test_run.identifier} 的报告",
                created_by="web-agent"
            )
            session.add(attachment)
            await session.flush()
            attachment_id = str(attachment.id)

        # 保存截图
        if screenshots:
            screenshot_dir = f"web-tests/{project_identifier}/runs/{test_run_id}/screenshots"
            for idx, screenshot_path in enumerate(screenshots):
                try:
                    screenshot_file = _resolve_workspace_path(screenshot_path)
                    if not await run_sync(screenshot_file.exists):
                        continue

                    screenshot_bytes = await run_sync(screenshot_file.read_bytes)
                    screenshot_name = f"screenshot-{idx + 1}{screenshot_file.suffix}"
                    screenshot_object_name = f"{screenshot_dir}/{screenshot_name}"

                    await run_sync(
                        MinIOClient.upload_bytes,
                        object_name=screenshot_object_name,
                        data=screenshot_bytes,
                        content_type="image/png"
                    )
                except Exception as e:
                    # 记录错误但继续处理其他截图
                    print(f"Warning: Failed to save screenshot {screenshot_path}: {e}")

        # 更新 test run 记录
        if report_object_name:
            test_run.report_path = report_object_name
        if screenshot_dir:
            test_run.screenshots_path = screenshot_dir
        test_run.updated_at = datetime.now(timezone.utc)

        await session.commit()

        return {
            "success": True,
            "attachment_id": attachment_id,
            "report_path": report_object_name,
            "screenshots_path": screenshot_dir,
            "message": "测试报告已保存"
        }


@tool
async def get_artifact_content(
    attachment_id: str
) -> dict:
    """
    获取附件内容

    Args:
        attachment_id: 附件 ID

    Returns:
        dict: 包含文件内容和元数据的字典
    """
    async with async_session_factory() as session:
        # 查询附件
        stmt = select(Attachment).where(
            Attachment.id == UUID(attachment_id)
        )
        result = await session.execute(stmt)
        attachment = result.scalar_one_or_none()

        if not attachment:
            return {"error": f"Attachment {attachment_id} not found"}

        # 从 MinIO 下载文件
        try:
            content_bytes = await run_sync(MinIOClient.download_file, attachment.object_name)
            content = content_bytes.decode('utf-8')

            return {
                "success": True,
                "attachment_id": str(attachment.id),
                "type": attachment.entity_type.value,
                "file_name": attachment.file_name,
                "content": content,
                "content_type": attachment.content_type,
                "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
            }
        except Exception as e:
            return {"error": f"Failed to download file: {str(e)}"}
