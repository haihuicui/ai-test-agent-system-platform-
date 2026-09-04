# Vendored LightRAG 本地补丁存档

## openai-empty-content-diagnostics.patch（2026-09-04，基于 vendored v1.5.5）

**背景**：103 生产实体抽取阶段 `InvalidResponseError: Received empty content
from OpenAI API` 重试耗尽致整篇文档失败（S55测试用例.xlsx，chunk-015）。
嫌疑有两个：推理模型（deepseek-v4-flash）思考烧光 completion 预算
（finish_reason=length）vs 提供商内容过滤（content_filter）——原代码
空响应时只打一句通用 error，无法区分，必须靠日志确诊。

**内容**（lightrag/llm/openai.py + 回归测试）：
- 非流式空内容分支的 error 日志补充 `finish_reason`、
  `reasoning_chars`（reasoning_content 长度）、`completion_tokens`
- 纯日志增强，不改重试策略/控制流；finish_reason=length 时同参数重试
  仍是确定性浪费，但止血靠部署侧加大预算（见下），不在本补丁范围
- 配套部署改动（非 vendored，仓库原生文件）：
  - `deploy/lightrag/.env.example` 新增
    `OPENAI_LLM_MAX_COMPLETION_TOKENS=16384`（OpenAILLMOptions 透传到
    每次 LLM 调用，给推理模型的思考+正文留足共享预算）
  - `deploy/deploy.sh` 把该键加入 sync-env 托管键列表，部署时自动补写
    进 103 的 lightrag/.env
- 测试：tests/llm/openai_impl/test_openai_empty_content_diagnostics.py
  2 例——日志含 finish_reason/尺寸；缺 reasoning/usage 时日志自身不炸

**验证**：tests/llm/openai_impl 12/12 PASS。

**重放**：
```bash
git apply LightRAG/local-patches/openai-empty-content-diagnostics.patch
```

**注意**：若确诊 finish_reason=length 仍频发，下一步是调
`OPENAI_LLM_EXTRA_BODY` 限制思考深度或换非推理抽取模型；上游若自带
空响应诊断则废弃本补丁。

## legacy-text-encoding-fallback.patch（2026-09-04，基于 vendored v1.5.5）

**背景**：上游 legacy 解析器对 txt/csv/md 等纯文本一律按 UTF-8 硬解码，
中文 Excel 导出的 GBK 编码 CSV 上传即报
`file_extraction_error: File is not valid UTF-8 encoded text`
（103 生产实测，`s52测试用例.csv`，0xd3 = GBK"测"首字节）。

**内容**（lightrag/parser/legacy/extractors.py + 回归测试）：
- `_decode_text` 改为三级解码：strict UTF-8（顺带 utf-8-sig 去 BOM）→
  strict GB18030 → charset-normalizer 统计检测 → 仍失败才抛
  LegacyExtractionError（保留原始 UTF-8 报错信息）
- **GB18030 优先于统计检测是刻意的**：实测 charset-normalizer 把短 GBK
  中文 CSV 误判为韩文 cp949 产出乱码；本部署非 UTF-8 上传绝大多数是
  GBK/GB2312。GB18030 strict 对非中文非法字节序列会抛错，此时才落到
  charset-normalizer 兜底西欧 legacy 编码
- 测试：tests/parser/test_legacy_parser.py 新增 GBK CSV 解码、UTF-8 BOM
  剥离、不可解码字节仍报错（stub 掉 charset-normalizer 保证确定性）3 例

**验证**：tests/parser 422 passed（8 个 docx golden 失败为 venv 版本漂移
存量问题，与本补丁无关——docx 子包不 import legacy）。

**重放**：
```bash
git apply LightRAG/local-patches/legacy-text-encoding-fallback.patch
```

**注意**：103 生产需重建镜像（deploy/deploy.sh）后生效；上游若合入
编码自适应解码（HKUDS/LightRAG 社区已有同类诉求）则废弃本补丁。

## workspace-request-routing.patch（2026-08-13，基于 vendored v1.5.5；8-19 扩展注册表）

**背景**：上游 PR #2445（全端点 per-request workspace 路由）2026-03 关闭未合并，
main 分支（含 v1.5.6）均仅 /health 支持 LIGHTRAG-WORKSPACE 头。本补丁在
vendored 1.5.5 上自研实现同等能力。

**内容**（lightrag/api/lightrag_server.py 单文件）：
- `WorkspaceContextMiddleware`：ASGI 层解析 LIGHTRAG-WORKSPACE 头 →
  请求级 contextvar，并在进入 endpoint 前完成实例懒加载
