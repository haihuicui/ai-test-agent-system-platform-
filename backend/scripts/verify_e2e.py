"""端到端验证 (独立运行——不依赖后端模块导入链)

模拟 4 条核心链路:
  1. 质量门禁: 脚本→扫描→分类→决策
  2. 错误归一化→匹配→分类
  3. 知识图谱: 搜索→记录→置信度演进 (SQLite)
  4. 执行策略: hash→skip/full 决策链
"""

import sys, os, json, re, asyncio, hashlib

# ====================================================================
# Inline: 从 artifacts_tools.py / healing_tools.py / execution_tools.py
# 复制的核心逻辑（避免后端模块导入链缺依赖问题）
# ====================================================================

# ---- 质量规则 ----
_SCRIPT_QUALITY_RULES = [
    {"id":"DEPRECATED_DOLLAR","severity":"error","pattern":r"page\.\$\(['\"]","message":"废弃 API","fix":"替换为 locator"},
    {"id":"HARD_WAIT_LONG","severity":"warning","pattern":r"await\s+page\.waitForTimeout\(\s*(\d{4,})\s*\)","message":"硬编码等待>1s","fix":"语义等待"},
    {"id":"UNSAFE_CLICK_NO_WAIT","severity":"warning","pattern":r"\.click\(\s*\)\s*;\s*\n\s*await\s+expect","message":"click后直接断言","fix":"中间加等待"},
    {"id":"TEXTCONTENT_ASSERTION","severity":"info","pattern":r"expect\(.*?\.textContent\(\)\)","message":"textContent断言","fix":"toHaveText"},
    {"id":"MISSING_BEFOREEACH_ISOLATION","severity":"info","pattern":r"test\.describe\(\s*['\"].*?['\"]\s*,\s*\(\s*\)\s*=>\s*\{","message":"缺少beforeEach","fix":"加beforeEach","_require_before_each_absent":True},
    {"id":"CSS_SELECTOR_ONLY","severity":"warning","pattern":r"page\.locator\(\s*['\"](\.|#)[^'\"]+['\"]\s*\)","message":"纯CSS选择器","fix":"语义定位器"},
    {"id":"NO_SOFT_ASSERTION","severity":"info","pattern":r"expect\(.*?\)\.(toBe|toHave|toContain)","message":"考虑expect.soft()","fix":"expect.soft()","_require_no_soft_on_line":True},
    {"id":"NO_AUTO_RETRY","severity":"info","pattern":r"const\s+\w+\s*=\s*await\s+page\.\$","message":"保存element handle","fix":"链式调用"},
]

def scan_quality(script):
    severity_order = {"error":0,"warning":1,"info":2}
    issues = []
    for rule in _SCRIPT_QUALITY_RULES:
        if rule.get("_require_before_each_absent"):
            if re.search(r"test\.beforeEach\s*\(", script):
                continue
        for match in re.finditer(rule["pattern"], script, re.MULTILINE):
            if rule.get("_require_no_soft_on_line"):
                ls = script.rfind("\n",0,match.start())+1
                le = script.find("\n",match.end())
                if le==-1: le=len(script)
                if "expect.soft" in script[ls:le]:
                    continue
            line_no = script[:match.start()].count("\n")+1
            issues.append({"id":rule["id"],"severity":rule["severity"],"line":line_no,"matched":match.group()[:80],"message":rule["message"]})
            break  # 每条规则只取第一个匹配
    issues.sort(key=lambda x:severity_order.get(x["severity"],99))
    return issues

# ---- 用例校验 ----
_INTERACTIVE = {"click","fill","type","select","check","uncheck","hover","dblclick"}
def validate_cases(tc_list):
    if not isinstance(tc_list,list) or not tc_list: return "empty"
    for i,tc in enumerate(tc_list):
        if not isinstance(tc,dict): return f"[{i}] not dict"
        if not isinstance(tc.get("name"),str) or not tc["name"].strip(): return f"[{i}].name missing"
        steps=tc.get("steps")
        if not isinstance(steps,list) or not steps: return f"[{i}].steps empty"
        for j,s in enumerate(steps):
            if not isinstance(s,dict) or not s.get("action"): return f"[{i}].steps[{j}] no action"
            if s["action"].lower() in _INTERACTIVE:
                if not s.get("selector") and not s.get("locator"):
                    return f"[{i}].steps[{j}] interactive '{s['action']}' missing selector"
        vps=tc.get("verification_points")
        if not isinstance(vps,list) or not vps: return f"[{i}].vps empty"
        for j,vp in enumerate(vps):
            if isinstance(vp,str) and len(vp.strip())<10: return f"[{i}].vps[{j}] too short '{vp}'"
            if isinstance(vp,dict) and not vp.get("expected") and not vp.get("assertion"): return f"[{i}].vps[{j}] missing expected"
    return None

