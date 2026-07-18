"""Web MCP Agent 提示词与工具签名回归测试。

锁定方案 B 成果：
1. 生成流程结束后主动说明产物并询问是否执行；
2. 登录类等场景使用参数化用例（data_variants）而非重复子功能；
3. 非默认 test-id 属性时使用 test.use + getByTestId；
4. create_web_function 的 business_module 必填；
5. execute_web_script 返回字段统一为 report_attachment_id（不是 report_url）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
AGENT_PY = BACKEND_ROOT / "app" / "agents" / "web_mcp" / "agent.py"
FUNCTION_TOOLS_PY = BACKEND_ROOT / "app" / "agents" / "tools" / "web" / "function_tools.py"
ARTIFACTS_TOOLS_PY = BACKEND_ROOT / "app" / "agents" / "tools" / "web" / "artifacts_tools.py"
EXECUTION_TOOLS_PY = BACKEND_ROOT / "app" / "agents" / "tools" / "web" / "execution_tools.py"
PLANNER_SKILL = PROJECT_ROOT / ".claude" / "skills" / "web_mcp" / "planner" / "SKILL.md"
CASE_DESIGNER_SKILL = PROJECT_ROOT / ".claude" / "skills" / "web_mcp" / "case-designer" / "SKILL.md"
GENERATOR_SKILL = PROJECT_ROOT / ".claude" / "skills" / "web_mcp" / "generator" / "SKILL.md"
EXECUTOR_SKILL = PROJECT_ROOT / ".claude" / "skills" / "web_mcp" / "executor" / "SKILL.md"
HEALER_SKILL = PROJECT_ROOT / ".claude" / "skills" / "web_mcp" / "healer" / "SKILL.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_system_prompt() -> str:
    src = _read(AGENT_PY)
    m = re.search(r'SYSTEM_PROMPT = """(.*?)"""', src, re.DOTALL)
    assert m, "未在 agent.py 中找到 SYSTEM_PROMPT"
    return m.group(1)


# -----------------------------------------------------------------------------
# 1. SYSTEM_PROMPT 工作流与返回字段
# -----------------------------------------------------------------------------

def test_system_prompt_asks_for_execution_after_generation():
    """生成流程末尾必须主动说明已保存并询问是否执行。"""
    prompt = _extract_system_prompt()
    assert "执行邀约" in prompt, "缺少执行邀约步骤"
    assert "尚未执行" in prompt, "未明确告知用户尚未执行"
    assert "暂无 HTML 报告" in prompt or "暂无 HTML 报告和执行摘要" in prompt


def test_system_prompt_uses_report_attachment_id_not_url():
    """SYSTEM_PROMPT 中执行工具返回字段应为 report_attachment_id。"""
    prompt = _extract_system_prompt()
    assert "report_attachment_id" in prompt, "未提及 report_attachment_id"
    assert "report_url" not in prompt, "仍使用已废弃的 report_url"


def test_system_prompt_create_web_function_requires_business_module():
    """创建功能示例必须包含 display_name、name 和 business_module。"""
    prompt = _extract_system_prompt()
    assert "create_web_function" in prompt
    assert "display_name" in prompt
    assert "business_module" in prompt
    assert "business_module 为必填" in prompt or "必须传入" in prompt


def test_system_prompt_execute_web_script_requires_sub_function_id():
    """执行示例必须包含 sub_function_id。"""
    prompt = _extract_system_prompt()
    assert "execute_web_script" in prompt
    assert "sub_function_id" in prompt


# -----------------------------------------------------------------------------
# 2. 工具层约束
# -----------------------------------------------------------------------------

def test_function_tools_business_module_is_required():
    """create_web_function 代码中 business_module 不再是 Optional。"""
    src = _read(FUNCTION_TOOLS_PY)
    # 签名中应为 business_module: str
    assert "business_module: str" in src, "business_module 未声明为 str"
    assert "business_module: Optional[str]" not in src, "business_module 仍为 Optional"
    # 存在非空校验
    assert "business_module 为必填参数" in src, "缺少 business_module 必填校验提示"


def test_artifacts_tools_supports_data_variants():
    """save_web_test_cases 校验逻辑支持参数化字段。"""
    src = _read(ARTIFACTS_TOOLS_PY)
    assert "data_variants" in src, "未识别 data_variants"
    assert "is_parameterized" in src, "未识别 is_parameterized"


def test_execution_tools_returns_report_attachment_id():
    """execute_web_script 返回说明使用 report_attachment_id。"""
    src = _read(EXECUTION_TOOLS_PY)
    assert "report_attachment_id" in src, "未返回 report_attachment_id"
    assert "report_url" not in src, "仍使用 report_url"


# -----------------------------------------------------------------------------
# 3. Skill 文档一致性
# -----------------------------------------------------------------------------

def test_planner_skill_requires_business_module():
    """planner skill 要求创建 Web 功能时必须传入 business_module。"""
    src = _read(PLANNER_SKILL)
    assert "business_module" in src
    assert "create_web_function" in src
    assert "必须作为必填参数传入" in src or "不得为空" in src


def test_planner_skill_prefers_getbytestid_for_non_default_testid():
    """planner skill 要求非默认 test-id 属性时优先使用 getByTestId。"""
    src = _read(PLANNER_SKILL)
    assert "getByTestId" in src
    assert "TestIdAttribute" in src


def test_case_designer_skill_supports_object_data_variants():
    """case-designer skill 支持 data_variants 为对象列表。"""
    src = _read(CASE_DESIGNER_SKILL)
    assert "data_variants" in src
    assert "is_parameterized" in src
    assert "对象" in src or "object" in src.lower()


def test_generator_skill_enforces_testid_attribute():
    """generator skill 要求非默认 test-id 时加 test.use。"""
    src = _read(GENERATOR_SKILL)
    assert "test.use({ testIdAttribute:" in src
    assert "getByTestId" in src


def test_generator_skill_supports_parameterized_tests():
    """generator skill 支持参数化用例生成。"""
    src = _read(GENERATOR_SKILL)
    assert "data_variants" in src
    assert "for (const data of variants)" in src or "test.each" in src


def test_executor_skill_uses_report_attachment_id():
    """executor skill 不再引用 report_url。"""
    src = _read(EXECUTOR_SKILL)
    assert "report_attachment_id" in src
    assert "report_url" not in src


def test_healer_skill_uses_report_attachment_id():
    """healer skill 不再引用 report_url。"""
    src = _read(HEALER_SKILL)
    assert "report_attachment_id" in src
    assert "report_url" not in src


# -----------------------------------------------------------------------------
# 4. 校验器行为
# -----------------------------------------------------------------------------

def test_validate_test_cases_rejects_empty_parameterized_variants():
    """参数化用例的 data_variants 为空时应被拦截。"""
    from app.agents.tools.web.artifacts_tools import _validate_test_cases

    cases = [
        {
            "name": "登录 - 多账户",
            "is_parameterized": True,
            "data_variants": [],
            "steps": [
                {"step_number": 1, "action": "navigate", "target": "https://example.com", "locator": None, "data": None},
            ],
            "verification_points": [
                {"type": "element_visible", "description": "商品列表", "locator": "getByTestId('inventory-list')", "expected": True}
            ],
        }
    ]
    error = _validate_test_cases(cases)
    assert error is not None
    assert "data_variants" in error


def test_validate_test_cases_accepts_parameterized_objects():
    """参数化用例的 data_variants 为对象列表时通过校验。"""
    from app.agents.tools.web.artifacts_tools import _validate_test_cases

    cases = [
        {
            "name": "登录 - 多账户",
            "is_parameterized": True,
            "data_variants": [
                {"username": "standard_user", "password": "secret_sauce", "expected": "success"},
                {"username": "locked_out_user", "password": "secret_sauce", "expected": "failure"},
            ],
            "steps": [
                {"step_number": 1, "action": "navigate", "target": "https://example.com", "locator": None, "data": None},
                {"step_number": 2, "action": "fill", "target": "用户名", "locator": "getByTestId('username')", "data": "{{username}}"},
            ],
            "verification_points": [
                {"type": "element_visible", "description": "商品列表", "locator": "getByTestId('inventory-list')", "expected": True}
            ],
        }
    ]
    assert _validate_test_cases(cases) is None


def test_validate_test_cases_accepts_non_parameterized():
    """普通用例仍可通过校验。"""
    from app.agents.tools.web.artifacts_tools import _validate_test_cases

    cases = [
        {
            "name": "登录成功",
            "steps": [
                {"step_number": 1, "action": "navigate", "target": "https://example.com", "locator": None, "data": None},
            ],
            "verification_points": [
                {"type": "url", "description": "验证跳转", "locator": None, "expected": "/dashboard"}
            ],
        }
    ]
    assert _validate_test_cases(cases) is None