- workspace 实例注册表：懒加载 + per-workspace asyncio.Lock 防并发首请求；
  默认 workspace 走全局单例零开销路径
- `WorkspaceRAGProxy` / `WorkspaceDocManagerProxy`：router 闭包拿到的 rag /
  doc_manager 为代理，属性访问按 contextvar 透明路由——**router 代码零改动**
- lifespan 关闭时 finalize 全部懒加载实例
- kwargs 函数化 `_build_rag_kwargs(workspace)`：默认与懒加载实例共用构造配置
- **（8-19 新增）workspace 目录注册表**：懒加载成功即把 workspace 名登记到
  `{working_dir}/_workspaces.json`（asyncio.Lock 串行 + tmp 原子替换），
  配套 `GET /workspaces` 端点供 WebUI 切换器列举已有空间——服务端各存储
  后端命名空间布局不同，反向扫描不可靠，显式注册表与后端无关

**验证**：tests/workspace/e2e_request_routing_isolation.py（真实入库+查询）
6/6 PASS——alpha 知 A 不知 B、beta 知 B 不知 A、默认库均不知。
复跑方式：先 `python tests/workspace/e2e_request_routing_server.py`（本地轻量
存储，9622 端口），再 `python tests/workspace/e2e_request_routing_isolation.py`。
8-19 生产（103）全链路验证通过，见 docs/lightrag-workspace-isolation-research.md。

**重放**（vendored 升级后若改动被覆盖）：
```bash
# 基线为 1dc080b^（vendored 1.5.5 原版）：
git apply LightRAG/local-patches/workspace-request-routing.patch
# 冲突时手工参照本说明合入；上游若正式合入路由功能则废弃本补丁
```

**注意**：上游正在演进 pipeline ingress 新架构（#3458/#3467），未来升级
vendored 时需重新评估本补丁与上游的兼容性。

## webui-workspace-switcher.patch（2026-08-19，基于 vendored v1.5.5；同日扩展列表/创建引导）

**背景**：与 workspace-request-routing.patch 配套的前端半区。服务端按
LIGHTRAG-WORKSPACE 头路由后，WebUI 所有请求仍不带头——管理员经 WebUI
上传的文档全部落默认 workspace，与各项目知识库脱节。本补丁给 WebUI 加
workspace 切换能力。

**内容**（lightrag_webui/src，2 个新文件 + 存量小改）：
- `stores/settings.ts`：`workspace`（存消毒后值，''=默认库）+
  `workspaceHistory`（≤8）字段，persist version 20→21 迁移
- `api/lightrag.ts`：axios 拦截器 + `_buildStreamHeaders`（流式检索的原生
  fetch 路径）统一注头；分页请求 dedup key 加 workspace 命名空间；
  新增 `abortAllDocumentsPaginated()`；新增 `getWorkspaces()`（读服务端
  注册表）；`silentRefreshGuestToken` 刻意不注（/auth-status 是全局端点，
  注头只会无谓触发服务端实例懒加载）
- `services/workspace.ts`（新）：`sanitizeWorkspace`（与服务端同规则）+
  `switchWorkspace` 统一切换入口（图谱 reset/version bump、检索历史清空、
  分页 in-flight abort、标签下拉刷新、/health 重查）
- `components/WorkspaceSwitcher.tsx`（新）：Sidebar footer 常显切换器。
  下拉列表 = 服务端 /workspaces 注册表 ∪ 本地历史；输入未知名称时显示
  "首次使用时将自动创建"引导（创建即懒加载，无独立创建步骤）；
  消毒预览 + 全下划线撞库警告
- `Sidebar.tsx` footer 接入；`App.tsx` `<DocumentManager key={workspace}>`
  remount；`RetrievalView.tsx` 检索历史写入加 workspace 守卫（防进行中的
  流写回新 workspace）；`UploadDocumentsDialog.tsx` 显示目标 workspace 防呆
- `locales/*.json` ×11：`workspace.*` 键组 + 上传对话框 targetWorkspace

**验证**：`bun test` 45/45（含新增 workspace 头注入/缺省断言、跨 workspace
不 dedup、abortAll）；`bunx tsc --noEmit` 干净；本机 9621 补丁版实例 E2E
10/10（`ui/scripts/e2e_webui_workspace_switcher.mjs`，Playwright）——切换器
渲染、消毒预览、创建引导、注册表登记、localStorage 持久化、刷新后 /health
带头、切回默认库头消失。

**重放**：
```bash
# 基线为 91e3434^（vendored 原版 WebUI）：
git apply LightRAG/local-patches/webui-workspace-switcher.patch
# settings.ts migrate 链与 locales 为上游高频改动区：冲突时保留双方，
# persist 迁移版本号顺延
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
