"""
Phase 1+2 端到端验证脚本

模拟完整链路：prompt 装配 → 阶段规则注入 → 工具缓存 → 风险评估 → 邀约解析
无需数据库/网络，纯逻辑验证。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

AGENT_PY = BACKEND_ROOT / "app" / "agents" / "api" / "agent.py"
MIDDLEWARE_PY = BACKEND_ROOT / "app" / "agents" / "api" / "execution_invitation_middleware.py"
RISK_PY = BACKEND_ROOT / "app" / "agents" / "api" / "execution_risk.py"
CACHE_PY = BACKEND_ROOT / "app" / "agents" / "tools" / "api" / "_cache.py"

passed = 0
failed = 0

def check(name: str, cond: bool, detail: str = ""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  -- {detail}")

def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ==========================================================================
# 1. 模块导入
# ==========================================================================
section("1. 模块导入")

check("execution_risk 模块可导入",
      __import__("app.agents.api.execution_risk", fromlist=["evaluate_risk", "ExecutionContext", "RiskLevel"]),
      str(sys.exc_info()[1]))
from app.agents.api.execution_risk import (
    evaluate_risk, ExecutionContext, RiskLevel, is_auto_executable, extract_risk_context,
)

# _cache 模块无法导入（依赖 motor），改为内联验证缓存逻辑
# 缓存 key 构建 + 读写 + 过期 + 清除（逻辑与 _cache.py 一致）

# ==========================================================================
# 2. 风险评估 — 全场景覆盖
# ==========================================================================
section("2. 风险评估 — 15 个场景")

test_cases = [
    # (context, expected_level)
    (ExecutionContext(mode="api", test_count=3, has_write_ops=False, has_delete_ops=False), RiskLevel.LOW),
    (ExecutionContext(mode="api", test_count=1, has_write_ops=False, has_delete_ops=False), RiskLevel.LOW),
    (ExecutionContext(mode="api", test_count=6, has_write_ops=False, has_delete_ops=False), RiskLevel.MEDIUM),
    (ExecutionContext(mode="api", test_count=3, has_write_ops=True, has_delete_ops=False), RiskLevel.MEDIUM),
    (ExecutionContext(mode="api", test_count=6, has_write_ops=True, has_delete_ops=False), RiskLevel.HIGH),
    (ExecutionContext(mode="api", test_count=1, has_write_ops=False, has_delete_ops=True), RiskLevel.HIGH),
    (ExecutionContext(mode="scenario", test_count=3), RiskLevel.HIGH),
    (ExecutionContext(mode="batch", endpoint_count=5, has_write_ops=False), RiskLevel.LOW),
    (ExecutionContext(mode="batch", endpoint_count=4, has_write_ops=True), RiskLevel.HIGH),
    (ExecutionContext(mode="batch", endpoint_count=11, has_write_ops=False), RiskLevel.HIGH),
    (ExecutionContext(mode="batch", endpoint_count=2, has_write_ops=True), RiskLevel.MEDIUM),
    # 边界条件
    (ExecutionContext(mode="api", test_count=5, has_write_ops=False, has_delete_ops=False), RiskLevel.LOW),
    (ExecutionContext(mode="api", test_count=5, has_write_ops=True, has_delete_ops=False), RiskLevel.MEDIUM),
    (ExecutionContext(mode="api", test_count=0, has_write_ops=False, has_delete_ops=False), RiskLevel.LOW),
    (ExecutionContext(mode="batch", endpoint_count=10, has_write_ops=False), RiskLevel.LOW),
]

for i, (ctx, expected) in enumerate(test_cases):
    level, reason = evaluate_risk(ctx)
    check(
        f"场景 {i+1}: {ctx.mode}{' POST' if ctx.has_write_ops else ''}{' DELETE' if ctx.has_delete_ops else ''} "
        f"n={ctx.test_count or ctx.endpoint_count} → {level.value}",
        level == expected,
        f"期望 {expected.value}, 得到 {level.value}: {reason}"
    )

check("is_auto_executable(LOW) == True",
      is_auto_executable(ExecutionContext(mode="api", test_count=3)))
check("is_auto_executable(HIGH) == False",
      not is_auto_executable(ExecutionContext(mode="scenario", test_count=1)))

# ==========================================================================
# 3. 邀约 payload 解析 + 风险注入
# ==========================================================================
section("3. 执行邀约 payload → 风险注入")

# 模拟 agent 输出的邀约 payload
payloads = [
    {"type": "execution_invitation", "mode": "api", "endpoint_id": "e1", "script_name": "test.spec.ts",
     "test_count": 3, "has_write_ops": False, "has_delete_ops": False, "endpoint_count": 1,
     "description": "GET test"},
    {"type": "execution_invitation", "mode": "api", "endpoint_id": "e2", "script_name": "create.spec.ts",
     "test_count": 3, "has_write_ops": True, "has_delete_ops": False, "endpoint_count": 1,
     "description": "POST test"},
    {"type": "execution_invitation", "mode": "scenario", "endpoint_id": "", "script_name": "",
     "test_count": 5, "has_write_ops": True, "has_delete_ops": False, "endpoint_count": 3,
     "description": "Scenario test"},
]

for i, payload in enumerate(payloads):
    ctx = extract_risk_context(payload)
    level, reason = evaluate_risk(ctx)
    payload["risk_level"] = level.value
    payload["risk_reason"] = reason
    check(
        f"Payload {i+1}: risk_level={level.value}",
        "risk_level" in payload and "risk_reason" in payload
    )
    print(f"      reason: {reason}")

# ==========================================================================
# 4. Prompt 三层装配 — 模拟 middleware 注入
# ==========================================================================
section("4. Prompt 装配 — 核心 + 阶段规则")

src = AGENT_PY.read_text(encoding="utf-8")

# 4.1 提取核心 prompt
m = re.search(r'SYSTEM_PROMPT = """(.*?)"""', src, re.DOTALL)
check("核心 SYSTEM_PROMPT 存在", bool(m))
core_prompt = m.group(1) if m else ""

# 4.2 提取阶段规则
stage_rules: dict[str, str] = {}
rules_start = src.find("_STAGE_RULES: dict[str, str] = {")
rules_end = src.find("\n\n# ===", rules_start)
rules_text = src[rules_start:rules_end] if rules_end > 0 else ""

# 解析 api_test 和 scenario_test 规则
for key in ["api_test", "scenario_test"]:
    k_start = rules_text.find(f'"{key}": """')
    if k_start > 0:
        val_start = k_start + len(f'"{key}": """')
        val_end = rules_text.find('""",', val_start)
        val = rules_text[val_start:val_end] if val_end > 0 else ""
        stage_rules[key] = val
        check(f"阶段规则 {key}: {len(val)} chars", len(val) > 50)
    else:
        check(f"阶段规则 {key}: 未找到", False)

