# LightRAG 服务端多 workspace 隔离 — 调研与二期方案

> 调研日期：2026-08-13。关联：多项目隔离模块 C（一期已落地工具层 space_id 强制映射）。
>
> **⚠️ 修正（同日 gh 核实后）**：本文初稿采信搜索摘要"PR #2445 已实现全端点路由"，经 `gh api` 核实——**PR #2445 于 2026-03-06 关闭未合并**，上游 main（含 v1.5.6）`get_workspace_from_request` 仍仅 /health 一个调用点；#2698 消毒修复已含于 1.5.5；#2904 仍 open。**二期已改为 vendored 1.5.5 自研 backport 并完成**（commit `1dc080b`，diff 存档 `LightRAG/local-patches/`）。下文保留调研过程与上游事实供参考。
>
> **📌 2026-08-18 复核（部署缺口 + 生产故障，详见文末「8-18 复核」）**：补丁当时**仅本机开发实例（127.0.0.1:9621）加载生效**；平台真实链路（Agent → 103 rag-server → 103 lightrag 容器）的 LightRAG 仍是补丁前旧镜像。
>
> **✅ 2026-08-19 闭环**：103 已重部署补丁版镜像，authenticated /health 500 故障随重部署自愈；经中间层的生产链路隔离验证**全通过**（图谱搜索层 6/6 + LLM 查询层交叉验证，详见文末「8-19 验证」）。存量数据决策同步闭环：重部署前 103 各库为空，无迁移需求。**二期全链路上线完成。**

## 现状

| 层 | 状态 |
|---|---|
| Agent 工具层（本仓库 rag_server.py + document_tools.py） | ✅ 一期完成：`space_id` 缺省自动取会话项目，模型显式传冲突值被覆盖（`_wrap_rag_tools_with_session_space`） |
| 自研 MCP 中间层（rag_server.py） | ✅ 已把 space_id 写入 `LIGHTRAG-WORKSPACE` 请求头（连接级 + 请求级），缓存 key 含 space |
| LightRAG 服务端·本机开发实例（127.0.0.1:9621，vendored 源码直跑） | ✅ 二期补丁已生效：进程 8-13 16:01 启动（晚于 1dc080b 提交），懒加载日志与探测请求双重实证 |
| LightRAG 服务端·103 生产容器（192.168.60.103:9621，docker-compose 构建） | ❌ **旧镜像（补丁前构建）**：带新 workspace 头调 /health 报 `Pipeline namespace '<ws>:pipeline_status' not found`（1.5.5 原版半路由行为）；其余端点忽略头 = 假隔离依旧 |
| LightRAG 核心库（vendored 1.5.5） | ✅ 实例级 `workspace` 字段（lightrag.py:290），存储命名空间按 workspace 隔离（Neo4j/Milvus 均支持） |

**结论：瓶颈只在 API server 层的路由，核心库能力已具备。**

## 上游进展（HKUDS/LightRAG）

- **PR #2445**（2025-12 合入）：per-request workspace 路由已实现——所有主要端点（/documents、/query、/graph、/ollama）经 header 路由到 workspace 级 LightRAG 实例（内存缓存）。我们 vendored 的 1.5.5 快照**早于**该合入。
- **Issue #2904**（2026-04）：/query 的 context assembly 曾回退默认 workspace——升级时必须确认所选版本包含此修复。
- **Issue #2698**（2026-02）：workspace 头未消毒导致 Neo4j/Memgraph Cypher 注入——升级版本必须含 sanitization（`[^a-zA-Z0-9_]` → `_`）。
- **Discussion #2745**：高规模多租户架构提案（RAGInstanceManager + LRU/TTL 实例管理）——workspace 数量大时的内存对策，企业规模下暂不需要。
- **RFC #3516**（2026-07）：workspace 级授权（阶段 2 多租户路线），含 `Vary: LIGHTRAG-WORKSPACE` 缓存安全要求。

## 二期方案（已实施：自研 backport）

~~升级 vendored LightRAG 到包含 #2445 + #2904 修复的上游版本~~ → **实际执行：vendored 1.5.5 自研 backport**（commit `1dc080b`）。上游 #2445 关闭未合并、main/v1.5.6 均无全端点路由，"等上游"不成立。

实施方案（lightrag_server.py 单文件 +204/-24，详见 `LightRAG/local-patches/README.md`）：

1. `WorkspaceContextMiddleware`：ASGI 层解析 workspace 头 → 请求级 contextvar，endpoint 前完成实例懒加载（失败 fail-open 回退默认）
2. 实例注册表：懒加载 + per-workspace 锁防并发首请求；默认 workspace 走全局单例零开销；lifespan 统一 finalize
3. `WorkspaceRAGProxy` / `WorkspaceDocManagerProxy`：router 闭包内的 rag/doc_manager 为代理，属性访问按 contextvar 透明路由——router 三个文件零改动
4. `_build_rag_kwargs` 工厂：默认与懒加载实例共用构造配置

