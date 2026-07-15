#!/usr/bin/env bash
# ==============================================================================
# FastAPI Backend 容器入口
# 1) 等 PostgreSQL 就绪
# 2) 空库判定（项目约定：alembic 迁移假定 create_all 已建基表，
#    见 backend/alembic/versions/0001_baseline_bs.py docstring）：
#      无 alembic_version 表 → init_db() 建全表 + alembic stamp head   （全新部署）
#      有 alembic_version 表 → alembic upgrade head                      （升级）
# 3) exec app/main.py（Mongo/MinIO 启动期惰性连接，无需等待）
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
    echo "[entrypoint-backend] fresh DB detected: create_all -> alembic stamp head"
    # init_db 与 main.py 的 DEBUG 分支无关，直接调用；settings 从容器环境变量取值
    python -c "import asyncio, sys; sys.path.insert(0, '.'); from app.config.database import init_db; asyncio.run(init_db())"
    alembic stamp head
else
    echo "[entrypoint-backend] existing DB detected: alembic upgrade head"
    alembic upgrade head
fi

exec python app/main.py
