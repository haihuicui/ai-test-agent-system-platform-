"""Tests for ModuleSelfCheckMiddleware.

验证批量创建前模块级自检中间件的行为：
- 仅对 batch_create_test_cases_tool 生效
- 合规用例放行
- 不合规用例拦截并返回同构 violations
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import ToolMessage

from app.agents.testcase.module_self_check_middleware import (
    ModuleSelfCheckMiddleware,
    _resolve_expected_module,
)


def _make_request(tool_name: str, args: dict[str, Any]) -> MagicMock:
    """构造一个模拟的 ToolCallRequest。"""
    request = MagicMock()
    request.tool_call = {
        "id": "call_001",
        "name": tool_name,
        "args": args,
    }
    return request


def _valid_case(number: str = "TC-PROJ-LOGIN-001") -> dict[str, Any]:
    return {
        "name": "正确凭证登录成功",
        "case_number": number,
        "module": "登录模块",
        "priority": "critical",
        "test_data": {"username": "test001", "password": "Test@123"},
        "test_case_steps": [
            {
                "step": "输入正确用户名密码并点击登录",
                "result": "页面跳转至 /home 并显示昵称 test001",
            }
        ],
    }


class TestResolveExpectedModule:
    def test_returns_most_common_module(self):
        cases = [
            {"module": "登录模块"},
            {"module": "登录模块"},
            {"module": "订单模块"},
        ]
        assert _resolve_expected_module(cases) == "登录模块"

    def test_returns_none_when_no_module(self):
        assert _resolve_expected_module([{"name": "x"}]) is None

    def test_returns_none_for_empty_list(self):
        assert _resolve_expected_module([]) is None


class TestModuleSelfCheckMiddleware:
    @pytest.fixture
    def middleware(self):
        return ModuleSelfCheckMiddleware()

    @pytest.fixture
    def ok_handler(self):
        async def handler(request):
            return ToolMessage(
                content='{"success": true}',
                tool_call_id=request.tool_call["id"],
                name=request.tool_call["name"],
            )

        return handler

    @pytest.mark.asyncio
    async def test_non_target_tool_passes_through(self, middleware, ok_handler):
        request = _make_request("create_test_case_tool", {"name": "x"})
        result = await middleware.awrap_tool_call(request, ok_handler)
        assert isinstance(result, ToolMessage)
        assert result.status != "error"
        assert "success" in result.content

    @pytest.mark.asyncio
    async def test_valid_batch_passes_through(self, middleware, ok_handler):
        request = _make_request(
            "batch_create_test_cases_tool",
            {
                "project_identifier": "PROJ-1",
                "test_cases": [
                    _valid_case("TC-PROJ-LOGIN-001"),
                    _valid_case("TC-PROJ-LOGIN-002"),
                ],
            },
        )
        result = await middleware.awrap_tool_call(request, ok_handler)
        assert isinstance(result, ToolMessage)
        assert result.status != "error"

    @pytest.mark.asyncio
    async def test_invalid_batch_is_blocked(self, middleware):
        bad_case = _valid_case("TC-PROJ-LOGIN-001")
        bad_case["case_number"] = "BAD-NUMBER"  # 格式错误

        request = _make_request(
            "batch_create_test_cases_tool",
            {
                "project_identifier": "PROJ-1",
                "test_cases": [bad_case],
            },
        )

        handler = MagicMock()
        result = await middleware.awrap_tool_call(request, handler)

        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert result.name == "batch_create_test_cases_tool"
        handler.assert_not_called()

        payload = json.loads(result.content)
        assert payload["success"] is False
        assert any(
            "格式不符合" in " ".join(v["messages"])
            for v in payload["violations"]
            if v["level"] == "error"
        )

    @pytest.mark.asyncio
    async def test_empty_test_cases_passes_through(self, middleware, ok_handler):
        request = _make_request(
            "batch_create_test_cases_tool",
            {"project_identifier": "PROJ-1", "test_cases": []},
        )
        result = await middleware.awrap_tool_call(request, ok_handler)
        assert isinstance(result, ToolMessage)
        assert result.status != "error"

    @pytest.mark.asyncio
    async def test_missing_module_skips_check(self, middleware, ok_handler):
        request = _make_request(
            "batch_create_test_cases_tool",
            {
                "project_identifier": "PROJ-1",
                "test_cases": [{"name": "无模块用例"}],
            },
        )
        result = await middleware.awrap_tool_call(request, ok_handler)
        assert isinstance(result, ToolMessage)
        assert result.status != "error"

    @pytest.mark.asyncio
    async def test_sync_version_blocks(self, middleware):
        bad_case = _valid_case("TC-PROJ-LOGIN-001")
        bad_case["case_number"] = "BAD"

        request = _make_request(
            "batch_create_test_cases_tool",
            {"project_identifier": "PROJ-1", "test_cases": [bad_case]},
        )

        def handler(request):
            return ToolMessage(
                content='{"success": true}',
                tool_call_id=request.tool_call["id"],
                name=request.tool_call["name"],
            )

        result = middleware.wrap_tool_call(request, handler)
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
