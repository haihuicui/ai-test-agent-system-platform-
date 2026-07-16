#!/bin/bash
# ==============================================================================
# AI Test Agent 演示环境一键部署（5 个容器，轻量级）
# 用法: bash deploy/deploy-demo.sh
# ==============================================================================
set -euo pipefail

COMPOSE_FILE="docker-compose.demo.yml"
ENV_FILE=".env.demo"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

if [ ! -d "$REPO_ROOT/.git" ]; then
    echo ">>> 错误: 请先 git clone 仓库，然后在仓库根目录执行: bash deploy/deploy-demo.sh"
    echo "    git clone https://github.com/haihuicui/ai-test-agent-system-platform-.git"
    echo "    cd ai-test-agent-system-platform- && bash deploy/deploy-demo.sh"
    exit 1
fi

cd "$REPO_ROOT/deploy"

# ---- 1. 更新代码 ----
echo ">>> git pull origin ${1:-main} ..."
git -C "$REPO_ROOT" pull origin "${1:-main}"

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
MISSING_KEYS=""
for key in DEEPSEEK_API_KEY IMAGE_PARSER_API_KEY; do
    if grep -q "${key}=CHANGE_ME" "$ENV_FILE" 2>/dev/null; then
        MISSING_KEYS="$MISSING_KEYS  $ENV_FILE: $key"
    fi
done
LIGHTRAG_ENV_FILE="lightrag/.env"
for key in LLM_BINDING_API_KEY EMBEDDING_BINDING_API_KEY RERANK_BINDING_API_KEY VLM_LLM_BINDING_API_KEY; do
    if [ -f "$LIGHTRAG_ENV_FILE" ] && grep -q "${key}=CHANGE_ME" "$LIGHTRAG_ENV_FILE" 2>/dev/null; then
        MISSING_KEYS="$MISSING_KEYS  $LIGHTRAG_ENV_FILE: $key"
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

# ---- 3.1 低内存检测与自动 swap ----
TOTAL_MEM_MB=$(free -m 2>/dev/null | awk '/Mem:/{print $2}' || echo "0")
if [ "$TOTAL_MEM_MB" -gt 0 ] && [ "$TOTAL_MEM_MB" -lt 3000 ]; then
    SWAP_MB=$(free -m 2>/dev/null | awk '/Swap:/{print $2}' || echo "0")
    if [ "$SWAP_MB" -lt 2000 ]; then
        echo ""
        echo "  =============================================="
        echo "   当前内存: ${TOTAL_MEM_MB}MB  Swap: ${SWAP_MB}MB"
        echo "   内存不足 3GB，建议开启 swap 防止 OOM"
        echo "  =============================================="
        echo ""
        read -p "  自动创建 4GB swap？(Y/n) " -r
        if [[ ! "$REPLY" =~ ^[Nn]$ ]]; then
            SWAPFILE="/swapfile"
            if [ ! -f "$SWAPFILE" ]; then
                echo "  >>> 创建 swapfile（需要 sudo）..."
                sudo fallocate -l 4G "$SWAPFILE"
                sudo chmod 600 "$SWAPFILE"
                sudo mkswap "$SWAPFILE"
                sudo swapon "$SWAPFILE"
                # 持久化
                if ! grep -q "$SWAPFILE" /etc/fstab 2>/dev/null; then
                    echo "$SWAPFILE none swap sw 0 0" | sudo tee -a /etc/fstab > /dev/null
                fi
                echo "  >>> swap 已开启（$(free -h | awk '/Swap:/{print $2}')），重启后自动挂载"
            else
                echo "  >>> $SWAPFILE 已存在，尝试 swapon..."
                sudo swapon "$SWAPFILE" 2>/dev/null || true
            fi
        fi
        export DOCLING_MEMORY_LIMIT=512m
    fi
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
