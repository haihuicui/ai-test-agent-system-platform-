"""API Agent 提示词质量与断言门禁回归测试。

锁定方案三（提示词三层瘦身）+ 阶段规则注入 + 代码兜底的成果：
1. SYSTEM_PROMPT 已瘦身（核心 ~66 行），场景规则移入 _STAGE_RULES；
2. 代码强制的规则不再占用 prompt 篇幅（由 tools/middleware 兜底）；
3. 条件断言反模式（if (x !== undefined) expect(...)）只出现在"禁止"语境；
4. save_test_script 不再有 force 放行开关，WEAK 一律硬拒；
5. 断言质量门禁行为符合"每用例 ≥1 状态码 + ≥2 有效业务断言"的统一口径。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
AGENT_PY = BACKEND_ROOT / "app" / "agents" / "api" / "agent.py"
ARTIFACTS_PY = BACKEND_ROOT / "app" / "agents" / "tools" / "api" / "artifacts_tools.py"
GENERATOR_SKILL = PROJECT_ROOT / ".claude" / "skills" / "api" / "generator" / "SKILL.md"


SCENARIO_SKILL = PROJECT_ROOT / ".claude" / "skills" / "api" / "scenario" / "SKILL.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_all_prompt_text() -> str:
    """提取 SYSTEM_PROMPT + _STAGE_RULES 的完整文本（模拟 agent 实际收到的内容）。"""
    src = _read(AGENT_PY)
    m = re.search(r'SYSTEM_PROMPT = """(.*?)"""', src, re.DOTALL)
    assert m, "未在 agent.py 中找到 SYSTEM_PROMPT"
    core = m.group(1)

    # 提取 _STAGE_RULES 字典中的所有阶段规则文本
    rules_match = re.search(r'_STAGE_RULES: dict\[str, str\] = \{(.*?)\}', src, re.DOTALL)
    stage_text = ""
    if rules_match:
        stage_text = rules_match.group(1)

    return core + "\n" + stage_text


def _extract_system_prompt() -> str:
    """仅提取核心 SYSTEM_PROMPT（用于瘦身检查）。"""
    src = _read(AGENT_PY)
    m = re.search(r'SYSTEM_PROMPT = """(.*?)"""', src, re.DOTALL)
    assert m, "未在 agent.py 中找到 SYSTEM_PROMPT"
    return m.group(1)


# 反模式：条件断言（字段不存在就跳过断言，等于没测）
_ANTIPATTERN = re.compile(r"!==\s*undefined\)\s*expect")


def _antipattern_occurrences(text: str) -> list[tuple[str, bool]]:
    """返回 (上下文, 是否为禁令语境)。禁令语境=前方 40 字符内含『禁止』或『❌』。"""
    out = []
    for m in _ANTIPATTERN.finditer(text):
        before = text[max(0, m.start() - 40):m.start()]
        is_prohibition = ("禁止" in before) or ("❌" in before)
        ctx = text[max(0, m.start() - 40):m.end() + 10].replace("\n", " ")
        out.append((ctx, is_prohibition))
    return out


# ---------------------------------------------------------------------------
# 1. 提示词三层瘦身 + 红线保留
# ---------------------------------------------------------------------------

def test_system_prompt_is_slimmed():
    """瘦身目标：核心 prompt 远低于原始 100+ 行，锁定在 80 行以内。"""
    prompt = _extract_system_prompt()
    line_count = prompt.count("\n") + 1
    assert line_count < 80, f"SYSTEM_PROMPT 仍有 {line_count} 行，瘦身不彻底"


@pytest.mark.parametrize("red_line", [
    "禁硬编码",                        # 红线 1
    "fallback token",                  # 红线 2: 禁 process.env.X || 'test'
    "derive_test_skeleton",            # 红线 3: 用例须有确定性底座
    "修复不降断言",                    # 红线 4: 保留 400/401/403 预期
    "token 失效是环境问题",            # 红线 5
    "重试上限",                        # 红线 6: 同一操作最多重试 3 次
    "成果必存",                        # 红线 7
    "自动获取接口信息",                # 红线 8
    "必传 execution_config",           # 红线 9
    "假阳性必检",                      # 红线 10
])
def test_core_prompt_keeps_critical_red_lines(red_line: str):
    """核心 SYSTEM_PROMPT 必须保留所有代码无法强制的高危红线。"""
    prompt = _extract_system_prompt()
    assert red_line in prompt, f"核心 SYSTEM_PROMPT 缺失关键红线: {red_line}"


@pytest.mark.parametrize("rule_text", [
    "场景规范",
    "request_body",
    "`{xxx}`",
    "add_teardown_step",
    "模板变量语法",
    "覆盖旧场景",
    "add_step_extractor",
])
def test_stage_rules_contain_scenario_guidelines(rule_text: str):
    """场景相关的红线已移入 _STAGE_RULES，由中间件按需注入。"""
    src = _read(AGENT_PY)
    # 提取 _STAGE_RULES 区域（从定义开始到下一个顶级定义）
    start = src.find("_STAGE_RULES: dict[str, str]")
    assert start > 0, "未找到 _STAGE_RULES 定义"
    # 找到下一个顶级赋值或类定义
    rest = src[start:]
    # _STAGE_RULES 以 } 结尾，后面跟空行和下一个定义
    end_of_rules = rest.find('\n\n# ===')
    if end_of_rules > 0:
        stage_text = rest[:end_of_rules]
    else:
        # Fallback: take the next 2000 chars
        stage_text = rest[:2000]
    assert rule_text in stage_text, f"_STAGE_RULES 缺失场景规范: {rule_text}"


def test_tool_gates_mentioned_in_core_prompt():
    """核心 prompt 必须告知 agent 工具内置门禁的存在（代码强制规则不需要展开说）。"""
    prompt = _extract_system_prompt()
    assert "工具内置门禁" in prompt, "未告知 agent 存在工具门禁"
    assert "save_test_script" in prompt, "未提及 save_test_script 门禁"
    assert "audit_script_assertions" in prompt, "未提及断言预检工具"


def test_system_prompt_does_not_endorse_conditional_assertion():
    """条件断言反模式只允许出现在"禁止"语境，不得作为正面示例。"""
    prompt = _extract_all_prompt_text()
    occurrences = _antipattern_occurrences(prompt)
    bad = [ctx for ctx, is_prohib in occurrences if not is_prohib]
    assert not bad, f"提示词中条件断言被用作正面示例: {bad}"


def test_generator_skill_does_not_endorse_conditional_assertion():
    skill = _read(GENERATOR_SKILL)
    occurrences = _antipattern_occurrences(skill)
    bad = [ctx for ctx, is_prohib in occurrences if not is_prohib]
    assert not bad, f"generator skill 中条件断言被用作正面示例: {bad}"


@pytest.mark.parametrize("phrase", [
    "检查表 A：请求体与参数",
    "检查表 B：数据依赖",
    "检查表 C：断言",
    "检查表 D：清理",
    "request_body.required",
    "target_path=\"path.siteId\"",
    "add_teardown_step",
    "page`/`size",
])
def test_scenario_skill_contains_generation_guidelines(phrase: str):
    skill = _read(SCENARIO_SKILL)
    assert phrase in skill, f"scenario skill 缺失生成规范: {phrase}"


# ---------------------------------------------------------------------------
# 2. save_test_script 去 force 后门
# ---------------------------------------------------------------------------

def test_save_test_script_has_no_force_backdoor():
    src = _read(ARTIFACTS_PY)
    assert "force: bool" not in src, "save_test_script 仍保留 force 参数"
    assert "and not force" not in src, "WEAK 仍存在 force 放行分支"
    assert "force=true" not in src.lower(), "仍存在 force=true 放行提示"


# ---------------------------------------------------------------------------
# 3. 断言质量门禁行为（统一口径：≥1 状态码 + ≥2 有效业务断言）
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def report():
    from app.agents.tools.api.artifacts_tools import _build_assertion_report
    return _build_assertion_report


def test_gate_fails_status_only(report):
    script = (
        "import { test, expect } from '@playwright/test';\n"
        "test('create', async () => {\n"
        "  const r = await fetch(u, { method: 'POST' });\n"
        "  expect(r.status).toBe(201);\n"
        "});\n"
    )
    assert report(script)["verdict"] == "FAIL"


def test_gate_weak_when_below_floor(report):
    """1 状态码 + 仅 1 个有效业务断言（低于每用例 2 个下限）→ WEAK。"""
    script = (
        "import { test, expect } from '@playwright/test';\n"
        "test('create', async () => {\n"
        "  const r = await fetch(u, { method: 'POST', body: JSON.stringify(p) });\n"
        "  expect(r.status).toBe(201);\n"
        "  const b = await r.json();\n"
        "  expect(b).toHaveProperty('data');\n"
        "});\n"
    )
    assert report(script)["verdict"] == "WEAK"


def test_gate_ok_when_meets_floor(report):
    """1 状态码 + ≥2 个有效业务断言 → OK。"""
    script = (
        "import { test, expect } from '@playwright/test';\n"
        "test('create', async () => {\n"
        "  const r = await fetch(u, { method: 'POST', body: JSON.stringify(p) });\n"
        "  expect(r.status).toBe(201);\n"
        "  const b = await r.json();\n"
        "  expect(b).toHaveProperty('data');\n"
        "  expect(b.data).toHaveProperty('id');\n"
        "  expect(typeof b.data.id).toBe('string');\n"
        "});\n"
    )
    assert report(script)["verdict"] == "OK"


def test_gate_treats_broad_truthiness_as_weak(report):
    """宽泛断言不计入有效断言：状态码 + toBeTruthy → 仍按不足处理。"""
    script = (
        "import { test, expect } from '@playwright/test';\n"
        "test('get', async () => {\n"
        "  const r = await fetch(u);\n"
        "  expect(r.status).toBe(200);\n"
        "  const b = await r.json();\n"
        "  expect(b).toBeTruthy();\n"
        "});\n"
    )
    assert report(script)["verdict"] in {"WEAK", "FAIL"}


# -----------------------------------------------------------------------------
# 4. 人机交互（HITL）规则
# -----------------------------------------------------------------------------

def test_system_prompt_asks_for_execution_after_generation():
    """生成流程末尾必须主动说明已保存并输出执行邀约标记。"""
    prompt = _extract_all_prompt_text()
    assert "执行邀约" in prompt, "缺少执行邀约步骤"
    assert "尚未执行" in prompt, "未明确告知用户尚未执行"
    assert "暂无 HTML 报告" in prompt or "暂无 HTML 测试报告和执行摘要" in prompt
    assert "<EXECUTION_INVITATION>" in prompt, "未提供执行邀约标记示例"
    assert '"type":"execution_invitation"' in prompt, "执行邀约标记类型不正确"


def test_system_prompt_prohibits_execution_without_confirmation():
    """收到用户决策后方可调用执行类工具。"""
    prompt = _extract_all_prompt_text()
    assert "[执行邀约]" in prompt or "收到用户决策" in prompt
    assert "execute_api_script" in prompt
    assert "execute_scenario" in prompt


def test_api_agent_has_hitl_for_dangerous_tools():
    """危险工具必须注册在 interrupt_on 中；执行类工具已由执行邀约面板统一 gate。"""
    from app.agents.api.agent import DANGEROUS_TOOLS_HITL

    dangerous = {
        "delete_api_script",
    }
    assert dangerous.issubset(DANGEROUS_TOOLS_HITL.keys()), (
        f"以下危险工具未配置 HITL: {dangerous - set(DANGEROUS_TOOLS_HITL.keys())}"
    )

    # 执行类工具不再通过 ToolApprovalInterrupt 二次确认
    execution_tools = {
        "execute_api_script",
        "execute_api_script_by_artifact_id",
        "run_tests",
        "execute_scenario",
        "batch_run_tests",
    }
    assert execution_tools.isdisjoint(DANGEROUS_TOOLS_HITL.keys()), (
        f"执行类工具应移出 DANGEROUS_TOOLS_HITL，避免双重确认: {execution_tools & set(DANGEROUS_TOOLS_HITL.keys())}"
    )


def test_delete_api_script_only_approve_reject():
    """删除脚本只允许批准/拒绝，不支持编辑。"""
    from app.agents.api.agent import DANGEROUS_TOOLS_HITL

    cfg = DANGEROUS_TOOLS_HITL["delete_api_script"]
    assert isinstance(cfg, dict)
    assert cfg["allowed_decisions"] == ["approve", "reject"]


def test_dangerous_tools_allow_approve_reject():
    """所有危险工具至少支持批准和拒绝。"""
    from app.agents.api.agent import DANGEROUS_TOOLS_HITL

    for name, cfg in DANGEROUS_TOOLS_HITL.items():
        assert isinstance(cfg, dict), f"{name} 的配置必须是 dict"
        assert "approve" in cfg["allowed_decisions"], f"{name} 必须允许 approve"
        assert "reject" in cfg["allowed_decisions"], f"{name} 必须允许 reject"


def test_api_agent_creation_passes_interrupt_on():
    """agent 创建代码中必须传入 interrupt_on。"""
    src = _read(AGENT_PY)
    assert "interrupt_on=DANGEROUS_TOOLS_HITL" in src, "create_agent 未传入 interrupt_on"
