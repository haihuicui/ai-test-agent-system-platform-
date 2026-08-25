"""web_api_request 工具与 storageState 凭据提取的单元测试。

覆盖：
- extract_credentials_from_storage_state_data：localStorage token 优先、
  cookie Authorization 回退、均无则 None
- web_api_request：非法方法/URL 拒绝、域名不匹配拒绝、鉴权注入与敏感头脱敏、
  响应截断、写方法（POST/DELETE）放行、超时与异常兜底
"""

import json
from types import SimpleNamespace

import pytest

import app.agents.tools.web.api_request_tools as mod
from app.agents.tools.web.api_request_tools import web_api_request
from app.utils.web_mcp_storage_state import (
    extract_credentials_from_storage_state_data,
)


class TestExtractCredentials:
    def test_localstorage_token_priority(self):
        ss = {
            "origins": [
                {
                    "origin": "https://a.com",
                    "localStorage": [{"name": "token", "value": "ls-token"}],
                }
            ],
            "cookies": [{"name": "Authorization", "value": "cookie-token"}],
        }
        token, cookies = extract_credentials_from_storage_state_data(ss)
        assert token == "ls-token"
        assert len(cookies) == 1

    def test_cookie_authorization_fallback(self):
        ss = {
            "origins": [],
            "cookies": [{"name": "Authorization", "value": "cookie-token"}],
        }
        token, _ = extract_credentials_from_storage_state_data(ss)
        assert token == "cookie-token"

    def test_no_credentials(self):
        token, cookies = extract_credentials_from_storage_state_data({"origins": []})
        assert token is None
        assert cookies == []


class _FakeResponse:
    def __init__(self, status=200, text='{"code":"2000","data":{"id":"x-1"}}'):
        self.status_code = status
        self.text = text


class _FakeClient:
    """记录请求参数的 httpx.AsyncClient 替身。"""

    last_request = None
    response = _FakeResponse()
    raise_exc = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def request(self, method, url, headers=None, json=None):
        type(self).last_request = {"method": method, "url": url, "headers": headers, "json": json}
        if type(self).raise_exc:
            raise type(self).raise_exc
        return type(self).response


@pytest.fixture(autouse=True)
def _patch_http(monkeypatch):
    _FakeClient.last_request = None
    _FakeClient.response = _FakeResponse()
    _FakeClient.raise_exc = None
    monkeypatch.setattr(mod.httpx, "AsyncClient", _FakeClient)
    yield


def _env(base_url="https://sit.example.com", auth_type="bearer"):
    return SimpleNamespace(name="sit", base_url=base_url, auth_type=auth_type)


def _patch_env(monkeypatch, env):
    async def fake_resolve(_pid):
        return SimpleNamespace(id="p1"), env

    monkeypatch.setattr(mod, "_resolve_project_env", fake_resolve)


def _patch_auth(monkeypatch, headers=None, cookies=None, source="env(bearer)"):
    async def fake_build_auth(_pid, _env):
        return headers or {}, cookies or [], source

    monkeypatch.setattr(mod, "_build_auth", fake_build_auth)


