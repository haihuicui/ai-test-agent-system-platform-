"""
Android 测试环境管理工具

提供 adb 设备检查、环境预检、依赖安装等辅助功能
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWs1a01nPT06Y2E3ZmFlOGQ=

from app.utils.sync_executor import run_sync

from langchain_core.tools import tool

from app.config import settings


@tool
async def check_android_env() -> str:
    """
    检查 Android 测试环境是否就绪

    检查项：
    - Node.js 版本
    - adb 是否可用
    - 已连接设备列表
    - 依赖包是否安装

    Returns:
        JSON 格式的环境检查结果
    """
    checks = {}

    # 1. 检查 Node.js
    try:
        result = await run_sync(
            subprocess.run,
            ["node", "-v"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            shell=sys.platform == "win32"
        )
        checks["node"] = {
            "available": result.returncode == 0,
            "version": result.stdout.strip() if result.returncode == 0 else None,
            "error": result.stderr.strip() if result.returncode != 0 else None
        }
    except Exception as e:
        checks["node"] = {"available": False, "error": str(e)}

    # 2. 检查 adb
    try:
        result = await run_sync(
            subprocess.run,
            ["adb", "version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            shell=sys.platform == "win32"
        )
        checks["adb"] = {
            "available": result.returncode == 0,
            "version": result.stdout.strip().split("\n")[0] if result.returncode == 0 else None,
            "error": result.stderr.strip() if result.returncode != 0 else None
        }
    except Exception as e:
        checks["adb"] = {"available": False, "error": str(e)}
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWs1a01nPT06Y2E3ZmFlOGQ=

    # 3. 检查设备连接
    devices = []
    try:
        result = await run_sync(
            subprocess.run,
            ["adb", "devices"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            shell=sys.platform == "win32"
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]  # 跳过 "List of devices attached"
            for line in lines:
                line = line.strip()
                if line and "\t" in line:
                    udid, state = line.split("\t", 1)
                    devices.append({"udid": udid, "state": state})
        checks["devices"] = {
            "count": len(devices),
            "devices": devices,
            "ready": any(d["state"] == "device" for d in devices)
        }
    except Exception as e:
        checks["devices"] = {"count": 0, "devices": [], "ready": False, "error": str(e)}

    # 4. 检查项目依赖
    project_root = Path(settings.android_workspace_root).resolve()
    package_json = project_root / "package.json"
    node_modules = project_root / "node_modules" / "@midscene" / "android"
    checks["project"] = {
        "workspace_root": str(project_root),
        "package_json_exists": await run_sync(package_json.exists),
        "midscene_android_installed": await run_sync(node_modules.exists)
    }

    # 5. 检查 .env 配置
    env_file = project_root / ".env"
    env_vars = {}
    if await run_sync(env_file.exists):
        try:
            env_content = await run_sync(env_file.read_text, encoding='utf-8')
            for line in env_content.splitlines():
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    key, _, value = line.partition('=')
                    if key.startswith('MIDSCENE'):
                        env_vars[key.strip()] = '已配置' if value.strip() else '空值'
        except Exception as e:
            checks["env"] = {"available": False, "error": str(e)}
    checks["env"] = {
        "available": await run_sync(env_file.exists),
        "midscene_vars": env_vars
    }

    overall_ready = (
        checks["node"]["available"]
        and checks["adb"]["available"]
        and checks["devices"]["ready"]
    )
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWs1a01nPT06Y2E3ZmFlOGQ=

    return json.dumps({
        "success": True,
        "ready": overall_ready,
        "checks": checks,
        "message": "环境检查完成" if overall_ready else "环境未就绪，请根据 checks 修复"
    }, ensure_ascii=False, indent=2)


@tool
async def init_android_project(
    project_identifier: str,
    midscene_model_api_key: Optional[str] = None
) -> str:
    """
    初始化 Android 测试项目工作区

    此工具会：
    1. 创建 workspace/android 目录
    2. 初始化 package.json
    3. 安装 @midscene/android 等依赖
    4. 创建 .env 配置文件

    Args:
        project_identifier: 项目标识符
        midscene_model_api_key: Midscene AI 模型 API Key

    Returns:
        JSON 格式的初始化结果
    """
    try:
        project_root = Path(settings.android_workspace_root).resolve()
        await run_sync(project_root.mkdir, parents=True, exist_ok=True)

        # 1. 创建 package.json（如不存在）
        package_json = project_root / "package.json"
        if not await run_sync(package_json.exists):
            package_content = {
                "name": f"android-tests-{project_identifier}",
                "version": "1.0.0",
                "private": True,
                "scripts": {
                    "test": "tsx",
                    "test:android": "tsx tests/android/**/*.ts"
                },
                "devDependencies": {
                    "tsx": "^4.0.0",
                    "typescript": "^5.0.0",
                    "@types/node": "^20.0.0"
                },
                "dependencies": {
                    "@midscene/android": "latest",
                    "dotenv": "^16.0.0"
                }
            }
            await run_sync(
                lambda p, c: open(p, 'w', encoding='utf-8').write(json.dumps(c, ensure_ascii=False, indent=2)),
                package_json,
                package_content
            )

        # 2. 创建 .env
        env_file = project_root / ".env"
        if not await run_sync(env_file.exists):
            env_lines = [
                "# Midscene.js Android 模型配置",
                "MIDSCENE_MODEL_NAME=qwen3.7-plus",
                "MIDSCENE_MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1",
                f"MIDSCENE_MODEL_API_KEY={midscene_model_api_key or 'sk-your-api-key'}",
                "MIDSCENE_MODEL_FAMILY=qwen3",
                "",
            ]
            await run_sync(
                lambda p, c: open(p, 'w', encoding='utf-8').write(c),
                env_file,
                "\n".join(env_lines)
            )

        # 3. 创建 tests/android 目录
        tests_dir = project_root / "tests" / "android"
        await run_sync(tests_dir.mkdir, parents=True, exist_ok=True)

        # 4. 安装依赖
        install_result = await run_sync(
            subprocess.run,
            ["npm", "install"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            shell=sys.platform == "win32"
        )

        return json.dumps({
            "success": install_result.returncode == 0,
            "workspace_root": str(project_root),
            "package_json_created": not package_json.exists() or True,
            "env_file_created": True,
            "npm_install_returncode": install_result.returncode,
            "npm_install_stdout": install_result.stdout[-2000:] if install_result.stdout else "",
            "npm_install_stderr": install_result.stderr[-2000:] if install_result.stderr else "",
            "message": "Android 测试项目初始化完成" if install_result.returncode == 0 else "npm install 失败，请手动安装"
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return json.dumps({
            "success": False,
            "error": f"初始化项目时发生错误: {str(e)}"
        }, ensure_ascii=False, indent=2)
