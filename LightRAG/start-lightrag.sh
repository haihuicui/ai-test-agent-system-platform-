#!/usr/bin/env bash
# LightRAG 一键启动脚本（Git Bash / WSL）
# 用法：./start-lightrag.sh

cd "$(dirname "$0")" || exit 1

export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

echo "==========================================="
echo " Starting LightRAG Server (Backend + WebUI)"
echo " WebUI:    http://localhost:9621"
echo " API Docs: http://localhost:9621/docs"
echo "==========================================="
echo ""

.venv/Scripts/lightrag-server.exe
