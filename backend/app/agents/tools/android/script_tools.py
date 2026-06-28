"""
Android 测试脚本管理工具

提供从数据库查询脚本、从 MinIO 下载脚本到本地测试目录的功能
"""

import os
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


WORKSPACE_TESTS_ROOT = Path(settings.android_workspace_root) / "tests"


def ensure_workspace_tests_dir() -> Path:
    """确保测试目录存在并返回路径"""
    WORKSPACE_TESTS_ROOT.mkdir(parents=True, exist_ok=True)
    return WORKSPACE_TESTS_ROOT


@tool
async def get_android_script_info(script_id: str) -> str:
    """
    根据 Android 测试脚本 ID 查询脚本的详细信息

    Args:
        script_id: Android 测试脚本附件的 ID

    Returns:
        JSON 格式的脚本信息
    """
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(Attachment).where(Attachment.id == UUID(script_id))
            )
            attachment = result.scalar_one_or_none()
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VEdsd1FnPT06MTlkMjZkNmI=

            if not attachment:
                return json.dumps({
                    "success": False,
                    "error": f"未找到脚本 ID: {script_id}"
                }, ensure_ascii=False, indent=2)

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
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VEdsd1FnPT06MTlkMjZkNmI=


@tool
async def download_android_script(
    script_id: str,
    filename: Optional[str] = None
) -> str:
    """
    从 MinIO 下载 Android 测试脚本到本地测试目录

    Args:
        script_id: Android 测试脚本附件的 ID
        filename: 可选，指定下载后的文件名（不含扩展名）

    Returns:
        JSON 格式的下载结果
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

            script_id_str = str(attachment.id)
            original_filename = attachment.file_name
            file_size = attachment.file_size
            content_type = attachment.content_type
            object_name = attachment.object_name

        script_bytes = await run_sync(MinIOClient.download_file, object_name)
        script_content = script_bytes.decode('utf-8')

        if not script_content:
            return json.dumps({
                "success": False,
                "error": f"无法从存储服务器下载脚本: {original_filename}"
            }, ensure_ascii=False, indent=2)

        workspace_tests_dir = ensure_workspace_tests_dir()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = Path(original_filename).suffix

        if not original_filename.endswith(('.spec.ts', '.test.ts', '.ts')):
            base_name = Path(original_filename).stem
            local_filename = f"{filename or base_name}_{timestamp}.ts"
        else:
            base_name = Path(original_filename).stem
            local_filename = f"{base_name}_{timestamp}.ts"

        local_path = workspace_tests_dir / local_filename

        await run_sync(
            lambda p, c: open(p, 'w', encoding='utf-8').write(c),
            local_path,
            script_content
        )

        print(f"[Android Script Download] 脚本已下载到: {local_path}")

        workspace_root = Path(settings.android_workspace_root).resolve()
        relative_path = local_path.resolve().relative_to(workspace_root).as_posix()

        return json.dumps({
            "success": True,
            "script_id": script_id_str,
            "original_filename": original_filename,
            "local_filename": local_filename,
            "local_path": relative_path,
            "absolute_path": str(local_path.resolve()),
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
async def delete_android_script(
    local_path: str
) -> str:
    """
    删除本地 Android 测试脚本文件

    Args:
        local_path: 本地脚本文件的完整路径

    Returns:
        JSON 格式的删除结果
    """
    try:
        script_path = Path(local_path)

        if not await run_sync(script_path.exists):
            return json.dumps({
                "success": False,
                "error": f"文件不存在: {local_path}"
            }, ensure_ascii=False, indent=2)

        workspace_tests_dir = ensure_workspace_tests_dir()
        if not str(script_path.resolve()).startswith(str(workspace_tests_dir.resolve())):
            return json.dumps({
                "success": False,
                "error": "只能删除 Android 测试目录下的文件"
            }, ensure_ascii=False, indent=2)

        await run_sync(script_path.unlink)

        print(f"[Android Script Management] 脚本已删除: {local_path}")
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VEdsd1FnPT06MTlkMjZkNmI=

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
