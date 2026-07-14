"""跨平台 shell 环境变量与 MCP 命令构建工具。

解决 Agent 中 LocalShellBackend 的 PATH 以及 MultiServerMCPClient 的启动命令
硬编码 Windows 路径导致 Linux/macOS 无法运行的问题。
"""

from __future__ import annotations

import asyncio
import json
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


# 避免并发请求同时触发 npm install 导致 node_modules 损坏。
_playwright_mcp_init_lock = asyncio.Lock()


def resolve_effective_headless(headless: bool) -> bool:
    """根据运行环境修正 headless 取值。

    在 Linux 且无 DISPLAY 的图形环境下，无法弹出真实浏览器窗口，强制降级为
    headless 模式，避免启动失败。
    """
    if not headless and sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        return True
    return headless


async def ensure_playwright_mcp_project(root_dir: str, headless: bool = False) -> None:
    """确保 Playwright MCP server 所需的配置文件与依赖已就绪。

    ``web_mcp_root`` 是运行时工作区（被 .gitignore 忽略），在新 clone 或清理后可能
    缺少 ``playwright.config.js`` / ``package.json`` / ``node_modules``，导致调用
    ``planner_setup_page(project="chromium")`` 时抛出 ``Project chromium not found``，
    或 seed 文件无法解析 ``@playwright/test``。

    本函数在启动 MCP server 前惰性地初始化这些文件，并在缺少依赖时自动运行
    ``npm install``。

    Args:
        root_dir: Playwright MCP 工作区根目录。
        headless: 是否以无头模式运行浏览器。``False`` 表示弹出真实浏览器窗口。
    """
    root = Path(root_dir)
    root.mkdir(parents=True, exist_ok=True)

    effective_headless = resolve_effective_headless(headless)
    headless_value = "true" if effective_headless else "false"
    workers_value = "4" if effective_headless else "1"

    config_file = root / "playwright.config.js"
    if not config_file.exists():
        config_file.write_text(
            f"""module.exports = {{
  testDir: './tests',
  timeout: 60000,
  retries: 2,
  workers: {workers_value},
  use: {{
    headless: {headless_value},
    viewport: {{ width: 1280, height: 720 }},
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: {{
      handleSIGINT: true,
      handleSIGTERM: true,
      handleSIGHUP: true,
    }},
  }},
  projects: [
    {{
      name: 'chromium',
      use: {{
        browserName: 'chromium',
        viewport: {{ width: 1280, height: 720 }},
      }},
    }},
  ],
}};
""",
            encoding="utf-8",
        )

    package_file = root / "package.json"
    if not package_file.exists():
        package_file.write_text(
            json.dumps(
                {
                    "name": "web-mcp-project",
                    "version": "1.0.0",
                    "private": True,
                    "dependencies": {"@playwright/test": "^1.61.1"},
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    playwright_test = root / "node_modules" / "@playwright" / "test"
    if playwright_test.exists():
        return

    async with _playwright_mcp_init_lock:
        # 再次检查，防止等待锁期间其他协程已完成安装。
        if playwright_test.exists():
            return
        npm = shutil.which("npm") or "npm"
        proc = await asyncio.create_subprocess_exec(
            npm,
            "install",
            cwd=str(root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"Failed to install @playwright/test in {root}:"
                f"\n{stderr.decode('utf-8', errors='replace')}"
                f"\n{stdout.decode('utf-8', errors='replace')}"
            )


def get_playwright_mcp_command_args(root_dir: str, headless: bool = False) -> tuple[str, list[str]]:
    """返回适合当前平台的 Playwright MCP server 启动命令与参数。

    Windows 下使用 cmd /c 执行 cd & npx ...；
    Linux/macOS 下使用 bash -c 执行 cd && npx ...，并优先定位 npx 绝对路径。

    Args:
        root_dir: Playwright MCP 工作区根目录。
        headless: 是否以无头模式运行浏览器。``False`` 表示弹出真实浏览器窗口。
    """
    npx = shutil.which("npx") or "npx"
    effective_headless = resolve_effective_headless(headless)
    headless_flag = " --headless" if effective_headless else ""
    if sys.platform == "win32":
        return "cmd", ["/c", f"cd {root_dir} & {npx} playwright run-test-mcp-server{headless_flag}"]
    return "bash", ["-c", f"cd {root_dir} && {npx} playwright run-test-mcp-server{headless_flag}"]
