"""轨迹规则单测：每条规则至少一组「该抓的抓到 / 不该抓的不抓」。

轨迹全部用手工构造的消息字面量（与 thread_dump.json 同构），
不依赖 LangGraph 服务、不消耗 token、不进 venv 外部依赖。
"""
from __future__ import annotations

from tests.eval.traj_extract import detect_agent, extract
from tests.eval.traj_rules import RULES, run_rules

# ── 构造辅助 ──────────────────────────────────────────────────────────


def human(text: str) -> dict:
    return {"type": "HumanMessage", "content": text}


def ai(text: str = "", calls: list[tuple[str, dict]] | None = None) -> dict:
    msg: dict = {"type": "AIMessage", "content": text}
    if calls:
        msg["tool_calls"] = [{"name": n, "args": a} for n, a in calls]
    return msg


def tool(name: str, content: str) -> dict:
    return {"type": "ToolMessage", "name": name, "content": content}


def violations_of(messages: list[dict], agent: str) -> set[str]:
    return {v.rule_id for v in run_rules(extract(messages), agent)}


def check(rule_id: str, messages: list[dict], agent: str, expect_hit: bool) -> None:
    hits = violations_of(messages, agent)
    if expect_hit:
        assert rule_id in hits, f"{rule_id} 应命中但未命中（实际命中 {hits or '无'}）"
    else:
        assert rule_id not in hits, f"{rule_id} 不应命中但命中了"


# ── extract / detect_agent 基础 ───────────────────────────────────────


class TestExtract:
    def test_args_str_and_dict_both_parse(self):
        # args 为 JSON 字符串时也应解析为 dict
        traj = extract([
            human("需求"),
            {"type": "AIMessage", "content": "", "tool_calls": [
                {"name": "t_str", "args": '{"a": 1}'},
                {"name": "t_dict", "args": {"b": 2}},
            ]},
        ])
        assert traj.calls[0].args == {"a": 1}
        assert traj.calls[1].args == {"b": 2}

    def test_content_blocks_flattened(self):
        traj = extract([
            {"type": "HumanMessage", "content": [{"type": "text", "text": "你好"}]},
        ])
        assert traj.human_texts[0][1] == "你好"

    def test_error_result_detection(self):
        traj = extract([
            ai(calls=[("x", {})]),
            tool("x", '{"success": false, "error": "boom"}'),
            tool("x", '{"success": true}'),
        ])
        assert traj.results[0].is_error is True
        assert traj.results[1].is_error is False

    def test_detect_agent_by_tools_and_filename(self):
        web_traj = extract([ai(calls=[("browser_navigate", {}), ("planner_setup_page", {})])])
        assert detect_agent(web_traj) == "web"
        api_traj = extract([ai(calls=[("get_endpoint_details", {})])])
        assert detect_agent(api_traj) == "api"
        tc_traj = extract([ai(calls=[("save_feature_matrix_tool", {})])])
        assert detect_agent(tc_traj) == "testcase"
        assert detect_agent(extract([]), "tc_abcdef12.json") == "testcase"
        assert detect_agent(extract([ai(calls=[("write_todos", {})])])) == "unknown"


# ── testcase 规则 ─────────────────────────────────────────────────────


