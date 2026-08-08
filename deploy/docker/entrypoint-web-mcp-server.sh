#!/usr/bin/env bash
# ==============================================================================
# 常驻 Playwright MCP server 容器入口
#
# 背景：web_agent 此前每条会话都 per-run stdio 冷启动一个 MCP server
# （npx 解析 + node 启动 + MCP 握手，实测 ~12s）。本服务把 server 常驻化，
# 通过 Streamable HTTP (/mcp) /  legacy SSE (/sse) 供 langgraph 容器连接。
#
# 要点：
# - 复用 app 镜像（node/npx/chromium 都在），共享 backend-workspace 卷。
# - 使用专用配置 playwright.config.mcp-shared.js（-c 指定），不含任何
#   storageState：langgraph 侧的 ensure_playwright_mcp_project 每 run 会重写
#   playwright.config.js（可能注入某项目登录态），本 server 崩溃重启时若读
#   默认配置会误带登录态。有登录态的 run 在 agent 侧走 stdio 隔离，不经本服务。
# ==============================================================================
set -euo pipefail

ROOT="${WEB_MCP_ROOT:-/app/backend/workspace/web_mcp}"
PORT="${WEB_MCP_PORT:-8931}"

mkdir -p "$ROOT/tests"
cd "$ROOT"

# node_modules 通常已被 langgraph 侧 ensure 装好；缺失时兜底安装
if [ ! -d node_modules/@playwright/test ]; then
  echo "[web-mcp-server] node_modules missing, running npm install..."
  npm install
fi

# 专用配置：与 shell_env.py 生成的 playwright.config.js 同构，但固定无 storageState。
# 每次启动重写，防止旧残留。
cat > playwright.config.mcp-shared.js <<'EOF'
module.exports = {
  testDir: './tests',
  timeout: 60000,
  retries: 1,
  workers: 4,
  use: {
    headless: true,
    viewport: { width: 1280, height: 720 },
    trace: 'on',
    video: 'on',
    screenshot: 'on',
    launchOptions: {
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
      handleSIGINT: true,
      handleSIGTERM: true,
      handleSIGHUP: true,
    },
  },
  projects: [
    {
      name: 'chromium',
      use: {
        browserName: 'chromium',
        viewport: { width: 1280, height: 720 },
      },
    },
  ],
};
EOF

echo "[web-mcp-server] starting Playwright MCP on 0.0.0.0:${PORT} (HTTP /mcp, SSE /sse)"
exec npx playwright run-test-mcp-server -c playwright.config.mcp-shared.js --headless --host 0.0.0.0 --port "$PORT"
