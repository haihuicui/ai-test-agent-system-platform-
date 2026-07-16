#!/usr/bin/env bash
set -euo pipefail

# 首次部署或有新提交时自动分析项目，索引缓存于 /repo/.gitnexus（持久卷）
echo "[gitnexus] analyzing project..."
cd /repo
gitnexus analyze || echo "[gitnexus] analyze 部分失败（非致命，服务仍启动）"

echo "[gitnexus] starting server on 0.0.0.0:4747"
exec gitnexus serve --host 0.0.0.0 --port 4747
