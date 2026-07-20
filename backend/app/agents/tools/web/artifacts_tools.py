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
import re
from uuid import UUID, uuid4
from typing import Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path

from langchain_core.tools import tool
from sqlalchemy import select, update
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


def _escape_html(text: str) -> str:
    """转义 HTML 特殊字符，防止用户内容破坏页面结构。"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _build_execution_detail_html(
    execution_info: Optional[dict],
    screenshot_urls: list[dict],
    video_urls: list[dict],
) -> str:
    """生成执行详情 HTML 片段，内嵌到报告 </body> 前。

    包含：执行统计、用例结果表格、截图列表、视频列表。
    截图/视频使用 MinIO 预签名 URL，便于在浏览器中直接查看。
    """
    parts: list[str] = []
    parts.append("""
    <div style="margin-top:40px;padding-top:24px;border-top:2px solid #3498db;">
      <h2 style="color:#2c3e50;border-bottom:2px solid #3498db;padding-bottom:10px;">执行详情</h2>
    """)

    stats = (execution_info or {}).get("stats") or {}
    total = stats.get("total", 0)
    passed = stats.get("passed", 0)
    failed = stats.get("failed", 0)
    skipped = stats.get("skipped", 0)
    parts.append(f"""
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0;">
        <div style="background:#f8f9fa;border:1px solid #ddd;border-radius:8px;padding:12px;text-align:center;">
          <div style="font-size:24px;font-weight:bold;color:#333;">{total}</div>
          <div style="font-size:12px;color:#666;">总计</div>
        </div>
        <div style="background:#d4edda;border:1px solid #c3e6cb;border-radius:8px;padding:12px;text-align:center;">
          <div style="font-size:24px;font-weight:bold;color:#155724;">{passed}</div>
          <div style="font-size:12px;color:#155724;">通过</div>
        </div>
        <div style="background:#f8d7da;border:1px solid #f5c6cb;border-radius:8px;padding:12px;text-align:center;">
          <div style="font-size:24px;font-weight:bold;color:#721c24;">{failed}</div>
          <div style="font-size:12px;color:#721c24;">失败</div>
        </div>
        <div style="background:#fff3cd;border:1px solid #ffeeba;border-radius:8px;padding:12px;text-align:center;">
          <div style="font-size:24px;font-weight:bold;color:#856404;">{skipped}</div>
          <div style="font-size:12px;color:#856404;">跳过</div>
        </div>
      </div>
    """)

    cases = (execution_info or {}).get("cases") or []
    if cases:
        parts.append("""
          <h3 style="color:#34495e;margin-top:24px;">用例结果</h3>
          <table style="width:100%;border-collapse:collapse;margin:12px 0;font-size:14px;">
            <thead>
              <tr style="background:#f8f9fa;">
                <th style="border:1px solid #ddd;padding:10px;text-align:left;">用例</th>
                <th style="border:1px solid #ddd;padding:10px;text-align:center;width:80px;">状态</th>
                <th style="border:1px solid #ddd;padding:10px;text-align:right;width:100px;">耗时(ms)</th>
                <th style="border:1px solid #ddd;padding:10px;text-align:left;">错误信息</th>
              </tr>
            </thead>
            <tbody>
        """)
        for c in cases:
            status = c.get("status") or "unknown"
            if status in ("expected", "flaky"):
                status_label = "通过"
                status_color = "#155724"
                status_bg = "#d4edda"
            elif status == "unexpected":
                status_label = "失败"
                status_color = "#721c24"
                status_bg = "#f8d7da"
            elif status == "skipped":
                status_label = "跳过"
                status_color = "#856404"
                status_bg = "#fff3cd"
            else:
                status_label = status
                status_color = "#333"
                status_bg = "#f8f9fa"
            title = _escape_html(c.get("title") or "未命名用例")
            duration = int(c.get("duration_ms") or 0)
            error = _escape_html(c.get("error") or "")
            parts.append(f"""
              <tr>
                <td style="border:1px solid #ddd;padding:10px;">{title}</td>
                <td style="border:1px solid #ddd;padding:10px;text-align:center;">
                  <span style="background:{status_bg};color:{status_color};padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600;">{status_label}</span>
                </td>
                <td style="border:1px solid #ddd;padding:10px;text-align:right;">{duration}</td>
                <td style="border:1px solid #ddd;padding:10px;color:#721c24;">{error}</td>
              </tr>
            """)
        parts.append("""
            </tbody>
          </table>
        """)

    if screenshot_urls:
        parts.append("""
          <h3 style="color:#34495e;margin-top:24px;">截图</h3>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;margin:12px 0;">
        """)
        for s in screenshot_urls:
            url = _escape_html(s["url"])
            name = _escape_html(s.get("name") or "截图")
            parts.append(f"""
              <div style="border:1px solid #ddd;border-radius:8px;overflow:hidden;background:#fff;">
                <img src="{url}" style="width:100%;height:auto;display:block;" />
                <div style="padding:8px;font-size:12px;color:#666;word-break:break-all;">{name}</div>
              </div>
            """)
        parts.append("</div>")

    if video_urls:
        parts.append("""
          <h3 style="color:#34495e;margin-top:24px;">视频</h3>
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(400px,1fr));gap:16px;margin:12px 0;">
        """)
        for v in video_urls:
            url = _escape_html(v["url"])
            name = _escape_html(v.get("name") or "视频")
            parts.append(f"""
              <div style="border:1px solid #ddd;border-radius:8px;overflow:hidden;background:#fff;">
                <video controls src="{url}" style="width:100%;height:auto;display:block;"></video>
                <div style="padding:8px;font-size:12px;color:#666;word-break:break-all;">{name}</div>
              </div>
            """)
        parts.append("</div>")

    parts.append("</div>")
    return "".join(parts)


def _md_inline(text: str) -> str:
    """将 Markdown 行内标记转换为 HTML。"""
    # 加粗 **text** 或 __text__
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.*?)__", r"<strong>\1</strong>", text)
    # 斜体 *text*（避免匹配加粗后残留的单个星号）
    text = re.sub(r"(?<!\*)\*(?!\*)([^*]+)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    # 行内代码 `code`
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def _md_table(lines: list[str]) -> str:
    """将 Markdown 表格行列表转换为 HTML 表格。"""
    if not lines:
        return ""
    cells_list: list[list[str]] = []
    for line in lines:
        cells = [c.strip() for c in line.split("|")]
        # 去掉 Markdown 表格常见的首尾空单元格
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        cells_list.append(cells)

    if len(cells_list) < 2:
        # 不足两行（表头+分隔符），回退为段落
        return "".join(f"<p>{_md_inline(line)}</p>" for line in lines)

    header = cells_list[0]
    body_rows = cells_list[2:]  # 跳过分隔符行

    thead = "".join(f"<th>{_md_inline(c)}</th>" for c in header)
    tbody = ""
    for row in body_rows:
        # 补齐列数
        row = row + [""] * (len(header) - len(row))
        tbody += "<tr>" + "".join(
            f"<td>{_md_inline(c)}</td>" for c in row[: len(header)]
        ) + "</tr>"

    return f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>"


def _render_report_content(content: str) -> str:
    """把 Markdown 格式的报告内容渲染成 HTML。

    如果内容看起来已经是 HTML，则原样返回。这样 Agent 仍可自行提供精美 HTML，
    同时 Markdown 摘要也能在浏览器中直观展示。
    """
    if not content:
        return content

    stripped = content.strip().lower()
    html_prefixes = ("<!doctype", "<html", "<body", "<div", "<h", "<p", "<table", "<ul", "<ol", "<pre")
    if stripped.startswith(html_prefixes):
        return content

    html_parts: list[str] = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped_line = line.strip()

        # 标题
        if stripped_line.startswith("### "):
            html_parts.append(f"<h3>{_md_inline(stripped_line[4:])}</h3>")
        elif stripped_line.startswith("## "):
            html_parts.append(f"<h2>{_md_inline(stripped_line[3:])}</h2>")
        elif stripped_line.startswith("# "):
            html_parts.append(f"<h1>{_md_inline(stripped_line[2:])}</h1>")
        # 分隔线
        elif stripped_line == "---":
            html_parts.append("<hr>")
        # 表格
        elif "|" in stripped_line:
            table_lines: list[str] = []
            while i < len(lines) and "|" in lines[i].strip():
                table_lines.append(lines[i].strip())
                i += 1
            html_parts.append(_md_table(table_lines))
            continue
        # 无序列表
        elif stripped_line.startswith(("- ", "* ")):
            html_parts.append("<ul>")
            while i < len(lines) and lines[i].strip().startswith(("- ", "* ")):
                item = lines[i].strip()[2:]
                html_parts.append(f"<li>{_md_inline(item)}</li>")
                i += 1
            html_parts.append("</ul>")
            continue
        # 空行
        elif not stripped_line:
            html_parts.append("<br>")
        # 普通段落
        else:
            html_parts.append(f"<p>{_md_inline(stripped_line)}</p>")

        i += 1

    body = "\n".join(html_parts)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>测试执行摘要</title>
<style>
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  line-height: 1.6;
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
  color: #333;
  background: #fff;
}}
h1 {{
  color: #2c3e50;
  border-bottom: 2px solid #3498db;
  padding-bottom: 10px;
}}
h2 {{
  color: #34495e;
  border-bottom: 1px solid #bdc3c7;
  padding-bottom: 6px;
  margin-top: 32px;
}}
h3 {{ color: #34495e; }}
table {{
  border-collapse: collapse;
  width: 100%;
  margin: 16px 0;
  font-size: 14px;
}}
th, td {{
  border: 1px solid #ddd;
  padding: 10px 12px;
  text-align: left;
  vertical-align: top;
}}
th {{
  background-color: #f8f9fa;
  font-weight: 600;
}}
tr:nth-child(even) {{ background-color: #f8f9fa; }}
ul {{
  padding-left: 20px;
}}
li {{ margin: 6px 0; }}
strong {{ color: #2c3e50; }}
hr {{
  border: none;
  border-top: 1px solid #eee;
  margin: 24px 0;
}}
code {{
  background: #f4f4f4;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
}}
</style>
</head>
<body>
{body}
</body>
</html>"""


