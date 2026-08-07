#!/usr/bin/env bash
set -euo pipefail

# 首次部署或有新提交时自动分析项目，索引缓存于 /repo/.gitnexus（持久卷）
echo "[gitnexus] analyzing project..."
cd /repo

# 启动期恰逢整栈重启/高负载时，parse worker 的 5s ready 握手易超时，
# 触发"deterministic-startup 崩溃循环"误报导致 analyze 中止。
# 索引是增量的（持久卷），重试成本很低，故失败时退避重试最多 3 次。
attempt=1
max_attempts=3
until gitnexus analyze; do
  if [ "$attempt" -ge "$max_attempts" ]; then
    echo "[gitnexus] analyze ${max_attempts} 次均失败（非致命，服务仍启动；可手动补跑: docker exec ai-test-agent-gitnexus-1 sh -c 'cd /repo && gitnexus analyze'）"
    break
  fi
  attempt=$((attempt + 1))
  echo "[gitnexus] analyze 第 $((attempt - 1)) 次失败，30s 后重试（第 ${attempt}/${max_attempts} 次）..."
  sleep 30
done

echo "[gitnexus] starting server on 0.0.0.0:4747"
exec gitnexus serve --host 0.0.0.0 --port 4747
