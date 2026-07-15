"""断言分析器（assertion_analyzer）专项测试。

覆盖正则门禁搞不定、而结构化扫描/AST 能正确处理的场景：
多行链、嵌套括号参数、.rejects/.resolves、条件断言反模式、Python assert、
schema 校验调用、URL 中的正则字面量、字符串/注释干扰、按用例归属与下限判定。
"""
from __future__ import annotations

import pytest

from app.agents.tools.api.assertion_analyzer import (
    analyze_assertions,
    build_assertion_report,
)


def _verdict(content: str, lang: str = "typescript", fmt: str = "playwright") -> str:
    return build_assertion_report(content, lang, fmt)["verdict"]


def _metrics(content: str, lang: str = "typescript", fmt: str = "playwright") -> dict:
    return analyze_assertions(content, lang, fmt)


# ---------------------------------------------------------------------------
# JS/TS 结构扫描：解析准确性
# ---------------------------------------------------------------------------

def test_multiline_and_nested_paren_args():
    """多行 expect 链 + 参数内嵌套括号（旧正则会截断/漏判）。"""
    content = """
import { test, expect } from '@playwright/test';
test('multi', async () => {
  expect(
    response.status
  ).toBe(200);
  expect(body.data.total).toBe(
    computeTotal(1, 2)
  );
  expect(body.data.id).toBeDefined();
});
"""
    m = _metrics(content)
    assert m["total_expects"] == 3
    assert m["status_asserts"] == 1
    # computeTotal(1,2) 嵌套括号 + 非裸变量 toBeDefined 都应计为有效
    assert m["effective_asserts"] == 2
    assert m["parser"] == "structural_scan"


def test_rejects_resolves_modifiers():
    """Jest 的 .rejects/.resolves 修饰符被识别，matcher 正确归属。"""
    content = """
test('异常', async () => {
  await expect(api.post('/x', {})).rejects.toMatchObject({ response: { status: 400 } });
  await expect(api.get('/y')).resolves.toBeDefined();
});
"""
    m = _metrics(content, "javascript", "jest")
    assert m["total_expects"] == 2
    assert m["effective_asserts"] == 2


def test_negated_matcher_counted():
    content = """
test('neg', async () => {
  expect(response.status).toBe(200);
  expect(body.error).not.toBeDefined();
  expect(body.data.id).toBe('abc');
});
"""
    m = _metrics(content)
    assert m["total_expects"] == 3
    # .not.toBeDefined() 接收者为字段路径 → 有效
    assert m["effective_asserts"] == 2


def test_regex_literal_does_not_break_balance():
    """URL 拼接中的正则字面量 /\\/$/ 不应破坏括号平衡，后续断言仍被解析。"""
    content = r"""
test('url', async () => {
  const url = `${BASE_URL.replace(/\/$/, '')}/customer`;
  const response = await fetch(url);
  expect(response.status).toBe(200);
  expect(body).toHaveProperty('data');
  expect(body.data).toHaveProperty('id');
});
"""
    m = _metrics(content)
    assert m["total_expects"] == 3
    assert m["effective_asserts"] == 2


def test_expect_in_string_and_comment_ignored():
    """字符串/注释里的 expect 不应被误计。"""
    content = """
// expect(fake.status).toBe(999) 这是注释，不应计数
const tip = "expect(alsoFake).toBe(1)"; // 字符串，不应计数
test('real', async () => {
  expect(response.status).toBe(200);
  expect(body).toHaveProperty('data');
  expect(body.data).toHaveProperty('id');
});
"""
    m = _metrics(content)
    assert m["total_expects"] == 3  # 只有真实用例里的 3 个
    assert m["status_asserts"] == 1


# ---------------------------------------------------------------------------
# 条件断言反模式
# ---------------------------------------------------------------------------

def test_conditional_assertion_excluded_from_effective():
    """if (x !== undefined) expect(...) 不计入有效断言。"""
    content = """
test('c', async () => {
  expect(response.status).toBe(201);
  if (body.success !== undefined) expect(body.success).toBe(true);
});
"""
    m = _metrics(content)
    assert m["conditional_asserts"] == 1
    assert m["effective_asserts"] == 0
    # 只剩状态码 + 条件断言 → 有效为 0 → status_only → FAIL
    assert _verdict(content) == "FAIL"


