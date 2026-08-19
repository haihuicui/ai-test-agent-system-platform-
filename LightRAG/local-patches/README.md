# Vendored LightRAG 本地补丁存档

## workspace-request-routing.patch（2026-08-13，基于 vendored v1.5.5）

**背景**：上游 PR #2445（全端点 per-request workspace 路由）2026-03 关闭未合并，
main 分支（含 v1.5.6）均仅 /health 支持 LIGHTRAG-WORKSPACE 头。本补丁在
vendored 1.5.5 上自研实现同等能力。

**内容**（lightrag/api/lightrag_server.py 单文件，+204/-24）：
- `WorkspaceContextMiddleware`：ASGI 层解析 LIGHTRAG-WORKSPACE 头 →
  请求级 contextvar，并在进入 endpoint 前完成实例懒加载
- workspace 实例注册表：懒加载 + per-workspace asyncio.Lock 防并发首请求；
  默认 workspace 走全局单例零开销路径
- `WorkspaceRAGProxy` / `WorkspaceDocManagerProxy`：router 闭包拿到的 rag /
  doc_manager 为代理，属性访问按 contextvar 透明路由——**router 代码零改动**
- lifespan 关闭时 finalize 全部懒加载实例
- kwargs 函数化 `_build_rag_kwargs(workspace)`：默认与懒加载实例共用构造配置

**验证**：tests/workspace/e2e_request_routing_isolation.py（真实入库+查询）
6/6 PASS——alpha 知 A 不知 B、beta 知 B 不知 A、默认库均不知。
复跑方式：先 `python tests/workspace/e2e_request_routing_server.py`（本地轻量
存储，9622 端口），再 `python tests/workspace/e2e_request_routing_isolation.py`。

**重放**（vendored 升级后若改动被覆盖）：
```bash
git apply LightRAG/local-patches/workspace-request-routing.patch
# 冲突时手工参照本说明合入；上游若正式合入路由功能则废弃本补丁
```

**注意**：上游正在演进 pipeline ingress 新架构（#3458/#3467），未来升级
vendored 时需重新评估本补丁与上游的兼容性。

## webui-workspace-switcher.patch（2026-08-19，基于 vendored v1.5.5）

**背景**：与 workspace-request-routing.patch 配套的前端半区。服务端按
LIGHTRAG-WORKSPACE 头路由后，WebUI 所有请求仍不带头——管理员经 WebUI
上传的文档全部落默认 workspace，与各项目知识库脱节。本补丁给 WebUI 加
workspace 切换能力。

**内容**（lightrag_webui/src，2 个新文件 + 8 处存量小改）：
- `stores/settings.ts`：`workspace`（存消毒后值，''=默认库）+
  `workspaceHistory`（≤8）字段，persist version 20→21 迁移
- `api/lightrag.ts`：axios 拦截器 + `_buildStreamHeaders`（流式检索的原生
  fetch 路径）统一注头；分页请求 dedup key 加 workspace 命名空间；
  新增 `abortAllDocumentsPaginated()`；`silentRefreshGuestToken` 刻意不注
  （/auth-status 是全局端点，注头只会无谓触发服务端实例懒加载）
- `services/workspace.ts`（新）：`sanitizeWorkspace`（与服务端同规则）+
  `switchWorkspace` 统一切换入口（图谱 reset/version bump、检索历史清空、
  分页 in-flight abort、标签下拉刷新、/health 重查）
- `components/WorkspaceSwitcher.tsx`（新）：Sidebar footer 常显切换器，
  自由文本输入 + 消毒预览 + 全下划线撞库警告 + 历史下拉
- `Sidebar.tsx` footer 接入；`App.tsx` `<DocumentManager key={workspace}>`
  remount；`RetrievalView.tsx` 检索历史写入加 workspace 守卫（防进行中的
  流写回新 workspace）；`UploadDocumentsDialog.tsx` 显示目标 workspace 防呆
- `locales/*.json` ×11：`workspace.*` 键组 + 上传对话框 targetWorkspace

**验证**：`bun test` 45/45（含新增 workspace 头注入/缺省断言、跨 workspace
不 dedup、abortAll）；`bunx tsc --noEmit` 干净；本机 9621 补丁版实例 E2E
7/7（`ui/scripts/e2e_webui_workspace_switcher.mjs`，Playwright）——切换器
渲染、消毒预览、localStorage 持久化、刷新后 /health 带头、切回默认库头消失。

**重放**：
```bash
git apply LightRAG/local-patches/webui-workspace-switcher.patch
# settings.ts migrate 链（version 21）与 locales 为上游高频改动区：
# 冲突时保留双方、迁移版本号顺延
```

**注意**：WebUI 构建产物进 `lightrag/api/webui/`（gitignored），Docker 镜像
构建时自动包含本补丁效果，103 重跑 deploy.sh 即生效。上游若正式合入 #2445
类功能且 WebUI 自带切换器，废弃本补丁。

## webui-workspace-switcher.patch（2026-08-19，基于 vendored v1.5.5）

**背景**：与 workspace-request-routing.patch 配套的前端半区。服务端按
`LIGHTRAG-WORKSPACE` 头路由后，WebUI 所有请求原本不带头，文档上传永远落
默认 workspace。本补丁给 WebUI 加 workspace 切换能力。

**内容**（lightrag_webui/src，20 文件 +575/-19）：
- `stores/settings.ts`：`workspace`/`workspaceHistory` 字段（persist v21 迁移），
  存**消毒后**的值（与服务端 `_sanitize_workspace_header` 同规则）
- `api/lightrag.ts`：axios 拦截器 + `_buildStreamHeaders`（流式检索的原生 fetch
  路径）统一注头；文档分页 dedup key 加 workspace 前缀（根治跨 workspace 的
  in-flight 复用）；新增 `abortAllDocumentsPaginated()`；`/auth-status` 刻意
  不注头（全局端点，避免无谓的实例懒加载）
- `services/workspace.ts`（新增）：`sanitizeWorkspace` + `switchWorkspace`
  统一切换入口（失效链：abort in-flight → 图谱 reset+version bump →
  清检索历史 → 标签下拉重取 → /health 重查）
- `components/WorkspaceSwitcher.tsx`（新增）：Sidebar footer 常显切换器，
  自由文本输入 + 消毒预览 + 全下划线撞库警告 + 历史下拉
- `App.tsx`：`<DocumentManager key={workspace}>` remount（本地状态原子重置）
- `RetrievalView.tsx`：历史写入加 workspace 守卫（防进行中的流写回新 workspace）
- `UploadDocumentsDialog.tsx`：上传对话框显示目标 workspace 防呆
- `locales/*.json`：11 语言全量 `workspace.*` 键组

**验证**：`bun test` 45/45（含新增 workspace 头/dedup/abortAll 用例）；
`bunx tsc --noEmit` 干净；本机 9621 E2E 7/7 PASS（切换器渲染、消毒预览、
localStorage 持久化、/health 带头、切回默认库头消失，复跑脚本
`ui/scripts/e2e_webui_workspace_switcher.mjs`）；服务端日志确认 PR_1
懒加载由 WebUI 请求头触发。

**重放**：
```bash
git apply LightRAG/local-patches/webui-workspace-switcher.patch
# settings.ts migrate 链与 locales 为上游高频改动区：冲突时保留双方，
# persist 迁移版本号顺延（勿复用已占版本号）。
```

**注意**：本补丁不改变任何构建配置——Docker 镜像内 `bun run build` 自动
打包新切换器。上游若正式合入 #2445 类功能且 WebUI 自带切换器，废弃本补丁。
