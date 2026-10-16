"""
APITestExecutor 核心解析/匹配/摘要逻辑单元测试

覆盖：
- Playwright list reporter stdout 解析
- trace 条目与测试标题匹配
- 请求/响应/断言摘要构建
- 测试名称中端点与方法解析

注意：当前项目未安装 pytest，如需运行请先安装：
    uv add --dev pytest pytest-asyncio
或
    pip install pytest pytest-asyncio
"""

import json

import pytest

from app.schemas.enums import TestResultStatus
from app.services.api_test_executor import (
    APITestExecutor,
    API_BUSINESS_SUCCESS_CODES,
    _get_business_code_env_value,
    _extract_test_block,
    _script_expects_business_failure,
    _script_status_expectation,
)


class TestParsePlaywrightListOutput:
    def test_parses_ok_line(self):
        stdout = "  ok  1 [api-tests] › tests/example.spec.ts:3:7 › GET /users › should work (125ms)"
        result = APITestExecutor._parse_playwright_list_output(stdout)
        assert len(result) == 1
        assert result[0]["status"] == "passed"
        assert result[0]["title"] == "GET /users › should work"

    def test_parses_x_line(self):
        stdout = "  x   1 [api-tests] › tests/example.spec.ts:4:7 › POST /users › bad case (234ms)"
        result = APITestExecutor._parse_playwright_list_output(stdout)
        assert len(result) == 1
        assert result[0]["status"] == "failed"
        assert result[0]["title"] == "POST /users › bad case"

    def test_parses_check_mark_line(self):
        stdout = "  ✓  1 [chromium] › example.spec.ts:3:1 › GET /api/users (125ms)"
        result = APITestExecutor._parse_playwright_list_output(stdout)
        assert len(result) == 1
        assert result[0]["status"] == "passed"
        assert result[0]["title"] == "GET /api/users"

    def test_parses_multiple_lines(self):
        stdout = """Running 3 tests using 1 worker

  ok  1 [api-tests] › tests/example.spec.ts:3:7 › GET /users › should work (125ms)
  x   2 [api-tests] › tests/example.spec.ts:4:7 › POST /users › bad case (234ms)
  -   3 [api-tests] › tests/example.spec.ts:5:7 › PUT /users/1
"""
        result = APITestExecutor._parse_playwright_list_output(stdout)
        assert len(result) == 3
        assert result[0]["status"] == "passed"
        assert result[1]["status"] == "failed"
        assert result[2]["status"] == "skipped"

    def test_parses_seconds_duration_line(self):
        stdout = "  ok  1 [api-tests] › tests/example.spec.ts:3:7 › GET /users › should work (3.9s)"
        result = APITestExecutor._parse_playwright_list_output(stdout)
        assert len(result) == 1
        assert result[0]["status"] == "passed"
        assert result[0]["title"] == "GET /users › should work"

    def test_returns_empty_for_invalid_output(self):
        stdout = "some random output without test results"
        result = APITestExecutor._parse_playwright_list_output(stdout)
        assert result == []


class TestMatchTraceEntries:
    def test_match_by_exact_leaf_title(self):
        entries = [
            {"testTitle": "should work", "testName": "example.spec.ts › GET /users › should work"}
        ]
        matched = APITestExecutor._match_trace_entries("should work", entries)
        assert len(matched) == 1

    def test_match_by_full_stdout_title(self):
        entries = [
            {"testTitle": "should work", "testName": "example.spec.ts › GET /users › should work"}
        ]
        matched = APITestExecutor._match_trace_entries("GET /users › should work", entries)
        assert len(matched) == 1

    def test_match_by_full_path_with_file_prefix(self):
        entries = [
            {"testTitle": "should work", "testName": "example.spec.ts › GET /users › should work"}
        ]
        matched = APITestExecutor._match_trace_entries("GET /users › should work", entries)
        assert len(matched) == 1

    def test_match_chinese_title(self):
        entries = [
            {
                "testTitle": "【正常】成功新增客户",
                "testName": "customer.spec.ts › POST /customers › 【正常】成功新增客户",
            }
        ]
        stdout_title = "POST /customers › 【正常】成功新增客户"
        matched = APITestExecutor._match_trace_entries(stdout_title, entries)
        assert len(matched) == 1

    def test_no_match_returns_empty(self):
        entries = [
            {"testTitle": "other", "testName": "example.spec.ts › GET /other › other"}
        ]
        matched = APITestExecutor._match_trace_entries("GET /users › should work", entries)
        assert len(matched) == 0

    def test_multiple_entries_match_all(self):
        entries = [
            {"testTitle": "should work", "testName": "example.spec.ts › GET /users › should work"},
            {"testTitle": "should work", "testName": "example.spec.ts › GET /users › should work"},
        ]
        matched = APITestExecutor._match_trace_entries("GET /users › should work", entries)
        assert len(matched) == 2


