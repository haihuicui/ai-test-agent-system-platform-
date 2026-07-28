"""RAG MCP Server 单元测试

覆盖：
- RAGServiceClient 认证头、重试、工作空间头、JWT 刷新
- RAGQueryCache 命中/过期/LRU/排除规则
- _build_query_body 与白名单过滤
- 7 个 MCP 工具的调用与错误处理
- CLI 默认密码安全

注意：rag_server.py 是独立入口脚本，为了不触发 app.agents.tools 包中
其他工具的重依赖链，此处通过 importlib 直接从文件路径加载该模块。
"""

import asyncio
import importlib.util
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import AsyncMock, patch

import httpx
import pytest


# 直接从文件路径加载 rag_server.py，避免 app.agents.tools __init__ 的依赖链
_RAG_SERVER_PATH = (
    Path(__file__).resolve().parents[3]
    / "backend"
    / "app"
    / "agents"
    / "tools"
    / "testcase"
    / "mcp"
    / "rag_server.py"
)
_spec = importlib.util.spec_from_file_location("_rag_server_under_test", _RAG_SERVER_PATH)
_rag_server = importlib.util.module_from_spec(_spec)
sys.modules["_rag_server_under_test"] = _rag_server
_spec.loader.exec_module(_rag_server)


API_KEY_HEADER = _rag_server.API_KEY_HEADER
SPACE_HEADER = _rag_server.SPACE_HEADER
QUERY_REQUEST_FIELDS = _rag_server.QUERY_REQUEST_FIELDS
DEFAULT_BASE_URL = _rag_server.DEFAULT_BASE_URL
VALID_QUERY_MODES = _rag_server.VALID_QUERY_MODES
RAGAPIError = _rag_server.RAGAPIError
RAGQueryCache = _rag_server.RAGQueryCache
RAGServiceClient = _rag_server.RAGServiceClient
_build_query_body = _rag_server._build_query_body
_build_argument_parser = _rag_server._build_argument_parser
parse_arguments = _rag_server.parse_arguments
rag_query = _rag_server.rag_query
rag_query_data = _rag_server.rag_query_data
rag_graph_search = _rag_server.rag_graph_search
rag_graph_get = _rag_server.rag_graph_get
rag_graph_labels = _rag_server.rag_graph_labels
rag_document_status = _rag_server.rag_document_status
rag_health = _rag_server.rag_health


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def api_key_client() -> RAGServiceClient:
    """使用 API Key 认证的客户端"""
    return RAGServiceClient(
        base_url="http://rag.test",
        api_key="secret-key",
        default_space_id="cmp_space",
    )


@pytest.fixture
def jwt_client() -> RAGServiceClient:
    """使用 JWT 认证的客户端"""
    return RAGServiceClient(
        base_url="http://rag.test",
        username="admin",
        password="admin-pass",
    )


@pytest.fixture
async def async_api_key_client() -> RAGServiceClient:
    """异步关闭的 API Key 客户端"""
    client = RAGServiceClient(
        base_url="http://rag.test",
        api_key="secret-key",
    )
    yield client
    await client.close()


def make_fake_context(client: RAGServiceClient) -> Any:
    """构造一个足以让 _get_client 工作的最小 Fake Context"""
    lifespan_ctx = SimpleNamespace(client=client)
    request_ctx = SimpleNamespace(lifespan_context=lifespan_ctx)
    return SimpleNamespace(request_context=request_ctx)


# ============================================================================
# RAGServiceClient HTTP 行为
# ============================================================================


@pytest.mark.asyncio
async def test_api_key_sent_as_x_api_key_header(
    httpx_mock, api_key_client: RAGServiceClient
):
    """API Key 模式下应发送 X-API-Key，不应发送 Authorization"""
    httpx_mock.add_response(
        url="http://rag.test/query",
        method="POST",
        json={"response": "ok"},
    )

    await api_key_client.post("/query", {"query": "hello", "mode": "mix"})

    request = httpx_mock.get_request()
    assert request.headers[API_KEY_HEADER] == "secret-key"
    assert "Authorization" not in request.headers
    await api_key_client.close()


@pytest.mark.asyncio
async def test_jwt_login_and_bearer_header(httpx_mock, jwt_client: RAGServiceClient):
    """JWT 模式下先 POST /login 获取 token，再带 Bearer 调用目标接口"""
    httpx_mock.add_response(
        url="http://rag.test/login",
        method="POST",
        json={"access_token": "jwt-token-123"},
    )
    httpx_mock.add_response(
        url="http://rag.test/query",
        method="POST",
        json={"response": "ok"},
    )

    await jwt_client.post("/query", {"query": "hello", "mode": "mix"})

    requests = httpx_mock.get_requests()
    assert len(requests) == 2
    login_req, query_req = requests
    assert login_req.url.path == "/login"
    assert query_req.headers["Authorization"] == "Bearer jwt-token-123"
    await jwt_client.close()


