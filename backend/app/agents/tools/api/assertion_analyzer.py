"""断言分析的 AST 化实现（纯 Python，零外部依赖）。

背景：门禁原先用正则解析 expect 链，对多行链、嵌套括号参数、`.rejects/.resolves`、
条件断言反模式（`if (x !== undefined) expect(...)`）以及 Python `assert` 都会漏判/误判。
本模块用「字符串/注释/正则字面量掩码 + 平衡定界符结构扫描」替代脆弱正则：
- JS/TS：tokenizer 掩码后做结构扫描，准确提取 expect 链、test/it 归属、条件断言、schema 校验调用。
- Python：内置 `ast` 模块解析 `assert` / `pytest.raises` / `self.assertX`。
- 任何异常都降级到增强版正则，保证门禁永不因解析器问题硬阻塞。

统一口径：每个用例 ≥1 个状态码断言 + ≥2 个有效业务断言（非状态码、非宽泛、非条件断言）。
schema 整体校验调用（expectSchema/ajv.validate/jsonschema.validate）计为有效结构断言。
"""
from __future__ import annotations

import ast as pyast
import re
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 常量与判定阈值
# ---------------------------------------------------------------------------

_MIN_EFFECTIVE_PER_TEST = 2  # 每用例有效业务断言下限（与提示词/generator skill 口径一致）

_STATUS_SUFFIX = (".status", ".statuscode", ".status_code", ".ok")
_WEAK_ALWAYS = {"tobetruthy", "tobefalsy"}
_WEAK_CTX = {"tobedefined", "tobeundefined"}
_VALUE_MATCHERS = {"tobe", "toequal", "tostrictequal"}
_BROAD_MATCHERS = {"tobeinstanceof"}

# 合法「少断言」用例（安全/删除/清理类）——按用例名豁免 status-only 降级
_EXEMPT_NAME_RE = re.compile(
    r"delet|204|teardown|清理|删除|认证失败|未授权|越权|无权限|unauthor|forbidden|"
    r"invalid.*(token|auth|credential)|安全|security|401|403",
    re.I,
)


# ---------------------------------------------------------------------------
# 1. JS/TS tokenizer：掩码字符串/模板/注释/正则字面量（保持长度与换行，便于按偏移取原文）
# ---------------------------------------------------------------------------

def _scan_string(src: str, i: int, quote: str) -> int:
    """从 src[i]==quote 起，返回字符串结束后的位置（跳过转义）。"""
    n = len(src)
    j = i + 1
    while j < n:
        c = src[j]
        if c == "\\":
            j += 2
            continue
        if c == quote:
            return j + 1
        j += 1
    return n


def _scan_template(src: str, i: int) -> int:
    """从 src[i]=='`' 起扫描模板字面量，处理 ${...} 嵌套（含内部字符串），返回结束位置。"""
    n = len(src)
    j = i + 1
    while j < n:
        c = src[j]
        if c == "\\":
            j += 2
            continue
        if c == "`":
            return j + 1
        if c in "\"'":
            j = _scan_string(src, j, c)
            continue
        if c == "$" and j + 1 < n and src[j + 1] == "{":
            # 进入 ${...}，按花括号平衡扫描（内部可能含字符串/模板）
            depth = 1
            j += 2
            while j < n and depth > 0:
                cc = src[j]
                if cc == "\\":
                    j += 2
                    continue
                if cc in "\"'":
                    j = _scan_string(src, j, cc)
                    continue
                if cc == "`":
                    j = _scan_template(src, j)
                    continue
                if cc == "{":
                    depth += 1
                elif cc == "}":
                    depth -= 1
                j += 1
            continue
        j += 1
    return n


def _scan_regex(src: str, i: int) -> int:
    """从 src[i]=='/' 起扫描正则字面量，处理 \\/ 与字符类 [...]，返回结束位置（含 flags）。"""
    n = len(src)
    j = i + 1
    in_class = False
    while j < n:
        c = src[j]
        if c == "\\":
            j += 2
            continue
        if c == "[":
            in_class = True
        elif c == "]":
            in_class = False
        elif c == "/" and not in_class:
            j += 1
            while j < n and src[j].isalpha():  # flags
                j += 1
            return j
        j += 1
    return n