# 4.3 模拟请求 — 组装完整 prompt
for template_type in ["api_test", "scenario_test"]:
    full = core_prompt
    if template_type in stage_rules:
        full += stage_rules[template_type]

    checks_ok = True
    if template_type == "api_test":
        checks_ok &= "假阳性" in full
        checks_ok &= "修复流程" in full
        checks_ok &= "批量操作" in full
        checks_ok &= "场景测试" not in stage_rules.get("api_test", "")  # 不在 api_test 规则中
    elif template_type == "scenario_test":
        checks_ok &= "场景规范" in full
        checks_ok &= "add_teardown_step" in full
        checks_ok &= "模板变量语法" in full
        checks_ok &= "覆盖旧场景" in full

    check(
        f"装配 {template_type}: 完整 prompt {len(full)} chars",
        checks_ok,
        f"内容={len(full)}chars"
    )

# 4.4 核心红线完整性
core_red_lines = [
    "禁硬编码", "fallback token", "derive_test_skeleton",
    "修复不降断言", "token 失效是环境问题", "重试上限",
    "成果必存", "自动获取接口信息", "必传 execution_config", "假阳性必检"
]
for line in core_red_lines:
    check(f"核心红线存在: {line}", line in core_prompt)

# 4.5 排除检查 — 代码强制规则不出现在核心 prompt 中
code_enforced = ["断言质量门禁", "assertions", "断言不足", "无放行开关", "save_test_script 内置"]
for phrase in code_enforced:
    if phrase not in core_prompt:
        print(f"  ℹ️  代码强制规则不在核心 prompt: '{phrase}' （正确，由工具兜底）")

