#!/usr/bin/env bash
# ==============================================================================
# FastAPI Backend 容器入口
# 1) 等 PostgreSQL 就绪
# 2) create_all（幂等，无论空库/半空库/已有库均安全）
# 3) alembic stamp head（新库）或 upgrade head（已有库）
# 4) exec app/main.py（Mongo/MinIO 启动期惰性连接，无需等待）
# ==============================================================================
set -euo pipefail
cd /app/backend

echo "[entrypoint-backend] waiting for postgres..."
python - <<'PY'
import os, sys, time
import psycopg

dsn = (
    f"host={os.environ['POSTGRES_HOST']} port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']} "
    f"dbname={os.environ['POSTGRES_DB']} connect_timeout=3"
)
for i in range(60):
    try:
        with psycopg.connect(dsn) as conn:
            conn.execute("SELECT 1")
        print("[entrypoint-backend] postgres ready")
        sys.exit(0)
    except Exception as e:
        print(f"[entrypoint-backend] postgres not ready ({i+1}/60): {e}", flush=True)
        time.sleep(2)
sys.exit("[entrypoint-backend] postgres wait timeout")
PY

# ---- 建表（幂等，先于 alembic） ----
# 无论空库/半空库（有 alembic_version 但表不全）/已有完整库，
# create_all(checkfirst=True) 均安全 —— 已有表跳过，缺失表补齐。
echo "[entrypoint-backend] create_all (idempotent)..."
python -c "
import asyncio, sys
sys.path.insert(0, '.')
from app.config.database import init_db
asyncio.run(init_db())
"

# ---- 迁移标记 ----
HAS_ALEMBIC="$(python - <<'PY'
import os
import psycopg
with psycopg.connect(
    host=os.environ["POSTGRES_HOST"], port=os.environ.get("POSTGRES_PORT", "5432"),
    user=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"],
    dbname=os.environ["POSTGRES_DB"], connect_timeout=5,
) as conn:
    exists = conn.execute("SELECT to_regclass('public.alembic_version')").fetchone()[0]
    print("yes" if exists else "no")
PY
)"

if [ "$HAS_ALEMBIC" = "no" ]; then
    echo "[entrypoint-backend] fresh DB: alembic stamp head"
    alembic stamp head
else
    echo "[entrypoint-backend] existing DB: alembic upgrade head"
    alembic upgrade head
fi

# Python 3.13 默认不将 CWD 加入 sys.path，显式注入
exec python -c "
import sys
sys.path.insert(0, '.')
exec(open('app/main.py').read())
"