@pytest.mark.asyncio
async def test_workspace_header_sent_as_lightrag_workspace(
    httpx_mock, api_key_client: RAGServiceClient
):
    """space_id 应通过 LIGHTRAG-WORKSPACE 头发出"""
    httpx_mock.add_response(
        url="http://rag.test/health",
        method="GET",
        json={"status": "healthy"},
    )

    await api_key_client.get("/health", space_id="space-a")

    request = httpx_mock.get_request()
    assert request.headers[SPACE_HEADER] == "space-a"
    await api_key_client.close()


@pytest.mark.asyncio
async def test_retry_on_5xx_then_success(api_key_client: RAGServiceClient):
    """5xx 应自动重试，成功时返回结果"""
    call_count = 0

    def handler(request):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    client = RAGServiceClient(
        base_url="http://rag.test",
        api_key="secret-key",
    )
    # 注入自定义 transport 以便精确控制重试
    async with httpx.AsyncClient(
        base_url="http://rag.test", transport=transport
    ) as raw_client:
        client._client = raw_client
        result = await client.get("/health")
        assert result == {"status": "ok"}
        assert call_count == 3
    await client.close()


@pytest.mark.asyncio
async def test_no_retry_on_4xx(httpx_mock, api_key_client: RAGServiceClient):
    """4xx 客户端错误不应重试，直接抛 RAGAPIError"""
    httpx_mock.add_response(
        url="http://rag.test/query",
        method="POST",
        status_code=422,
        json={"detail": "Invalid query mode"},
    )

    with pytest.raises(RAGAPIError) as exc_info:
        await api_key_client.post("/query", {"query": "x", "mode": "bad"})

    assert exc_info.value.status_code == 422
    assert "Invalid query mode" in exc_info.value.detail
    assert len(httpx_mock.get_requests()) == 1
    await api_key_client.close()


@pytest.mark.asyncio
async def test_jwt_refresh_on_401(httpx_mock, jwt_client: RAGServiceClient):
    """JWT 过期返回 401 时应重新登录并重放请求"""
    # 第一次登录
    httpx_mock.add_response(
        url="http://rag.test/login",
        method="POST",
        json={"access_token": "token-v1"},
    )
    # 第一次调用 401
    httpx_mock.add_response(
        url="http://rag.test/query",
        method="POST",
        status_code=401,
        text="Unauthorized",
    )
    # 重新登录
    httpx_mock.add_response(
        url="http://rag.test/login",
        method="POST",
        json={"access_token": "token-v2"},
    )
    # 重放成功
    httpx_mock.add_response(
        url="http://rag.test/query",
        method="POST",
        json={"response": "ok"},
    )

    result = await jwt_client.post("/query", {"query": "hello", "mode": "mix"})

    assert result == {"response": "ok"}
    requests = httpx_mock.get_requests()
    assert len(requests) == 4
    # 第二次 /query 使用新 token
    assert requests[3].headers["Authorization"] == "Bearer token-v2"
    await jwt_client.close()


# ============================================================================
# RAGQueryCache
# ============================================================================


def test_cache_hit_returns_value():
    cache = RAGQueryCache(ttl_seconds=60, max_entries=10)
    body = {"query": "hello", "mode": "mix"}
    cache.set("POST", "/query", body, None, {"response": "ok"})

    assert cache.get("POST", "/query", body, None) == {"response": "ok"}


def test_cache_miss_for_different_space_id():
    cache = RAGQueryCache(ttl_seconds=60, max_entries=10)
    body = {"query": "hello", "mode": "mix"}
    cache.set("POST", "/query", body, "space-a", {"response": "a"})

    assert cache.get("POST", "/query", body, "space-b") is None


def test_cache_ttl_expires():
    cache = RAGQueryCache(ttl_seconds=0.01, max_entries=10)
    body = {"query": "hello"}
    cache.set("POST", "/query", body, None, {"response": "ok"})

    time.sleep(0.02)
    assert cache.get("POST", "/query", body, None) is None


def test_cache_lru_eviction():
    cache = RAGQueryCache(ttl_seconds=60, max_entries=2)
    cache.set("POST", "/query", {"query": "a"}, None, 1)
    cache.set("POST", "/query", {"query": "b"}, None, 2)
    cache.set("POST", "/query", {"query": "c"}, None, 3)

    assert cache.get("POST", "/query", {"query": "a"}, None) is None
    assert cache.get("POST", "/query", {"query": "b"}, None) == 2
    assert cache.get("POST", "/query", {"query": "c"}, None) == 3