class TestWebApiRequest:
    @pytest.mark.asyncio
    async def test_reject_invalid_method(self, monkeypatch):
        _patch_env(monkeypatch, _env())
        _patch_auth(monkeypatch)
        result = json.loads(
            await web_api_request.ainvoke(
                {"method": "OPTIONS", "url": "https://sit.example.com/api/x", "purpose": "t"}
            )
        )
        assert result["success"] is False
        assert "不支持的 HTTP 方法" in result["error"]

    @pytest.mark.asyncio
    async def test_reject_incomplete_url(self, monkeypatch):
        _patch_env(monkeypatch, _env())
        _patch_auth(monkeypatch)
        result = json.loads(
            await web_api_request.ainvoke(
                {"method": "GET", "url": "/api/x", "purpose": "t"}
            )
        )
        assert result["success"] is False
        assert "URL 不完整" in result["error"]

    @pytest.mark.asyncio
    async def test_reject_domain_mismatch(self, monkeypatch):
        _patch_env(monkeypatch, _env(base_url="https://sit.example.com"))
        _patch_auth(monkeypatch)
        result = json.loads(
            await web_api_request.ainvoke(
                {
                    "method": "POST",
                    "url": "https://evil.example.com/api/x",
                    "purpose": "t",
                }
            )
        )
        assert result["success"] is False
        assert "不一致" in result["error"]
        assert _FakeClient.last_request is None  # 未发出请求

    @pytest.mark.asyncio
    async def test_post_allowed_with_auth_and_redaction(self, monkeypatch):
        _patch_env(monkeypatch, _env())
        _patch_auth(monkeypatch, headers={"Authorization": "Bearer secret-token"})
        result = json.loads(
            await web_api_request.ainvoke(
                {
                    "method": "POST",
                    "url": "https://sit.example.com/api/orders",
                    "purpose": "验证造数端点",
                    "body": {"sku": "SKU-001"},
                    "project_identifier": "PR-1",
                }
            )
        )
        assert result["success"] is True
        assert result["status"] == 200
        # 鉴权头实际注入到请求
        assert _FakeClient.last_request["headers"]["Authorization"] == "Bearer secret-token"
        assert _FakeClient.last_request["json"] == {"sku": "SKU-001"}
        # 返回值中敏感头已脱敏
        assert result["request_headers_sent"]["Authorization"] == "***"
        assert result["auth_source"] == "env(bearer)"

    @pytest.mark.asyncio
    async def test_delete_method_allowed(self, monkeypatch):
        _patch_env(monkeypatch, _env())
        _patch_auth(monkeypatch)
        result = json.loads(
            await web_api_request.ainvoke(
                {
                    "method": "DELETE",
                    "url": "https://sit.example.com/api/orders/x-1",
                    "purpose": "清理测试数据",
                }
            )
        )
        assert result["success"] is True
        assert _FakeClient.last_request["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_response_body_truncated(self, monkeypatch):
        _patch_env(monkeypatch, _env())
        _patch_auth(monkeypatch)
        _FakeClient.response = _FakeResponse(status=200, text="x" * 5000)
        result = json.loads(
            await web_api_request.ainvoke(
                {"method": "GET", "url": "https://sit.example.com/api/x", "purpose": "t"}
            )
        )
        assert result["success"] is True
        assert result["body_truncated"] is True
        assert len(result["body"]) == 2000

    @pytest.mark.asyncio
    async def test_timeout_returns_error_envelope(self, monkeypatch):
        import httpx as real_httpx

        _patch_env(monkeypatch, _env())
        _patch_auth(monkeypatch)
        _FakeClient.raise_exc = real_httpx.TimeoutException("timeout")
        result = json.loads(
            await web_api_request.ainvoke(
                {"method": "GET", "url": "https://sit.example.com/api/x", "purpose": "t"}
            )
        )
        assert result["success"] is False
        assert "超时" in result["error"]

    @pytest.mark.asyncio
    async def test_no_env_skips_domain_check(self, monkeypatch):
        """项目未配置环境时退化为不做域名校验（仅记录），请求仍发出。"""
        _patch_env(monkeypatch, None)
        _patch_auth(monkeypatch)
        result = json.loads(
            await web_api_request.ainvoke(
                {"method": "GET", "url": "https://any.example.com/api/x", "purpose": "t"}
            )
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_4xx_returns_failure_with_body(self, monkeypatch):
        _patch_env(monkeypatch, _env())
        _patch_auth(monkeypatch)
        _FakeClient.response = _FakeResponse(status=422, text='{"message":"name 必填"}')
        result = json.loads(
            await web_api_request.ainvoke(
                {
                    "method": "POST",
                    "url": "https://sit.example.com/api/orders",
                    "purpose": "t",
                    "body": {},
                }
            )
        )
        assert result["success"] is False
        assert result["status"] == 422
        assert "name 必填" in result["body"]
