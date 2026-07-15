#!/bin/bash
# ==============================================================================
# AI Test Agent 一键部署/更新脚本
# 用法:
#   首次: bash deploy/deploy.sh
#   更新: bash deploy/deploy.sh
# 首次运行自动生成随机密码，只需手动填 API key（DeepSeek/DashScope/火山引擎）
# ==============================================================================
set -euo pipefail

REPO="https://github.com/haihuicui/ai-test-agent-system-platform-.git"
DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
BRANCH="${1:-main}"

cd "$DEPLOY_DIR"

# ---- 1. 拉取/更新代码 ----
# 从 deploy/ 回到项目根判断是否已在仓库中
REPO_ROOT="$(dirname "$DEPLOY_DIR")"
if [ -d "$REPO_ROOT/.git" ]; then
    echo ">>> git pull origin $BRANCH ..."
    git -C "$REPO_ROOT" pull origin "$BRANCH"
    cd "$REPO_ROOT/deploy"
else
    echo ">>> 首次部署: git clone $REPO ..."
    CLONE_DIR="${HOME}/ai-test-agent"
    git clone "$REPO" "$CLONE_DIR"
    cd "$CLONE_DIR/deploy"
    DEPLOY_DIR="$CLONE_DIR/deploy"
    echo "    代码已克隆到 $CLONE_DIR"
fi

# ---- 2. 首次生成 .env 并自动填充随机密码 ----

# 2.1 先统一生成所有共享密码
PGPASS="$(openssl rand -hex 16)"
RAG_PASS="$(openssl rand -hex 12)"
NEO4J_PASS="$(openssl rand -hex 16)"

# 2.2 生成 .env（如果不存在）
if [ ! -f ".env" ]; then
    echo ">>> 生成 .env（自动填充随机密码）..."
    cp .env.production.example .env

    SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    [ -z "$SERVER_IP" ] && SERVER_IP="127.0.0.1"

    sed -i.bak \
        -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PGPASS}|" \
        -e "s|^MINIO_ACCESS_KEY=.*|MINIO_ACCESS_KEY=minioadmin|" \
        -e "s|^MINIO_SECRET_KEY=.*|MINIO_SECRET_KEY=$(openssl rand -hex 16)|" \
        -e "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|" \
        -e "s|^TESTAGENT_SECRET_KEY=.*|TESTAGENT_SECRET_KEY=$(python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())" 2>/dev/null || echo "auto-$(openssl rand -hex 32)")|" \
        -e "s|^RAG_PASSWORD=.*|RAG_PASSWORD=${RAG_PASS}|" \
        -e "s|^NEO4J_PASSWORD=.*|NEO4J_PASSWORD=${NEO4J_PASS}|" \
        -e "s|http://AUTO_DETECT_IP/langgraph|http://${SERVER_IP}/langgraph|" \
        .env
    rm -f .env.bak

    # 兜底：干掉所有残留 __AUTO__
    if grep -q "__AUTO__" .env 2>/dev/null; then
        echo "    【警告】.env 仍有 __AUTO__ 残留，部分配置需手动补全"
    fi
fi

# 2.3 生成 lightrag/.env（如果不存在）
if [ ! -f "lightrag/.env" ]; then
    echo ">>> 生成 lightrag/.env（自动填充随机密码）..."
    cp lightrag/.env.example lightrag/.env

    LIGHTRAG_TOKEN="$(openssl rand -hex 32)"

    sed -i.bak \
        -e "s|^AUTH_ACCOUNTS=.*|AUTH_ACCOUNTS='admin:${RAG_PASS}'|" \
        -e "s|^TOKEN_SECRET=.*|TOKEN_SECRET=${LIGHTRAG_TOKEN}|" \
        -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PGPASS}|" \
        -e "s|^NEO4J_PASSWORD=.*|NEO4J_PASSWORD=${NEO4J_PASS}|" \
        lightrag/.env
    rm -f lightrag/.env.bak
fi

# ---- 3. 检查 API key ----
MISSING_KEYS=""
for key in DEEPSEEK_API_KEY IMAGE_PARSER_API_KEY; do
    if grep -q "${key}=CHANGE_ME" .env 2>/dev/null; then
        MISSING_KEYS="$MISSING_KEYS  deploy/.env: $key"
    fi
done
for key in LLM_BINDING_API_KEY EMBEDDING_BINDING_API_KEY RERANK_BINDING_API_KEY VLM_LLM_BINDING_API_KEY; do
    if grep -q "${key}=CHANGE_ME" lightrag/.env 2>/dev/null; then
        MISSING_KEYS="$MISSING_KEYS  deploy/lightrag/.env: $key"
    fi
done

if [ -n "$MISSING_KEYS" ]; then
    echo ""
    echo "  =============================================="
    echo "   以下 API key 尚未填写（服务可启动，对应功能不可用）："
    echo "$MISSING_KEYS"
    echo "  =============================================="
    echo ""
fi

# ---- 4. 构建 ----
echo ">>> docker compose build ..."
docker compose build

# ---- 5. 启动 ----
echo ">>> docker compose up -d ..."
docker compose up -d

# ---- 6. 等待健康检查 ----
echo ">>> 等待服务就绪（最多 300s）..."
TIMEOUT=300
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    UNHEALTHY=$(docker compose ps --format json 2>/dev/null | grep -v '"Health":"healthy"' | grep -v '"Health":"exited"' | grep -vc '"Health":""' || echo "0")
    if [ "$UNHEALTHY" -le 0 ]; then
        SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
        [ -z "$SERVER_IP" ] && SERVER_IP="127.0.0.1"
        echo ""
        echo "========== 部署完成 =========="
        echo "  UI:         http://${SERVER_IP}/"
        echo "  API 文档:   http://${SERVER_IP}/docs"
        echo "  知识库:     http://${SERVER_IP}:9621"
        echo "=============================="
        docker compose ps
        exit 0
    fi
    sleep 10
    ELAPSED=$((ELAPSED + 10))
    echo -n "."
done

echo ""
echo ">>> 部分服务仍未 healthy，请检查: docker compose logs <服务名>"
docker compose ps
exit 1
