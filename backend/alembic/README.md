# 数据库迁移（Alembic）

本目录承载所有 PostgreSQL schema 的版本化迁移。

## 工作流

### 首次本地准备

```bash
cd backend
pip install -e .          # 或 uv pip install -e .
alembic upgrade head      # 把空库升级到最新版本
```

### 增量修改 model 后

1. 在 `app/models/*.py` 增删字段。
2. 自动生成迁移脚本：
   ```bash
   alembic revision --autogenerate -m "describe change"
   ```
3. **必须**人工 review 生成的脚本（PG 枚举、JSONB default、自定义 server_default 等
   alembic 有时无法 100% 自动捕获）。
4. 应用迁移：
   ```bash
   alembic upgrade head
   ```

### 回滚

```bash
alembic downgrade -1
```

## 设计约定

- 一律使用同步 psycopg2 URL（`settings.postgres_sync_url`），异步引擎留给业务运行时。
- 所有 model 通过 `app.models.__init__` 集中导入，`env.py` 触发 `Base.metadata` 加载。
- `app.config.database.init_db()` 仅用于开发态 / 单元测试快速建表，生产部署一律用 alembic。
- 文件名格式：`YYYY_MM_DD_HHMM-<rev>_<slug>.py`。