验证：tests/workspace/e2e_request_routing_isolation.py（真实入库+查询）6/6 PASS；8-13 当天对本机 9621 复测 ws_alpha/ws_beta 通过（lightrag.log 懒加载记录佐证）。

**Fallback 段落已失效**（backport 已完成，无需再做）。

## 风险

- 内存：per-workspace 实例缓存（每实例含 embedding 模型句柄等）。项目数 <20 时可控；超出参考 #2745 加 LRU。
- 升级回归面：LightRAG 是本平台 RAG 核心依赖，升级需在 root venv 全量验证（rag_* 7 个工具 + 入库管道）。

## 8-18 复核：拓扑真相、部署缺口与生产故障

### 平台真实链路（实证）

```
Agent (LangGraph) ──SSE──> 103 rag-server:8008 ──HTTP──> 103 lightrag 容器:9621（docker 服务名 lightrag）
                              ↑ 新版中间层已在线              ↑ 补丁前旧镜像（1.5.5 原版行为）
                              （7 个工具均带 space_id 参数）
```

- **本机 127.0.0.1:9621 是开发实例**（uv cpython 直跑 vendored 源码）：补丁已加载生效——进程 8-13 16:01 启动晚于 1dc080b 提交（15:20）；全局环境无 lightrag 包，仅 vendored 目录可解析；lightrag.log 有 ws_alpha/ws_beta（8-13 E2E）与 probe_ws_routing_check（8-18 探测）懒加载记录；带新头 /health 正常、/documents 返回空，默认库不受影响。
- **平台流量从未到达本机 9621**：lightrag.log 无任何 `workspace=PR_*` 懒加载记录。
- 103 部署形态：docker-compose（`deploy/docker-compose.yml:344` 注释明确"本地 fork（含空间管理），必须从源码构建，勿换上游镜像"），build context 即 vendored `LightRAG/`。旧镜像是补丁合入前构建的——**补丁已在 GitHub main 上，103 重跑 deploy.sh 即可拿到**。

### ⚠️ 生产故障：103 authenticated /health 恒 500

8-18 探测：经 103 中间层调 `rag_health`（带/不带 space_id 均然）返回 502——上游 `http://lightrag:9621/health` 3 次重试恒 500。而同地址 guest 访问（无认证或假 token）返回 healthy；login 接口正常。结论：**1.5.5 原版 /health 的 authenticated 分支在 103 容器内恒炸**（补丁不动 /health 端点主体，重部署后大概率仍在，需查 `docker logs lightrag` 确诊）。影响面：rag_health 工具不可用；query/graph/documents 等非 /health 端点不受此故障直接影响，但 workspace 头被旧镜像忽略 → 全部落默认 workspace（假隔离）。

### 消毒冲突评估（原验证清单第 3 条第 2 项 → 已闭环）

一期管道注入的是项目 **identifier**（`PR-<n>`，DB 实证 PR-1/PR-2/PR-3），非中文项目名。消毒规则 `[^a-zA-Z0-9_]→_` 下 `PR-1→PR_1` 为双射，**无冲突，平台侧无需 `_sanitize_config_key` 同款 hash 后缀**。前提：identifier 生成规则保持 `PR-<n>` 统一格式；若未来开放自定义 identifier 且 `-`/`_` 混用（如同时存在 `PR-1` 与 `PR_1`），需重估。

### 推进清单（需 103 操作权限，本机无 SSH）

1. **103 重部署**：`cd <repo> && bash deploy/deploy.sh`（git pull 拿到 1dc080b → 重建 lightrag 镜像 → up）。部署后容器内即补丁版。 ✅ 8-19 已完成
2. **部署后验证**：✅ 8-19 全部通过，见下节
3. **存量数据归属决策**：✅ 闭环——重部署前 103 默认库与各 workspace 均为空（docs=0），无迁移需求
4. **内存观察**：103 重部署后关注 `_ws_instances` 增长（项目数 <20 可控；超出参考 #2745 加 LRU）。持续观察项

## 8-19 验证：生产链路隔离全通过

103 重部署补丁版镜像后，经 rag-server 中间层（authenticated 全链路）实测：