_REGEX_PREV_CHARS = set("([{,;:!&|?+=<>*%^~")
_REGEX_PREV_WORDS = {
    "return", "typeof", "case", "else", "in", "of", "new", "delete", "void",
    "do", "instanceof", "await", "yield", "throw",
}


def _is_regex_start(prev_char: str, prev_word: str) -> bool:
    if prev_word in _REGEX_PREV_WORDS:
        return True
    if prev_char == "" or prev_char in _REGEX_PREV_CHARS:
        return True
    return False


def _mask_source(src: str) -> tuple[str, list[tuple[int, int]]]:
    """返回 (masked_src, string_spans)。字符串/模板/注释/正则内容置为空格（保留换行与长度）。

    string_spans 记录普通字符串字面量的 (start,end)，用于从原文读取 test 名称。
    """
    out = list(src)
    strings: list[tuple[int, int]] = []
    n = len(src)
    i = 0
    prev_char = ""   # 上一个有效字符（非空白非掩码）
    prev_word = ""   # 上一个标识符

    def _blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = src[i]
        two = src[i:i + 2]
        if two == "//":
            j = src.find("\n", i)
            j = n if j == -1 else j
            _blank(i, j)
            i = j
            continue
        if two == "/*":
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            _blank(i, j)
            i = j
            continue
        if c in "\"'":
            j = _scan_string(src, i, c)
            strings.append((i, j))
            _blank(i, j)
            prev_char, prev_word = "x", ""
            i = j
            continue
        if c == "`":
            j = _scan_template(src, i)
            _blank(i, j)
            prev_char, prev_word = "x", ""
            i = j
            continue
        if c == "/":
            if _is_regex_start(prev_char, prev_word):
                j = _scan_regex(src, i)
                _blank(i, j)
                prev_char, prev_word = "x", ""
                i = j
                continue
            prev_char, prev_word = "/", ""
            i += 1
            continue
        if c.isalpha() or c == "_" or c == "$":
            j = i + 1
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            prev_word = src[i:j]
            prev_char = "x"
            i = j
            continue
        if not c.isspace():
            prev_char = c
            prev_word = ""
        i += 1
    return "".join(out), strings


# ---------------------------------------------------------------------------
# 2. 平衡定界符与结构扫描
# ---------------------------------------------------------------------------

def _find_matching(masked: str, open_pos: int, open_ch: str, close_ch: str) -> int:
    """masked[open_pos]==open_ch，返回匹配的 close_ch 位置；未找到返回 -1。masked 已去除字符串/注释。"""
    depth = 0
    for k in range(open_pos, len(masked)):
        c = masked[k]
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return k
    return -1


def _skip_ws(masked: str, i: int) -> int:
    while i < len(masked) and masked[i].isspace():
        i += 1
    return i


