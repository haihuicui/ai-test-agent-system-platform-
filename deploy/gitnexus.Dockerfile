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

WORKDIR /repo
EXPOSE 4747

# 启动时先分析项目，再起服务
COPY deploy/docker/entrypoint-gitnexus.sh /entrypoint-gitnexus.sh
RUN chmod +x /entrypoint-gitnexus.sh
ENTRYPOINT ["/entrypoint-gitnexus.sh"]
