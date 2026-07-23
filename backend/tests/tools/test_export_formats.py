"""导出格式生成器单元测试"""

import csv
import io
import json

import pytest

from app.agents.tools.testcase.export_common import (
    EXPORT_HEADERS,
    case_key,
    extract_field,
    flatten_expected_results,
    flatten_preconditions,
    flatten_steps,
    flatten_test_data,
    localize_case_type,
    localize_priority,
)
from app.agents.tools.testcase.export_formats import (
    generate_test_cases_csv_bytes,
    generate_test_cases_json_bytes,
    generate_test_cases_markdown_bytes,
)


def test_localize_case_type():
    assert localize_case_type("functional") == "功能测试"
    assert localize_case_type("FUNCTIONAL") == "功能测试"
    assert localize_case_type("功能测试") == "功能测试"
    assert localize_case_type("unknown") == "unknown"
    assert localize_case_type(None) is None


def test_localize_priority():
    assert localize_priority("critical") == "P0"
    assert localize_priority("high") == "P1"
    assert localize_priority("P2") == "P2"
    assert localize_priority("unknown") == "unknown"


def test_extract_field_with_aliases():
    case = {"id": "", "identifier": "TC-001", "name": "登录"}
    assert extract_field(case, "id", "identifier") == "TC-001"

    case = {"title": "", "name": "注册"}
    assert extract_field(case, "title", "name") == "注册"

    case = {"remarks": None, "description": "备注"}
    assert extract_field(case, "remarks", "description") == "备注"


def test_flatten_steps_with_dicts():
    steps = [
        {"seq": 1, "step": "输入账号", "target": "账号框", "data": "user1"},
        {"seq": 2, "action": "点击登录", "target": "登录按钮"},
    ]
    text = flatten_steps(steps)
    assert "1. 输入账号 [账号框]（数据：user1）" in text
    assert "2. 点击登录 [登录按钮]" in text


def test_flatten_steps_with_strings():
    assert flatten_steps(["打开页面", "点击提交"]) == "1. 打开页面\n2. 点击提交"
    assert flatten_steps("already flat") == "already flat"
    assert flatten_steps([]) == ""


def test_flatten_test_data():
    assert flatten_test_data({"username": "admin"}) == "username: admin"
    assert flatten_test_data("raw data") == "raw data"
    assert flatten_test_data(None) == ""


def test_flatten_expected_results():
    assert flatten_expected_results(["成功", "跳转"]) == "1. 成功\n2. 跳转"
    assert flatten_expected_results("plain") == "plain"
    assert flatten_expected_results([]) == ""


def test_flatten_preconditions():
    assert flatten_preconditions(["已登录", "有权限"]) == "1. 已登录\n2. 有权限"
    assert flatten_preconditions(None) == ""


def test_case_key():
    assert case_key({"id": "TC-001", "name": "x"}) == "TC-001"
    assert case_key({"name": "x"}) == "x"
    assert case_key({}) is None


def test_generate_test_cases_json_bytes():
    cases = [
        {
            "id": "TC-001",
            "title": "登录",
            "module": "用户模块",
            "type": "functional",
            "priority": "high",
            "preconditions": "已注册",
            "steps": "1. 输入账号\n2. 点击登录",
            "test_data": "username: admin",
            "expected_results": "登录成功",
            "remarks": "",
        }
    ]
    data = generate_test_cases_json_bytes(cases)
    parsed = json.loads(data.decode("utf-8"))
    assert isinstance(parsed, list)
    assert parsed[0]["id"] == "TC-001"
    assert parsed[0]["title"] == "登录"
    # 步骤被还原为结构化列表
    assert isinstance(parsed[0]["steps"], list)
    assert parsed[0]["steps"][0]["seq"] == 1
    assert parsed[0]["steps"][0]["action"] == "输入账号"


def test_generate_test_cases_csv_bytes():
    cases = [
        {
            "id": "TC-001",
            "title": "登录",
            "module": "用户模块",
            "type": "功能测试",
            "priority": "P1",
            "preconditions": "已注册",
            "steps": "1. 输入账号\n2. 点击登录",
            "test_data": "username: admin",
            "expected_results": "登录成功",
            "remarks": "",
        }
    ]
    data = generate_test_cases_csv_bytes(cases)
    assert data.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM

    text = data.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    assert rows[0] == EXPORT_HEADERS
    assert rows[1][0] == "TC-001"
    assert rows[1][1] == "登录"


def test_generate_test_cases_csv_bytes_quoting():
    cases = [
        {
            "id": "TC-002",
            "title": "包含,逗号",
            "module": "模块",
            "type": "",
            "priority": "",
            "preconditions": "包含\n换行",
            "steps": '包含"引号',
            "test_data": "",
            "expected_results": "",
            "remarks": "",
        }
    ]
    data = generate_test_cases_csv_bytes(cases)
    text = data.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    assert len(rows) == 2
    assert rows[1][1] == "包含,逗号"
    assert rows[1][5] == "包含\n换行"
    assert rows[1][6] == '包含"引号'


def test_generate_test_cases_markdown_bytes():
    cases = [
        {
            "id": "TC-001",
            "title": "登录",
            "module": "用户模块",
            "type": "功能测试",
            "priority": "P1",
            "preconditions": "已注册",
            "steps": "1. 输入账号\n2. 点击登录",
            "test_data": "username: admin",
            "expected_results": "登录成功",
            "remarks": "",
        }
    ]
    data = generate_test_cases_markdown_bytes(cases)
    text = data.decode("utf-8")
    assert "# 测试用例导出" in text
    assert "| 用例编号 |" in text
    assert "| TC-001 |" in text
    # 换行应被替换为 <br>
    assert "1. 输入账号<br>2. 点击登录" in text
    assert "\n" in text  # 仍有换行作为表格行分隔


def test_generate_test_cases_markdown_bytes_escapes_pipe():
    cases = [
        {
            "id": "TC-003",
            "title": "A|B|C",
            "module": "模块",
            "type": "",
            "priority": "",
            "preconditions": "",
            "steps": "",
            "test_data": "",
            "expected_results": "",
            "remarks": "",
        }
    ]
    data = generate_test_cases_markdown_bytes(cases)
    text = data.decode("utf-8")
    # 管道符应被转义，避免破坏表格
    assert "A\\|B\\|C" in text


def test_generate_test_cases_markdown_bytes_empty():
    data = generate_test_cases_markdown_bytes([])
    text = data.decode("utf-8")
    assert "暂无测试用例" in text
