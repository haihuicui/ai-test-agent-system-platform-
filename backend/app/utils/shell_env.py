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


async def ensure_playwright_mcp_project(
    root_dir: str,
    headless: bool = False,
    storage_state: str | None = None,
) -> None:
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
        storage_state: 全局登录态文件路径；未传入时使用 ``settings.web_mcp_storage_state``。
            每次调用都会重写 ``playwright.config.js``，确保 ``storageState`` 配置项
            与当前设置保持一致。
    """
    root = Path(root_dir)
    root.mkdir(parents=True, exist_ok=True)

    effective_headless = resolve_effective_headless(headless)
    headless_value = "true" if effective_headless else "false"
    workers_value = "4" if effective_headless else "1"

    # 延迟 import，避免与配置加载产生循环依赖。超时/重试预算统一从 settings 读取，
    # 与 execute_web_script 的命令行覆盖保持一致。
    from app.config import settings
    test_timeout = settings.web_exec_test_timeout_ms
    retries = settings.web_exec_retries

    # 全局登录态（storageState）：传入路径优先，其次 settings.web_mcp_storage_state。
    # 文件存在时注入 config；未配置或文件缺失则不启用（保持现状）。
    storage_state_line = ""
    ss = storage_state or getattr(settings, "web_mcp_storage_state", None)
    if ss:
        ss_path = Path(ss)
        if ss_path.exists():
            # JS 中用正斜杠，避免 Windows 反斜杠转义问题
            storage_state_line = f"    storageState: {json.dumps(ss_path.as_posix())},\n"
        else:
            print(f"[Web MCP] 配置的 storageState 文件不存在，跳过注入: {ss_path}")

    config_file = root / "playwright.config.js"
    # 删除旧配置，避免从 Windows 开发机拷入的绝对路径等残留配置干扰 Linux 运行。
    if config_file.exists():
        config_file.unlink()
    # 在 Docker/CI 等无 sandbox 环境自动注入 --no-sandbox。
    no_sandbox_args = ""
    if os.environ.get("PLAYWRIGHT_NO_SANDBOX", "").lower() in ("1", "true", "yes"):
        no_sandbox_args = "\n      args: ['--no-sandbox', '--disable-setuid-sandbox'],"
    # 每次调用都重写配置，确保 headless / timeout / retries / storageState 变更生效。
    config_file.write_text(
        f"""module.exports = {{
  testDir: './tests',
  timeout: {test_timeout},
  retries: {retries},
  workers: {workers_value},
  use: {{
    headless: {headless_value},
{storage_state_line}    viewport: {{ width: 1280, height: 720 }},
    trace: 'on',
    video: 'on',
    screenshot: 'on',
    launchOptions: {{
      handleSIGINT: true,
      handleSIGTERM: true,
      handleSIGHUP: true,{no_sandbox_args}
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
                    "dependencies": {"@playwright/test": "1.61.1"},
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    playwright_test = root / "node_modules" / "@playwright" / "test"
    npm = shutil.which("npm") or "npm"

    async with _playwright_mcp_init_lock:
        if not playwright_test.exists():
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

        # 兜底安装浏览器二进制。构建期可能只在 api workspace 预装 Chromium；
        # 且 Docker volume 中的 node_modules 与浏览器缓存可能不同步，因此每次
        # ensure 都检查一次，已安装时 Playwright 会快速跳过。
        browser_proc = await asyncio.create_subprocess_exec(
            npm,
            "exec",
            "--",
            "playwright",
            "install",
            "chromium",
            cwd=str(root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        browser_stdout, browser_stderr = await browser_proc.communicate()
        if browser_proc.returncode != 0:
            raise RuntimeError(
                f"Failed to install Playwright browsers in {root}:"
                f"\n{browser_stderr.decode('utf-8', errors='replace')}"
                f"\n{browser_stdout.decode('utf-8', errors='replace')}"
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