def _split_top_level(text: str) -> list[str]:
    """按顶层逗号切分（考虑括号/方括号/花括号/字符串嵌套）。用于拆 matcher 参数。"""
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in "\"'`":
            q = c
            cur.append(c)
            i += 1
            while i < n:
                cur.append(text[i])
                if text[i] == "\\":
                    if i + 1 < n:
                        cur.append(text[i + 1])
                        i += 2
                        continue
                elif text[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        if c == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


_IDENT_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$")


def _read_ident(masked: str, i: int) -> tuple[str, int]:
    j = i
    while j < len(masked) and masked[j] in _IDENT_CHARS:
        j += 1
    return masked[i:j], j


def _line_of(src: str, pos: int) -> int:
    return src.count("\n", 0, pos) + 1


def _parse_expect(src: str, masked: str, kw_end: int) -> Optional[dict]:
    """masked 中 expect 关键字结束于 kw_end。解析 expect(<recv>).<mod...>.<matcher>(<args>)。"""
    i = _skip_ws(masked, kw_end)
    if i >= len(masked) or masked[i] != "(":
        return None
    close = _find_matching(masked, i, "(", ")")
    if close == -1:
        return None
    receiver = src[i + 1:close].strip()

    # 走 .name 链：not/resolves/rejects 为修饰符；第一个带 ( 的 name 为 matcher
    modifiers: list[str] = []
    matcher = ""
    args: list[str] = []
    pos = close + 1
    while True:
        pos = _skip_ws(masked, pos)
        if pos >= len(masked) or masked[pos] != ".":
            break
        name, nend = _read_ident(masked, pos + 1)
        if not name:
            break
        after = _skip_ws(masked, nend)
        if after < len(masked) and masked[after] == "(":
            mclose = _find_matching(masked, after, "(", ")")
            if mclose == -1:
                break
            matcher = name
            args = _split_top_level(src[after + 1:mclose])
            pos = mclose + 1
            break
        else:
            modifiers.append(name)
            pos = nend
    if not matcher:
        return None
    return {
        "receiver": receiver,
        "matcher": matcher,
        "modifiers": [m for m in modifiers if m in ("not", "resolves", "rejects")],
        "negated": "not" in modifiers,
        "args": args,
        "pos": kw_end,  # 用 expect 之后的位置做归属/行号
    }


def _parse_if(src: str, masked: str, kw_end: int) -> Optional[tuple[int, int]]:
    """解析 if(<cond>)<body>；若 cond 含 !== undefined 返回 body 区间，否则 None。"""
    i = _skip_ws(masked, kw_end)
    if i >= len(masked) or masked[i] != "(":
        return None
    close = _find_matching(masked, i, "(", ")")
    if close == -1:
        return None
    cond = src[i + 1:close]
    if not re.search(r"!==\s*undefined", cond):
        return None
    body = _skip_ws(masked, close + 1)
    if body < len(masked) and masked[body] == "{":
        bend = _find_matching(masked, body, "{", "}")
        bend = bend if bend != -1 else body
        return (body, bend)
    # 单语句 body：到分号为止
    semi = masked.find(";", body)
    bend = semi if semi != -1 else body + 1
    return (body, bend)


_SCHEMA_CALL_RE = re.compile(
    r"\b(?:expectSchema|validateSchema|assertSchema|expect_schema|validate_schema|assert_schema)\s*\("
    r"|\b(?:ajv|jsonschema|schema|validator)\s*\.\s*validate\s*\(",
    re.I,
)


def _analyze_js_ts(src: str) -> dict:
    """结构扫描 JS/TS 脚本，返回 expects/tests/schemaCalls/rigorSignals。"""
    masked, strings = _mask_source(src)

    blocks: list[dict] = []   # {start,end,name,kind}
    expects: list[dict] = []
    if_spans: list[tuple[int, int]] = []
    schema_calls: list[dict] = []
    rigor = 0

    n = len(masked)
    i = 0
    while i < n:
        c = masked[i]
        if c in _IDENT_CHARS and (c.isalpha() or c in "_$") and (i == 0 or masked[i - 1] not in _IDENT_CHARS):
            word, j = _read_ident(masked, i)
            if word in ("test", "it", "describe"):
                p = _skip_ws(masked, j)
                if p < n and masked[p] == "(":
                    close = _find_matching(masked, p, "(", ")")
                    if close != -1:
                        # 取首个字符串字面量作为用例名
                        name = "(unnamed)"
                        for (s0, s1) in strings:
                            if p < s0 < close and s1 <= close + 1:
                                name = src[s0 + 1:s1 - 1]
                                break
                        kind = "describe" if word == "describe" else "test"
                        blocks.append({"start": p, "end": close, "name": name, "kind": kind})
            elif word == "expect":
                e = _parse_expect(src, masked, j)
                if e:
                    expects.append(e)
            elif word == "if":
                span = _parse_if(src, masked, j)
                if span:
                    if_spans.append(span)
            i = j
            continue
        i += 1

    # expect.assertions(n) / expect.hasAssertions()
    rigor += len(re.findall(r"\bexpect\s*\.\s*(?:assertions|hasAssertions)\s*\(", masked))
    # schema 整体校验调用
    for m in _SCHEMA_CALL_RE.finditer(masked):
        schema_calls.append({"pos": m.start()})

    # 归属：expect/schema 归入最内层包含它的 test/describe
    def _owner(pos: int) -> Optional[str]:
        best = None
        best_len = None
        for b in blocks:
            if b["start"] <= pos <= b["end"]:
                span = b["end"] - b["start"]
                if best_len is None or span < best_len:
                    best_len = span
                    best = b
        return best["name"] if best else None

    def _conditional(pos: int) -> bool:
        return any(a <= pos <= b for (a, b) in if_spans)

    for e in expects:
        e["testName"] = _owner(e["pos"])
        e["line"] = _line_of(src, e["pos"])
        e["conditional"] = _conditional(e["pos"])
        e.pop("pos", None)
    for s in schema_calls:
        s["testName"] = _owner(s["pos"])
        s.pop("pos", None)

    tests = [b["name"] for b in blocks if b["kind"] == "test"]
    return {
        "expects": expects,
        "tests": tests,
        "schemaCalls": schema_calls,
        "rigorSignals": rigor,
    }


# ---------------------------------------------------------------------------
# 3. Python 脚本分析（内置 ast）
# ---------------------------------------------------------------------------

def _attr_name(node: Any) -> str:
    if isinstance(node, pyast.Name):
        return node.id
    if isinstance(node, pyast.Attribute):
        base = _attr_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, pyast.Call):
        return _attr_name(node.func)
    return ""


