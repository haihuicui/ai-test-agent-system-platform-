# AI Test Agent 部署指南（Docker Compose）

## 架构

```
浏览器 ──HTTP──> nginx:80（平台唯一对外端口）
                  ├─ /            → ui:3000        Next.js 前端
                  ├─ /api/        → backend:8001   FastAPI（SSE 一跳直达）
                  ├─ /langgraph/  → langgraph:2026 LangGraph Server（前缀剥离，SSE/WS）
                  └─ /docs|/health→ backend:8001   API 文档/健康检查
知识库管理 ──HTTP──> lightrag:9621（LIGHTRAG_PUBLISH_PORT，AUTH_ACCOUNTS 认证）

内部网络（不暴露端口）:
  postgres:5432 / mongo:27017 / redis:6379 / minio:9000(+console 9001)

RAG 服务链（testcase agent 的 RAG 工具）:
  testcase agent ─SSE→ rag-server:8008 ─HTTP→ lightrag:9621
    lightrag 存储后端: redis(KV) + postgres:lightrag库(文档状态) + neo4j:7687(图谱) + milvus:19530(向量)
    milvus 依赖: milvus-etcd(元数据) + milvus-minio(数据文件，与应用 minio 独立)
    文档解析: docling:5001（docling-serve，PDF OCR）
共享卷 backend-workspace: 挂载到 langgraph + backend 两容器（playwright 工作区/trace/报告）
```

- `langgraph` 与 `backend` 共用同一镜像（`deploy/app.Dockerfile`），仅启动命令不同。
- `lightrag` 从本地 fork 源码构建（`../LightRAG`，含空间管理功能），**不要**换成上游镜像。
- 浏览器经 nginx 同源访问全部后端，无 CORS。
- 前端 assistant_id 由 graph_id 确定性派生（uuid5），换库不变，无需动态配置。

## 前置条件

- 全新 Linux 服务器（x86_64），Docker 24+ 与 docker compose v2 插件
- **资源建议 4C16G 起步**（RAG 链较重：neo4j + milvus + etcd + docling + lightrag，镜像合计约 10GB）
- 开放 80 端口（或 `HTTP_PORT` 指定的端口）与 9621 端口（知识库 WebUI，可选）
- 构建期网络可达：Docker Hub、quay.io（etcd/docling-serve）、npm registry、nodejs.org、Debian 源、Python 包源、GitHub releases（安全工具，断网可跳过）、bun.sh（LightRAG webui 构建）
- 运行时网络可达：npm registry（security 图表 MCP）、LLM/Embedding/Rerank/VLM API、HuggingFace（docling 首次解析下载模型，默认走 hf-mirror）

```bash
# 一条命令完事（首次会自动生成 .env 模板并提示修改）
bash deploy/deploy.sh
```

部署脚本 `deploy/deploy.sh` 自动完成：git pull → 检查 .env → docker compose build → up -d → 等待 healthy。

## 手动逐步部署

如果需要细粒度控制，按以下步骤操作：

## 验证清单

| # | 检查 | 命令/操作 | 期望 |
|---|------|-----------|------|
| 1 | 容器状态 | `docker compose ps` | 全绿（minio-init 为 Exited 0） |
| 2 | LangGraph 存活 | `curl http://<服务器>/langgraph/ok` | `{"ok":true}` |
| 3 | 两套表 | `docker compose exec postgres psql -U postgres -d ai_test_platform_db -c '\dt'` | assistants/threads/checkpoints（LangGraph）+ users/projects/test_cases（业务） |
| 4 | alembic 基线 | `... psql ... -c 'select * from alembic_version'` | = head 版本号 |
| 5 | 后端存活 | `curl http://<服务器>/health` | healthy |
| 6 | 默认用户 | backend 日志 `Default test user` | 已创建（admin@test.com） |
| 7 | UI | 浏览器 `http://<服务器>/` | 页面加载，无 CORS 报错 |
| 8 | AI 对话 | UI 测试用例页发起 AI 对话 | SSE 流式正常（DevTools → eventsource） |
| 9 | web agent 冒烟 | UI 触发一条 web 自动化（如打开 example.com 断言标题） | logs 见 chromium headless 启动、执行通过 |
| 10 | playwright 版本 | `docker compose exec langgraph npx --prefix /app/backend/workspace/api playwright --version` | 1.61.1 |
| 11 | lightrag 数据库 | `docker compose exec postgres psql -U postgres -c '\\l'` | 含 lightrag 库 |
| 12 | LightRAG 健康 | `curl http://<服务器>:9621/health` | 200（含 storage status） |
| 13 | Milvus 集合 | `curl http://<服务器>:9621/api/collections`（需认证） | lightrag 集合已建 |
| 14 | RAG 工具可用 | `docker compose logs rag-server` + `docker compose logs langgraph` | rag-server 连接 lightrag 成功；testcase agent 日志无 RAG 加载失败 warning |
| 15 | docling | `docker compose exec docling curl -sf localhost:5001/health` | healthy |
| 16 | Neo4j | `docker compose exec lightrag python -c "from neo4j import GraphDatabase; d=GraphDatabase.driver('neo4j://neo4j:7687',auth=('neo4j','$NEO4J_PASSWORD')); d.verify_connectivity(); print('ok')"` 或浏览器 `http://<服务器>:7474`（需临时映射端口） | 连接成功

