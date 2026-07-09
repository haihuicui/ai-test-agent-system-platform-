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

import pytest

from app.schemas.enums import TestResultStatus
from app.services.api_test_executor import APITestExecutor


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
