# syntax=docker/dockerfile:1
# ==============================================================================
# AI Test Agent 前端镜像（Next.js 14）
# 构建上下文 = 项目根目录（.dockerignore 已排除 ui/node_modules、ui/.next）
# NEXT_PUBLIC_* 构建期内联，来自 compose build.args；修改后必须重建镜像
# ==============================================================================

# ---- deps: 安装依赖（package-lock 独立层，缓存友好） ------------------------
FROM node:20-bookworm-slim AS deps
WORKDIR /app
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund

# ---- builder: 构建 ----------------------------------------------------------
FROM node:20-bookworm-slim AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY ui/ ./
# NEXT_PUBLIC_* 构建期内联进客户端 bundle
ARG NEXT_PUBLIC_LANGGRAPH_API_URL
ARG NEXT_PUBLIC_API_URL=""
ARG NEXT_PUBLIC_TESTCASE_GENERATOR_ASSISTANT_ID=testcase_generator_agent
ENV NEXT_PUBLIC_LANGGRAPH_API_URL=$NEXT_PUBLIC_LANGGRAPH_API_URL \
    NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_TESTCASE_GENERATOR_ASSISTANT_ID=$NEXT_PUBLIC_TESTCASE_GENERATOR_ASSISTANT_ID
RUN npm run build

# ---- runner: 生产运行 --------------------------------------------------------
FROM node:20-bookworm-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
RUN groupadd --system nodejs && useradd --system --gid nodejs nextjs
COPY --from=builder /app/package.json      ./package.json
COPY --from=builder /app/next.config.mjs   ./next.config.mjs
COPY --from=builder /app/public            ./public
COPY --from=builder /app/.next             ./.next
COPY --from=deps    /app/node_modules      ./node_modules
USER nextjs
EXPOSE 3000
# next start 默认 0.0.0.0:3000；启动时重新求值 next.config.mjs，
# 因此 API_INTERNAL_URL（rewrites 目标）是运行时变量，改它无需重建镜像
CMD ["npm", "start"]
