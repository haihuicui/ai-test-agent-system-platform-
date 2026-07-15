#!/usr/bin/env bash
# ==============================================================================
# LangGraph Server 容器入口
# 1) 等 PostgreSQL 就绪（compose healthcheck 之外的二次保险，应对重启乱序）
# 2) 等 Redis 就绪（storage/migrations 用 Redis 分布式锁）
# 3) exec start_server_postgres.py（59 个存储迁移在启动时自动执行，无需手工迁移）
# ==============================================================================
set -euo pipefail

echo "[entrypoint-langgraph] waiting for postgres..."
python - <<'PY'
import os, sys, time
import psycopg

dsn = os.environ["POSTGRES_URI"]  # compose 从 POSTGRES_* 分量派生, postgresql:// 格式
for i in range(60):
    try:
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        print("[entrypoint-langgraph] postgres ready")
        sys.exit(0)
    except Exception as e:
        print(f"[entrypoint-langgraph] postgres not ready ({i+1}/60): {e}", flush=True)
        time.sleep(2)
sys.exit("[entrypoint-langgraph] postgres wait timeout")
PY

echo "[entrypoint-langgraph] waiting for redis..."
python - <<'PY'
import os, sys, time
import redis

url = os.environ["REDIS_URI"]
for i in range(30):
    try:
        redis.Redis.from_url(url, socket_connect_timeout=3).ping()
        print("[entrypoint-langgraph] redis ready")
        sys.exit(0)
    except Exception as e:
        print(f"[entrypoint-langgraph] redis not ready ({i+1}/30): {e}", flush=True)
        time.sleep(2)
sys.exit("[entrypoint-langgraph] redis wait timeout")
PY

exec python /app/start_server_postgres.py
