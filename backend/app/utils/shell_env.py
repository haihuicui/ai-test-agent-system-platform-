"""跨平台 shell 环境变量与 MCP 命令构建工具。

解决 Agent 中 LocalShellBackend 的 PATH 以及 MultiServerMCPClient 的启动命令
硬编码 Windows 路径导致 Linux/macOS 无法运行的问题。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

from app.utils.sync_executor import run_sync


def _sanitize_config_key(key: str) -> str:
    """把项目标识符等任意字符串转为可安全用于文件名的 key。

    非 ASCII 字符（如中文项目名）统一替换为 ``_``，并追加标识符的短 hash：
    不同标识符 sanitize 后可能退化为同名（「项目一」「项目二」→ ``___``），
    hash 后缀保证文件名唯一，前缀保留可读性。
    """
    if not key:
        return "global"
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", key)
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()[:8]
    return f"{safe}-{digest}"


def _validate_storage_state_if_present(path: Path) -> bool:
    """校验 storageState 文件是否有效（延迟导入避免循环依赖）。"""
    from app.utils.storage_state_validator import validate_storage_state

    validation = validate_storage_state(path)
    return validation.is_valid


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


# 允许进入 Agent shell / 测试子进程的环境变量白名单（比较时统一大写）。
# 设计原则：模型生成的脚本在子进程中运行，绝不能让进程密钥
# （LLM API Key、数据库密码、Langfuse Secret、MinIO 密钥等）泄漏进去。
# 仅放行操作系统与工具链运行所必需的非敏感变量。
_RESTRICTED_ENV_KEYS = frozenset({
    # Windows 基础运行时（CreateProcess / cmd / 节点 shim 依赖）
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC", "OS",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432", "COMMONPROGRAMFILES",
    "APPDATA", "LOCALAPPDATA", "TEMP", "TMP",
    "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
    # POSIX 基础运行时
    "HOME", "SHELL", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TMPDIR",
    "USER", "LOGNAME", "HOSTNAME",
    "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
    # Node / Playwright / npm 工具链
    "NODE_ENV", "PLAYWRIGHT_BROWSERS_PATH", "PLAYWRIGHT_NO_SANDBOX",
    "NPM_CONFIG_CACHE",
    # 企业代理（npm install / 下载依赖必需；URL 内嵌凭据的边缘情况可接受）
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
})


def build_restricted_env(
    extra_paths: list[str] | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """构建密钥隔离的白名单环境变量字典。

    与 build_shell_env 的区别：从 os.environ 中仅挑选白名单内的安全变量，
    用于配合 ``LocalShellBackend(inherit_env=False)`` 或测试子进程，
    防止模型生成的脚本通过 ``process.env`` / ``env`` 读取进程密钥。

    比较时按大写匹配（兼容 Windows 的 ``Path`` 与 Linux 的 ``http_proxy`` 等
    大小写变体），保留变量原始名称。

    Args:
        extra_paths: 需要优先追加到 PATH 的额外目录。
        extra_env: 需要额外设置/覆盖的环境变量（调用方显式注入，如 AUTH_TOKEN，
            不受白名单限制——这是受控的注入通道）。
    """
    env: dict[str, str] = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in _RESTRICTED_ENV_KEYS
    }
    env["PATH"] = build_shell_path(extra_paths=extra_paths)
    if extra_env:
        env.update(extra_env)
    return env


# 避免并发请求同时触发 npm install 导致 node_modules 损坏。
_playwright_mcp_init_lock = asyncio.Lock()

# 已安装 Chromium 二进制的 glob 模式（相对 Playwright browsers 目录），
# 覆盖 Linux（chrome-linux / chrome-linux64）、headless shell、macOS、Windows 布局。
_CHROMIUM_BINARY_GLOBS = (
    "chromium-*/chrome-linux/chrome",
    "chromium-*/chrome-linux64/chrome",
    "chromium_headless_shell-*/chrome-linux/headless_shell",
    "chromium_headless_shell-*/chrome-linux64/headless_shell",
    "chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
    "chromium-*/chrome-win/chrome.exe",
)


def playwright_chromium_installed() -> bool:
    """快速检测 Playwright Chromium 二进制是否已安装。

    直接按已知目录布局 glob 可执行文件，避免每次 ensure 都 spawn 一次
    ``npm exec playwright install chromium``（即使已安装也要 ~6s 的
    node/npm 启动开销）。

    可通过环境变量 ``WEB_MCP_FORCE_BROWSER_INSTALL=1`` 强制回到旧行为
    （始终执行 install 检查）。
    """
    if os.environ.get("WEB_MCP_FORCE_BROWSER_INSTALL", "").lower() in ("1", "true", "yes"):
        return False
    base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(
        Path.home() / ".cache" / "ms-playwright"
    )
    base_path = Path(base)
    try:
        for pattern in _CHROMIUM_BINARY_GLOBS:
            if any(base_path.glob(pattern)):
                return True
    except OSError:
        return False
    return False


def resolve_effective_headless(headless: bool) -> bool:
    """根据运行环境修正 headless 取值。

    在 Linux 且无 DISPLAY 的图形环境下，无法弹出真实浏览器窗口，强制降级为
    headless 模式，避免启动失败。
    """
    if not headless and sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        return True
    return headless


def _build_playwright_config_content(
    *,
    headless_value: str,
    workers_value: str,
    test_timeout: int,
    retries: int,
    storage_state_line: str = "",
    no_sandbox_args: str = "",
) -> str:
    """生成 playwright.config.js 文本（共享静态模板与 per-run 登录态配置共用）。"""
    return f"""module.exports = {{
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
"""


def _no_sandbox_args_if_needed() -> str:
    """在 Docker/CI 等无 sandbox 环境自动注入 --no-sandbox。"""
    if os.environ.get("PLAYWRIGHT_NO_SANDBOX", "").lower() in ("1", "true", "yes"):
        return "\n      args: ['--no-sandbox', '--disable-setuid-sandbox'],"
    return ""


async def ensure_playwright_mcp_project(
    root_dir: str,
    headless: bool = False,
) -> None:
    """确保 Playwright MCP server 所需的配置文件与依赖已就绪。

    ``web_mcp_root`` 是运行时工作区（被 .gitignore 忽略），在新 clone 或清理后可能
    缺少 ``playwright.config.js`` / ``package.json`` / ``node_modules``，导致调用
    ``planner_setup_page(project="chromium")`` 时抛出 ``Project chromium not found``，
    或 seed 文件无法解析 ``@playwright/test``。

    本函数在启动 MCP server 前惰性地初始化这些文件，并在缺少依赖时自动运行
    ``npm install``。

    共享 ``playwright.config.js`` 固定为**无登录态**静态模板：storageState 属于
    per-run 变量，并发 run 若共用一份配置会互相覆盖（登录态丢失 / 跨项目串扰）。
    需要登录态的调用方应使用 ``write_storage_state_config`` 生成独立配置。

    Args:
        root_dir: Playwright MCP 工作区根目录。
        headless: 是否以无头模式运行浏览器。``False`` 表示弹出真实浏览器窗口。
    """
    root = Path(root_dir)
    await run_sync(root.mkdir, parents=True, exist_ok=True)

    effective_headless = resolve_effective_headless(headless)
    headless_value = "true" if effective_headless else "false"
    workers_value = "4" if effective_headless else "1"

    # 延迟 import，避免与配置加载产生循环依赖。超时/重试预算统一从 settings 读取，
    # 与 execute_web_script 的命令行覆盖保持一致。
    from app.config import settings
    test_timeout = settings.web_exec_test_timeout_ms
    retries = settings.web_exec_retries

    config_file = root / "playwright.config.js"
    # 删除旧配置，避免从 Windows 开发机拷入的绝对路径等残留配置干扰 Linux 运行。
    if await run_sync(config_file.exists):
        await run_sync(config_file.unlink)
    # 每次调用都重写配置，确保 headless / timeout / retries 变更生效。
    config_content = _build_playwright_config_content(
        headless_value=headless_value,
        workers_value=workers_value,
        test_timeout=test_timeout,
        retries=retries,
        no_sandbox_args=_no_sandbox_args_if_needed(),
    )
    await run_sync(config_file.write_text, config_content, encoding="utf-8")

    package_file = root / "package.json"
    if not await run_sync(package_file.exists):
        package_content = json.dumps(
            {
                "name": "web-mcp-project",
                "version": "1.0.0",
                "private": True,
                "dependencies": {"@playwright/test": "1.61.1"},
            },
            indent=2,
        )
        await run_sync(package_file.write_text, package_content, encoding="utf-8")

    playwright_test = root / "node_modules" / "@playwright" / "test"
    npm = await run_sync(shutil.which, "npm") or "npm"

    async with _playwright_mcp_init_lock:
        if not await run_sync(playwright_test.exists):
            try:
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
            except (NotImplementedError, OSError) as e:
                print(f"[Web MCP] 跳过 npm install (当前环境不支持子进程): {e}")
                # 跳过 Playwright 依赖安装，运行时若无 node_modules 将报清晰错误。
                # 开发环境建议手动执行 npm install。

        ## 兜底安装浏览器二进制。构建期可能只在 api workspace 预装 Chromium；
        ## 且 Docker volume 中的 node_modules 与浏览器缓存可能不同步。
        ## 已安装时直接按二进制布局跳过（~6s 的 npm exec 开销），仅在缺失
        ## 或 WEB_MCP_FORCE_BROWSER_INSTALL=1 时才执行 install 检查。
        if playwright_chromium_installed():
            pass
        else:
            try:
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
            except (NotImplementedError, OSError) as e:
                print(f"[Web MCP] 跳过 playwright install (当前环境不支持子进程): {e}")


async def write_storage_state_config(
    root_dir: str,
    storage_state: str,
    headless: bool = False,
    config_key: str = "global",
) -> str | None:
    """生成携带 storageState 的独立 playwright 配置，返回配置文件路径。

    命名 ``playwright.config.ss-<config_key>.js``，与共享 ``playwright.config.js``
    同级，保证 ``testDir: './tests'`` 的相对解析一致。同名文件按 key 复用：
    同项目并发写入的内容相同（解析自同一登录态），登录态续期后后写覆盖为更新值，
    语义均正确；写盘走临时文件 + ``os.replace`` 原子替换，避免并发读到半截文件。

    Args:
        root_dir: Playwright MCP 工作区根目录。
        storage_state: storageState 文件路径；不存在或校验无效时返回 ``None``。
        headless: 是否以无头模式运行浏览器。
        config_key: 配置隔离键（通常为 project_identifier；全局回退用 ``global``）。

    Returns:
        生成的配置文件绝对路径；storageState 无效时返回 ``None``。
    """
    ss_path = Path(storage_state)
    if not await run_sync(ss_path.exists):
        print(f"[Web MCP] storageState 文件不存在，跳过生成独立配置: {ss_path}")
        return None
    if not await run_sync(_validate_storage_state_if_present, ss_path):
        print(f"[Web MCP] storageState 校验无效，跳过生成独立配置: {ss_path}")
        return None

    root = Path(root_dir)
    effective_headless = resolve_effective_headless(headless)
    from app.config import settings
    config_content = _build_playwright_config_content(
        headless_value="true" if effective_headless else "false",
        workers_value="4" if effective_headless else "1",
        test_timeout=settings.web_exec_test_timeout_ms,
        retries=settings.web_exec_retries,
        # JS 中用正斜杠，避免 Windows 反斜杠转义问题
        storage_state_line=f"    storageState: {json.dumps(ss_path.as_posix())},\n",
        no_sandbox_args=_no_sandbox_args_if_needed(),
    )

    config_file = root / f"playwright.config.ss-{_sanitize_config_key(config_key)}.js"
    tmp_file = config_file.with_suffix(config_file.suffix + ".tmp")
    await run_sync(tmp_file.write_text, config_content, encoding="utf-8")
    await run_sync(os.replace, tmp_file, config_file)
    return str(config_file)


async def get_playwright_mcp_command_args(
    root_dir: str,
    headless: bool = False,
    config_path: str | None = None,
) -> tuple[str, list[str]]:
    """返回适合当前平台的 Playwright MCP server 启动命令与参数。

    Windows 下使用 cmd /c 执行 cd & npx ...；
    Linux/macOS 下使用 bash -c 执行 cd && npx ...，并优先定位 npx 绝对路径。

    Args:
        root_dir: Playwright MCP 工作区根目录。
        headless: 是否以无头模式运行浏览器。``False`` 表示弹出真实浏览器窗口。
        config_path: 可选的独立配置文件路径（如携带登录态的
            ``playwright.config.ss-*.js``）；未传时 MCP server 加载默认共享配置。
    """
    npx = await run_sync(shutil.which, "npx") or "npx"
    effective_headless = resolve_effective_headless(headless)
    headless_flag = " --headless" if effective_headless else ""
    config_flag = f' -c "{config_path}"' if config_path else ""
    if sys.platform == "win32":
        return "cmd", ["/c", f"cd {root_dir} & {npx} playwright run-test-mcp-server{config_flag}{headless_flag}"]
    return "bash", ["-c", f"cd {root_dir} && {npx} playwright run-test-mcp-server{config_flag}{headless_flag}"]