def test_cache_skips_conversation_history():
    cache = RAGQueryCache(ttl_seconds=60, max_entries=10)
    body = {"query": "hello", "conversation_history": [{"role": "user", "content": "x"}]}

    assert cache._make_key("POST", "/query", body, None) is None


def test_cache_skips_stream_and_context_only():
    cache = RAGQueryCache(ttl_seconds=60, max_entries=10)

    assert cache._make_key("POST", "/query", {"stream": True}, None) is None
    assert cache._make_key("POST", "/query", {"only_need_context": True}, None) is None
    assert cache._make_key("POST", "/query", {"only_need_prompt": True}, None) is None


def test_cache_disabled_env():
    with patch.object(_rag_server, "CACHE_DISABLED", True):
        cache = RAGQueryCache(ttl_seconds=60, max_entries=10)
        body = {"query": "hello"}
        cache.set("POST", "/query", body, None, {"response": "ok"})

        assert cache.get("POST", "/query", body, None) is None


# ============================================================================
# Query Body Builder & Whitelist
# ============================================================================


def test_build_query_body_excludes_none_and_vlm():
    body = _build_query_body(query="hello")

    assert "enable_vlm_enhanced" not in body
    assert all(v is not None for v in body.values())
    assert body["query"] == "hello"
    assert body["mode"] == "mix"


def test_build_query_body_includes_optional_fields():
    body = _build_query_body(
        query="hello",
        max_entity_tokens=100,
        response_type="Multiple Paragraphs",
        hl_keywords=["a", "b"],
    )

    assert body["max_entity_tokens"] == 100
    assert body["response_type"] == "Multiple Paragraphs"
    assert body["hl_keywords"] == ["a", "b"]


def test_build_query_body_boolean_flags_only_when_true():
    body_false = _build_query_body(query="hello", only_need_context=False, only_need_prompt=False)
    assert "only_need_context" not in body_false
    assert "only_need_prompt" not in body_false

    body_true = _build_query_body(query="hello", only_need_context=True, only_need_prompt=True)
    assert body_true["only_need_context"] is True
    assert body_true["only_need_prompt"] is True


def test_query_request_fields_match_build_body():
    """确保 _build_query_body 可能产生的所有键都在白名单内"""
    body = _build_query_body(
        query="hello",
        mode="mix",
        top_k=10,
        chunk_top_k=5,
        max_entity_tokens=1,
        max_relation_tokens=1,
        max_total_tokens=1,
        hl_keywords=["a"],
        ll_keywords=["b"],
        conversation_history=[{"role": "user", "content": "hi"}],
        enable_rerank=True,
        include_references=True,
        include_chunk_content=True,
        response_type="x",
        user_prompt="y",
        only_need_context=True,
        only_need_prompt=True,
        stream=False,
    )
    assert set(body.keys()).issubset(QUERY_REQUEST_FIELDS)


# ============================================================================
# MCP Tools
# ============================================================================


@pytest.mark.asyncio
async def test_rag_query_returns_response_text(httpx_mock):
    httpx_mock.add_response(
        url="http://rag.test/query",
        method="POST",
        json={"response": "This is the answer."},
    )
    client = RAGServiceClient(base_url="http://rag.test", api_key="secret-key")
    ctx = make_fake_context(client)

    result = await rag_query("What is AI?", ctx=ctx)

    assert result == "This is the answer."
    await client.close()


@pytest.mark.asyncio
async def test_rag_query_empty_response():
    client = RAGServiceClient(base_url="http://rag.test", api_key="secret-key")
    ctx = make_fake_context(client)

    with patch.object(
        client, "post", new_callable=AsyncMock, return_value={"response": ""}
    ):
        result = await rag_query("What is AI?", ctx=ctx)
        assert result == "(空响应)"

    await client.close()


@pytest.mark.asyncio
async def test_rag_query_invalid_mode():
    client = RAGServiceClient(base_url="http://rag.test", api_key="secret-key")
    ctx = make_fake_context(client)

    result = await rag_query("hello", mode="invalid", ctx=ctx)

    assert "无效模式" in result
    assert all(m in result for m in VALID_QUERY_MODES)
    await client.close()


@pytest.mark.asyncio
async def test_rag_query_error_includes_status_code(httpx_mock):
    httpx_mock.add_response(
        url="http://rag.test/query",
        method="POST",
        status_code=404,
        json={"detail": "not found"},
    )
    client = RAGServiceClient(base_url="http://rag.test", api_key="secret-key")
    ctx = make_fake_context(client)

    result = await rag_query("hello", ctx=ctx)

    assert "404" in result
    assert "not found" in result
    await client.close()


