"""
API 测试脚本管理工具

提供从数据库查询脚本、从 MinIO 下载脚本到 MCP 测试目录的功能
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select

from app.utils.sync_executor import run_sync
from app.config import settings
from app.config.database import async_session_factory
from app.models.attachment import Attachment
from app.config.minio_client import MinIOClient

# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WmtobldBPT06ZmU2NjQ0MGU=

# ============================================================================
# workspace 测试目录配置
# ============================================================================

# workspace 测试服务器根目录
WORKSPACE_TESTS_ROOT = Path(settings.api_workspace_root) / "tests"


def ensure_workspace_tests_dir() -> Path:
    """
    确保 测试目录存在并返回路径

    Returns:
        测试目录的绝对路径
    """
    WORKSPACE_TESTS_ROOT.mkdir(parents=True, exist_ok=True)
    ensure_schema_helpers()
    return WORKSPACE_TESTS_ROOT


def ensure_schema_helpers() -> None:
    """确保契约断言 helper 已就位（惰性脚手架）。

    workspace 被 .gitignore 忽略，全新 clone/清理后可能缺少 tests/_helpers/schema.ts
    与 schema.py，导致生成脚本 `import './_helpers/schema'` 失败。这里从 git 跟踪的
    _assets 复制（仅在缺失时），与 ensure_playwright_mcp_project 补齐配置的模式一致。
    """
    assets_dir = Path(__file__).parent / "_assets"
    helpers_dir = WORKSPACE_TESTS_ROOT / "_helpers"
    for name in ("schema.ts", "schema.py"):
        src = assets_dir / name
        dst = helpers_dir / name
        if not dst.exists() and src.exists():
            helpers_dir.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


@tool
async def get_api_script_info(script_id: str) -> str:
    """
    根据 API 测试脚本 ID 查询脚本的详细信息

    Args:
        script_id: API 测试脚本附件的 ID

    Returns:
        JSON 格式的脚本信息，包含：
        - success: 是否成功
        - script: 脚本详细信息
        - local_path: 如果已下载到本地，显示本地路径

    Example:
        >>> info = await get_api_script_info("550e8400-e29b-41d4-a716-446655440000")
    """
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(Attachment).where(Attachment.id == UUID(script_id))
            )
            attachment = result.scalar_one_or_none()

            if not attachment:
                return json.dumps({
                    "success": False,
                    "error": f"未找到脚本 ID: {script_id}"
                }, ensure_ascii=False, indent=2)

            # 检查是否已下载到本地
            workspace_tests_dir = ensure_workspace_tests_dir()
            local_script_path = workspace_tests_dir / attachment.file_name
            is_downloaded = await run_sync(local_script_path.exists)

            script_info = {
                "success": True,
                "script": {
                    "id": str(attachment.id),
                    "file_name": attachment.file_name,
                    "description": attachment.description,
                    "file_size": attachment.file_size,
                    "content_type": attachment.content_type,
                    "object_name": attachment.object_name,
                    "entity_id": str(attachment.entity_id),
                    "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
                    "updated_at": attachment.updated_at.isoformat() if attachment.updated_at else None,
                }
            }

            if is_downloaded:
                script_info["script"]["local_path"] = str(local_script_path)
                script_info["message"] = "脚本已下载到本地"

            return json.dumps(script_info, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"查询脚本信息时发生错误: {str(e)}"
        }, ensure_ascii=False, indent=2)

# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WmtobldBPT06ZmU2NjQ0MGU=

@tool
async def download_api_script(
    script_id: str,
    filename: Optional[str] = None
) -> str:
    """
    从 MinIO 下载 API 测试脚本到 MCP 测试目录

    此工具会：
    1. 从数据库查询脚本信息
    2. 从 MinIO 下载脚本内容
    3. 保存到 测试目录（backend/workspace/api/tests/）
    4. 使用时间戳重命名避免冲突
    5. 返回本地文件路径

    Args:
        script_id: API 测试脚本附件的 ID
        filename: 可选，指定下载后的文件名（不含扩展名，会自动添加 .spec.ts）

    Returns:
        JSON 格式的下载结果，包含：
        - success: 是否成功
        - script_id: 脚本 ID
        - original_filename: 原始文件名
        - local_filename: 本地文件名（带时间戳）
        - local_path: 本地完整路径
        - file_size: 文件大小
        - download_time: 下载时间

    Example:
        >>> result = await download_api_script(
        ...     script_id="550e8400-e29b-41d4-a716-446655440000",
        ...     filename="login_test"
        ... )
    """
    try:
        # 1. 从数据库查询脚本信息
        async with async_session_factory() as db:
            result = await db.execute(
                select(Attachment).where(Attachment.id == UUID(script_id))
            )
            attachment = result.scalar_one_or_none()

            if not attachment:
                return json.dumps({
                    "success": False,
                    "error": f"未找到脚本 ID: {script_id}"
                }, ensure_ascii=False, indent=2)

            # 保存脚本信息
            script_id_str = str(attachment.id)
            original_filename = attachment.file_name
            file_size = attachment.file_size
            content_type = attachment.content_type
            object_name = attachment.object_name

        # 2. 从 MinIO 下载脚本内容
        script_bytes = await run_sync(MinIOClient.download_file, object_name)
        script_content = script_bytes.decode('utf-8')

        if not script_content:
            return json.dumps({
                "success": False,
                "error": f"无法从存储服务器下载脚本: {original_filename}"
            }, ensure_ascii=False, indent=2)

        # 3. 确保 测试目录存在
        workspace_tests_dir = ensure_workspace_tests_dir()

        # 4. 生成本地文件名（带时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = Path(original_filename).suffix

        # 确保文件名符合 Playwright 的测试文件模式
        if not original_filename.endswith(('.spec.ts', '.test.ts')):
            base_name = Path(original_filename).stem
            local_filename = f"{filename or base_name}_{timestamp}.spec{file_extension}"
        else:
            base_name = original_filename.replace('.spec.', '_').replace('.test.', '_')
            local_filename = f"test_{timestamp}.spec{file_extension}"
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WmtobldBPT06ZmU2NjQ0MGU=

        # 5. 保存到本地
        local_path = workspace_tests_dir / local_filename

        await run_sync(
            lambda p, c: open(p, 'w', encoding='utf-8').write(c),
            local_path,
            script_content
        )

        print(f"[Script Download] 脚本已下载到: {local_path}")

        # 6. 计算相对于 workspace_root 的路径（供 FixedFilesystemBackend 使用）
        workspace_root = Path(settings.api_workspace_root).resolve()
        relative_path = local_path.resolve().relative_to(workspace_root).as_posix()

        # 7. 返回结果
        return json.dumps({
            "success": True,
            "script_id": script_id_str,
            "original_filename": original_filename,
            "local_filename": local_filename,
            "local_path": relative_path,  # 相对于 workspace_root 的路径，使用 POSIX 格式
            "absolute_path": str(local_path.resolve()),  # 绝对路径供参考
            "file_size": file_size,
            "content_type": content_type,
            "download_time": datetime.now().isoformat(),
            "message": "脚本已下载到测试目录"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return json.dumps({
            "success": False,
            "error": f"下载脚本时发生错误: {str(e)}"
        }, ensure_ascii=False, indent=2)


@tool
async def delete_api_script(
    local_path: str
) -> str:
    """
    删除本地测试脚本文件

    从 MCP 测试目录删除已下载的脚本文件

    Args:
        local_path: 本地脚本文件的完整路径

    Returns:
        JSON 格式的删除结果

    Example:
        >>> result = await delete_api_script(
        ...     local_path="backend/workspace/api/tests/login_test_20260211.spec.ts"
        ... )
    """
    try:
        script_path = Path(local_path)

        if not await run_sync(script_path.exists):
            return json.dumps({
                "success": False,
                "error": f"文件不存在: {local_path}"
            }, ensure_ascii=False, indent=2)

        # 确保路径在 测试目录内
        workspace_tests_dir = ensure_workspace_tests_dir()
        if not str(script_path.resolve()).startswith(str(workspace_tests_dir.resolve())):
            return json.dumps({
                "success": False,
                "error": "只能删除 MCP 测试目录下的文件"
            }, ensure_ascii=False, indent=2)

        # 删除文件
        await run_sync(script_path.unlink)
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WmtobldBPT06ZmU2NjQ0MGU=

        print(f"[Script Management] 脚本已删除: {local_path}")

        return json.dumps({
            "success": True,
            "local_path": local_path,
            "message": "脚本已删除"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"删除脚本时发生错误: {str(e)}"
        }, ensure_ascii=False, indent=2)
