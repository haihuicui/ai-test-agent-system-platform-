"""
Android 测试成果物管理工具

用于保存和查询 Android 测试相关的测试成果物：
- 测试计划 (test_plan)
- 测试用例 (test_case)
- 测试脚本 (test_script)
"""

import json
import os
from uuid import UUID, uuid4
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.tools import tool
from sqlalchemy import select

from app.utils.sync_executor import run_sync
from app.models.project import Project
from app.models.attachment import Attachment, AttachmentEntityType
from app.models.android_test import AndroidTest
from app.repositories.android_test_repo import AndroidTestRepository
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
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTB3NU5RPT06Y2M3Nzc2ODQ=

    workspace_root = Path(settings.android_workspace_root).resolve()

    if os.name == 'nt':
        if file_path.startswith('/') or file_path.startswith('\\'):
            file_path = file_path.lstrip('/\\')
            path = Path(file_path)

    if path.is_absolute():
        return path

    if path.exists():
        return path.resolve()

    workspace_path = workspace_root / path
    if workspace_path.exists():
        return workspace_path

    mcp_output_root = os.environ.get('ANDROID_WORKSPACE_ROOT')
    if mcp_output_root:
        mcp_path = Path(mcp_output_root) / path
        if mcp_path.exists():
            return mcp_path

    return workspace_root / path


def _get_project_id(session, project_identifier: str) -> Optional[UUID]:
    """根据项目标识符查询项目 ID"""
    if not project_identifier:
        return None
    stmt = select(Project).where(Project.identifier == project_identifier)
    result = session.execute(stmt)
    project = result.scalar_one_or_none()
    return project.id if project else None


@tool
async def save_android_test_plan(
    project_identifier: str,
    plan_path: Optional[str] = None,
    test_plan: Optional[dict] = None,
    plan_content: Optional[str] = None,
    plan_format: str = "markdown"
) -> dict:
    """
    保存 Android 测试计划到 MinIO

    支持三种方式提供测试计划内容：
    1. 通过 plan_path 指定测试计划文件路径
    2. 通过 test_plan 直接提供测试计划字典（JSON 格式）
    3. 通过 plan_content 直接提供测试计划内容（Markdown/字符串）

    Args:
        project_identifier: 项目标识符
        plan_path: 测试计划文件路径，如 "./android-test-plan.md"
        test_plan: 测试计划内容（字典格式）
        plan_content: 测试计划内容（Markdown/字符串格式）
        plan_format: 计划格式（markdown, json），默认为 markdown

    Returns:
        dict: 包含 attachment_id 和 file_path 的字典
    """
    plan_bytes = None
    content_type = None
    file_extension = None

    if plan_path:
        try:
            plan_file = _resolve_workspace_path(plan_path)
            if not await run_sync(plan_file.exists):
                return {
                    "error": f"Test plan file not found: {plan_path}",
                    "hint": f"Resolved path: {plan_file}",
                }
            plan_content = await run_sync(plan_file.read_text, encoding='utf-8')
            plan_bytes = plan_content.encode('utf-8')

            if plan_file.suffix in ['.md', '.markdown']:
                plan_format = "markdown"
                content_type = "text/markdown"
                file_extension = "md"
            elif plan_file.suffix == '.json':
                plan_format = "json"
                content_type = "application/json"
                file_extension = "json"
            else:
                content_type = "text/markdown"
                file_extension = "md"
        except Exception as e:
            return {"error": f"Failed to read test plan file: {str(e)}"}
    elif test_plan:
        plan_json = json.dumps(test_plan, ensure_ascii=False, indent=2)
        plan_bytes = plan_json.encode('utf-8')
        content_type = "application/json"
        file_extension = "json"
        plan_format = "json"
    elif plan_content:
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
        project_stmt = select(Project).where(Project.identifier == project_identifier)
        project_result = await session.execute(project_stmt)
        project = project_result.scalar_one_or_none()

        if not project:
            return {"error": f"Project {project_identifier} not found"}

        object_name = f"android-tests/{project_identifier}/plans/test-plan-{uuid4()}.{file_extension}"

        await run_sync(
            MinIOClient.upload_bytes,
            object_name=object_name,
            data=plan_bytes,
            content_type=content_type
        )

        existing_stmt = select(Attachment).where(Attachment.object_name == object_name)
        existing_result = await session.execute(existing_stmt)
        existing_attachment = existing_result.scalar_one_or_none()

        file_name = f"android-test-plan.{file_extension}"
        format_desc = "Markdown" if plan_format == "markdown" else "JSON"
        description = f"Android 测试计划 ({format_desc})"

        if existing_attachment:
            existing_attachment.file_size = len(plan_bytes)
            existing_attachment.content_type = content_type
            existing_attachment.file_name = file_name
            existing_attachment.description = description
            existing_attachment.updated_at = datetime.now()
            attachment = existing_attachment
        else:
            attachment = Attachment(
                entity_type=AttachmentEntityType.ANDROID_TEST_PLAN,
                entity_id=project.id,
                project_id=project.id,
                file_name=file_name,
                file_size=len(plan_bytes),
                content_type=content_type,
                object_name=object_name,
                description=description,
                created_by="android-agent"
            )
            session.add(attachment)
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTB3NU5RPT06Y2M3Nzc2ODQ=

        await session.commit()
        await session.refresh(attachment)

        return {
            "success": True,
            "attachment_id": str(attachment.id),
            "file_path": object_name,
            "format": plan_format,
            "message": f"Android 测试计划已保存 ({format_desc})"
        }


