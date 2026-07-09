#!/bin/bash
# run_all.sh — 批量执行 Midscene.js Android 测试脚本
# 用法: bash run_all.sh [--retry-failed]

set -euo pipefail

RETRY_FAILED=false
if [[ "${1:-}" == "--retry-failed" ]]; then
  RETRY_FAILED=true
fi

# 测试脚本列表（按执行顺序）
SCRIPTS=(
  "tests/android/test_login_TC001.ts"
  "tests/android/test_search_TC002.ts"
  "tests/android/test_cart_TC003.ts"
  # 在此添加更多脚本...
)

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
FAILED_SCRIPTS=()
TOTAL=${#SCRIPTS[@]}
START_TIME=$(date +%s)

echo -e "${CYAN}========================================="
echo "  Midscene.js Android Test Runner"
echo "=========================================${NC}"
echo "Total scripts: $TOTAL"
echo "Started at: $(date)"
echo ""

for script in "${SCRIPTS[@]}"; do
  if [ ! -f "$script" ]; then
    echo -e "${RED}[SKIP] $script — file not found${NC}"
    continue
  fi

  echo -e "${CYAN}-----------------------------------------"
  echo "Running: $script"
  echo "-----------------------------------------${NC}"

  START_SCRIPT=$(date +%s)

  if npx tsx "$script"; then
    DURATION=$(( $(date +%s) - START_SCRIPT ))
    echo -e "${GREEN}[PASS] $script ($DURATION s)${NC}"
    ((PASS++))
  else
    DURATION=$(( $(date +%s) - START_SCRIPT ))
    echo -e "${RED}[FAIL] $script ($DURATION s)${NC}"
    ((FAIL++))
    FAILED_SCRIPTS+=("$script")
  fi
  echo ""
done

TOTAL_DURATION=$(( $(date +%s) - START_TIME ))

echo -e "${CYAN}========================================="
echo "  Results"
echo "=========================================${NC}"
echo -e "Total:   $TOTAL"
echo -e "Passed:  ${GREEN}$PASS${NC}"
echo -e "Failed:  ${RED}$FAIL${NC}"
echo -e "Duration: ${TOTAL_DURATION} s"
echo ""

if [ $FAIL -gt 0 ]; then
  echo -e "${RED}Failed scripts:${NC}"
  for f in "${FAILED_SCRIPTS[@]}"; do
    echo "  - $f"
  done
  echo ""
fi

# 写入结果日志
{
  echo "=== $(date) ==="
  echo "Total: $TOTAL, Pass: $PASS, Fail: $FAIL, Duration: ${TOTAL_DURATION}s"
  for f in "${FAILED_SCRIPTS[@]}"; do
    echo "FAILED: $f"
  done
} >> test_results.log

# 如果指定了重试失败用例
if $RETRY_FAILED && [ ${#FAILED_SCRIPTS[@]} -gt 0 ]; then
  echo -e "${CYAN}Retrying failed scripts...${NC}"
  for f in "${FAILED_SCRIPTS[@]}"; do
    echo "Retrying: $f"
    npx tsx "$f" && echo -e "${GREEN}[RETRY PASS] $f${NC}" || echo -e "${RED}[RETRY FAIL] $f${NC}"
  done
fi

exit $FAIL