class TestTestcaseRules:
    GOOD_FLOW = [
        human("为这个需求生成测试用例……（一段足够具体的需求描述）"),
        ai(calls=[("write_todos", {"todos": []})]),
        tool("write_todos", '{"success": true}'),
        ai(calls=[("save_feature_matrix_tool", {"project_identifier": "PR-1"})]),
        tool("save_feature_matrix_tool", '{"success": true}'),
        ai(calls=[("save_test_cases_file", {"file_path": "m01.jsonl", "test_cases": [{}] * 5})]),
        tool("save_test_cases_file", '{"success": true}'),
        ai(calls=[("module_self_check_tool", {"input_files": ["m01.jsonl"]})]),
        tool("module_self_check_tool", '{"passed": true}'),
        ai("## 测试用例生成完成"),
        human("[阶段评审：通过]"),
        ai(calls=[("compute_coverage_report", {"project_identifier": "PR-1"})]),
        tool("compute_coverage_report", '{"coverage_rate": 1.0}'),
        ai(calls=[("batch_create_test_cases_tool", {"input_file": ["m01.jsonl"]})]),
        tool("batch_create_test_cases_tool", '{"success": true}'),
    ]

    def test_good_flow_no_error(self):
        errs = {v.rule_id for v in run_rules(extract(self.GOOD_FLOW), "testcase")
                if v.severity == "error"}
        assert not errs, f"标杆流程不应有 error：{errs}"

    def test_t01_first_call_must_be_todos(self):
        bad = [human("需求"), ai(calls=[("rag_query_data", {})]),
               ai(calls=[("write_todos", {})])]
        check("TC-T01", bad, "testcase", True)
        check("TC-T01", self.GOOD_FLOW, "testcase", False)
        # PDF 场景 parse 优先不算违规
        pdf_first = [human("[系统提示] 用户上传了 PDF 文件 a.pdf"),
                     ai(calls=[("parse_document_from_url", {"url": "http://x"})]),
                     ai(calls=[("write_todos", {})])]
        check("TC-T01", pdf_first, "testcase", False)

    def test_t02_pdf_attachment_must_parse_first(self):
        bad = [
            human("[系统提示] 用户上传了 PDF 文件 `需求.pdf`，URL: http://x"),
            ai(calls=[("write_todos", {})]),
            ai(calls=[("parse_document_from_url", {"url": "http://x"})]),
        ]
        check("TC-T02", bad, "testcase", True)
        good = [
            human("[系统提示] 用户上传了 PDF 文件 `需求.pdf`，URL: http://x"),
            ai(calls=[("parse_document_from_url", {"url": "http://x"})]),
        ]
        check("TC-T02", good, "testcase", False)

    def test_t03_save_requires_self_check(self):
        bad = [
            ai(calls=[("write_todos", {})]),
            ai(calls=[("save_test_cases_file", {"file_path": "m01.jsonl"})]),
            ai(calls=[("save_test_cases_file", {"file_path": "m02.jsonl"})]),
        ]
        check("TC-T03", bad, "testcase", True)
        check("TC-T03", self.GOOD_FLOW, "testcase", False)

    def test_t04_coverage_before_persist(self):
        bad = [
            ai(calls=[("write_todos", {})]),
            ai(calls=[("batch_create_test_cases_tool", {"input_file": ["m01.jsonl"]})]),
        ]
        check("TC-T04", bad, "testcase", True)
        check("TC-T04", self.GOOD_FLOW, "testcase", False)

    def test_t05_batch_limits(self):
        bad_save = [
            ai(calls=[("write_todos", {})]),
            ai(calls=[("save_test_cases_file", {"file_path": "m.jsonl", "test_cases": [{}] * 11})]),
        ]
        check("TC-T05", bad_save, "testcase", True)
        bad_inline = [
            ai(calls=[("write_todos", {})]),
            ai(calls=[("compute_coverage_report", {})]),
            ai(calls=[("batch_create_test_cases_tool", {"test_cases": [{}]})]),
        ]
        check("TC-T05", bad_inline, "testcase", True)
        check("TC-T05", self.GOOD_FLOW, "testcase", False)

    def test_t06_review_citations_verified(self):
        bad = [
            ai(calls=[("write_todos", {})]),
            ai(calls=[("task", {"subagent_type": "adversarial-reviewer", "description": "评审"})]),
            ai("## 📊 测试用例质量评审报告"),
        ]
        check("TC-T06", bad, "testcase", True)
        good = bad[:-1] + [
            ai(calls=[("verify_review_citations", {"result_dir": "/x"})]),
            ai("## 📊 测试用例质量评审报告"),
        ]
        check("TC-T06", good, "testcase", False)

    def test_t07_duplicate_spin(self):
        bad = [
            ai(calls=[("write_todos", {})]),
            ai(calls=[("read_file", {"path": "/a.jsonl"})]),
            tool("read_file", "ok"),
            ai(calls=[("read_file", {"path": "/a.jsonl"})]),
        ]
        check("TC-T07", bad, "testcase", True)
        # 同工具不同参数不算
        ok = [
            ai(calls=[("read_file", {"path": "/a.jsonl"})]),
            tool("read_file", "ok"),
            ai(calls=[("read_file", {"path": "/b.jsonl"})]),
        ]
        check("TC-T07", ok, "testcase", False)