## RAG 链首次使用

```bash
# 1. 创建空间（WebUI）
#    管理员登录 http://<服务器>:9621 → 空间管理 → 新建空间
#    空间编码即 deploy/.env 的 RAG_SPACE_ID（默认 cmp_space）

# 2. 上传文档
#    WebUI 上传 PDF/DOCX/PPTX/TXT → lightrag 自动解析入库
#    首次解析 PDF 时 docling 会下载 OCR 模型（3-8GB，走 HF_ENDPOINT），等几分钟

# 3. 验证 testcase agent 能调用 RAG 工具
docker compose logs rag-server | tail -20   # SSE 已启动
docker compose logs langgraph | grep -i rag  # 无 "Failed to load RAG MCP tools"
```

## 升级流程

```bash
git pull
docker compose build          # 代码变更
docker compose up -d          # backend 自动 alembic upgrade head; langgraph 自动增量迁移
```

- **改 `NEXT_PUBLIC_*`** → 必须重建 ui 镜像：`docker compose build ui && docker compose up -d ui`
- **改 `API_INTERNAL_URL`** → 运行时变量，只需 `docker compose up -d ui`
- **workspace 依赖变更（@playwright/test 版本等）** → 重建 app 镜像后还需清卷（命名卷首挂后不再同步镜像内容）：

  ```bash
  docker compose down
  docker volume rm ai-test-agent_backend-workspace   # agent 产物会丢失; 业务数据在 PG/MinIO 不受影响
  docker compose up -d
  ```

## 从既有环境迁移数据库

`backend` 入口的"空库 → create_all + stamp head"分支**仅适用于全新空库**。
若迁移已有数据的库（如 192.168.60.103 的 ai_test_platform_db）：

1. 先用旧环境代码完成 `alembic stamp head`（若从未 stamp 过）或 `alembic upgrade head`
2. `pg_dump` 导出 → 恢复到新容器 postgres
3. 再启动本 compose（命中"existing DB → upgrade head"分支）

直接对从未 stamp 的旧库启动会把它标记为全部迁移已应用 → schema 漂移。

## 常见问题

- **langgraph 首启慢**：正常，59 个存储迁移 + 4 个 graph 加载，healthcheck start_period 180s。
- **lightrag 首启慢**：正常，各存储（neo4j/milvus/redis/postgres）连接初始化 + space 加载，healthcheck start_period 120s。
- **docling 首次解析慢**：PDF OCR 模型首次下载 3-8GB，走 `HF_ENDPOINT`（国内默认 hf-mirror）；可通过 `docker compose logs -f docling` 观察。下载完成后模型在 `docling-models` 卷中持久化。
- **testcase agent 没有 RAG 工具**：检查 `RAG_SPACE_ID` 与 LightRAG WebUI 创建的 space 名一致；`docker compose logs rag-server` 是否有连接错误；`docker compose logs langgraph | grep rag` 确认 `get_rag_tools` 是否失败。
- **chromium 启动失败**：确认容器 `shm_size: 1g` 未被移除；确认非 root 运行（compose 默认 USER app）。
- **MinIO console**：不对外暴露。临时访问：`ssh -L 9001:localhost:9001 <服务器>` 后 `docker compose port minio 9001`。
- **Mongo / milvus-minio 无独立认证**：仅内部网络可达，不发布端口，属预期。
- **Windows 上编辑过 .sh**：Dockerfile 已 `sed 's/\r$//'` 兜底；仓库根 `.gitattributes` 已强制 `*.sh eol=lf`。
- **Milvus 用 CPU 版**：当前 `milvusdb/milvus:v2.6.11` 不含 GPU 推理。有 GPU 可改为 `milvusdb/milvus:v2.6.11-gpu` 并加 runtime nvidia 配置（参考 LightRAG/docker-compose-full.yml）。