def test_conditional_assertion_suggestion_present():
    content = """
test('c', async () => {
  expect(response.status).toBe(201);
  if (body.success !== undefined) expect(body.success).toBe(true);
});
"""
    r = build_assertion_report(content)
    assert any("条件断言" in s for s in r["suggestions"])


# ---------------------------------------------------------------------------
# schema 校验调用
# ---------------------------------------------------------------------------

def test_schema_validation_satisfies_structure():
    """expectSchema / ajv.validate 计为有效结构断言，status+schema 即合格。"""
    for call in ("expectSchema(body, SCHEMA);", "const ok = ajv.validate(SCHEMA, body);"):
        content = f"""
test('schema', async () => {{
  expect(response.status).toBe(200);
  {call}
}});
"""
        m = _metrics(content)
        assert m["schema_validation_calls"] >= 1, call
        assert _verdict(content) == "OK", call


# ---------------------------------------------------------------------------
# Python pytest
# ---------------------------------------------------------------------------

def test_python_assert_classification():
    content = """
import pytest

def test_login_success():
    r = client.post("/login", json={"u": "a"})
    assert r.status_code == 200
    data = r.json()
    assert "token" in data
    assert isinstance(data["token"], str)

def test_login_invalid():
    r = client.post("/login", json={})
    assert r.status_code == 401
    assert "error" in r.json()
    assert r.json()["error"] is not None
"""
    m = _metrics(content, "python", "pytest")
    assert m["parser"] == "python_ast"
    assert m["total_tests"] == 2
    assert m["status_asserts"] == 2
    # 每个用例 2 个有效断言 → OK
    assert _verdict(content, "python", "pytest") == "OK"


def test_python_pytest_raises_counts():
    content = """
import pytest

def test_a():
    assert r.status_code == 200
    assert "id" in data
    with pytest.raises(ValueError):
        raise ValueError("x")
"""
    m = _metrics(content, "python", "pytest")
    assert m["effective_asserts"] == 2  # in 成员 + raises


def test_python_bare_truthiness_is_weak():
    content = """
def test_a():
    assert r.status_code == 200
    assert data
"""
    m = _metrics(content, "python", "pytest")
    assert m["weak_asserts"] == 1
    assert m["effective_asserts"] == 0
    assert _verdict(content, "python", "pytest") == "FAIL"


# ---------------------------------------------------------------------------
# 按用例归属与下限判定
# ---------------------------------------------------------------------------

def test_per_test_thin_named():
    content = """
test('good case', async () => {
  expect(r.status).toBe(200);
  expect(b).toHaveProperty('data');
  expect(b.data).toHaveProperty('id');
});
test('thin case', async () => {
  expect(r2.status).toBe(200);
  expect(b2).toHaveProperty('data');
});
"""
    m = _metrics(content)
    assert m["thin_tests"] == ["thin case"]
    assert _verdict(content) == "WEAK"


def test_security_test_exempt_not_penalized():
    """安全/删除类用例（只有状态码）按名豁免，不拖低整体判定。"""
    content = """
test('成功场景', async () => {
  expect(r.status).toBe(200);
  expect(b).toHaveProperty('data');
  expect(b.data).toHaveProperty('id');
});
test('安全测试 - 认证失败', async () => {
  expect([401, 403]).toContain(response.status);
});
"""
    assert _verdict(content) == "OK"


def test_delete_204_exempt():
    content = """
test('创建并删除', async () => {
  expect(r.status).toBe(201);
  expect(b).toHaveProperty('id');
  expect(typeof b.id).toBe('string');
});
test('删除 - 204', async () => {
  expect(r.status).toBe(204);
});
"""
    assert _verdict(content) == "OK"


# ---------------------------------------------------------------------------
# 降级与边界
# ---------------------------------------------------------------------------

def test_empty_script_fails():
    assert _verdict("import { test } from '@playwright/test';") == "FAIL"


def test_postman_not_applicable():
    m = _metrics('{"info": {}}', "json", "postman")
    assert m["parser"] == "n/a"
    assert m["weak"] is False


def test_python_content_sniffing():
    """未显式传 language 时，按内容嗅探出 Python。"""
    content = "def test_x():\n    assert r.status_code == 200\n    assert 'id' in d\n    assert isinstance(d['id'], int)"
    m = _metrics(content)  # 默认 typescript/playwright
    assert m["parser"] == "python_ast"