def _classify_python_assert(test_expr: Any) -> tuple[str, str]:
    """返回 (category, receiver_text)。category ∈ status/weak/effective。"""
    try:
        text = pyast.unparse(test_expr)
    except Exception:
        text = ""
    if isinstance(test_expr, pyast.Compare):
        left = pyast.unparse(test_expr.left) if test_expr.left else ""
        if any(s in left for s in ("status_code", ".status", "statusCode")):
            return "status", left
        ops = {type(o).__name__ for o in test_expr.ops}
        if ops & {"In", "NotIn"}:
            return "effective", left          # 字段/成员存在性
        if ops & {"Is", "IsNot", "Eq", "NotEq", "Gt", "Lt", "GtE", "LtE"}:
            return "effective", left          # 值/非空/比较
        return "effective", left
    if isinstance(test_expr, pyast.Call):
        name = _attr_name(test_expr.func)
        if name == "isinstance":
            return "effective", text          # 类型断言
        return "effective", text
    # 裸真值断言 assert x / assert resp.ok
    if isinstance(test_expr, (pyast.Name, pyast.Attribute)):
        if isinstance(test_expr, pyast.Attribute) and test_expr.attr in ("status_code", "status", "ok"):
            return "status", text
        return "weak", text
    return "effective", text


def _analyze_python(src: str) -> dict:
    try:
        tree = pyast.parse(src)
    except SyntaxError:
        return {"expects": [], "tests": [], "schemaCalls": [], "rigorSignals": 0}

    expects: list[dict] = []
    tests: list[str] = []
    schema_calls: list[dict] = []

    for fn in pyast.walk(tree):
        if not isinstance(fn, (pyast.FunctionDef, pyast.AsyncFunctionDef)):
            continue
        if not fn.name.startswith("test"):
            continue
        tests.append(fn.name)
        for node in pyast.walk(fn):
            if isinstance(node, pyast.Assert):
                cat, recv = _classify_python_assert(node.test)
                expects.append({
                    "receiver": recv, "matcher": "assert", "modifiers": [], "negated": False,
                    "args": [], "testName": fn.name, "line": node.lineno,
                    "conditional": False, "category": cat,
                })
            elif isinstance(node, pyast.With):
                for item in node.items:
                    ce = item.context_expr
                    if isinstance(ce, pyast.Call) and _attr_name(ce.func).endswith("raises"):
                        expects.append({
                            "receiver": "pytest.raises", "matcher": "raises", "modifiers": [],
                            "negated": False, "args": [], "testName": fn.name,
                            "line": node.lineno, "conditional": False, "category": "effective",
                        })
            elif isinstance(node, pyast.Call):
                name = _attr_name(node.func)
                # schema 整体校验调用（camelCase / snake_case / jsonschema.validate 等）
                _SCHEMA_PY = {
                    "expectSchema", "validateSchema", "assertSchema",
                    "expect_schema", "validate_schema", "assert_schema",
                }
                if (name in _SCHEMA_PY or name.endswith(".validate")
                        or name.endswith(".validate_schema") or name.endswith(".assert_schema")):
                    schema_calls.append({"testName": fn.name})
    return {"expects": expects, "tests": tests, "schemaCalls": schema_calls, "rigorSignals": 0}


