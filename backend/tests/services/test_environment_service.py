"""
EnvironmentService 动态 token 相关单元测试

注意：当前项目未安装 pytest，如需运行请先安装：
    uv add --dev pytest pytest-asyncio pytest-httpx
或
    pip install pytest pytest-asyncio pytest-httpx
"""

import asyncio
import json

import pytest

from app.utils.auth_resolver import (
    render_template,
    extract_by_path,
    DynamicTokenError,
    _TokenCache,
    build_auth_headers,
    resolve_auth_credentials,
)


class TestRenderTemplate:
    def test_string_replacement(self):
        assert render_template("{{user}}:{{pass}}", {"user": "admin", "pass": "secret"}) == "admin:secret"

    def test_no_match_left_unchanged(self):
        assert render_template("{{missing}}", {"other": "x"}) == "{{missing}}"

    def test_dict_rendering(self):
        result = render_template(
            {"username": "{{user}}", "password": "{{pass}}"},
            {"user": "a", "pass": "b"},
        )
        assert result == {"username": "a", "password": "b"}

    def test_list_rendering(self):
        result = render_template(["{{x}}", "{{y}}"], {"x": "1", "y": "2"})
        assert result == ["1", "2"]

    def test_nested_rendering(self):
        result = render_template(
            {"data": {"name": "{{name}}"}, "list": ["{{v}}"]},
            {"name": "test", "v": "val"},
        )
        assert result == {"data": {"name": "test"}, "list": ["val"]}


class TestExtractByPath:
    def test_dot_path(self):
        data = {"data": {"token": "abc123"}}
        assert extract_by_path(data, "data.token") == "abc123"

    def test_jsonpath(self):
        data = {"data": {"token": "abc123"}}
        assert extract_by_path(data, "$.data.token") == "abc123"

    def test_missing_dot_path(self):
        with pytest.raises(DynamicTokenError):
            extract_by_path({}, "data.token")

    def test_missing_jsonpath(self):
        with pytest.raises(DynamicTokenError):
            extract_by_path({}, "$.data.token")

    def test_invalid_path_type(self):
        with pytest.raises(DynamicTokenError):
            extract_by_path({"data": "string"}, "data.token")


class TestTokenCache:
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        cache = _TokenCache(default_ttl=60)
        await cache.set("env-1", {"url": "https://example.com"}, "token-1")
        assert await cache.get("env-1", {"url": "https://example.com"}) == "token-1"

    @pytest.mark.asyncio
    async def test_cache_miss_different_config(self):
        cache = _TokenCache(default_ttl=60)
        await cache.set("env-1", {"url": "https://example.com"}, "token-1")
        assert await cache.get("env-1", {"url": "https://other.com"}) is None

    @pytest.mark.asyncio
    async def test_cache_expires(self):
        cache = _TokenCache(default_ttl=0)
        await cache.set("env-1", {"url": "https://example.com"}, "token-1", ttl=0)
        # ttl=0 means immediately expired in this tiny cache window
        assert await cache.get("env-1", {"url": "https://example.com"}) is None


class TestBuildAuthHeaders:
    def test_none_returns_empty(self):
        assert build_auth_headers("none", "secret", {}) == {}

    def test_bearer(self):
        headers = build_auth_headers("bearer", "token123", {})
        assert headers == {"Authorization": "Bearer token123"}

    def test_oauth2(self):
        headers = build_auth_headers("oauth2", "token123", {})
        assert headers == {"Authorization": "Bearer token123"}

    def test_api_key_default_header(self):
        headers = build_auth_headers("api_key", "key123", {})
        assert headers == {"X-API-Key": "key123"}

    def test_api_key_custom_header(self):
        headers = build_auth_headers("api_key", "key123", {"api_key_header": "X-Custom-Key"})
        assert headers == {"X-Custom-Key": "key123"}

    def test_dynamic_bearer_returns_empty(self):
        # 动态 token 需要异步获取，build_auth_headers 不处理
        assert build_auth_headers("dynamic_bearer", "", {}) == {}

    def test_missing_secret_returns_empty(self):
        assert build_auth_headers("bearer", None, {}) == {}


class TestResolveAuthCredentials:
    @pytest.mark.asyncio
    async def test_bearer_credentials(self):
        env = type(
            "FakeEnv",
            (),
            {
                "auth_type": "bearer",
                "auth_secret": "token123",
                "auth_config": {},
            },
        )()
        creds = await resolve_auth_credentials(env)
        assert creds.headers == {"Authorization": "Bearer token123"}
        assert creds.token == "token123"
        assert creds.auth_type == "bearer"

    @pytest.mark.asyncio
    async def test_api_key_credentials(self):
        env = type(
            "FakeEnv",
            (),
            {
                "auth_type": "api_key",
                "auth_secret": "key123",
                "auth_config": {"api_key_header": "X-Api-Key"},
            },
        )()
        creds = await resolve_auth_credentials(env)
        assert creds.headers == {"X-Api-Key": "key123"}
        assert creds.token == "key123"

    @pytest.mark.asyncio
    async def test_none_credentials(self):
        env = type(
            "FakeEnv",
            (),
            {
                "auth_type": "none",
                "auth_secret": None,
                "auth_config": {},
            },
        )()
        creds = await resolve_auth_credentials(env)
        assert creds.headers == {}
        assert creds.token is None


class TestResolveDynamicBearerToken:
    """动态 token 解析的集成测试需要 pytest-httpx 和数据库 mock，此处占位。"""

    @pytest.mark.skip(reason="需要 pytest-httpx 和 AsyncSession mock")
    @pytest.mark.asyncio
    async def test_resolve_token_success(self):
        pass
