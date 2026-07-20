"""API Agent 提示词质量与断言门禁回归测试。

锁定方案三（提示词瘦身）+ 两个 P0 快赢项（去 force 后门、删条件断言反模式）的成果：
1. SYSTEM_PROMPT 已瘦身，且保留全部红线；
2. 条件断言反模式（if (x !== undefined) expect(...)）只出现在"禁止"语境，不再是正面示例；
3. save_test_script 不再有 force 放行开关，WEAK 一律硬拒；
4. 断言质量门禁行为符合"每用例 ≥1 状态码 + ≥2 有效业务断言"的统一口径。
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


def _extract_system_prompt() -> str:
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
# 1. 提示词瘦身 + 红线保留
# ---------------------------------------------------------------------------

def test_system_prompt_is_slimmed():
    """瘦身目标：远低于原始 381 行，锁定在 200 行以内。"""
    prompt = _extract_system_prompt()
    line_count = prompt.count("\n") + 1
    assert line_count < 200, f"SYSTEM_PROMPT 仍有 {line_count} 行，瘦身不彻底"


@pytest.mark.parametrize("red_line", [
    "无放行开关",                       # 门禁硬性，无 force 后门
    "derive_test_skeleton",             # 用例须有确定性底座
    "禁止 fallback token",              # 禁 process.env.X || 'test'
    "修复即更新",                       # 传原 endpoint_id 更新而非新建
    "禁止硬编码",                       # 禁 URL/token/业务唯一值
    "execute_api_script_by_artifact_id",  # 按附件执行已有脚本
    "1 个状态码断言 + 2 个有效业务断言",   # 统一断言口径
    "一次对话一个场景",                  # 场景数量控制
    "场景步骤必须基于接口 schema",        # 场景必填字段
    "路径参数必须闭环映射",              # 路径参数映射
    "创建类步骤必须提取 ID 并配 teardown",  # 创建类步骤 teardown
    "分页/列表步骤必须做业务断言",        # 分页业务断言
    "模板变量语法必须规范",              # 模板变量空格
])
def test_system_prompt_keeps_red_lines(red_line: str):
    prompt = _extract_system_prompt()
    assert red_line in prompt, f"SYSTEM_PROMPT 缺失红线: {red_line}"


def test_system_prompt_does_not_endorse_conditional_assertion():
    """条件断言反模式只允许出现在"禁止"语境，不得作为正面示例。"""
    prompt = _extract_system_prompt()
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