# ---------------------------------------------------------------------------
# 4. 分类（JS/TS expect）
# ---------------------------------------------------------------------------

def _is_bare_ident(receiver: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_$][\w$]*!?", receiver.strip()))


def _classify_expect(e: dict) -> str:
    """返回 status | weak | conditional | effective。"""
    if "category" in e:  # Python 已预分类
        return e["category"]
    if e.get("conditional"):
        return "conditional"
    recv = (e.get("receiver") or "").strip()
    matcher = (e.get("matcher") or "").lower()
    arg_text = " ".join(e.get("args") or []).lower()
    rl = recv.lower()

    if rl.endswith(_STATUS_SUFFIX) or ".status" in rl or ".status" in arg_text or "status_code" in rl:
        return "status"
    if matcher in _WEAK_ALWAYS:
        return "weak"
    if matcher in _WEAK_CTX and _is_bare_ident(recv):
        return "weak"
    if matcher in _BROAD_MATCHERS and ("object" in arg_text or not arg_text):
        return "weak"
    if matcher in _VALUE_MATCHERS and arg_text in {"", "undefined", "null"}:
        return "weak"
    return "effective"


# ---------------------------------------------------------------------------
# 5. 指标聚合 + 判定
# ---------------------------------------------------------------------------

def _is_exempt(name: Optional[str]) -> bool:
    return bool(name) and bool(_EXEMPT_NAME_RE.search(name))


def _build_metrics(parsed: dict, parser: str, language: str) -> dict:
    expects = parsed.get("expects", [])
    tests = parsed.get("tests", [])
    schema_calls = parsed.get("schemaCalls", [])
    rigor = parsed.get("rigorSignals", 0)

    per_test: dict[str, dict] = {}

    def _bucket(name: Optional[str]) -> dict:
        return per_test.setdefault(
            name or "(global)",
            {"status": 0, "weak": 0, "conditional": 0, "effective": 0, "schema": 0, "total": 0},
        )

    status_asserts = weak_asserts = conditional_asserts = effective_asserts = 0
    for e in expects:
        cat = _classify_expect(e)
        b = _bucket(e.get("testName"))
        b["total"] += 1
        b[cat] += 1
        if cat == "status":
            status_asserts += 1
        elif cat == "weak":
            weak_asserts += 1
        elif cat == "conditional":
            conditional_asserts += 1
        else:
            effective_asserts += 1

    schema_by_test = 0
    for s in schema_calls:
        b = _bucket(s.get("testName"))
        b["schema"] += 1
        schema_by_test += 1

    total_expects = len(expects)
    total_tests = len(tests) if tests else (1 if (expects or schema_calls) else 0)
    non_status_asserts = total_expects - status_asserts
    # schema 整体校验调用计为有效结构断言
    effective_total = effective_asserts + schema_by_test
    avg_effective = round(effective_total / max(total_tests, 1), 2)

    status_only = total_expects > 0 and effective_total == 0
    # 按用例粒度判定（比全局平均更精确，豁免用例不参与）：
    # - status_only_tests：非豁免且只有状态码（有效=0 且无 schema 校验）
    # - thin_tests：非豁免、无 schema 校验、有效业务断言在 (0, 下限) 之间
    status_only_tests: list[str] = []
    thin_tests: list[str] = []
    for name, b in per_test.items():
        if b["total"] == 0 or _is_exempt(name):
            continue
        if b["effective"] == 0 and b["schema"] == 0:
            status_only_tests.append(name)
        elif b["schema"] == 0 and b["effective"] < _MIN_EFFECTIVE_PER_TEST:
            thin_tests.append(name)
    # schema 校验视为满足结构断言：有 schema 的用例不计入 thin
    weak = bool(status_only_tests or thin_tests)

    return {
        "total_tests": total_tests,
        "total_expects": total_expects,
        "status_asserts": status_asserts,
        "non_status_asserts": non_status_asserts,
        "weak_asserts": weak_asserts,
        "conditional_asserts": conditional_asserts,
        "effective_asserts": effective_asserts,
        "schema_validation_calls": schema_by_test,
        "avg_effective_per_test": avg_effective,
        "status_only": status_only,
        "weak": weak,
        "status_only_tests": status_only_tests,
        "thin_tests": thin_tests,
        "rigor_signals": rigor,
        "parser": parser,
        "language": language,
        "per_test": [
            {"test": name, **counts} for name, counts in per_test.items()
        ],
    }