# ---- 错误归一化 ----
_DYNAMIC_PATTERNS = [
    (re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"),"<UUID>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"),"<TIMESTAMP>"),
    (re.compile(r"(?:tests?/)?[\w-]+\.spec\.(?:ts|js|mjs)"),"<SPEC>"),
    (re.compile(r"(?:in|at)\s+\S+[/\\]\S+"),"<LOC>"),
    (re.compile(r"'[^']*?'"),"<VAL>"),
    (re.compile(r"\d{3,}"),"<NUM>"),
    (re.compile(r"ref=e\d+"),"<REF>"),
]
def normalize(msg):
    s=msg[:500]
    for p,r in _DYNAMIC_PATTERNS: s=p.sub(r,s)
    return s.strip()

def categorize(msg):
    m=msg.lower()
    for kw in ("selector","locator","resolved to 0","not found","element not","getby"):
        if kw in m: return "selector"
    for kw in ("timeout","timed out","loading","networkidle","waitfor","to be visible"):
        if kw in m: return "timing"
    for kw in ("expect","assert","expected","to have","to contain","tobe","totext"):
        if kw in m: return "assertion"
    for kw in ("auth","login","credential","session","401","403","permission"):
        if kw in m: return "environment"
    return "application"

# ---- 执行策略 ----
def compute_strategy(last_exec, script_hash):
    if not last_exec: return {"strategy":"full","reason":"no history"}
    lh = (last_exec.get("execution_config") or {}).get("script_hash","")
    ls = (last_exec.get("execution_config") or {}).get("strategy","full")
    # 优先级1: 上次是skip → 强制full,打破跳过链
    if ls=="skip": return {"strategy":"full","reason":"break skip chain"}
    # 优先级2: 未变更+全绿 → skip
    if last_exec.get("failed_tests",1)==0 and script_hash and script_hash==lh:
        return {"strategy":"skip","reason":"unchanged+all_pass","cached":last_exec}
    # 优先级3: 未变更+有失败 → full (TODO: failed_only)
    if script_hash and script_hash==lh:
        return {"strategy":"full","reason":"unchanged+has_failures (TODO: failed_only)"}
    return {"strategy":"full","reason":"script changed"}


# ====================================================================
# Test 1: 质量门禁全链路
# ====================================================================
print("="*60)
print("Test 1: Quality Gate Pipeline")
print("="*60)

bad = '''import { test, expect } from "@playwright/test";
test.describe("X", () => {
  test("t", async ({ page }) => {
    const btn = await page.$(".btn");
    await page.waitForTimeout(5000);
    await btn.click();
    expect(await page.locator(".msg").textContent()).toBe("OK");
    await page.locator(".cart").click();
    await expect(page.locator(".cart")).toHaveText("5");
  });
});
'''
issues = scan_quality(bad)
ec = sum(1 for i in issues if i["severity"]=="error")
wc = sum(1 for i in issues if i["severity"]=="warning")
ic = sum(1 for i in issues if i["severity"]=="info")
assert ec>=1 and wc>=2, f"Expected >=1 error + >=2 warnings, got {ec}e/{wc}w/{ic}i"
print(f"  1a: Bad script → {ec} errors, {wc} warnings, {ic} info: OK")

good = '''import { test, expect } from "@playwright/test";
test.use({ testIdAttribute: "data-test" });
test.describe("Login", () => {
  test.beforeEach(async ({ page }) => { await page.goto("/login"); });
  test("t", async ({ page }) => {
    await page.getByTestId("user").fill("u");
    await page.getByRole("button",{name:"Login"}).click();
    await page.waitForLoadState("networkidle");
    await expect(page.getByTestId("welcome")).toBeVisible();
  });
});
'''
gi=scan_quality(good)
ew=[i for i in gi if i["severity"] in ("error","warning")]
assert len(ew)==0, f"False positives: {[i['id'] for i in ew]}"
print(f"  1b: Good script → 0 errors/warnings: OK")

# 用例校验
assert validate_cases([{"name":"T","steps":[{"action":"click","selector":"x"}],"verification_points":["valid point here"]}]) is None
e1=validate_cases([{"name":"T","steps":[{"action":"click"}],"verification_points":["valid point"]}])
assert e1 and "selector" in e1.lower(), f"Missing selector not caught: {e1}"
e2=validate_cases([{"name":"T","steps":[{"action":"nav"}],"verification_points":["ok"]}])
assert e2 and "short" in e2.lower(), f"Short VP not caught: {e2}"
print(f"  1c: Test case validation → 3/3: OK")

# ====================================================================
# Test 2: 错误归一化 + 分类
# ====================================================================
print()
print("="*60)
print("Test 2: Error Normalization + Categorization")
print("="*60)

e1="Timeout waiting for getByTestId('submit-btn') in spec tests/checkout.spec.ts"
e2="Timeout waiting for getByTestId('login-btn') in spec tests/login.spec.ts"
assert normalize(e1)==normalize(e2), "Same pattern should match"
print("  2a: Same error → same signature: OK")

e3="Element is not attached to the DOM"
assert normalize(e1)!=normalize(e3), "Different patterns should differ"
print("  2b: Different errors → different signatures: OK")

assert categorize(e1)=="selector"
assert categorize("Timeout 30000ms exceeded")=="timing"
assert categorize("Expected 'OK' but got 'Error'")=="assertion"
assert categorize("Error: 401 Unauthorized")=="environment"
print("  2c: Category inference → 4/4: OK")

# ====================================================================
# Test 3: 知识图谱 (SQLite)
# ====================================================================
print()
print("="*60)
print("Test 3: Knowledge Graph (SQLite)")
print("="*60)

# Use standard library sqlite3 (no aiosqlite needed)
import sqlite3

DB = ":memory:"

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS web_healing_knowledge (
            id TEXT PRIMARY KEY,
            error_signature TEXT NOT NULL,
            error_category TEXT NOT NULL,
            fix_strategy TEXT NOT NULL,
            fix_code_template TEXT,
            confidence REAL DEFAULT 0.5,
            apply_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sig ON web_healing_knowledge(error_signature)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cat ON web_healing_knowledge(error_category)")
    conn.commit()
    return conn

def search_knowledge(conn, error_msg, top_k=3):
    sig = normalize(error_msg)
    cat = categorize(error_msg)
    cur = conn.execute(
        "SELECT * FROM web_healing_knowledge WHERE error_signature=? AND error_category=? ORDER BY confidence DESC LIMIT ?",
        (sig, cat, top_k)
    )
    matches = [dict(zip([c[0] for c in cur.description], row)) for row in cur.fetchall()]
    if len(matches) < top_k:
        cur2 = conn.execute(
            "SELECT * FROM web_healing_knowledge WHERE error_signature LIKE ? AND error_category=? ORDER BY confidence DESC LIMIT ?",
            (f"%{sig[:60]}%", cat, top_k - len(matches))
        )
        for row in cur2.fetchall():
            d = dict(zip([c[0] for c in cur2.description], row))
            if d["id"] not in {m["id"] for m in matches}:
                matches.append(d)
    return sig, cat, matches

def record_result(conn, sig, cat, strategy, template, success):
    cur = conn.execute(
        "SELECT * FROM web_healing_knowledge WHERE error_signature=? AND error_category=? AND fix_strategy=?",
        (sig, cat, strategy)
    )
    row = cur.fetchone()
    now = "2026-07-25T00:00:00"
    if row:
        d = dict(zip([c[0] for c in cur.description], row))
        new_apply = d["apply_count"] + 1
        new_success = d["success_count"] + (1 if success else 0)
        new_conf = min(0.98, d["confidence"] + 0.03) if success else max(0.10, d["confidence"] - 0.10)
        conn.execute(
            "UPDATE web_healing_knowledge SET apply_count=?, success_count=?, confidence=?, updated_at=? WHERE id=?",
            (new_apply, new_success, new_conf, now, d["id"])
        )
        conn.commit()
        return {"action":"updated","confidence":new_conf,"apply_count":new_apply,"success_count":new_success}
    else:
        import uuid
        cid = str(uuid.uuid4())
        conf = 0.55 if success else 0.40
        conn.execute(
            "INSERT INTO web_healing_knowledge VALUES (?,?,?,?,?,?,?,?,?,?)",
            (cid, sig, cat, strategy, template, conf, 1, 1 if success else 0, now, now)
        )
        conn.commit()
        return {"action":"created","confidence":conf,"apply_count":1,"success_count":1 if success else 0}

conn = init_db()

# 3a: 冷启动 → 无结果
sig, cat, matches = search_knowledge(conn, "getByTestId('submit-btn') resolved to 0 elements")
assert len(matches)==0, f"Cold start should have 0 matches, got {len(matches)}"
print("  3a: Cold start → 0 matches: OK")

# 3b: 记录第一次修复
r = record_result(conn, sig, cat, "test.use({ testIdAttribute: 'data-test' })", "test.use({ testIdAttribute: 'data-test' })", True)
assert r["action"]=="created" and r["confidence"]>=0.50
print(f"  3b: First fix recorded → {r['action']}, confidence={r['confidence']:.0%}: OK")

# 3c: 第二次搜索 → 有结果
_, _, matches = search_knowledge(conn, "getByTestId('submit-btn') resolved to 0 elements")
assert len(matches)>=1
print(f"  3c: Second search → {len(matches)} match: OK")

# 3d: 累加 14 次成功 → 置信度演进
for _ in range(14):
    record_result(conn, sig, cat, "test.use({ testIdAttribute: 'data-test' })", "test.use({ testIdAttribute: 'data-test' })", True)
_, _, matches = search_knowledge(conn, "getByTestId('login-btn') resolved to 0 elements")
m = matches[0]
assert m["confidence"]>=0.70, f"Confidence should rise: {m['confidence']}"
assert m["apply_count"]>=10
print(f"  3d: 15x success → confidence={m['confidence']:.0%}, count={m['apply_count']}: OK")

# 3e: 一次失败 → 置信度下降
before = m["confidence"]
record_result(conn, sig, cat, "test.use({ testIdAttribute: 'data-test' })", "test.use({ testIdAttribute: 'data-test' })", False)
_, _, matches = search_knowledge(conn, "getByTestId('submit-btn') resolved to 0 elements")
after = matches[0]["confidence"]
assert after < before, f"Confidence should drop: {after} >= {before}"
print(f"  3e: Failure → confidence: {before:.0%} → {after:.0%}: OK")

# 3f: 跨签名模糊匹配
e4 = "getByTestId('cart-icon') resolved to 0 elements"
_, _, matches = search_knowledge(conn, e4)
assert len(matches)>=1, f"Cross-signature should match: got {len(matches)}"
print(f"  3f: Cross-signature match → {len(matches)} results: OK")

# ====================================================================
# Test 4: 执行策略全链路
# ====================================================================
print()
print("="*60)
print("Test 4: Execution Strategy Pipeline")
print("="*60)

h1 = hashlib.sha256(b"v1").hexdigest()
h2 = hashlib.sha256(b"v2").hexdigest()

r = compute_strategy(None, h1)
assert r["strategy"]=="full"
print(f"  4a: No history → {r['strategy']}: OK")

r = compute_strategy({"failed_tests":0,"passed_tests":5,"total_tests":5,"execution_config":{"script_hash":h1}}, h1)
assert r["strategy"]=="skip" and r["cached"] is not None
print(f"  4b: Unchanged+all_pass → {r['strategy']} (cached): OK")

r = compute_strategy({"failed_tests":2,"passed_tests":3,"total_tests":5,"execution_config":{"script_hash":h1}}, h1)
assert r["strategy"]=="full"  # TODO: failed_only
print(f"  4c: Unchanged+failed → {r['strategy']} (TODO: failed_only): OK")

r = compute_strategy({"failed_tests":0,"passed_tests":5,"total_tests":5,"execution_config":{"script_hash":h1}}, h2)
assert r["strategy"]=="full"
print(f"  4d: Changed script → {r['strategy']}: OK")

r = compute_strategy({"failed_tests":0,"passed_tests":5,"total_tests":5,"execution_config":{"script_hash":h1,"strategy":"skip"}}, h1)
assert r["strategy"]=="full"
print(f"  4e: Skip chain break → {r['strategy']}: OK")

# ====================================================================
print()
print("="*60)
print("END-TO-END TESTS: ALL 17/17 PASSED")
print("="*60)
print("""
  Test 1: Quality Gate        -> 3/3
  Test 2: Error Normalization -> 3/3
  Test 3: Knowledge Graph     -> 6/6
  Test 4: Execution Strategy  -> 5/5
""")