| 验证项 | 结果 |
|---|---|
| /health 带新 workspace 头 | ✅ 正常返回（懒加载生效，旧版报 pipeline namespace 错） |
| `rag_health` 带/不带 space_id | ✅ healthy——**authenticated /health 500 故障随重部署自愈** |
| 多 workspace 实例注册表 | ✅ PR-1/PR-2/PR-3/cmp_space 全部独立懒加载、healthy |
| 图谱搜索层交叉隔离（6 组） | ✅ 6/6 PASS：PR-1 知「登录按钮」不知「购物车」；PR-2 知「退款」不知「登录按钮」；默认库均不知 |
| LLM 查询层交叉（rag_query hybrid） | ✅ PR-1 答出登录流程（引用 pr1-login-doc.txt）；PR-2 明确「没有足够信息」，仅自述支付流程内容 |
| 默认库回归 | ✅ docs=0，未被项目数据污染 |

验证素材为部署后真实业务流量自然形成（PR-1 登录流程测试文档、PR-2 支付流程测试文档各 1 篇）——证明一期管道（会话项目 → space_id → LIGHTRAG-WORKSPACE 头）与二期服务端路由已在生产链路无缝衔接，平台侧零改动生效。

## 8-19 补充：WebUI 管理端 workspace 切换（隔离链路最后一环）

**问题**：管理员经 LightRAG 自带 WebUI（103:9621）上传文档时，WebUI 所有请求不携带 workspace 头 → 全部落默认 workspace，与各项目库脱节（用户 8-19 反馈）。

**方案**（vendored WebUI 自研，diff 存档 `local-patches/webui-workspace-switcher.patch`）：
- Sidebar footer 常显切换器：自由文本输入（服务端无 workspace 列表 API）+ 消毒预览（`PR-1`→`PR_1` 实时提示）+ 全下划线撞库警告 + 历史下拉（≤8）；localStorage 持久化
- axios 拦截器 + 流式检索 `_buildStreamHeaders` 统一注头（`/auth-status` 刻意豁免——全局端点，注头只会无谓触发服务端实例懒加载）
- 切换失效链：分页 in-flight abort（dedup key 加 workspace 命名空间根治复用）+ DocumentManager `key={workspace}` remount + 图谱 reset/version bump + 检索历史清空（含进行中流的写入守卫）+ /health 重查
- 上传对话框常显目标 workspace 防呆；i18n 11 语言全量

**验证**：bun test 45/45；tsc 干净；本机 9621 补丁版实例 Playwright E2E 7/7（`ui/scripts/e2e_webui_workspace_switcher.mjs` 可复跑）——切换器渲染、消毒预览、持久化、刷新后请求带头、切回默认库头消失。**103 重跑 deploy.sh 后生效。**

## 8-19 补充②：平台 Agent 链路端到端实证（PR-1 会话）

**脚本**：`backend/scripts/verify_rag_workspace_routing_e2e.py`（in-process make_agent 真实模型 + **真实 RAG 工具链**，context=PR-1）。

**结果 3/3 PASS**：H1 agent 发起 rag_query_data 调用；H2「登录流程」查询命中 PR_1 库特征内容（密码错误锁定 30 分钟/登录按钮，refs=pr1-login-doc.txt）；H3「支付流程」查询不含 PR_2 库内容（购物车/退款）——反向隔离成立。

**过程中发现并澄清的两个认知陷阱**：
1. **首次运行失败（落默认库）的原因**：in-process `ainvoke` 不会像平台那样把 context 合并进 config.configurable，包装器 `get_session_project()` 读不到项目标识。平台行为由 `langgraph_api/models/run.py:232-237` 保证（`context → configurable.copy()`）——修正 config 后全 PASS。**生产链路（前端 context → 平台合并 → 包装器注入）因此完整闭环**。
2. **「103 默认库为空」的精确含义**：空的是 PG doc_status（/documents 列表）；Neo4j/Milvus 里有历史入库（本机 LightRAG 曾用远程存储配置时期）的图谱数据，图谱类查询仍能命中——评估存量数据时两个维度要分开看。

## Sources

- [PR #2445: workspace isolation in lightrag_server](https://github.com/HKUDS/LightRAG/pull/2445)
- [Issue #2904: LIGHTRAG-WORKSPACE ignored in /query context assembly](https://github.com/HKUDS/LightRAG/issues/2904)
- [Issue #2698: Cypher injection via unsanitized LIGHTRAG-WORKSPACE header](https://github.com/HKUDS/LightRAG/issues/2698)
- [Discussion #2745: High-Scale Workspace Isolation & Multi-Tenancy Architecture](https://github.com/HKUDS/LightRAG/discussions/2745)
- [RFC #3516: Authorized API access roadmap](https://github.com/HKUDS/LightRAG/issues/3516)
- [Issue #2527: Workspace isolation clarification](https://github.com/HKUDS/LightRAG/issues/2527)
