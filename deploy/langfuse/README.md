# Langfuse 自部署运维指南

LLM 观测平台（trace 采集 / 成本看板 / 评估数据集），部署在内网 Linux 服务器。
**严禁暴露公网**——trace 内含医疗业务 PRD 等敏感数据。

## 一、首次部署（约 15 分钟）

```bash
# 1. 拷贝配置并修改所有 CHANGE_ME（密钥生成方式见 .env.example 头部注释）
cd deploy/langfuse
cp .env.example .env
vim .env

# 2. 启动（首次 ClickHouse 迁移需 1-2 分钟）
docker compose up -d
docker compose ps        # 6 个常驻服务全部 healthy + minio-init 为 Exited (0) 即正常
docker compose logs -f langfuse-web   # 观察迁移日志，出现 Ready 即可
```

## 二、验证

1. 浏览器访问 `NEXTAUTH_URL` 配置的地址（如 `http://192.168.60.X:3100`），
   用 `LANGFUSE_INIT_USER_EMAIL` / `LANGFUSE_INIT_USER_PASSWORD` 登录。
2. Settings → Projects 应已存在 `AI智能测试平台` 项目（免手工初始化），
   API Keys 与 `.env` 中的 `LANGFUSE_INIT_PROJECT_PUBLIC_KEY/SECRET_KEY` 一致。
3. **立即修改 admin 密码**（首启初始化密码仅用于首次登录）。

## 三、Agent 侧接入（本仓库 backend）

项目根目录 `.env`（gitignored）追加：

```bash
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://192.168.60.X:3100
LANGFUSE_PUBLIC_KEY=pk-lf-...        # 与 LANGFUSE_INIT_PROJECT_PUBLIC_KEY 一致
LANGFUSE_SECRET_KEY=sk-lf-...        # 与 LANGFUSE_INIT_PROJECT_SECRET_KEY 一致
LANGFUSE_TRACE_MAX_CHARS=20000
```

重启 Agent 服务后执行任意任务，Langfuse UI → Tracing → Traces 应在数秒内出现记录。

**接入实现**：`backend/app/core/tracing.py` 的 `with_langfuse_tracing()`，
在各 Agent 工厂产出 graph 处挂 LangChain 回调（Pregel.with_config 返回 Pregel 副本，
checkpointer / interrupt / history 行为不变）。设计铁律：

- **fail-open**：观测链路任何异常（未装包 / 服务不可达 / 初始化失败）都不影响 Agent 运行
- **总开关**：`LANGFUSE_ENABLED=false`（默认）时完全旁路，30 秒可回滚
- **不阻塞事件循环**：v3 SDK 后台批量上报；回调内无任何自定义 I/O

## 四、日常运维

| 操作 | 命令 |
|------|------|
| 查看状态 | `docker compose ps` |
| 重启 | `docker compose restart` |
| 升级镜像 | `docker compose pull && docker compose up -d` |
| 停止 | `docker compose down`（**不加 -v**，否则数据丢失） |

**备份**：核心数据在 3 个 volume——`langfuse_pgdata`（元数据）、
`langfuse_clickhousedata`（trace）、`langfuse_miniodata`（原始 payload）。
备份 postgres + clickhouse 即可恢复绝大部分数据。

**磁盘**：trace 持续增长，建议每周检查 `docker system df`；
可在 Langfuse UI 配置数据保留策略，或对 ClickHouse 表设 TTL。

## 五、常见问题

| 症状 | 排查 |
|------|------|
| 登录后跳转到错误地址 | `NEXTAUTH_URL` 与实际访问地址不一致，改 `.env` 后 `docker compose up -d` 重建 web 容器 |
| Traces 为空 | ① Agent 侧 `LANGFUSE_ENABLED=true`？② Agent 机器能访问 `LANGFUSE_HOST`（容器内外 localhost 含义不同）？③ 看 Agent 启动日志是否有 `[Langfuse] 观测已启用` |
| trace 数据延迟几秒出现 | 正常，SDK 后台批量上报 |
| ClickHouse 内存高 | 正常偏高；宿主机内存紧张时在 compose 中加 `deploy.resources.limits` |
| 回滚 Agent 观测 | 根 `.env` 设 `LANGFUSE_ENABLED=false`，重启 Agent 即可，无需动 Langfuse 服务 |
