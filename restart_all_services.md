# 所有服务重启指南

## 服务清单

| 服务 | 端口 | 依赖 |
|------|------|------|
| LightRAG | 9621 | 无 |
| RAG MCP Server | 8008 | LightRAG (9621) |
| 后端 (FastAPI) | 8003 | RAG MCP Server (8008) |
| Agent (LangGraph) | 2026 | 后端 (8003), Redis |
| 前端 (Next.js) | 3000 | 后端 (8003), Agent (2026) |

---

## 1. 停止旧服务

```bash
for pid in $(netstat -ano | grep -E ':3000|:8003|:2026|:8008|:9621' | grep LISTENING | awk '{print $5}' | sort -u); do
  taskkill //PID "$pid" //F 2>/dev/null
done
sleep 3
```

---

## 2. LightRAG（本地存储模式，端口 9621）

```bash
cd D:\project\ai-test-agent\LightRAG
set PYTHONIOENCODING=utf-8
set LIGHTRAG_KV_STORAGE=JsonKVStorage
set LIGHTRAG_DOC_STATUS_STORAGE=JsonDocStatusStorage
set LIGHTRAG_GRAPH_STORAGE=NetworkXStorage
set LIGHTRAG_VECTOR_STORAGE=NanoVectorDBStorage
.venv\Scripts\python -m lightrag.api.lightrag_server
```

> 后台启动：
> ```bash
> cd D:\project\ai-test-agent\LightRAG && \
> PYTHONIOENCODING=utf-8 \
> LIGHTRAG_KV_STORAGE=JsonKVStorage \
> LIGHTRAG_DOC_STATUS_STORAGE=JsonDocStatusStorage \
> LIGHTRAG_GRAPH_STORAGE=NetworkXStorage \
> LIGHTRAG_VECTOR_STORAGE=NanoVectorDBStorage \
> .venv/Scripts/python -m lightrag.api.lightrag_server > lightrag.log 2>&1 &
> ```

---

## 3. RAG MCP Server（端口 8008）

```bash
cd D:\project\ai-test-agent\backend
.venv\Scripts\python app\agents\tools\testcase\mcp\rag_server.py --rag-url http://localhost:9621 --transport sse --port 8008
```

> 后台启动：
> ```bash
> cd D:\project\ai-test-agent\backend && \
> .venv/Scripts/python app/agents/tools/testcase/mcp/rag_server.py \
>   --rag-url http://localhost:9621 \
>   --transport sse \
>   --port 8008 \
>   > rag_mcp.log 2>&1 &
> ```

---

## 4. 清理前端缓存

```bash
cd D:\project\ai-test-agent
rm -rf ui/.next
```

---

## 5. 启动后端（端口 8003）

```bash
cd D:\project\ai-test-agent\backend
..\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8003
```

> 后台启动：
> ```bash
> cd D:\project\ai-test-agent\backend && \
> ../.venv/Scripts/uvicorn.exe app.main:app --host 0.0.0.0 --port 8003 \
>   > fastapi_8003_nohup.log 2>&1 &
> ```

---

## 6. 启动 Agent（端口 2026）

```bash
cd D:\project\ai-test-agent
.venv\Scripts\python start_server_postgres.py
```

> 后台启动：
> ```bash
> cd D:\project\ai-test-agent && \
> .venv/Scripts/python start_server_postgres.py \
>   > langgraph_server.log 2>&1 &
> ```

> Agent 依赖 Redis（`REDIS_URI=redis://192.168.60.103:6379`），需确认远程 Redis 已启动。

---

## 7. 等待后端 & Agent 就绪（约 25s）

```bash
sleep 25
```

---

## 8. 启动前端（端口 3000）

```bash
cd D:\project\ai-test-agent\ui
npm run dev
```

> 后台启动：
> ```bash
> cd D:\project\ai-test-agent\ui && \
> npm run dev > next-dev.log 2>&1 &
> ```

---

## 9. 等待前端编译（约 15s）

```bash
sleep 15
```

---

## 10. 验证所有服务

```bash
echo "=== LightRAG (9621) ===" && curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:9621/ && echo ""
echo "=== RAG MCP (8008) ===" && curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:8008/ && echo ""
echo "=== 前端 (3000) ===" && curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:3000/ && echo ""
echo "=== 后端 (8003) ===" && curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:8003/ && echo ""
echo "=== Agent (2026) ===" && curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:2026/ok && echo ""
```

全部返回 200 即可。

---

## 一键后台启动脚本（完整版）

```bash
#!/bin/bash
# 项目根目录: D:\project\ai-test-agent

# 1. 停止旧服务
for pid in $(netstat -ano | grep -E ':3000|:8003|:2026|:8008|:9621' | grep LISTENING | awk '{print $5}' | sort -u); do
  taskkill //PID "$pid" //F 2>/dev/null
done
sleep 3

# 2. 启动 LightRAG
cd D:\project\ai-test-agent\LightRAG
PYTHONIOENCODING=utf-8 \
LIGHTRAG_KV_STORAGE=JsonKVStorage \
LIGHTRAG_DOC_STATUS_STORAGE=JsonDocStatusStorage \
LIGHTRAG_GRAPH_STORAGE=NetworkXStorage \
LIGHTRAG_VECTOR_STORAGE=NanoVectorDBStorage \
.venv/Scripts/python -m lightrag.api.lightrag_server > lightrag.log 2>&1 &

# 3. 启动 RAG MCP Server
cd D:\project\ai-test-agent\backend
.venv/Scripts/python app/agents/tools/testcase/mcp/rag_server.py \
  --rag-url http://localhost:9621 --transport sse --port 8008 > rag_mcp.log 2>&1 &

# 4. 清理前端缓存
cd D:\project\ai-test-agent
rm -rf ui/.next

# 5. 启动后端
cd backend && ../.venv/Scripts/uvicorn.exe app.main:app --host 0.0.0.0 --port 8003 > fastapi_8003_nohup.log 2>&1 &

# 6. 启动 Agent
cd D:\project\ai-test-agent
.venv/Scripts/python start_server_postgres.py > langgraph_server.log 2>&1 &

# 7. 等待后端 & Agent 就绪
sleep 25

# 8. 启动前端
cd ui && npm run dev > next-dev.log 2>&1 &

# 9. 等待前端编译
sleep 15

# 10. 验证
echo "=== LightRAG (9621) ===" && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9621/
echo "=== RAG MCP (8008) ===" && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8008/
echo "=== 前端 (3000) ===" && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/
echo "=== 后端 (8003) ===" && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8003/
echo "=== Agent (2026) ===" && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:2026/ok
```

---

## 注意事项

- LightRAG 使用本地存储模式（`JsonKVStorage` + `NanoVectorDBStorage`），无需外部数据库。
- RAG MCP Server 依赖 LightRAG 先启动。
- Agent 依赖远程 Redis（`redis://192.168.60.103:6379`）。
- 前端 `.env.local` 中 `NEXT_PUBLIC_API_URL=http://127.0.0.1:8003`。
- 前端 `next.config.mjs` 包含 `/langgraph/*` → `127.0.0.1:2026` 的 rewrite。
- 如端口被占用，用 `netstat -ano | grep :<端口>` 查找占用进程。