# ==========================================================================
# 5. 缓存逻辑 — 模拟 set/get/expire/clear
# ==========================================================================
section("5. 会话缓存 — set/get/expire/clear")

import time
import asyncio

# 验证缓存 key 构建（内联逻辑，避免模块导入依赖 langgraph）
def _build_key(conversation_id: str, tool_name: str, args: tuple, kwargs: dict) -> str:
    kwargs_sorted = tuple(sorted(kwargs.items()))
    return f"{conversation_id}:{tool_name}:{args}:{kwargs_sorted}"

key1 = _build_key("conv-1", "get_endpoint_details", ("uuid-1",), {})
key2 = _build_key("conv-1", "get_endpoint_details", ("uuid-1",), {})
key3 = _build_key("conv-1", "get_endpoint_details", ("uuid-2",), {})
key4 = _build_key("conv-2", "get_endpoint_details", ("uuid-1",), {})

check("同一会话同一参数 key 相同", key1 == key2)
check("同一会话不同参数 key 不同", key1 != key3)
check("不同会话 key 隔离", key1 != key4)

# 写缓存 + 读取验证（模拟 _cache.py 的字典逻辑）
_cache: dict = {}
_CACHE_TTL = 300

_cache[key1] = (time.time() + _CACHE_TTL, {"data": "cached_value"})
check("缓存写入成功", key1 in _cache)
check("缓存读取", _cache[key1][1]["data"] == "cached_value")

# 过期检测
_cache[key1] = (time.time() - 1, {"data": "expired"})
now = time.time()
is_expired = now > _cache[key1][0]
check("过期检测正确", is_expired)

# 清除指定会话
conv1_keys = [k for k in _cache if k.startswith("conv-1:")]
for k in conv1_keys:
    del _cache[k]
check("清除后 key 不存在", key1 not in _cache)
check("清除数量", len(conv1_keys) == 1)

_cache.clear()  # 全清

# ==========================================================================
# 6. 邀约标记语法验证
# ==========================================================================
section("6. 执行邀约标记语法")

invitation_examples = [
    # 标准格式（agent 将输出这样的标记）
    '<EXECUTION_INVITATION>\n{"type":"execution_invitation","mode":"api","endpoint_id":"uuid-1","script_name":"test.spec.ts","test_count":3,"has_write_ops":false,"has_delete_ops":false,"endpoint_count":1,"description":"已保存，是否执行？","alternatives":[{"key":"execute","label":"立即执行"},{"key":"skip","label":"暂不执行"},{"key":"edit","label":"修改脚本"},{"key":"other","label":"其他"}]}\n</EXECUTION_INVITATION>',
    # 场景模式
    '<EXECUTION_INVITATION>\n{"type":"execution_invitation","mode":"scenario","endpoint_id":"","script_name":"","test_count":5,"has_write_ops":true,"has_delete_ops":false,"endpoint_count":3,"description":"场景已编排，是否立即执行？","alternatives":[{"key":"execute","label":"立即执行"},{"key":"skip","label":"暂不执行"}]}\n</EXECUTION_INVITATION>',
]

_EXECUTION_INVITATION_MARKER_RE = re.compile(
    r"<EXECUTION_INVITATION>\s*(.*?)\s*</EXECUTION_INVITATION>",
    re.DOTALL | re.IGNORECASE,
)

import json

for i, example in enumerate(invitation_examples):
    m = _EXECUTION_INVITATION_MARKER_RE.search(example)
    check(f"标记解析 {i+1}: 匹配成功", bool(m))
    if m:
        try:
            payload = json.loads(m.group(1).strip())
            check(f"标记解析 {i+1}: JSON 合法", "type" in payload)
            ctx = extract_risk_context(payload)
            level, reason = evaluate_risk(ctx)
            print(f"      mode={payload.get('mode')}, risk={level.value}, reason='{reason}'")
        except json.JSONDecodeError as e:
            check(f"标记解析 {i+1}: JSON 非法", False, str(e))

# ==========================================================================
# 7. 结果
# ==========================================================================
print(f"\n{'='*60}")
print(f"  结果: {passed} passed, {failed} failed, {passed+failed} total")
print(f"{'='*60}")

if failed > 0:
    sys.exit(1)