def _verdict_and_suggestions(m: dict) -> tuple[str, str, list[str]]:
    if m["total_expects"] == 0 and m["schema_validation_calls"] == 0:
        return (
            "FAIL",
            "脚本未检测到任何断言（expect/assert/schema 校验），无法验证任何行为，禁止保存。",
            ["为每个用例至少添加 1 个状态码断言 + 2 个有效业务断言（字段存在性/类型/枚举/业务值）。"],
        )
    if m["status_only"]:
        return (
            "FAIL",
            "断言严重不足：脚本只包含状态码断言，缺少响应体字段/类型/业务断言，禁止保存。",
            _base_suggestions(m),
        )
    if m["status_only_tests"]:
        names = "、".join(str(t) for t in m["status_only_tests"][:5])
        return (
            "WEAK",
            f"以下用例只有状态码断言、缺少业务断言：{names}。",
            _base_suggestions(m),
        )
    if m.get("thin_tests"):
        names = "、".join(str(t) for t in m["thin_tests"][:5])
        return (
            "WEAK",
            f"以下用例的有效业务断言不足 {_MIN_EFFECTIVE_PER_TEST} 个：{names}。",
            _base_suggestions(m),
        )
    return "OK", "断言基本充足。", _base_suggestions(m) if m["conditional_asserts"] else []


def _base_suggestions(m: dict) -> list[str]:
    s = [
        "对 2xx 响应补充 body 关键字段存在性断言，如 expect(body.data).toHaveProperty('id')",
        "根据 OpenAPI responses schema 补充字段类型断言，如 expect(typeof body.data.id).toBe('number')",
        "对业务状态字段补充枚举断言，如 expect(['pending','paid']).toContain(body.data.status)",
        "对 4xx 错误响应补充 error message / code 断言，验证具体错误原因",
        "查询类接口补充数组类型和 total 类型断言，避免空数据误通过",
        "避免 expect(body).toBeTruthy() / expect(response).toBeDefined() 等宽泛断言，应指向具体字段",
    ]
    if m.get("conditional_asserts"):
        s.append(
            "检测到条件断言 if (x !== undefined) expect(...)：字段缺失时会跳过等于没测，"
            "请改为直接断言 expect(x).toBe(...)。"
        )
    s.append("推荐用 expectSchema(body, schema) 对响应整体做契约校验，一次覆盖全部字段/类型/必填/枚举。")
    return s


# ---------------------------------------------------------------------------
# 6. 语言识别与正则降级
# ---------------------------------------------------------------------------

def _normalize_language(script_language: str, script_format: str, content: str) -> str:
    lang = (script_language or "").lower()
    fmt = (script_format or "").lower()
    if fmt == "postman":
        return "postman"
    if lang in ("python", "py") or fmt == "pytest":
        return "python"
    if lang in ("typescript", "javascript", "ts", "js", "java", ""):
        # 内容嗅探兜底：pytest 风格
        head = content[:4000]
        if "def test_" in head or "import pytest" in head or "self.assert" in head:
            return "python"
        return "js"
    return "js"


# —— 正则降级（保留原 _analyze_script_assertions 语义，仅在结构扫描异常时使用）——

