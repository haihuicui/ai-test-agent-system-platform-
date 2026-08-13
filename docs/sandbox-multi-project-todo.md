# 沙箱隔离 + 多项目隔离 — 待办清单

> 一期已于 2026-08-13 完成并推送（沙箱 L0 `c1444d5` / 会话作用域+观测 `502109d` / RAG 映射 `9d1a069`）。
> 本清单跟踪遗留事项，按优先级排序；每项含前置条件与验收标准。

## 一、待手动验证（重启服务后执行，阻塞二期开工）

> 2026-08-13 已全部验证通过（修复包 `439e030`）。E2E 抓到两个真实 bug 并已修复：
> `execute_web_script` 的 execution_id 作用域、Langfuse 打标通道（改 handler 子类派生）。

- [x] **重启三服务**（前端 3000 / 后端 8003 / Agent 2026），激活一期改动 ✅ 全部 200
- [x] **白名单环境功能回归**：API 链路执行真实用例（动态 token 环境）——playwright 栈、trace helper、Authorization 注入+脱敏全部正常（用例失败为被测环境业务 404，与沙箱无关）✅
- [x] **Web 链路回归**：web agent 全链路 2/2 通过，登录态注入、test_run/报告/摘要持久化正常 ✅（期间修复 execution_id 作用域 bug）
- [x] **金丝雀验证**：子进程 62 个可见 env 键全部可解释（白名单 + npm/playwright 运行时注入），敏感键零泄露 ✅
- [x] **Langfuse 维度确认**：trace session=thread_id、tags=['project:PR-1'] ✅（经 fallback 预案：handler 子类从平台注入 metadata 派生；中间件写 config.metadata 实测不传播）
  - 已知行为（低优先级）：图级 `langfuse_tags: [agent:<name>]` 被 LangGraph Server run metadata 覆盖从未生效，graph_id 已在 metadata 中可等价使用
- [x] **Android 链路回归**：按用户指示跳过

## 二、二期：LightRAG 服务端真 workspace 隔离（多团队推广前必须）

调研结论：[lightrag-workspace-isolation-research.md](lightrag-workspace-isolation-research.md)。
**方案修正（2026-08-13）**：上游 PR #2445 关闭未合并，main/v1.5.6 均无全端点路由——
不存在可升级的 tag，改为 vendored 1.5.5 自研 backport（`1dc080b`）。

- [x] ~~**升级 vendored LightRAG**~~ → **自研 backport**：实例注册表（懒加载+per-workspace 锁）+ WorkspaceRAGProxy/DocManagerProxy（router 零改动）+ WorkspaceContextMiddleware ✅ `1dc080b`
- [x] **服务端隔离验证**：本地轻量存储实例 + 真实 LLM 入库查询 6/6 PASS（alpha 知 A 不知 B、beta 知 B 不知 A、默认库均不知）✅ 复验脚本 `LightRAG/tests/workspace/e2e_request_routing_*.py`
- [x] **diff 存档**：`LightRAG/local-patches/workspace-request-routing.patch` + README（防 vendored 升级覆盖）✅
- [x] **生产存储隔离验证**：Neo4j/Milvus 下双 workspace 6/6 PASS（本机 9621，含默认库存量零影响确认）✅ 2026-08-13
- [ ] **远程部署 backport（用户侧操作）**：103 的 lightrag 容器从本仓库 vendored 源码构建（deploy/docker-compose.yml:344），需 `git pull origin main`（≥1dc080b）后重新 `docker compose build lightrag && docker compose up -d lightrag rag-server`。**注意**：当前远程 lightrag 容器 /health 500，部署前先确认其状态
- [ ] **跨项目串扰 E2E（平台级）**：两项目并发会话检索互不可见——待 103 部署后执行；平台管道（space_id → workspace 头）已有单测覆盖，服务端隔离已验证，风险低
- [ ] **项目标识符消毒对齐**：中文项目名会被服务端转 `_`（不同项目可能退化同名）——平台侧注入 space_id 前先做 `_sanitize_config_key` 同款 hash 后缀
- [ ] **清理测试 workspace**：生产存储中的 ws_alpha/ws_beta 测试文档（隔离命名空间内，不污染默认库与 cmp_space），验证完毕后可经 WebUI 删除
- [ ] 验收：A 项目会话检索不到 B 项目文档；内存占用随 workspace 数增长可控（>20 项目参考 #2745 加 LRU）

## 三、二期：容器化执行（沙箱 L1，多团队推广前）

- [ ] **执行镜像**：预装 Node 22 + Playwright Chromium 依赖的基础镜像（`platform-test-runner`）
- [ ] **每会话一容器**：`docker run --rm --network=<内网白名单> --memory=1g --cpus=1 --pids-limit=256 -v <会话workspace>:/workspace`；env 经 `-e` 显式传白名单变量
- [ ] **网络出口白名单**：容器 network 仅可达被测环境域名
- [ ] **资源硬限制接管**：容器 `--memory` 生效后，proc_watchdog 降级为兜底保留
- [ ] **跨进程执行锁**：FastAPI(8003) 与 Agent(2026) 共享 workspace 的互斥（容器化后按容器名/标签天然隔离，评估是否仍需）
- [ ] **执行审计日志**：谁、何时、哪个项目、脚本 hash、退出码落库（企业内控前提）
- [ ] 验收：容器内脚本无法读到宿主 env、无法访问非白名单网络、内存超限被 cgroup kill 且不影响宿主与其他会话

## 四、阶段 2 配套（多团队推广时插队实现）

- [ ] **API/Web 执行 workspace 按会话切分**：`workspace_root/<project>/<thread>/` 模式推广（testcase 已验证），api_workspace_root/web_mcp_root 的产物层对齐
- [ ] **最小 RBAC**：User 模型加 role 字段（管理员/测试工程师/只读三档）
- [ ] **度量看板数据源**：Langfuse 按 project_id 聚合成本（一期打标已就位，仅需查询侧）

---

**完成定义**：一、二、三节全部勾完 = 平台具备多团队推广的安全与隔离前提。
