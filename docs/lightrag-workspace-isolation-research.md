# LightRAG 服务端多 workspace 隔离 — 调研与二期方案

> 调研日期：2026-08-13。关联：多项目隔离模块 C（一期已落地工具层 space_id 强制映射）。
>
> **⚠️ 修正（同日 gh 核实后）**：本文初稿采信搜索摘要"PR #2445 已实现全端点路由"，经 `gh api` 核实——**PR #2445 于 2026-03-06 关闭未合并**，上游 main（含 v1.5.6）`get_workspace_from_request` 仍仅 /health 一个调用点；#2698 消毒修复已含于 1.5.5；#2904 仍 open。**二期已改为 vendored 1.5.5 自研 backport 并完成**（commit `1dc080b`，diff 存档 `LightRAG/local-patches/`）。下文保留调研过程与上游事实供参考。

## 现状

| 层 | 状态 |
|---|---|
| Agent 工具层（本仓库 rag_server.py + document_tools.py） | ✅ 一期完成：`space_id` 缺省自动取会话项目，模型显式传冲突值被覆盖（`_wrap_rag_tools_with_session_space`） |
| 自研 MCP 中间层（rag_server.py） | ✅ 已把 space_id 写入 `LIGHTRAG-WORKSPACE` 请求头（连接级 + 请求级），缓存 key 含 space |
| LightRAG 服务端（vendored 1.5.5） | ❌ **假隔离**：`get_workspace_from_request` 仅 `/health` 一个调用点（lightrag_server.py:1420 定义、:2292 调用），`/query`、`/documents` 等端点全部使用启动时单例 workspace |
| LightRAG 核心库（vendored 1.5.5） | ✅ 实例级 `workspace` 字段（lightrag.py:290），存储命名空间按 workspace 隔离（Neo4j/Milvus 均支持） |

**结论：瓶颈只在 API server 层的路由，核心库能力已具备。**

## 上游进展（HKUDS/LightRAG）

- **PR #2445**（2025-12 合入）：per-request workspace 路由已实现——所有主要端点（/documents、/query、/graph、/ollama）经 header 路由到 workspace 级 LightRAG 实例（内存缓存）。我们 vendored 的 1.5.5 快照**早于**该合入。
- **Issue #2904**（2026-04）：/query 的 context assembly 曾回退默认 workspace——升级时必须确认所选版本包含此修复。
- **Issue #2698**（2026-02）：workspace 头未消毒导致 Neo4j/Memgraph Cypher 注入——升级版本必须含 sanitization（`[^a-zA-Z0-9_]` → `_`）。
- **Discussion #2745**：高规模多租户架构提案（RAGInstanceManager + LRU/TTL 实例管理）——workspace 数量大时的内存对策，企业规模下暂不需要。
- **RFC #3516**（2026-07）：workspace 级授权（阶段 2 多租户路线），含 `Vary: LIGHTRAG-WORKSPACE` 缓存安全要求。

## 二期方案（推荐）

**升级 vendored LightRAG 到包含 #2445 + #2904 修复的上游版本**，而非自行 backport：

1. 升级前在 LightRAG/.venv 跑通其自带回归（workspace 隔离测试：tests/workspace/ 已有 README_WORKSPACE_ISOLATION_TESTS.md）
2. 部署侧：RAG 实例仍单进程（192.168.60.103 或本机 9621），per-workspace 实例由服务端内存缓存管理
3. 验证清单：
   - 两 workspace 分别入库不同文档，/query 互不可见（对齐平台侧跨项目串扰 E2E）
   - workspace 头消毒（中文项目标识符会被转为 `_` 前缀+需确认唯一性——必要时平台侧先做 `_sanitize_config_key` 同款 hash 后缀）
4. 平台侧零改动：一期管道（space_id=project_identifier → LIGHTRAG-WORKSPACE 头）自动生效

**Fallback（不升级时）**：backport 工作量集中在 lightrag_server.py——实例注册表（workspace → LightRAG 懒加载缓存）+ 各端点 Depends 注入，预估 2~3 天 + 自测覆盖。

## 风险

- 内存：per-workspace 实例缓存（每实例含 embedding 模型句柄等）。项目数 <20 时可控；超出参考 #2745 加 LRU。
- 升级回归面：LightRAG 是本平台 RAG 核心依赖，升级需在 root venv 全量验证（rag_* 7 个工具 + 入库管道）。

## Sources

- [PR #2445: workspace isolation in lightrag_server](https://github.com/HKUDS/LightRAG/pull/2445)
- [Issue #2904: LIGHTRAG-WORKSPACE ignored in /query context assembly](https://github.com/HKUDS/LightRAG/issues/2904)
- [Issue #2698: Cypher injection via unsanitized LIGHTRAG-WORKSPACE header](https://github.com/HKUDS/LightRAG/issues/2698)
- [Discussion #2745: High-Scale Workspace Isolation & Multi-Tenancy Architecture](https://github.com/HKUDS/LightRAG/discussions/2745)
- [RFC #3516: Authorized API access roadmap](https://github.com/HKUDS/LightRAG/issues/3516)
- [Issue #2527: Workspace isolation clarification](https://github.com/HKUDS/LightRAG/issues/2527)
