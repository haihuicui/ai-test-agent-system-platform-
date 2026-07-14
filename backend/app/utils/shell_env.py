"""跨平台 shell 环境变量与 MCP 命令构建工具。

解决 Agent 中 LocalShellBackend 的 PATH 以及 MultiServerMCPClient 的启动命令
硬编码 Windows 路径导致 Linux/macOS 无法运行的问题。
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _path_sep() -> str:
    """返回当前平台的路径分隔符。"""
    return os.pathsep


def build_shell_path(extra_paths: list[str] | None = None) -> str:
    """构建跨平台的 PATH 字符串。

    以当前进程 PATH 为基础，追加常见 node/npm 目录以及调用方指定的额外路径，
    避免覆盖宿主环境已有的 PATH。
    """
    sep = _path_sep()
    base_path = os.environ.get("PATH", "")
    existing = {p.strip() for p in base_path.split(sep) if p.strip()}

    if sys.platform == "win32":
        candidates = [
            r"C:\Program Files\nodejs",
            r"C:\Program Files (x86)\nodejs",
            os.path.expandvars(r"%APPDATA%\npm"),
            r"C:\Windows\System32",
            r"C:\Windows",
        ]
    else:
        candidates = [
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            os.path.expanduser("~/.npm-global/bin"),
            os.path.expanduser("~/.local/bin"),
        ]

    if extra_paths:
        candidates = extra_paths + candidates

    new_paths = [p for p in candidates if p and p not in existing and Path(p).exists()]

    if base_path:
        return sep.join([base_path] + new_paths)
    return sep.join(new_paths)


def build_shell_env(
    extra_paths: list[str] | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """构建跨平台的 shell 环境变量字典，供 LocalShellBackend 使用。

    Args:
        extra_paths: 需要优先追加到 PATH 的额外目录。
        extra_env: 需要额外设置/覆盖的环境变量。

    Returns:
        包含 PATH 的环境变量字典，可在 LocalShellBackend(env=...) 中使用。
    """
    env: dict[str, str] = {"PATH": build_shell_path(extra_paths=extra_paths)}
    if extra_env:
        env.update(extra_env)
    return env


def get_playwright_mcp_command_args(root_dir: str) -> tuple[str, list[str]]:
    """返回适合当前平台的 Playwright MCP server 启动命令与参数。

    Windows 下使用 cmd /c 执行 cd & npx ...；
    Linux/macOS 下使用 bash -c 执行 cd && npx ...，并优先定位 npx 绝对路径。
    """
    npx = shutil.which("npx") or "npx"
    if sys.platform == "win32":
        return "cmd", ["/c", f"cd {root_dir} & {npx} playwright run-test-mcp-server"]
    return "bash", ["-c", f"cd {root_dir} && {npx} playwright run-test-mcp-server"]
