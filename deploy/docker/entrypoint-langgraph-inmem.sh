#!/usr/bin/env bash
# ==============================================================================
# LangGraph Server（in-memory 模式）— 无需 Postgres/Redis，启动即用
# pip 已安装 langgraph-api==0.8.7，本地 langgraph_api/（旧版 v0.5.23）会覆盖
# pip 新版导致 _checkpointer 缺失 + protobuf 冲突。改名让 Python 回退到 pip 版本。
# postgres 模式（entrypoint-langgraph.sh）不同：需要本地定制版，不能改名。
# ==============================================================================
set -euo pipefail
mv /app/langgraph_api /app/langgraph_api_local
exec python /app/start_server_inmem.py