# ── web 规则 ──────────────────────────────────────────────────────────


class TestWebRules:
    GOOD_FLOW = [
        human("测试登录功能"),
        ai(calls=[("planner_setup_page", {"project": "chromium"})]),
        tool("planner_setup_page", "ok"),
        ai(calls=[("browser_navigate", {"url": "https://x/login"})]),
        tool("browser_navigate", "ok"),
        ai(calls=[("browser_snapshot", {})]),
        tool("browser_snapshot", "snapshot"),
        ai(calls=[("generator_write_test", {})]),
        tool("generator_write_test", "ok"),
        ai('<EXECUTION_INVITATION>{"type":"execution_invitation"}</EXECUTION_INVITATION>'),
        human("[执行邀约] 立即执行"),
        ai(calls=[("execute_web_script", {"script_path": "login.spec.ts"})]),
        tool("execute_web_script", '{"execution_result": {"stats": {}}}'),
    ]

    def test_good_flow_no_error(self):
        errs = {v.rule_id for v in run_rules(extract(self.GOOD_FLOW), "web")
                if v.severity == "error"}
        assert not errs, f"标杆流程不应有 error：{errs}"

    def test_t01_setup_before_browser(self):
        bad = [human("测"), ai(calls=[("browser_navigate", {"url": "http://x"})])]
        check("WB-T01", bad, "web", True)
        check("WB-T01", self.GOOD_FLOW, "web", False)

    def test_t01_close_requires_re_setup(self):
        bad = [
            ai(calls=[("planner_setup_page", {})]),
            ai(calls=[("browser_navigate", {})]),
            ai(calls=[("browser_close", {})]),
            ai(calls=[("browser_navigate", {})]),  # close 后未重新 setup
        ]
        check("WB-T01", bad, "web", True)

    def test_t02_invitation_before_execute(self):
        bad = [human("测"), ai(calls=[("execute_web_script", {"script_path": "a"})])]
        check("WB-T02", bad, "web", True)
        # 有邀约但用户未决策就执行 → 仍违规
        no_decision = [
            ai('<EXECUTION_INVITATION>{}</EXECUTION_INVITATION>'),
            ai(calls=[("execute_web_script", {})]),
        ]
        check("WB-T02", no_decision, "web", True)
        check("WB-T02", self.GOOD_FLOW, "web", False)

    def test_t04_mcp_test_run_bypass(self):
        bad = [
            ai(calls=[("planner_setup_page", {})]),
            ai(calls=[("browser_navigate", {})]),
            ai(calls=[("test_run", {})]),
        ]
        check("WB-T04", bad, "web", True)
        check("WB-T04", self.GOOD_FLOW, "web", False)

    def test_t05_unsafe_code_needs_snapshot(self):
        bad = [
            ai(calls=[("planner_setup_page", {})]),
            ai(calls=[("browser_run_code_unsafe", {"code": "x"})]),
            tool("browser_run_code_unsafe", "Error: fail"),
            ai(calls=[("browser_run_code_unsafe", {"code": "y"})]),
        ]
        check("WB-T05", bad, "web", True)
        ok = bad[:3] + [
            ai(calls=[("browser_snapshot", {})]),
            ai(calls=[("browser_run_code_unsafe", {"code": "y"})]),
        ]
        check("WB-T05", ok, "web", False)

    def test_t06_browser_spin(self):
        bad = [
            ai(calls=[("planner_setup_page", {})]),
            ai(calls=[("browser_click", {"ref": "e1"})]),
            tool("browser_click", "Error"),
            ai(calls=[("browser_click", {"ref": "e1"})]),
            tool("browser_click", "Error"),
            ai(calls=[("browser_click", {"ref": "e1"})]),
        ]
        check("WB-T06", bad, "web", True)
        check("WB-T06", self.GOOD_FLOW, "web", False)


# ── api 规则 ──────────────────────────────────────────────────────────


