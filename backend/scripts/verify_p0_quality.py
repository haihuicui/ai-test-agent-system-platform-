"""独立验证脚本：质量扫描 + 用例校验逻辑"""

import re

# ===== 从 artifacts_tools.py 复制的规则和函数 =====

_SCRIPT_QUALITY_RULES = [
    {
        "id": "DEPRECATED_DOLLAR",
        "severity": "error",
        "pattern": r"page\.\$\(['\"]",
        "message": "deprecated page.$() API",
        "fix": "replace with page.locator()",
    },
    {
        "id": "HARD_WAIT_LONG",
        "severity": "warning",
        "pattern": r'await\s+page\.waitForTimeout\(\s*(\d{4,})\s*\)',
        "message": "hardcoded wait >1s",
        "fix": "use semantic waits",
    },
    {
        "id": "UNSAFE_CLICK_NO_WAIT",
        "severity": "warning",
        "pattern": r'\.click\(\s*\)\s*;\s*\n\s*await\s+expect',
        "message": "click then assert without wait",
        "fix": "add waitForLoadState between click and assert",
    },
    {
        "id": "TEXTCONTENT_ASSERTION",
        "severity": "info",
        "pattern": r'expect\(.*?\.textContent\(\)\)',
        "message": "using textContent() for assertion",
        "fix": "use toHaveText() instead",
    },
    {
        "id": "MISSING_BEFOREEACH_ISOLATION",
        "severity": "info",
        "pattern": r"test\.describe\(\s*['\"].*?['\"]\s*,\s*\(\s*\)\s*=>\s*\{",
        "message": "test.describe without beforeEach",
        "fix": "add beforeEach for state isolation",
        "_require_before_each_absent": True,
    },
    {
        "id": "CSS_SELECTOR_ONLY",
        "severity": "warning",
        "pattern": r"page\.locator\(\s*['\"](\.|#)[^'\"]+['\"]\s*\)",
        "message": "pure CSS class/id selector",
        "fix": "use semantic locators",
    },
    {
        "id": "NO_SOFT_ASSERTION",
        "severity": "info",
        "pattern": r'expect\(.*?\)\.(toBe|toHave|toContain)',
        "message": "consider expect.soft() for independent assertions",
        "fix": "replace independent expect() with expect.soft()",
        "_require_no_soft_on_line": True,
    },
    {
        "id": "NO_AUTO_RETRY",
        "severity": "info",
        "pattern": r"const\s+\w+\s*=\s*await\s+page\.\$",
        "message": "saving element handle to variable",
        "fix": "do not save locator references, chain calls directly",
    },
]


def scan_quality(script_content):
    severity_order = {"error": 0, "warning": 1, "info": 2}
    issues = []
    for rule in _SCRIPT_QUALITY_RULES:
        # Secondary check: only report MISSING_BEFOREEACH_ISOLATION if test.beforeEach is absent
        if rule.get("_require_before_each_absent"):
            if re.search(r"test\.beforeEach\s*\(", script_content):
                continue

        for match in re.finditer(rule["pattern"], script_content, re.MULTILINE):
            # Secondary check: skip lines that already use expect.soft
            if rule.get("_require_no_soft_on_line"):
                line_start = script_content.rfind("\n", 0, match.start()) + 1
                line_end = script_content.find("\n", match.end())
                if line_end == -1:
                    line_end = len(script_content)
                line_text = script_content[line_start:line_end]
                if "expect.soft" in line_text:
                    continue

            line_no = script_content[:match.start()].count("\n") + 1
            matched_text = match.group(0)[:100]
            issues.append({
                "id": rule["id"],
                "severity": rule["severity"],
                "line": line_no,
                "matched": matched_text,
                "message": rule["message"],
                "fix": rule["fix"],
            })
            break
    issues.sort(key=lambda x: severity_order.get(x["severity"], 99))
    return issues


def validate_test_cases(test_cases):
    INTERACTIVE = {"click", "fill", "type", "select", "check", "uncheck", "hover", "dblclick"}
    if not isinstance(test_cases, list) or not test_cases:
        return "test_cases must be non-empty list"
    for i, tc in enumerate(test_cases):
        if not isinstance(tc, dict):
            return f"test_cases[{i}] must be dict"
        name = tc.get("name")
        if not isinstance(name, str) or not name.strip():
            return f"test_cases[{i}].name missing"
        steps = tc.get("steps")
        if not isinstance(steps, list) or not steps:
            return f"test_cases[{i}].steps must be non-empty list"
        for j, step in enumerate(steps):
            if not isinstance(step, dict) or not step.get("action"):
                return f"test_cases[{i}].steps[{j}] must have action"
            action = (step.get("action") or "").lower()
            if action in INTERACTIVE:
                if not step.get("selector") and not step.get("locator"):
                    return (
                        f"test_cases[{i}].steps[{j}]: "
                        f"interactive action '{action}' missing selector/locator"
                    )
        vps = tc.get("verification_points")
        if not isinstance(vps, list) or not vps:
            return f"test_cases[{i}].verification_points must have at least 1"
        for j, vp in enumerate(vps):
            if isinstance(vp, str) and len(vp.strip()) < 10:
                return f"test_cases[{i}].verification_points[{j}] too short: '{vp}'"
            elif isinstance(vp, dict) and not vp.get("expected") and not vp.get("assertion"):
                return f"test_cases[{i}].verification_points[{j}] missing expected/assertion"
    return None


# ===== Test 1: Multi-anti-pattern script =====
print("=" * 60)
print("Test 1: Script with multiple anti-patterns")
print("=" * 60)

