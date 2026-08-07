# ==============================================================================
# GitNexus 代码智能分析服务
# 构建上下文 = 项目根
# ==============================================================================
FROM node:20-bookworm-slim

# CPU 容器内无需/无法安装 CUDA 库；跳过 onnxruntime-node 的 CUDA 解压，避免 postinstall 失败
ENV ONNXRUNTIME_NODE_INSTALL_CUDA=skip

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g gitnexus@latest

# 冷启动时 worker 加载 tree-sitter 原生绑定慢，5s ready 握手超时（硬编码）会
# 误杀 worker 槽位导致 analyze 中止；放宽到 30s。升级 gitnexus 后若 sed 未命中
# 需重新核对 dist 路径与常量名。
RUN sed -i 's/WORKER_READY_TIMEOUT_MS = 5_000/WORKER_READY_TIMEOUT_MS = 30_000/' \
        /usr/local/lib/node_modules/gitnexus/dist/core/ingestion/workers/worker-pool.js \
    && grep -q 'WORKER_READY_TIMEOUT_MS = 30_000' \
        /usr/local/lib/node_modules/gitnexus/dist/core/ingestion/workers/worker-pool.js

WORKDIR /repo
EXPOSE 4747

# 启动时先分析项目，再起服务
COPY deploy/docker/entrypoint-gitnexus.sh /entrypoint-gitnexus.sh
RUN chmod +x /entrypoint-gitnexus.sh
ENTRYPOINT ["/entrypoint-gitnexus.sh"]
