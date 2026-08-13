# 沙箱隔离 + 多项目隔离 — 待办清单

> 一期已于 2026-08-13 完成并推送（沙箱 L0 `c1444d5` / 会话作用域+观测 `502109d` / RAG 映射 `9d1a069`）。
> 本清单跟踪遗留事项，按优先级排序；每项含前置条件与验收标准。

## 一、待手动验证（重启服务后执行，阻塞二期开工）

- [ ] **重启三服务**（前端 3000 / 后端 8003 / Agent 2026），激活一期改动
  - 注意：root/.venv 为 LangGraph 生产环境，psutil 已双 venv 安装，无需再装
- [ ] **白名单环境功能回归**：API 链路执行 1 条真实用例（动态 token 环境），确认 AUTH_TOKEN 注入正常、脚本能跑通
- [ ] **Web 链路回归**：web agent 执行 1 条带子功能的脚本，确认登录态注入（storageState per-project config）在白名单 env 下正常
- [ ] **金丝雀验证**：让 api agent 执行一条 `console.log(Object.keys(process.env).length)` 脚本，从报告 stdout 确认可见环境变量仅白名单内（应 < 30 个，且无 *_KEY/*_SECRET/*PASSWORD）
- [ ] **Langfuse 维度确认**：跑一轮对话后在 Langfuse UI（192.168.60.103:3100）确认 trace 带 session（=thread_id）与 metadata.project_id
  - 若 metadata 未生效（中间件写 config.metadata 被重建），fallback：改 `core/tracing.py` 的 CallbackHandler 子类从 configurable 读
- [ ] **Android 链路回归**（如有设备）：执行 1 条 midscene 脚本，确认串行锁 + midscene_run 清理不影响报告解析

## 二、二期：LightRAG 服务端真 workspace 隔离（多团队推广前必须）

调研结论：[lightrag-workspace-isolation-research.md](lightrag-workspace-isolation-research.md)（上游 PR #2445 已实现全端点路由，vendored 1.5.5 早于该合入）。

- [ ] **升级 vendored LightRAG**：目标版本必须包含 #2445（per-request 路由）+ #2904 修复（/query context 回退 bug）+ #2698 修复（Cypher 注入消毒）
- [ ] **升级回归**：LightRAG/.venv 跑其自带 workspace 隔离测试（tests/workspace/）；root venv 全量验证 rag_* 7 工具 + 入库管道
- [ ] **跨项目串扰 E2E（服务端生效版）**：两 workspace 分别入库不同文档，/query 互不可见
- [ ] **项目标识符消毒对齐**：中文项目名会被服务端转 `_`（不同项目可能退化同名）——平台侧注入 space_id 前先做 `_sanitize_config_key` 同款 hash 后缀
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