@tool
async def save_android_test_cases(
    project_identifier: str,
    test_cases: list[dict]
) -> dict:
    """
    保存 Android 测试用例到 MinIO

    Args:
        project_identifier: 项目标识符
        test_cases: 测试用例列表，每个用例包含：
            - id: 用例 ID
            - name: 用例名称
            - description: 用例描述
            - preconditions: 前置条件
            - steps: 测试步骤
            - expected_result: 预期结果
            - priority: 优先级

    Returns:
        dict: 包含 attachment_id 和 file_path 的字典
    """
    async with async_session_factory() as session:
        project_stmt = select(Project).where(Project.identifier == project_identifier)
        project_result = await session.execute(project_stmt)
        project = project_result.scalar_one_or_none()

        if not project:
            return {"error": f"Project {project_identifier} not found"}

        cases_json = json.dumps(test_cases, ensure_ascii=False, indent=2)
        cases_bytes = cases_json.encode('utf-8')

        object_name = f"android-tests/{project_identifier}/cases/test-cases-{uuid4()}.json"

        await run_sync(
            MinIOClient.upload_bytes,
            object_name=object_name,
            data=cases_bytes,
            content_type="application/json"
        )

        existing_stmt = select(Attachment).where(Attachment.object_name == object_name)
        existing_result = await session.execute(existing_stmt)
        existing_attachment = existing_result.scalar_one_or_none()

        if existing_attachment:
            existing_attachment.file_size = len(cases_bytes)
            existing_attachment.description = f"Android 测试用例（共 {len(test_cases)} 个）"
            existing_attachment.updated_at = datetime.now()
            attachment = existing_attachment
        else:
            attachment = Attachment(
                entity_type=AttachmentEntityType.ANDROID_TEST_CASE,
                entity_id=project.id,
                project_id=project.id,
                file_name=f"android-test-cases.json",
                file_size=len(cases_bytes),
                content_type="application/json",
                object_name=object_name,
                description=f"Android 测试用例（共 {len(test_cases)} 个）",
                created_by="android-agent"
            )
            session.add(attachment)
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTB3NU5RPT06Y2M3Nzc2ODQ=

        await session.commit()
        await session.refresh(attachment)

        return {
            "success": True,
            "attachment_id": str(attachment.id),
            "file_path": object_name,
            "test_cases_count": len(test_cases),
            "message": f"已保存 {len(test_cases)} 个 Android 测试用例"
        }