class TestBuildTraceSummary:
    def test_success_case(self):
        entries = [
            {
                "method": "GET",
                "url": "https://api.example.com/users",
                "requestHeaders": {"Accept": "application/json"},
                "requestParams": {},
                "requestBody": None,
                "status": 200,
                "statusText": "OK",
                "responseHeaders": {"content-type": "application/json"},
                "responseBody": {"id": 1, "name": "test"},
                "durationMs": 100,
            }
        ]
        req, resp, assertions, duration = APITestExecutor._build_trace_summary(
            entries, TestResultStatus.PASSED
        )
        assert req["method"] == "GET"
        assert req["url"] == "https://api.example.com/users"
        assert resp["status"] == 200
        assert resp["body"] == {"id": 1, "name": "test"}
        assert resp["body_meta"]["truncated"] is False
        assert resp["body_meta"]["original_size"] == 0
        assert req["body_meta"]["truncated"] is False
        assert duration == 100
        assert any(a["assertion"]["type"] == "status" and a["passed"] for a in assertions)

    def test_body_meta_from_trace_entries(self):
        entries = [
            {
                "method": "POST",
                "url": "https://api.example.com/upload",
                "requestHeaders": {},
                "requestBody": {"name": "test"},
                "requestBodyOriginalSize": 25,
                "requestBodyTruncated": False,
                "status": 200,
                "responseHeaders": {},
                "responseBody": {"id": 1},
                "responseBodyOriginalSize": 50_001,
                "responseBodyTruncated": True,
                "durationMs": 100,
            }
        ]
        req, resp, _, _ = APITestExecutor._build_trace_summary(entries, TestResultStatus.PASSED)
        assert req["body_meta"]["original_size"] == 25
        assert req["body_meta"]["truncated"] is False
        assert resp["body_meta"]["original_size"] == 50_001
        assert resp["body_meta"]["truncated"] is True

    def test_prefers_entry_with_response_body(self):
        entries = [
            {
                "method": "GET",
                "url": "https://api.example.com/users",
                "status": 200,
                "responseBody": None,
                "durationMs": 50,
            },
            {
                "method": "GET",
                "url": "https://api.example.com/users",
                "status": 200,
                "responseBody": {"id": 1},
                "durationMs": 80,
            },
        ]
        req, resp, assertions, duration = APITestExecutor._build_trace_summary(
            entries, TestResultStatus.PASSED
        )
        assert resp["body"] == {"id": 1}
        assert duration == 80  # max duration

    def test_network_error_trace(self):
        entries = [
            {
                "method": "POST",
                "url": "https://api.example.com/users",
                "requestHeaders": {},
                "requestBody": {"name": "test"},
                "status": None,
                "statusText": "connect ECONNREFUSED",
                "responseHeaders": {},
                "responseBody": None,
                "durationMs": 10,
                "error": "connect ECONNREFUSED",
            }
        ]
        req, resp, assertions, duration = APITestExecutor._build_trace_summary(
            entries, TestResultStatus.FAILED
        )
        assert req is not None
        assert req["method"] == "POST"
        assert resp["status"] is None
        assert any(a["assertion"]["type"] == "test" and not a["passed"] for a in assertions)

    def test_empty_trace_entries(self):
        req, resp, assertions, duration = APITestExecutor._build_trace_summary(
            [], TestResultStatus.PASSED
        )
        assert req is None
        assert resp is None
        assert assertions is None
        assert duration is None


