# ==============================================================================
# GitNexus 代码智能分析服务
# 构建上下文 = 项目根
# ==============================================================================
FROM node:20-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# 预装 gitnexus 到全局，避免容器启动时每次 npx 下载
RUN npm install -g gitnexus@latest

WORKDIR /repo
EXPOSE 4747

CMD ["gitnexus", "serve", "--host", "0.0.0.0", "--port", "4747"]