@tool
async def save_android_test_script(
    project_identifier: str,
    script_path: Optional[str] = None,
    script_content: Optional[str] = None,
    script_language: str = "typescript",
    script_format: str = "midscene",
    android_test_id: Optional[str] = None,
    name: Optional[str] = None,
    app_package: Optional[str] = None,
) -> dict:
    """
    保存 Android 测试脚本到 MinIO，并创建/更新 AndroidTest 记录

    支持两种方式提供脚本内容：
    1. 通过 script_path 指定脚本文件路径
    2. 通过 script_content 直接提供脚本内容

    Args:
        project_identifier: 项目标识符
        script_path: 脚本文件路径
        script_content: 脚本内容（代码），可选
        script_language: 脚本语言（typescript, javascript, python）
        script_format: 脚本格式（midscene, appium, espresso）
        android_test_id: 已有的 Android 测试 ID（修复场景传入）
        name: 测试名称（新建时使用）
        app_package: 被测应用包名

    Returns:
        dict: 包含 attachment_id、android_test_id 和 file_path 的字典
    """
    if script_path:
        try:
            script_file = _resolve_workspace_path(script_path)
            if not await run_sync(script_file.exists):
                return {
                    "error": f"Script file not found: {script_path}",
                    "hint": f"Resolved path: {script_file}",
                }
            script_content = await run_sync(script_file.read_text, encoding='utf-8')
        except Exception as e:
            return {"error": f"Failed to read script file: {str(e)}"}
    elif not script_content:
        return {"error": "Either script_path or script_content must be provided"}

    async with async_session_factory() as session:
        project_stmt = select(Project).where(Project.identifier == project_identifier)
        project_result = await session.execute(project_stmt)
        project = project_result.scalar_one_or_none()

        if not project:
            return {"error": f"Project {project_identifier} not found"}

        extension = {
            "typescript": "ts",
            "javascript": "js",
            "python": "py",
            "java": "java",
        }.get(script_language, "txt")

        object_name = f"android-tests/{project_identifier}/scripts/test-script-{uuid4()}.{extension}"
        script_bytes = script_content.encode('utf-8')

        await run_sync(
            MinIOClient.upload_bytes,
            object_name=object_name,
            data=script_bytes,
            content_type="text/plain"
        )

        existing_stmt = select(Attachment).where(Attachment.object_name == object_name)
        existing_result = await session.execute(existing_stmt)
        existing_attachment = existing_result.scalar_one_or_none()

        if existing_attachment:
            existing_attachment.file_size = len(script_bytes)
            existing_attachment.description = f"Android 测试脚本 ({script_format} - {script_language})"
            existing_attachment.updated_at = datetime.now()
            attachment = existing_attachment
        else:
            attachment = Attachment(
                entity_type=AttachmentEntityType.ANDROID_TEST_SCRIPT,
                entity_id=project.id,
                project_id=project.id,
                file_name=f"android-test-script.{extension}",
                file_size=len(script_bytes),
                content_type="text/plain",
                object_name=object_name,
                description=f"Android 测试脚本 ({script_format} - {script_language})",
                created_by="android-agent"
            )
            session.add(attachment)

        # 创建或更新 AndroidTest 记录
        android_test_repo = AndroidTestRepository(session)
        android_test = None
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TTB3NU5RPT06Y2M3Nzc2ODQ=

        if android_test_id:
            try:
                test_uuid = UUID(android_test_id)
                stmt = select(AndroidTest).where(AndroidTest.id == test_uuid)
                result = await session.execute(stmt)
                android_test = result.scalar_one_or_none()
            except ValueError:
                pass

        if android_test:
            android_test.script_path = object_name
            android_test.script_format = script_format
            android_test.script_language = script_language
            android_test.updated_at = datetime.now(timezone.utc)
            if app_package:
                android_test.app_package = app_package
        else:
            identifier = await android_test_repo.get_next_identifier(project.id)
            android_test = AndroidTest(
                project_id=project.id,
                identifier=identifier,
                name=name or f"Android Test {identifier}",
                script_path=object_name,
                script_format=script_format,
                script_language=script_language,
                app_package=app_package,
                generated_by_agent="android_agent",
            )
            session.add(android_test)

        await session.commit()
        await session.refresh(attachment)
        await session.refresh(android_test)

        return {
            "success": True,
            "attachment_id": str(attachment.id),
            "android_test_id": str(android_test.id),
            "file_path": object_name,
            "language": script_language,
            "format": script_format,
            "message": "Android 测试脚本已保存"
        }


@tool
async def get_android_artifacts(
    project_identifier: str,
    artifact_type: Optional[str] = None
) -> dict:
    """
    获取 Android 项目的测试成果物列表

    Args:
        project_identifier: 项目标识符
        artifact_type: 成果物类型过滤（可选）:
            - ANDROID_TEST_PLAN: 测试计划
            - ANDROID_TEST_CASE: 测试用例
            - ANDROID_TEST_SCRIPT: 测试脚本
            - ANDROID_TEST_REPORT: 测试报告

    Returns:
        dict: 成果物列表
    """
    async with async_session_factory() as session:
        project_stmt = select(Project).where(Project.identifier == project_identifier)
        project_result = await session.execute(project_stmt)
        project = project_result.scalar_one_or_none()

        if not project:
            return {"error": f"Project {project_identifier} not found"}

        stmt = select(Attachment).where(Attachment.project_id == project.id)

        if artifact_type:
            try:
                entity_type = AttachmentEntityType[artifact_type]
                stmt = stmt.where(Attachment.entity_type == entity_type)
            except KeyError:
                return {"error": f"Invalid artifact_type: {artifact_type}"}

        # 进一步过滤对象名前缀为 android-tests
        stmt = stmt.where(Attachment.object_name.like("android-tests/%"))

        result = await session.execute(stmt)
        attachments = result.scalars().all()

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
            "project_identifier": project_identifier,
            "artifacts": artifacts,
            "total": len(artifacts)
        }


@tool
async def get_android_artifact_content(
    attachment_id: str
) -> dict:
    """
    获取 Android 测试附件内容

    Args:
        attachment_id: 附件 ID

    Returns:
        dict: 包含文件内容和元数据的字典
    """
    async with async_session_factory() as session:
        stmt = select(Attachment).where(Attachment.id == UUID(attachment_id))
        result = await session.execute(stmt)
        attachment = result.scalar_one_or_none()

        if not attachment:
            return {"error": f"Attachment {attachment_id} not found"}

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