def _legacy_regex_metrics(script_content: str) -> dict:
    test_pattern = re.compile(r"(?:test|it)\s*\(\s*['\"`]")
    expect_chain_pattern = re.compile(r"\bexpect\s*\(\s*(.*?)\s*\)\s*\.\s*(\w+)\s*\((.*?)\)", re.DOTALL)
    status_receiver_patterns = [re.compile(r"\.status\b"), re.compile(r"\.statusCode\b"),
                                re.compile(r"\.ok\b"), re.compile(r"\.status\s*\(\s*\)")]
    weak_receivers = {"body", "response", "data", "result", "res", "json", "error", "resp"}
    total_tests = len(test_pattern.findall(script_content))
    chains = expect_chain_pattern.findall(script_content)
    total_expects = len(chains)
    status_asserts = weak_asserts = effective_asserts = 0
    for receiver, matcher, args in chains:
        receiver = receiver.strip()
        args = args.strip()
        if any(p.search(receiver) for p in status_receiver_patterns):
            status_asserts += 1
            continue
        is_weak = False
        if matcher in {"toBeTruthy", "toBeFalsy"}:
            is_weak = True
        elif matcher in {"toBeDefined", "toBeUndefined"} and receiver in weak_receivers:
            is_weak = True
        elif matcher in {"toBeInstanceOf"} and ("Object" in args or args == ""):
            is_weak = True
        elif matcher in {"toBe", "toEqual", "toStrictEqual"} and args in {"", "undefined", "null"}:
            is_weak = True
        if is_weak:
            weak_asserts += 1
        else:
            effective_asserts += 1
    non_status_asserts = max(0, total_expects - status_asserts)
    status_only = total_expects > 0 and effective_asserts == 0
    avg_effective = effective_asserts / max(total_tests, 1)
    weak = total_expects > 0 and (total_tests == 0 or avg_effective < _MIN_EFFECTIVE_PER_TEST)
    return {
        "total_tests": total_tests,
        "total_expects": total_expects,
        "status_asserts": status_asserts,
        "non_status_asserts": non_status_asserts,
        "weak_asserts": weak_asserts,
        "conditional_asserts": 0,
        "effective_asserts": effective_asserts,
        "schema_validation_calls": 0,
        "avg_effective_per_test": round(avg_effective, 2),
        "status_only": status_only,
        "weak": weak,
        "status_only_tests": [],
        "rigor_signals": 0,
        "parser": "regex_fallback",
        "language": "js",
        "per_test": [],
    }


# ---------------------------------------------------------------------------
# 7. 对外入口
# ---------------------------------------------------------------------------

def analyze_assertions(script_content: str, script_language: str = "typescript",
                       script_format: str = "playwright") -> dict:
    """分析脚本断言分布，返回 metrics dict。"""
    language = _normalize_language(script_language, script_format, script_content)
    if language == "postman":
        return {
            "total_tests": 0, "total_expects": 0, "status_asserts": 0, "non_status_asserts": 0,
            "weak_asserts": 0, "conditional_asserts": 0, "effective_asserts": 0,
            "schema_validation_calls": 0, "avg_effective_per_test": 0, "status_only": False,
            "weak": False, "status_only_tests": [], "rigor_signals": 0,
            "parser": "n/a", "language": "postman", "per_test": [],
        }
    try:
        if language == "python":
            parsed = _analyze_python(script_content)
            return _build_metrics(parsed, "python_ast", "python")
        parsed = _analyze_js_ts(script_content)
        return _build_metrics(parsed, "structural_scan", "js")
    except Exception:
        # 解析器异常 → 正则降级，保证门禁不硬阻塞
        try:
            return _legacy_regex_metrics(script_content)
        except Exception:
            return {
                "total_tests": 0, "total_expects": 0, "status_asserts": 0, "non_status_asserts": 0,
                "weak_asserts": 0, "conditional_asserts": 0, "effective_asserts": 0,
                "schema_validation_calls": 0, "avg_effective_per_test": 0, "status_only": False,
                "weak": False, "status_only_tests": [], "rigor_signals": 0,
                "parser": "error", "language": language, "per_test": [],
            }


def build_assertion_report(script_content: str, script_language: str = "typescript",
                           script_format: str = "playwright") -> dict:
    """静态分析脚本断言分布并生成审查报告。返回 {verdict, message, metrics, suggestions, parser}。"""
    metrics = analyze_assertions(script_content, script_language, script_format)
    verdict, message, suggestions = _verdict_and_suggestions(metrics)
    return {
        "verdict": verdict,
        "message": message,
        "metrics": metrics,
        "suggestions": suggestions,
        "parser": metrics.get("parser"),
    }