@pytest.mark.asyncio
async def test_rag_query_data_returns_json(httpx_mock):
    httpx_mock.add_response(
        url="http://rag.test/query/data",
        method="POST",
        json={"data": {"entities": []}, "status": "success"},
    )
    client = RAGServiceClient(base_url="http://rag.test", api_key="secret-key")
    ctx = make_fake_context(client)

    result = await rag_query_data("hello", ctx=ctx)
    parsed = json.loads(result)

    assert parsed["data"]["entities"] == []
    # include_references 强制为 True
    request = httpx_mock.get_request()
    sent_body = json.loads(request.content)
    assert sent_body["include_references"] is True
    await client.close()


@pytest.mark.asyncio
async def test_rag_query_data_prunes_unknown_fields(httpx_mock):
    """即使工具内部多传了字段，最终请求体也应被白名单过滤"""
    httpx_mock.add_response(
        url="http://rag.test/query/data",
        method="POST",
        json={"data": {}},
    )
    client = RAGServiceClient(base_url="http://rag.test", api_key="secret-key")
    ctx = make_fake_context(client)

    await rag_query_data("hello", ctx=ctx)

    request = httpx_mock.get_request()
    sent_body = json.loads(request.content)
    assert "enable_vlm_enhanced" not in sent_body
    await client.close()


@pytest.mark.asyncio
async def test_rag_graph_search_clamps_limit(httpx_mock):
    httpx_mock.add_response(
        url="http://rag.test/graph/label/search?q=foo&limit=100",
        method="GET",
        json=["label-a"],
    )
    client = RAGServiceClient(base_url="http://rag.test", api_key="secret-key")
    ctx = make_fake_context(client)

    result = await rag_graph_search("foo", limit=200, ctx=ctx)
    parsed = json.loads(result)

    assert parsed == ["label-a"]
    await client.close()


@pytest.mark.asyncio
async def test_rag_graph_get_clamps_max_depth(httpx_mock):
    httpx_mock.add_response(
        url="http://rag.test/graphs?label=EntityA&max_depth=3",
        method="GET",
        json={"nodes": ["EntityA"], "edges": []},
    )
    client = RAGServiceClient(base_url="http://rag.test", api_key="secret-key")
    ctx = make_fake_context(client)

    result = await rag_graph_get("EntityA", max_depth=10, ctx=ctx)
    parsed = json.loads(result)

    assert parsed["nodes"] == ["EntityA"]
    await client.close()


@pytest.mark.asyncio
async def test_rag_graph_labels(httpx_mock):
    httpx_mock.add_response(
        url="http://rag.test/graph/label/list",
        method="GET",
        json=["PERSON", "ORG"],
    )
    client = RAGServiceClient(base_url="http://rag.test", api_key="secret-key")
    ctx = make_fake_context(client)

    result = await rag_graph_labels(ctx=ctx)
    parsed = json.loads(result)

    assert parsed == ["PERSON", "ORG"]
    await client.close()


@pytest.mark.asyncio
async def test_rag_document_status_active(httpx_mock):
    httpx_mock.add_response(
        url="http://rag.test/documents/pipeline_status",
        method="GET",
        json={"busy": False, "docs": 0},
    )
    client = RAGServiceClient(base_url="http://rag.test", api_key="secret-key")
    ctx = make_fake_context(client)

    result = await rag_document_status(ctx=ctx)
    parsed = json.loads(result)

    assert parsed["busy"] is False
    await client.close()


@pytest.mark.asyncio
async def test_rag_health_active(httpx_mock):
    httpx_mock.add_response(
        url="http://rag.test/health",
        method="GET",
        json={"status": "healthy"},
    )
    client = RAGServiceClient(base_url="http://rag.test", api_key="secret-key")
    ctx = make_fake_context(client)

    result = await rag_health(ctx=ctx)
    parsed = json.loads(result)

    assert parsed["status"] == "healthy"
    await client.close()


@pytest.mark.asyncio
async def test_rag_health_uses_workspace_header(httpx_mock):
    httpx_mock.add_response(
        url="http://rag.test/health",
        method="GET",
        json={"status": "healthy"},
    )
    client = RAGServiceClient(base_url="http://rag.test", api_key="secret-key")
    ctx = make_fake_context(client)

    await rag_health(space_id="space-x", ctx=ctx)

    request = httpx_mock.get_request()
    assert request.headers[SPACE_HEADER] == "space-x"
    await client.close()


# ============================================================================
# Security / CLI
# ============================================================================


def test_default_password_not_hardcoded():
    parser = _build_argument_parser()
    password_action = next(a for a in parser._actions if a.dest == "password")
    assert password_action.default is None
    assert password_action.default != "admin123"


def test_default_username_kept_for_compatibility():
    """用户名保留默认值 admin，但密码必须显式提供"""
    parser = _build_argument_parser()
    username_action = next(a for a in parser._actions if a.dest == "username")
    assert username_action.default == "admin"
