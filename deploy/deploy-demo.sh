#!/bin/bash
# ==============================================================================
# AI Test Agent 演示环境一键部署（5 个容器，轻量级）
# 用法: bash deploy/deploy-demo.sh
# ==============================================================================
set -euo pipefail

REPO="https://github.com/haihuicui/ai-test-agent-system-platform-.git"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$SCRIPT_DIR"
COMPOSE_FILE="docker-compose.demo.yml"
ENV_FILE=".env.demo"
BRANCH="${1:-main}"

cd "$DEPLOY_DIR"

# ---- 1. 拉取/更新代码 ----
REPO_ROOT="$(dirname "$DEPLOY_DIR")"
if [ -d "$REPO_ROOT/.git" ]; then
    echo ">>> git pull origin $BRANCH ..."
    git -C "$REPO_ROOT" pull origin "$BRANCH"
    cd "$REPO_ROOT/deploy"
else
    echo ">>> 首次部署: git clone $REPO ..."
    CLONE_DIR="${HOME}/ai-test-agent-demo"
    git clone "$REPO" "$CLONE_DIR"
    cd "$CLONE_DIR/deploy"
    DEPLOY_DIR="$CLONE_DIR/deploy"
    echo "    代码已克隆到 $CLONE_DIR"
fi

# ---- 2. 首次生成 demo .env ----
RAG_PASS="$(openssl rand -hex 12)"

if [ ! -f "$ENV_FILE" ]; then
    echo ">>> 生成 $ENV_FILE（自动填充随机密码）..."
    cp .env.demo.example "$ENV_FILE"

    SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    [ -z "$SERVER_IP" ] && SERVER_IP="127.0.0.1"

    PGPASS="$(openssl rand -hex 16)"
    sed -i.bak \
        -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PGPASS}|" \
        -e "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|" \
        -e "s|^TESTAGENT_SECRET_KEY=.*|TESTAGENT_SECRET_KEY=$(python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())" 2>/dev/null || echo "demo-$(openssl rand -hex 32)")|" \
        -e "s|^RAG_PASSWORD=.*|RAG_PASSWORD=${RAG_PASS}|" \
        -e "s|http://AUTO_DETECT_IP/langgraph|http://${SERVER_IP}/langgraph|" \
        "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
fi

# ---- 2.1 生成 lightrag/.env（从 env.demo 模板复制，自动填充密码） ----
LIGHTRAG_ENV="lightrag/.env"
if [ ! -f "$LIGHTRAG_ENV" ]; then
    echo ">>> 生成 $LIGHTRAG_ENV（自动填充随机密码）..."
    cp lightrag/env.demo "$LIGHTRAG_ENV"
    LIGHTRAG_TOKEN="$(openssl rand -hex 32)"
    sed -i.bak \
        -e "s/^AUTH_ACCOUNTS=.*/AUTH_ACCOUNTS='admin:${RAG_PASS}'/" \
        -e "s/^TOKEN_SECRET=.*/TOKEN_SECRET=${LIGHTRAG_TOKEN}/" \
        "$LIGHTRAG_ENV"
    rm -f "$LIGHTRAG_ENV.bak"
fi

# ---- 3. 检查 API key ----
if grep -q "CHANGE_ME" "$ENV_FILE" 2>/dev/null; then
    echo ""
    echo "  =============================================="
    echo "   API key 尚未填写（服务可启动，AI 功能不可用）"
    echo "   编辑 $ENV_FILE 修改 DEEPSEEK_API_KEY"
    echo "  =============================================="
    echo ""
fi

# ---- 4. 构建 ----
echo ">>> docker compose -f $COMPOSE_FILE --env-file $ENV_FILE build ..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build

# ---- 5. 启动 ----
echo ">>> docker compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d ..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

# ---- 6. 等 healthy ----
echo ">>> 等待服务就绪..."
TIMEOUT=180
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    UNHEALTHY=$(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps --format json 2>/dev/null | grep -v '"Health":"healthy"' | grep -v '"Health":"exited"' | grep -vc '"Health":""' || echo "0")
    if [ "$UNHEALTHY" -le 0 ]; then
        SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
        [ -z "$SERVER_IP" ] && SERVER_IP="127.0.0.1"
        echo ""
        echo "========== 演示环境就绪 =========="
        echo "  UI:   http://${SERVER_IP}/"
        echo "  API 文档: http://${SERVER_IP}/docs"
        echo "  容器数: 5（postgres + langgraph(inmem) + backend + ui + nginx）"
        echo "=============================="
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
        exit 0
    fi
    sleep 10
    ELAPSED=$((ELAPSED + 10))
    echo -n "."
done

echo ""
echo ">>> 部分服务未就绪:"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
exit 1