class TestBusinessCodeAssertionAwareSuppression:
    """业务码反假阳性的断言感知豁免：脚本断言已覆盖该业务失败时不再合成失败断言。"""

    SCRIPT = '''
import { test, expect } from '../api-trace-helper';

const PARAM_ERROR_CODE = '1000';

test('TC01 正向提交', async ({ request }) => {
  const resp = await request.post('/asset/delivery/submit', { data: {} });
  const body = await resp.json();
  expect(body.code).toBe(2000);
});

const requiredFields = [
  { field: 'sender', caseName: 'TC03-异常-缺少必填字段sender' },
  { field: 'sendTime', caseName: 'TC04-异常-缺少必填字段sendTime' },
];

for (const { field, caseName } of requiredFields) {
  test(caseName, async () => {
    const payload = { express: "{\\"a\\":1}" };
    delete payload[field];
    const { status, body } = await postDelivery('submit', payload);
    expect([200, 400, 422]).toContain(status);
    expect(body.code).toBe(PARAM_ERROR_CODE);
  });
}

test('TC08-异常-expressType类型错误', async ({ request }) => {
  const resp = await request.post('/asset/delivery/submit', { data: {} });
  const body = await resp.json();
  expect(body.code).toBe(PARAM_ERROR_CODE);
});

test('TC12-边界-shipments空数组', async ({ request }) => {
  const resp = await request.post('/asset/delivery/submit', { data: {} });
  const body = await resp.json();
  expect(resp.status()).toBeLessThan(500);
  expect(body.code).toBe(PARAM_ERROR_CODE);
});

test('TC13b-边界-tubeNumber未登记', async ({ request }) => {
  const resp = await request.post('/asset/delivery/submit', { data: {} });
  const body = await resp.json();
  expect(body.code).toBe('H047');
});

test('TC14-安全-无认证凭证', async ({ request }) => {
  const resp = await request.post('/asset/delivery/submit', { data: {} });
  expect(resp.status()).toBe(401);
});
'''

    @staticmethod
    def _trace(code=None, success=None, status=200):
        return [{
            "method": "POST",
            "url": "https://api.example.com/asset/delivery/submit",
            "status": status,
            "responseHeaders": {},
            "responseBody": {"code": code, "success": success, "message": "参数错误"},
            "durationMs": 42,
        }]

    def test_extract_test_block_hit_and_miss(self):
        # 参数化用例（for 循环内 test(caseName, ...)）通过数组项标题定位
        block = _extract_test_block(self.SCRIPT, "TC03-异常-缺少必填字段sender")
        assert block is not None
        assert "expect(body.code).toBe(PARAM_ERROR_CODE)" in block
        # 字符串字面量里的花括号不得干扰配平：块不应溢出到后续用例
        assert "TC08" not in block
        # 普通字面量标题直接命中
        assert _extract_test_block(self.SCRIPT, "TC01 正向提交") is not None
        assert _extract_test_block(self.SCRIPT, "不存在的用例") is None
        assert _extract_test_block("", "TC01 正向提交") is None

    def test_expects_business_failure_by_code(self):
        # 参数化用例 + 常量引用（const PARAM_ERROR_CODE = '1000'）
        assert _script_expects_business_failure(
            self.SCRIPT, "TC03-异常-缺少必填字段sender", code=1000
        ) is True
        assert _script_expects_business_failure(
            self.SCRIPT, "TC03-异常-缺少必填字段sender", code="1000"
        ) is True
        # 字面量标题 + 常量引用
        assert _script_expects_business_failure(
            self.SCRIPT, "TC08-异常-expressType类型错误", code=1000
        ) is True
        # 错误码值不匹配 → 不豁免
        assert _script_expects_business_failure(
            self.SCRIPT, "TC08-异常-expressType类型错误", code=4009
        ) is False
        # 正向用例未断言失败码 → 不豁免
        assert _script_expects_business_failure(
            self.SCRIPT, "TC01 正向提交", code=5000
        ) is False

    def test_expects_business_failure_by_success(self):
        script = "test('TC04 类型错误', async () => { expect(body.success).toBe(false); });"
        assert _script_expects_business_failure(script, "TC04 类型错误", success=False) is True
        # success=True 的 trace 不存在业务失败，不应触发豁免判定
        assert _script_expects_business_failure(script, "TC04 类型错误", success=True) is False

    def test_status_expectation_from_script(self):
        # expect(resp.status()).toBe(401)
        assert _script_status_expectation(self.SCRIPT, "TC14-安全-无认证凭证") == ("set", [401])
        # expect([200, 400, 422]).toContain(status)
        assert _script_status_expectation(
            self.SCRIPT, "TC03-异常-缺少必填字段sender"
        ) == ("set", [200, 400, 422])
        # expect(resp.status()).toBeLessThan(500)
        assert _script_status_expectation(self.SCRIPT, "TC12-边界-shipments空数组") == ("lt", 500)
        # 无状态码断言 → None（回退默认 2xx）
        assert _script_status_expectation(self.SCRIPT, "TC01 正向提交") is None

    def test_trace_summary_status_401_passes_with_script_expectation(self):
        """安全用例脚本预期 401，trace 实际 401 → 派生状态断言通过，不再误标。"""
        _, _, assertions, _ = APITestExecutor._build_trace_summary(
            self._trace(status=401), TestResultStatus.PASSED,
            script_text=self.SCRIPT, test_title="TC14-安全-无认证凭证",
        )
        st = [a for a in assertions if a["assertion"].get("type") == "status"]
        assert len(st) == 1
        assert st[0]["passed"] is True
        assert st[0]["expected"] == "401"

    def test_trace_summary_suppressed_when_script_covers(self):
        req, resp, assertions, _ = APITestExecutor._build_trace_summary(
            self._trace(code=1000), TestResultStatus.PASSED,
            script_text=self.SCRIPT, test_title="TC03-异常-缺少必填字段sender",
        )
        bc = [a for a in assertions if a["assertion"].get("type") == "business_code"]
        assert len(bc) == 1
        assert bc[0]["passed"] is True
        assert "豁免" in bc[0]["message"]
        # 无任何失败断言 → 外层 PASSED 不会被翻转
        assert not any(a.get("passed") is False for a in assertions)

    def test_trace_summary_not_suppressed_without_script(self):
        """未提供脚本源码时维持原行为：业务错误码合成失败断言。"""
        _, _, assertions, _ = APITestExecutor._build_trace_summary(
            self._trace(code=1000), TestResultStatus.PASSED,
        )
        bc = [a for a in assertions if a["assertion"].get("type") == "business_code"]
        assert len(bc) == 1
        assert bc[0]["passed"] is False

    def test_trace_summary_not_suppressed_for_sloppy_positive(self):
        """正向用例未断言业务码（偷懒脚本）→ 仍然合成失败断言，防护保留。"""
        _, _, assertions, _ = APITestExecutor._build_trace_summary(
            self._trace(code=5000), TestResultStatus.PASSED,
            script_text=self.SCRIPT, test_title="TC01 正向提交",
        )
        bc = [a for a in assertions if a["assertion"].get("type") == "business_code"]
        assert len(bc) == 1
        assert bc[0]["passed"] is False