bad_script = '''
import { test, expect } from "@playwright/test";

test.describe("Checkout Flow", () => {
  test("should checkout", async ({ page }) => {
    const btn = await page.$(".submit-btn");
    await page.waitForTimeout(5000);
    await btn.click();
    expect(await page.locator(".msg").textContent()).toBe("OK");
    await page.locator(".cart-count").click();
    await expect(page.locator(".cart-count")).toHaveText("5");
  });
});
'''

issues = scan_quality(bad_script)
for i in issues:
    icon = {"error": "X", "warning": "!", "info": "i"}.get(i["severity"], "?")
    print(f"  [{icon}] [{i['id']}] L{i['line']} ({i['severity']})")
    print(f"       {i['matched'][:70]}")

error_count = sum(1 for i in issues if i["severity"] == "error")
warning_count = sum(1 for i in issues if i["severity"] == "warning")
info_count = sum(1 for i in issues if i["severity"] == "info")
print(f"  => {error_count} errors, {warning_count} warnings, {info_count} info")

rule_ids = {i["id"] for i in issues}
assert "DEPRECATED_DOLLAR" in rule_ids, "MISSING: DEPRECATED_DOLLAR"
assert "HARD_WAIT_LONG" in rule_ids, "MISSING: HARD_WAIT_LONG"
assert "UNSAFE_CLICK_NO_WAIT" in rule_ids, "MISSING: UNSAFE_CLICK_NO_WAIT"
assert "TEXTCONTENT_ASSERTION" in rule_ids, "MISSING: TEXTCONTENT_ASSERTION"
assert "MISSING_BEFOREEACH_ISOLATION" in rule_ids, "MISSING: MISSING_BEFOREEACH_ISOLATION"
assert "CSS_SELECTOR_ONLY" in rule_ids, "MISSING: CSS_SELECTOR_ONLY"
assert "NO_SOFT_ASSERTION" in rule_ids, "MISSING: NO_SOFT_ASSERTION"
assert "NO_AUTO_RETRY" in rule_ids, "MISSING: NO_AUTO_RETRY"
print("  All 8 rules triggered: PASS")

# ===== Test 2: Well-written script =====
print()
print("=" * 60)
print("Test 2: Well-written script - zero false positives")
print("=" * 60)

good_script = '''
import { test, expect } from "@playwright/test";

test.use({ testIdAttribute: "data-test" });

test.describe("Login", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.evaluate(() => localStorage.clear());
  });

  test("should login", async ({ page }) => {
    await page.getByTestId("username").fill("testuser");
    await page.getByTestId("password").fill("secret");
    await page.getByRole("button", { name: "Login" }).click();
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("welcome")).toBeVisible();
    await expect(page.getByTestId("welcome")).toHaveText("Welcome");
  });
});
'''

good_issues = scan_quality(good_script)
# Allow info-level suggestions even in well-written scripts (they're advisory)
errors_or_warnings = [i for i in good_issues if i["severity"] in ("error", "warning")]
info_issues = [i for i in good_issues if i["severity"] == "info"]
if info_issues:
    print(f"  Info suggestions ({len(info_issues)}): {[i['id'] for i in info_issues]}")
assert len(errors_or_warnings) == 0, f"False errors/warnings: {[i['id'] for i in errors_or_warnings]}"
print("  Zero errors/warnings on well-written script: PASS")

# ===== Test 3: Edge cases =====
print()
print("=" * 60)
print("Test 3: Edge cases")
print("=" * 60)

short_wait = "await page.waitForTimeout(500);"
assert len(scan_quality(short_wait)) == 0
print("  waitForTimeout(500) no trigger: PASS")

# expect.soft with semantic locator = no trigger
soft_assert = 'await expect.soft(page.getByRole("button")).toBeVisible();'
assert len(scan_quality(soft_assert)) == 0
print("  expect.soft() no trigger: PASS")

semantic = 'await page.locator("button").click();'
issues3 = scan_quality(semantic)
assert not any(i["id"] == "CSS_SELECTOR_ONLY" for i in issues3)
print("  page.locator('button') no CSS_SELECTOR_ONLY: PASS")

# ===== Test 4: _validate_test_cases =====
print()
print("=" * 60)
print("Test 4: _validate_test_cases semantic checks")
print("=" * 60)

good_cases = [{
    "name": "Login with valid credentials",
    "steps": [
        {"action": "fill", "selector": "getByTestId('username')", "value": "testuser"},
        {"action": "click", "selector": "getByRole('button', { name: 'Login' })"},
    ],
    "verification_points": [
        {"assertion": "toHaveURL", "expected": "/dashboard"},
        "User is redirected to dashboard after successful login",
    ],
}]
assert validate_test_cases(good_cases) is None
print("  Valid test case passes: OK")

bad_cases = [{
    "name": "Click without selector",
    "steps": [{"action": "click"}],
    "verification_points": ["ok"],
}]
err = validate_test_cases(bad_cases)
assert err and "missing selector" in err.lower(), f"Wrong error: {err}"
print("  Missing selector detected: OK")

bad_cases2 = [{
    "name": "Too short VP",
    "steps": [{"action": "navigate"}],
    "verification_points": ["ok"],
}]
err2 = validate_test_cases(bad_cases2)
assert err2 and "too short" in err2.lower(), f"Wrong error: {err2}"
print("  Too-short verification point detected: OK")

empty_vp = [{
    "name": "No expected in dict VP",
    "steps": [{"action": "navigate"}],
    "verification_points": [{"type": "url_check"}],
}]
err3 = validate_test_cases(empty_vp)
assert err3 and "missing expected" in err3.lower(), f"Wrong error: {err3}"
print("  Missing expected/assertion in dict VP detected: OK")

# ===== Summary =====
print()
print("=" * 60)
print("ALL 4 TESTS PASSED")
print("=" * 60)
