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
