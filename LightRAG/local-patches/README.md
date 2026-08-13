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