class TestApiRules:
    GOOD_FLOW = [
        human("为端点 X 生成接口测试"),
        ai(calls=[("get_endpoint_details", {"endpoint_id": "e1"})]),
        tool("get_endpoint_details", '{"method": "POST"}'),
        ai(calls=[("get_endpoint_annotations", {"endpoint_id": "e1"})]),
        tool("get_endpoint_annotations", '{"annotations": []}'),
        ai(calls=[("derive_test_skeleton", {"endpoint_id": "e1"})]),
        tool("derive_test_skeleton", '{"skeleton": []}'),
        ai(calls=[("save_test_cases", {"test_cases": []})]),
        tool("save_test_cases", '{"success": true}'),
        ai(calls=[("audit_script_assertions", {"script_content": "..."})]),
        tool("audit_script_assertions", '{"verdict": "PASS"}'),
        ai(calls=[("save_test_script", {"script_content": "..."})]),
        tool("save_test_script", '{"success": true}'),
        ai('<EXECUTION_INVITATION>{"type":"execution_invitation","mode":"api"}</EXECUTION_INVITATION>'),
        human("[执行邀约] 立即执行"),
        ai(calls=[("execute_api_script", {"execution_config": {"env_id": "env1"}})]),
        tool("execute_api_script", '{"success": true}'),
    ]

    def test_good_flow_no_error(self):
        errs = {v.rule_id for v in run_rules(extract(self.GOOD_FLOW), "api")
                if v.severity == "error"}
        assert not errs, f"标杆流程不应有 error：{errs}"

    def test_t01_invitation_before_execute(self):
        bad = [human("测"), ai(calls=[("execute_api_script", {"execution_config": {"env_id": "e"}})])]
        check("API-T01", bad, "api", True)
        check("API-T01", self.GOOD_FLOW, "api", False)
        # scenario 同样受门禁
        bad_sc = [human("测"), ai(calls=[("execute_scenario", {"scenario_id": "s1"})])]
        check("API-T01", bad_sc, "api", True)

    def test_t02_audit_before_save(self):
        bad = [human("测"), ai(calls=[("save_test_script", {"script_content": "x"})])]
        check("API-T02", bad, "api", True)
        check("API-T02", self.GOOD_FLOW, "api", False)

    def test_t03_skeleton_before_cases(self):
        bad = [human("测"), ai(calls=[("save_test_cases", {"test_cases": []})])]
        check("API-T03", bad, "api", True)
        # 快速路径（有 details 无 skeleton）降级为 warning，不算 error
        fast = [human("测"), ai(calls=[("get_endpoint_details", {})]),
                ai(calls=[("save_test_cases", {"test_cases": []})])]
        hits = {v.rule_id: v.severity for v in run_rules(extract(fast), "api")}
        assert hits.get("API-T03") == "warning"

    def test_t04_annotations_consumed(self):
        bad = [
            human("测"),
            ai(calls=[("get_endpoint_details", {})]),
            ai(calls=[("derive_test_skeleton", {})]),
            ai(calls=[("save_test_cases", {"test_cases": []})]),
        ]
        check("API-T04", bad, "api", True)
        check("API-T04", self.GOOD_FLOW, "api", False)

    def test_t05_execute_requires_env(self):
        bad = [
            human("测"),
            ai('<EXECUTION_INVITATION>{}</EXECUTION_INVITATION>'),
            human("[执行邀约] 立即执行"),
            ai(calls=[("execute_api_script", {})]),
        ]
        check("API-T05", bad, "api", True)
        check("API-T05", self.GOOD_FLOW, "api", False)

    def test_t06_retry_budget(self):
        bad = [
            human("测"),
            ai(calls=[("web_api_request", {"url": "/x"})]),
            tool("web_api_request", '{"success": false, "error": "401"}'),
            ai(calls=[("web_api_request", {"url": "/x"})]),
            tool("web_api_request", '{"success": false, "error": "401"}'),
            ai(calls=[("web_api_request", {"url": "/x"})]),
            tool("web_api_request", '{"success": false, "error": "401"}'),
        ]
        check("API-T06", bad, "api", True)
        check("API-T06", self.GOOD_FLOW, "api", False)


# ── 规则注册表完整性 ──────────────────────────────────────────────────


class TestRuleRegistry:
    def test_unique_ids(self):
        ids = [r.rule_id for r in RULES]
        assert len(ids) == len(set(ids)), "规则 ID 重复"

    def test_all_agents_covered(self):
        agents = {r.agent for r in RULES}
        assert agents == {"testcase", "web", "api"}
