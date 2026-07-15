#!/bin/bash
# ==============================================================================
# AI Test Agent 一键部署/更新脚本
# 用法:
#   首次部署: ./deploy.sh
#   更新部署: ./deploy.sh
# 前置: 服务器已装 Docker 24+ 和 docker compose v2
# ==============================================================================
set -euo pipefail

REPO="https://github.com/haihuicui/ai-test-agent-system-platform-.git"
DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
BRANCH="${1:-main}"
FIRST_RUN=false

cd "$DEPLOY_DIR"

# ---- 1. 拉取/更新代码 ----
if [ -d ".git" ]; then
    echo ">>> git pull origin $BRANCH ..."
    git pull origin "$BRANCH"
else
    FIRST_RUN=true
    echo ">>> 首次部署: git clone $REPO ..."
    # 本项目就是仓库本身，如果已经在根目录则跳过
    PARENT="$(dirname "$DEPLOY_DIR")"
    if [ -f "$PARENT/start_server_postgres.py" ]; then
        echo "    已在仓库根目录，跳过 clone"
    else
        git clone "$REPO" "$PARENT/ai-test-agent"
        cd "$PARENT/ai-test-agent/deploy"
    fi
fi

# ---- 2. 首次生成 .env 模板（已存在则跳过） ----
if [ ! -f ".env" ]; then
    echo ">>> 生成 .env 模板 ..."
    cp -n .env.production.example .env 2>/dev/null || true
    echo "    【重要】请编辑 deploy/.env，把里面标注 【!】 的占位值改成真实密钥，然后重新运行本脚本"
    exit 0
fi

if [ ! -f "lightrag/.env" ]; then
    echo ">>> 生成 lightrag/.env 模板 ..."
    cp -n lightrag/.env.example lightrag/.env 2>/dev/null || true
    echo "    【重要】请编辑 deploy/lightrag/.env，把里面标注 【!】 的占位值改成真实密钥，然后重新运行本脚本"
    exit 0
fi

# ---- 3. 检查是否还是占位值 ----
if grep -q "CHANGE_ME" .env 2>/dev/null; then
    echo ">>> 【警告】deploy/.env 中仍有 CHANGE_ME 占位值，请先修改再重新运行！"
    exit 1
fi
if grep -q "CHANGE_ME" lightrag/.env 2>/dev/null; then
    echo ">>> 【警告】deploy/lightrag/.env 中仍有 CHANGE_ME 占位值，请先修改再重新运行！"
    exit 1
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
    UNHEALTHY=$(docker compose ps --format json | grep -v '"Health":"healthy"' | grep -v '"Health":"exited"' | grep -vc '"Health":""' || true)
    if [ "$UNHEALTHY" -eq 0 ]; then
        echo ""
        echo "========== 部署完成 =========="
        echo "  UI:         http://\$(hostname -I | awk '{print \$1}')/"
        echo "  API 文档:   http://\$(hostname -I | awk '{print \$1}')/docs"
        echo "  知识库:     http://\$(hostname -I | awk '{print \$1}'):9621"
        echo "=============================="
        docker compose ps
        exit 0
    fi
    sleep 10
    ELAPSED=$((ELAPSED + 10))
    echo -n "."
done

echo ""
echo ">>> 部分服务仍未 healthy，请检查: docker compose ps"
docker compose ps
exit 1
