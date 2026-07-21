# syntax=docker/dockerfile:1
# ==============================================================================
# AI Test Agent 应用镜像（langgraph server 与 fastapi backend 共用）
# 构建上下文 = 项目根目录（compose 中 context: ..）
# 两服务仅靠 compose 的 command 区分角色：entrypoint-langgraph.sh / entrypoint-backend.sh
# ==============================================================================
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    # 浏览器统一装到 /ms-playwright（构建期 root 安装 / 运行期 app 使用，同一路径）
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    # 非 root 用户在容器内运行 Chromium 需要关闭 sandbox
    PLAYWRIGHT_NO_SANDBOX=1 \
    NPM_CONFIG_AUDIT=false \
    NPM_CONFIG_FUND=false

# ---- L1: 系统依赖 + Node 20 官方二进制 -------------------------------------
# bash: agent 的 LocalShellBackend / MCP 启动命令需要
# nmap: security_agent 侦察工具; curl/git/unzip/xz-utils: 构建与安全工具下载
RUN apt-get update && apt-get install -y --no-install-recommends \
      bash curl ca-certificates git unzip xz-utils procps \
      nmap \
    && curl -fsSL https://nodejs.org/dist/v20.19.5/node-v20.19.5-linux-x64.tar.xz \
       | tar -xJ -C /usr/local --strip-components=1 \
    && rm -rf /var/lib/apt/lists/*

# ---- L2: Python 依赖（锁文件独立层，最大化构建缓存） ------------------------
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /usr/local/bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
# 注：pyproject 无 [build-system]，uv 视项目为 virtual，不会把项目自身装进 venv；
#     langgraph_api/ 等本地包靠 start_server_postgres.py 的 sys.path 注入，无需 pip install。

# ---- L3: 应用源码（分层 COPY，定向失效缓存） --------------------------------
# langgraph_api/ → postgres 模式需要（本地定制版含 postgres checkpoint/store）。
# inmem 模式由 entrypoint 启动前改名为 langgraph_api_local，避免与 pip 的
# langgraph-api==0.8.7 冲突（旧版会导致 _checkpointer 缺失、protobuf 冲突）。
COPY langgraph_api/              langgraph_api/
COPY langgraph_license/          langgraph_license/
COPY langgraph_runtime_postgres/ langgraph_runtime_postgres/
COPY langgraph_source/           langgraph_source/
COPY patches/                    patches/
COPY scripts/                    scripts/
COPY storage/                    storage/
COPY backend/app/                backend/app/
COPY backend/alembic/            backend/alembic/
COPY backend/alembic.ini         backend/alembic.ini
COPY .claude/skills/             .claude/skills/
COPY openapi.json langgraph.json start_server_postgres.py start_server_inmem.py ./
COPY deploy/docker/              deploy/docker/

# ---- L4: venv 铺层（替代 README 手动步骤 2/3）+ 补丁预写 + 脚本规范化 -------
# langgraph_source 的 postgres checkpoint/store 必须塞进已安装的 langgraph 命名空间包内
# deepagents 补丁预写后 PATCH_MARKER 命中，启动时 ensure_patched() 幂等跳过
RUN SP="$(/app/.venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')" && \
    cp -r langgraph_source/checkpoint/postgres "$SP/langgraph/checkpoint/" && \
    cp -r langgraph_source/store/postgres     "$SP/langgraph/store/" && \
    cp patches/deepagents/_messages_reducer.py "$SP/deepagents/_messages_reducer.py" && \
    sed -i 's/\r$//' deploy/docker/*.sh && chmod +x deploy/docker/*.sh

# ---- L5: workspace 预烘（构建期 npm install + chromium 及系统库） -----------
# api workspace 不会运行时自动 npm install，必须构建期预装；
# web_mcp workspace 预置后运行时 ensure 检查命中即跳过（消除双容器并发 npm install 竞争）
# @playwright/test 锁定 1.61.1：浏览器二进制修订版与包版本一一对应，勿浮动
COPY deploy/docker/workspace-api-package.json    backend/workspace/api/package.json
COPY deploy/docker/workspace-webmcp-package.json backend/workspace/web_mcp/package.json
RUN cd backend/workspace/api    && npm install && \
    cd ../web_mcp               && npm install
# --with-deps 需 root：自动 apt 安装 chromium 系统库；浏览器入 /ms-playwright
RUN cd backend/workspace/api && npx playwright install --with-deps chromium

# ---- L6: 安全测试工具（尽力而为，单个失败不阻断构建；缺工具时对应 agent 工具运行时报错） --
RUN /app/.venv/bin/python -m pip install --quiet sqlmap || true; \
    (curl -fsSL https://github.com/ffuf/ffuf/releases/download/v2.1.0/ffuf_2.1.0_linux_amd64.tar.gz \
       | tar -xz -C /usr/local/bin ffuf) || true; \
    (curl -fsSL -o /tmp/subfinder.zip https://github.com/projectdiscovery/subfinder/releases/download/v2.7.0/subfinder_2.7.0_linux_amd64.zip \
       && unzip -o -j /tmp/subfinder.zip subfinder -d /usr/local/bin) || true; \
    (curl -fsSL https://github.com/hahwul/dalfox/releases/download/v2.12.0/dalfox_2.12.0_linux_amd64.tar.gz \
       | tar -xz -C /usr/local/bin dalfox) || true; \
    chmod +x /usr/local/bin/ffuf /usr/local/bin/subfinder /usr/local/bin/dalfox 2>/dev/null || true; \
    rm -f /tmp/subfinder.zip

# ---- L7: 非 root 用户（root 跑 chromium 需 --no-sandbox，代码未传该参数） ----
RUN useradd --create-home --uid 10001 app && \
    mkdir -p /app/.langgraph_api /ms-playwright && \
    chown -R app:app /app /ms-playwright
USER app
ENV PATH="/app/.venv/bin:/home/app/.local/bin:$PATH" \
    HOME=/home/app \
    # start_server_postgres.py 的 MIGRATIONS_PATH 默认是 CWD 相对路径，容器内显式绝对化
    MIGRATIONS_PATH=/app/storage/migrations

# 不设置 ENTRYPOINT/CMD：由 compose 的 command 区分 langgraph / backend 两个角色
