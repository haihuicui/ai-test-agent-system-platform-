#!/usr/bin/env bash
# ==============================================================================
# LangGraph Server（in-memory 模式）— 无需 Postgres/Redis，启动即用
# ==============================================================================
set -euo pipefail
exec python /app/start_server_inmem.py