@tool
async def save_web_test_report(
    test_run_id: str,
    report_path: Optional[str] = None,
    report_content: Optional[str] = None,
    screenshots: Optional[list[str]] = None,
    videos: Optional[list[str]] = None,
    execution_info: Optional[dict] = None,
    project_identifier: str = ""
) -> dict:
    """
    保存 Web 测试执行报告到 MinIO

    Args:
        test_run_id: 测试运行 ID
        report_path: 报告文件路径（可选）
        report_content: 报告内容（HTML/Markdown），可选
        screenshots: 截图文件路径列表，可选
        videos: 视频文件路径列表，可选
        execution_info: 执行结构化信息（stats/cases 等），可选
        project_identifier: 项目标识符

    Returns:
        dict: 包含 attachment_id、file_path、screenshot_urls、video_urls 的字典
    """
    # 验证 test_run_id 是否为有效的 UUID
    try:
        run_uuid = UUID(test_run_id)
    except (ValueError, AttributeError):
        return {"error": f"Invalid test_run_id format: {test_run_id}. Must be a valid UUID."}

    async with async_session_factory() as session:
        # 仅选择本工具需要的列，避免加载 stdout/stderr 等可能因迁移未应用而缺失的列。
        # 这种 "column-select" 方式让工具对 schema 小幅落后具有容忍度，同时仍能通过
        # Core UPDATE 精确更新 report_path / screenshots_path。
        run_stmt = select(
            WebTestRun.id,
            WebTestRun.project_id,
            WebTestRun.web_test_id,
            WebTestRun.identifier,
            WebTestRun.status,
        ).where(WebTestRun.id == run_uuid)
        run_result = await session.execute(run_stmt)
        test_run = run_result.one_or_none()

        if test_run is None:
            return {"error": f"Test run {test_run_id} not found"}

        # 解包需要的字段，后续 Core UPDATE 不再依赖 ORM 对象状态
        run_project_id = test_run.project_id
        run_web_test_id = test_run.web_test_id
        run_identifier = test_run.identifier

        # 通过 WebTest 找到关联的子功能，让报告附件挂在 sub_function 下，
        # 与前文 execute_web_script 自动保存的 HTML 报告归属一致，确保
        # get_web_sub_function_artifacts(sub_function_id) 能展示该报告。
        sub_function_id = None
        sub_function_name = None
        if run_web_test_id:
            web_test_result = await session.execute(
                select(WebTest).where(WebTest.id == run_web_test_id)
            )
            web_test = web_test_result.scalar_one_or_none()
            if web_test:
                sub_function_id = web_test.sub_function_id
                sub_function_name = web_test.name

        # 附件归属：优先挂到 sub_function（前端成果物面板可见），
        # fallback 到 test_run_id（兼容无 sub_function 的场景）
        artifact_entity_id = sub_function_id or run_uuid

        report_object_name = None
        screenshot_dir = None
        video_dir = None
        attachment_id = None
        screenshot_urls: list[dict] = []
        video_urls: list[dict] = []

        # 统一计算媒体文件存放目录
        if screenshots or videos:
            if sub_function_id:
                media_dir = f"web-tests/{project_identifier}/sub-functions/{sub_function_id}"
            else:
                media_dir = f"web-tests/{project_identifier}/runs/{test_run_id}"

        # 先上传截图/视频到 MinIO 并收集预签名 URL
        if screenshots:
            screenshot_dir = f"{media_dir}/screenshots"
            for idx, screenshot_path in enumerate(screenshots):
                try:
                    screenshot_file = _resolve_workspace_path(screenshot_path)
                    if not await run_sync(screenshot_file.exists):
                        continue

                    screenshot_bytes = await run_sync(screenshot_file.read_bytes)
                    screenshot_name = f"screenshot-{idx + 1}{screenshot_file.suffix}"
                    screenshot_object_name = f"{screenshot_dir}/{screenshot_name}"
                    screenshot_content_type = (
                        "image/jpeg"
                        if screenshot_file.suffix.lower() in (".jpg", ".jpeg")
                        else "image/png"
                    )

                    await run_sync(
                        MinIOClient.upload_bytes,
                        object_name=screenshot_object_name,
                        data=screenshot_bytes,
                        content_type=screenshot_content_type
                    )
                    screenshot_urls.append({
                        "name": screenshot_name,
                        "object_name": screenshot_object_name,
                        "url": await run_sync(
                            MinIOClient.get_presigned_url,
                            screenshot_object_name,
                            expires=timedelta(hours=24)
                        ),
                    })
                except Exception as e:
                    print(f"Warning: Failed to save screenshot {screenshot_path}: {e}")

        if videos:
            video_dir = f"{media_dir}/videos"
            for idx, video_path in enumerate(videos):
                try:
                    video_file = _resolve_workspace_path(video_path)
                    if not await run_sync(video_file.exists):
                        continue

                    video_bytes = await run_sync(video_file.read_bytes)
                    video_name = f"video-{idx + 1}{video_file.suffix}"
                    video_object_name = f"{video_dir}/{video_name}"
                    video_content_type = {
                        ".webm": "video/webm",
                        ".mp4": "video/mp4",
                        ".mov": "video/quicktime",
                    }.get(video_file.suffix.lower(), "video/webm")

                    await run_sync(
                        MinIOClient.upload_bytes,
                        object_name=video_object_name,
                        data=video_bytes,
                        content_type=video_content_type
                    )
                    video_urls.append({
                        "name": video_name,
                        "object_name": video_object_name,
                        "url": await run_sync(
                            MinIOClient.get_presigned_url,
                            video_object_name,
                            expires=timedelta(hours=24)
                        ),
                    })
                except Exception as e:
                    print(f"Warning: Failed to save video {video_path}: {e}")

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

            base_html = _render_report_content(report_content)

            # 若提供了截图/视频/执行信息，在报告末尾追加执行详情
            if screenshot_urls or video_urls or execution_info:
                detail_html = _build_execution_detail_html(
                    execution_info,
                    screenshot_urls,
                    video_urls,
                )
                base_html = base_html.replace("</body>", f"{detail_html}</body>")

            report_bytes = base_html.encode('utf-8')
            # 报告对象路径：优先按 sub_function 组织，与 execute_web_script 产出同构
            if sub_function_id:
                report_object_name = f"web-tests/{project_identifier}/sub-functions/{sub_function_id}/test-report-{run_identifier}.html"
            else:
                report_object_name = f"web-tests/{project_identifier}/runs/{test_run_id}/report.html"

            await run_sync(
                MinIOClient.upload_bytes,
                object_name=report_object_name,
                data=report_bytes,
                content_type="text/html"
            )

            # 创建报告附件记录
            description = f"Web 测试运行 {run_identifier} 的执行摘要报告"
            if sub_function_name:
                description = f"{sub_function_name} - {description}"
            if screenshot_urls or video_urls:
                description += f"（含 {len(screenshot_urls)} 张截图、{len(video_urls)} 个视频）"
            attachment = Attachment(
                entity_type=AttachmentEntityType.WEB_TEST_REPORT,
                entity_id=artifact_entity_id,
                project_id=run_project_id,
                file_name=f"test-report-{run_identifier}.html",
                file_size=len(report_bytes),
                content_type="text/html",
                object_name=report_object_name,
                description=description,
                created_by="web-agent"
            )
            session.add(attachment)
            await session.flush()
            attachment_id = str(attachment.id)

        # 更新 test run 记录：仅更新本工具改动的列
        update_values = {"updated_at": datetime.now(timezone.utc)}
        if report_object_name:
            update_values["report_path"] = report_object_name
        if screenshot_dir:
            update_values["screenshots_path"] = screenshot_dir

        await session.execute(
            update(WebTestRun)
            .where(WebTestRun.id == run_uuid)
            .values(**update_values)
        )
        await session.commit()

        return {
            "success": True,
            "attachment_id": attachment_id,
            "report_path": report_object_name,
            "screenshots_path": screenshot_dir,
            "videos_path": video_dir,
            "screenshot_urls": screenshot_urls,
            "video_urls": video_urls,
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
