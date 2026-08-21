"""playwright_chromium_installed 与 MCP 客户端选择逻辑的单元测试。

覆盖：
- 方案 A：chromium 二进制存在时跳过 install 检查（含各平台布局、强制环境变量）
- 方案 B：_build_mcp_client 按 WEB_MCP_SERVER_URL 选择 streamable_http / stdio
"""

from pathlib import Path

import pytest

from app.utils.shell_env import (
    _CHROMIUM_BINARY_GLOBS,
    playwright_chromium_installed,
)


class TestPlaywrightChromiumInstalled:
    def test_installed_linux_chrome(self, tmp_path, monkeypatch):
        binary = tmp_path / "chromium-1228" / "chrome-linux64" / "chrome"
        binary.parent.mkdir(parents=True)
        binary.touch()
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
        monkeypatch.delenv("WEB_MCP_FORCE_BROWSER_INSTALL", raising=False)
        assert playwright_chromium_installed() is True

    def test_installed_headless_shell(self, tmp_path, monkeypatch):
        binary = (
            tmp_path
            / "chromium_headless_shell-1228"
            / "chrome-linux"
            / "headless_shell"
        )
        binary.parent.mkdir(parents=True)
        binary.touch()
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
        monkeypatch.delenv("WEB_MCP_FORCE_BROWSER_INSTALL", raising=False)
        assert playwright_chromium_installed() is True

    def test_not_installed(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
        monkeypatch.delenv("WEB_MCP_FORCE_BROWSER_INSTALL", raising=False)
        assert playwright_chromium_installed() is False

    def test_force_install_env_overrides_detection(self, tmp_path, monkeypatch):
        binary = tmp_path / "chromium-1228" / "chrome-linux64" / "chrome"
        binary.parent.mkdir(parents=True)
        binary.touch()
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
        monkeypatch.setenv("WEB_MCP_FORCE_BROWSER_INSTALL", "1")
        assert playwright_chromium_installed() is False

    def test_missing_browsers_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv(
            "PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "does-not-exist")
        )
        monkeypatch.delenv("WEB_MCP_FORCE_BROWSER_INSTALL", raising=False)
        assert playwright_chromium_installed() is False

    def test_globs_have_no_absolute_path(self):
        for pattern in _CHROMIUM_BINARY_GLOBS:
            assert not Path(pattern).is_absolute()


class TestGetPlaywrightMcpCommandArgs:
    """回归：MCP server 启动必须是真实 argv + cwd，禁止 shell 字符串包裹。

    旧实现拼 ``cmd /c "cd X & npx ... -c \\"path\\""`` 形式的 shell 字符串；
    subprocess 的 list2cmdline 会把内嵌引号二次转义（Python 3.13+ 转成 ``\"``），
    cmd 不认该转义，子进程（MS CRT 解析）最终收到带字面引号的 ``-c`` 参数，
    Playwright 把配置路径按相对路径解析到 cwd 下，``planner_setup_page`` 报
    ``does not exist``（路径形如 ``web_mcp\\"D:\\...\\ss-*.js"``）。
    """

    @pytest.mark.asyncio
    async def test_no_shell_wrapping(self, tmp_path):
        from app.utils.shell_env import get_playwright_mcp_command_args

        command, args, cwd = await get_playwright_mcp_command_args(str(tmp_path))
        assert command not in ("cmd", "bash")
        assert args[:2] == ["playwright", "run-test-mcp-server"]
        assert "--headless" not in args
        assert cwd == str(tmp_path)

    @pytest.mark.asyncio
    async def test_config_path_is_standalone_argv(self, tmp_path):
        from app.utils.shell_env import get_playwright_mcp_command_args

        config_file = tmp_path / "playwright.config.ss-PR-1-b80ec302.js"
        command, args, _cwd = await get_playwright_mcp_command_args(
            str(tmp_path), headless=True, config_path=str(config_file)
        )
        # -c 与路径是两个独立 argv 项，路径本身不含引号
        assert args[args.index("-c") + 1] == str(config_file)
        assert '"' not in str(config_file)
        assert args[-1] == "--headless"

    @pytest.mark.asyncio
    async def test_windows_list2cmdline_keeps_config_arg_clean(self, tmp_path):
        """Windows 回归：list2cmdline 重转义后命令行不得出现 ``\\"`` 残留。"""
        import subprocess
        import sys

        if sys.platform != "win32":
            pytest.skip("Windows-only regression")
        from app.utils.shell_env import get_playwright_mcp_command_args

        config_file = tmp_path / "playwright.config.ss-PR-1-b80ec302.js"
        _command, args, _cwd = await get_playwright_mcp_command_args(
            str(tmp_path), headless=True, config_path=str(config_file)
        )
        cmdline = subprocess.list2cmdline(args)
        assert '\\"' not in cmdline

    @pytest.mark.asyncio
    async def test_headless_env_forced_on_linux(self, tmp_path, monkeypatch):
        """无 DISPLAY 的 Linux 下 headless 强制为 True（resolve_effective_headless 语义）。"""
        import sys

        if sys.platform != "linux":
            pytest.skip("Linux-only behavior")
        from app.utils.shell_env import get_playwright_mcp_command_args

        monkeypatch.delenv("DISPLAY", raising=False)
        _command, args, _cwd = await get_playwright_mcp_command_args(str(tmp_path), headless=False)
        assert "--headless" in args


class TestBuildMcpClient:
    def test_shared_url_selects_streamable_http(self, monkeypatch):
        from app.agents.web_mcp import agent as agent_module

        monkeypatch.setattr(
            agent_module.settings,
            "web_mcp_server_url",
            "http://web-mcp-server:8931/mcp",
        )
        client = agent_module._build_mcp_client("bash", ["-c", "noop"])
        conn = client.connections["web_mcp"]
        assert conn["transport"] == "streamable_http"
        assert conn["url"] == "http://web-mcp-server:8931/mcp"
        # Playwright MCP 的 Host 头校验要求 localhost:<port>
        assert conn["headers"] == {"Host": "localhost:8931"}

    def test_empty_url_falls_back_to_stdio(self, monkeypatch):
        from app.agents.web_mcp import agent as agent_module

        monkeypatch.setattr(agent_module.settings, "web_mcp_server_url", None)
        client = agent_module._build_mcp_client("bash", ["-c", "noop"])
        conn = client.connections["web_mcp"]
        assert conn["transport"] == "stdio"
        assert conn["command"] == "bash"

    def test_blank_url_falls_back_to_stdio(self, monkeypatch):
        from app.agents.web_mcp import agent as agent_module

        monkeypatch.setattr(agent_module.settings, "web_mcp_server_url", "  ")
        client = agent_module._build_mcp_client("bash", ["-c", "noop"])
        assert client.connections["web_mcp"]["transport"] == "stdio"

    def test_stdio_connection_carries_cwd(self, monkeypatch):
        from app.agents.web_mcp import agent as agent_module

        monkeypatch.setattr(agent_module.settings, "web_mcp_server_url", None)
        client = agent_module._build_mcp_client(
            "npx", ["playwright", "run-test-mcp-server"], stdio_cwd=r"D:\ws"
        )
        conn = client.connections["web_mcp"]
        assert conn["transport"] == "stdio"
        assert conn["cwd"] == r"D:\ws"

    def test_stdio_connection_omits_cwd_when_absent(self, monkeypatch):
        from app.agents.web_mcp import agent as agent_module

        monkeypatch.setattr(agent_module.settings, "web_mcp_server_url", None)
        client = agent_module._build_mcp_client("bash", ["-c", "noop"])
        assert "cwd" not in client.connections["web_mcp"]


class TestProbeTcp:
    @pytest.mark.asyncio
    async def test_reachable(self, unused_tcp_port):
        import asyncio

        from app.agents.web_mcp.agent import _probe_tcp

        server = await asyncio.start_server(lambda r, w: None, "127.0.0.1", unused_tcp_port)
        try:
            assert await _probe_tcp(f"http://127.0.0.1:{unused_tcp_port}/mcp") is True
        finally:
            server.close()
            await server.wait_closed()

    @pytest.mark.asyncio
    async def test_unreachable(self, unused_tcp_port):
        from app.agents.web_mcp.agent import _probe_tcp

        assert await _probe_tcp(f"http://127.0.0.1:{unused_tcp_port}/mcp", timeout=0.5) is False