class TestTruncateBodyInData:
    def test_no_truncation_for_small_body(self):
        data = {
            "method": "GET",
            "body": {"id": 1},
            "body_meta": {"truncated": False, "original_size": 100},
        }
        result = APITestExecutor._truncate_body_in_data(data)
        assert result["body"] == {"id": 1}
        assert "preview_length" not in result["body_meta"]

    def test_truncation_for_large_body(self):
        data = {
            "method": "GET",
            "body": "x" * 5_000,
            "body_meta": {"truncated": True, "original_size": 5_000},
        }
        result = APITestExecutor._truncate_body_in_data(data)
        assert isinstance(result["body"], str)
        assert result["body"].endswith("...[truncated]")
        assert result["body_meta"]["preview_length"] == 2_000

    def test_passes_through_none(self):
        assert APITestExecutor._truncate_body_in_data(None) is None

    def test_passes_through_untruncated(self):
        data = {"method": "GET", "body": "small"}
        result = APITestExecutor._truncate_body_in_data(data)
        assert result["body"] == "small"


class TestParseEndpointFromTestName:
    def test_simple_title(self):
        assert APITestExecutor._parse_endpoint_from_test_name("GET /api/v1/users") == (
            "/api/v1/users",
            "GET",
        )

    def test_full_path_with_describe(self):
        assert APITestExecutor._parse_endpoint_from_test_name(
            "GET /api/v1/users › should return list"
        ) == ("/api/v1/users", "GET")

    def test_chinese_describe_title(self):
        assert APITestExecutor._parse_endpoint_from_test_name(
            "POST /xmetrix-data/customer - 新增客户 › 【正常】成功新增客户"
        ) == ("/xmetrix-data/customer", "POST")

    def test_lowercase_method(self):
        assert APITestExecutor._parse_endpoint_from_test_name("post /api/v1/users") == (
            "/api/v1/users",
            "POST",
        )

    def test_no_method_defaults_to_get(self):
        assert APITestExecutor._parse_endpoint_from_test_name("some test name") == (
            "some test name",
            "GET",
        )


class TestBusinessCodeCheck:
    def test_env_value_contains_all_success_codes(self):
        raw = _get_business_code_env_value()
        parsed = json.loads(raw)
        assert isinstance(parsed, list)
        for code in API_BUSINESS_SUCCESS_CODES:
            assert code in parsed

    def test_check_business_code_success_values(self):
        for code in [0, "0", 200, "200", 2000, "2000", "success", "SUCCESS", True]:
            entry = {"responseBody": {"code": code}}
            assert APITestExecutor._check_business_code(entry) is None

    def test_check_business_code_failing_values(self):
        for code in [4001, "4001", 4009, "5000", "failed"]:
            entry = {"responseBody": {"code": code}}
            result = APITestExecutor._check_business_code(entry)
            assert result is not None
            assert result["passed"] is False
            assert "body.code" in result["message"]

    def test_check_business_code_success_field_false(self):
        entry = {"responseBody": {"success": False, "code": "0"}}
        result = APITestExecutor._check_business_code(entry)
        assert result is not None
        assert result["passed"] is False
        assert "body.success" in result["message"]

    def test_check_business_code_success_field_true(self):
        entry = {"responseBody": {"success": True, "code": "4001"}}
        assert APITestExecutor._check_business_code(entry) is None

    def test_check_business_code_missing_body(self):
        assert APITestExecutor._check_business_code({"responseBody": None}) is None
        assert APITestExecutor._check_business_code({"responseBody": "plain text"}) is None
        assert APITestExecutor._check_business_code({}) is None
