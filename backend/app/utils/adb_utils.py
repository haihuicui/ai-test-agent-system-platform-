"""
ADB 工具封装

提供异步 ADB 命令执行和设备信息获取功能
"""

import asyncio
import logging
import os
import re
import shutil
import subprocess
import sys
from typing import Optional
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZW5KRFpRPT06NGJlNmNjNTQ=

from app.config import settings

logger = logging.getLogger(__name__)

is_windows = sys.platform == "win32"


def _find_adb() -> Optional[str]:
    """查找 adb 可执行文件路径，优先使用配置，再从 PATH 查找，最后尝试常见安装路径"""
    # 1. 优先使用配置中的 adb_path
    if settings.adb_path and os.path.isfile(settings.adb_path):
        logger.debug("使用配置的 adb 路径: %s", settings.adb_path)
        return settings.adb_path

    # 2. 从 PATH 查找
    adb_path = shutil.which("adb")
    if adb_path:
        return adb_path

    # 3. 尝试常见的 Android SDK 安装路径（Windows）
    common_paths = [
        r"C:\Users\{user}\AppData\Local\Android\Sdk\platform-tools\adb.exe",
        r"C:\Program Files\Android\Sdk\platform-tools\adb.exe",
        r"C:\Program Files (x86)\Android\Sdk\platform-tools\adb.exe",
        r"C:\Android\Sdk\platform-tools\adb.exe",
        r"C:\adb\platform-tools\adb.exe",
    ]

    user = os.getlogin() if hasattr(os, "getlogin") else os.environ.get("USERNAME", "")
    for path_template in common_paths:
        path = path_template.format(user=user)
        if os.path.isfile(path):
            logger.info("在常见路径找到 adb: %s", path)
            return path

    return None


def _run_adb_sync(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    """同步执行 adb 命令（内部使用，通过 asyncio.to_thread 避免阻塞）"""
    adb_path = _find_adb()
    if not adb_path:
        raise FileNotFoundError("adb 命令未找到，请确保 Android SDK Platform Tools 已安装并在 PATH 中")

    cmd = [adb_path, *args]
    print(f"[ADB] 执行命令: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=is_windows,
    )
    print(f"[ADB] 返回码: {result.returncode}")
    print(f"[ADB] stdout: {repr(result.stdout)}")
    print(f"[ADB] stderr: {repr(result.stderr)}")
    return result


async def run_adb(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    """异步执行 adb 命令"""
    return await asyncio.to_thread(_run_adb_sync, args, timeout)


def _map_device_state(state: str) -> str:
    """将 adb 设备状态映射为前端状态"""
    mapping = {
        "device": "connected",
        "offline": "offline",
        "unauthorized": "disconnected",
        "bootloader": "offline",
    }
    return mapping.get(state, "offline")

# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZW5KRFpRPT06NGJlNmNjNTQ=

async def get_connected_devices() -> list[dict]:
    """
    获取已连接的 Android 设备列表

    Returns:
        设备列表，每个设备包含 udid 和 status
    """
    adb_path = _find_adb()
    if not adb_path:
        logger.warning("adb 未找到，请检查 Android SDK Platform Tools 是否已安装并在 PATH 中")
        raise FileNotFoundError("adb 命令未找到")

    print(f"[ADB] 使用 adb 路径: {adb_path}")
    result = await run_adb(["devices", "-l"], timeout=10)
    print(f"[ADB] 解析到的行数: {len(result.stdout.strip().split(chr(10)))}")
    if result.returncode != 0:
        raise RuntimeError(f"adb devices 执行失败: {result.stderr}")

    devices = []
    lines = result.stdout.strip().split("\n")
    for line in lines[1:]:  # 跳过 "List of devices attached"
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue

        udid = parts[0]
        rest = parts[1]

        # 状态是第二个字段（用制表符或空格分隔）
        state_match = re.match(r"(\S+)", rest)
        if not state_match:
            continue
        state = state_match.group(1)

        devices.append({
            "udid": udid,
            "status": _map_device_state(state),
        })

    print(f"[ADB] 解析到 {len(devices)} 台设备")
    return devices

# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZW5KRFpRPT06NGJlNmNjNTQ=

async def get_device_info(udid: str) -> dict:
    """
    获取指定设备的详细信息

    Args:
        udid: 设备唯一标识

    Returns:
        设备信息字典，包含 model, version, name, screen_resolution, dpi 等
    """
    info = {
        "udid": udid,
        "model": "",
        "name": "",
        "version": "",
        "screen_resolution": "",
        "dpi": None,
    }

    async def _getprop(prop: str) -> str:
        result = await run_adb(["-s", udid, "shell", "getprop", prop], timeout=10)
        return result.stdout.strip() if result.returncode == 0 else ""

    # 并行获取属性
    model, name, version, size_result, density_result = await asyncio.gather(
        _getprop("ro.product.model"),
        _getprop("ro.product.name"),
        _getprop("ro.build.version.release"),
        run_adb(["-s", udid, "shell", "wm", "size"], timeout=10),
        run_adb(["-s", udid, "shell", "wm", "density"], timeout=10),
    )

    info["model"] = model or "Unknown"
    info["name"] = name or model or "Unknown Device"
    info["version"] = version or ""

    # 解析分辨率
    if size_result.returncode == 0:
        size_match = re.search(r"(\d+x\d+)", size_result.stdout)
        if size_match:
            info["screen_resolution"] = size_match.group(1)

    # 解析 DPI
    if density_result.returncode == 0:
        density_match = re.search(r"(\d+)", density_result.stdout)
        if density_match:
            info["dpi"] = int(density_match.group(1))
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZW5KRFpRPT06NGJlNmNjNTQ=

    return info


async def scan_devices() -> list[dict]:
    """
    扫描所有已连接的 Android 设备并获取详细信息

    Returns:
        完整的设备信息列表
    """
    logger.info("开始扫描 ADB 设备...")
    devices = await get_connected_devices()
    if not devices:
        logger.info("未检测到已连接的 ADB 设备")
        return []

    # 并行获取所有设备的详细信息
    detailed_tasks = [
        get_device_info(device["udid"]) for device in devices
    ]
    detailed_infos = await asyncio.gather(*detailed_tasks, return_exceptions=True)

    results = []
    for device, info in zip(devices, detailed_infos):
        if isinstance(info, Exception):
            logger.warning("获取设备 %s 详细信息失败: %s", device["udid"], info)
            # 获取详细信息失败时，仍返回基本设备信息
            results.append({
                "udid": device["udid"],
                "name": device["udid"],
                "model": "Unknown",
                "version": "",
                "status": device["status"],
                "screen_resolution": "",
                "dpi": None,
            })
        else:
            info["status"] = device["status"]
            results.append(info)

    logger.info("设备扫描完成，返回 %d 台设备", len(results))
    return results
