"""
RAG MCP Server — 生产级多租户 RAG 查询服务

基于 LightRAG API 的 MCP (Model Context Protocol) 服务器，提供：
- 7 个专业工具: 查询、结构化检索、图谱探索、文档状态、健康检查
- 多租户隔离: 通过 X-Space-Id 实现工作空间级数据隔离
- 认证支持: JWT Token / API Key 双重认证
- 生产级可靠性: 自动重试、指数退避、连接池管理
- 全面的错误处理与日志

工具列表:
  1. rag_query          — LLM 生成式回答（含引用来源）
  2. rag_query_data     — 结构化数据检索（实体/关系/文本块）
  3. rag_graph_search   — 知识图谱实体模糊搜索
  4. rag_graph_get      — 获取实体周围的子图
  5. rag_graph_labels   — 列出图谱中的实体标签
  6. rag_document_status — 文档处理状态与管线监控
  7. rag_health         — 服务健康检查
"""

import argparse
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP, Context

# ============================================================================
# Logging & Constants
# ============================================================================

logger = logging.getLogger("rag-mcp-server")

VALID_QUERY_MODES = ("local", "global", "hybrid", "naive", "mix", "bypass")
QueryMode = Literal["local", "global", "hybrid", "naive", "mix", "bypass"]
SPACE_HEADER = "X-Space-Id"
DEFAULT_BASE_URL = "http://localhost:9621"
DEFAULT_TIMEOUT = 120.0
MAX_RETRIES = 3
RETRY_BACKOFF = 0.5


# ============================================================================
# 生产级 RAG HTTP 客户端
# ============================================================================

class RAGServiceClient:
    """生产级 LightRAG API 客户端

    特性：
    - 连接池管理（httpx.AsyncClient）
    - 自动重试 + 指数退避
    - 多租户 X-Space-Id 请求头注入
    - JWT 登录认证 / API Key 双重认证
    - JWT Token 自动获取与缓存
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        default_space_id: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.username = username
        self.password = password
        self.timeout = timeout
        self.default_space_id = default_space_id
        self._client: Optional[httpx.AsyncClient] = None
        self._jwt_token: Optional[str] = None

    # ---- JWT 登录 ----

    async def _login(self) -> str:
        """通过 /login 端点获取 JWT Token（OAuth2 密码模式）"""
        if not self.username or not self.password:
            raise RAGAPIError(401, "未配置用户名/密码，无法登录。请设置 --username/--password 或 RAG_USERNAME/RAG_PASSWORD 环境变量。")

        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as tmp:
            resp = await tmp.post(
                "/login",
                data={"username": self.username, "password": self.password},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code != 200:
                detail = resp.text
                try:
                    detail = resp.json().get("detail", resp.text)
                except Exception:
                    pass
                raise RAGAPIError(resp.status_code, f"登录失败: {detail}")

            token_data = resp.json()
            token = token_data.get("access_token")
            if not token:
                raise RAGAPIError(500, f"登录响应中缺少 access_token: {token_data}")

            logger.info(f"JWT 登录成功: 用户={self.username}")
            return token

    # ---- 连接管理 ----

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # 优先级: JWT登录 > API Key > 无认证
            if self.username and self.password and not self._jwt_token:
                self._jwt_token = await self._login()

            headers: Dict[str, str] = {"Content-Type": "application/json"}
            if self._jwt_token:
                headers["Authorization"] = f"Bearer {self._jwt_token}"
            elif self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            if self.default_space_id:
                headers[SPACE_HEADER] = self.default_space_id
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        self._jwt_token = None

    # ---- 带重试的请求 ----

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        space_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """执行带自动重试的 HTTP 请求"""
        client = await self._ensure_client()
        extra_headers: Dict[str, str] = {}
        if space_id:
            extra_headers[SPACE_HEADER] = space_id

        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.request(
                    method, path,
                    json=json_body, params=params,
                    headers=extra_headers if extra_headers else None,
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                # 401 且有登录凭据 → JWT 过期，自动重新登录并重试
                if e.response.status_code == 401 and self.username and self.password:
                    logger.info("JWT Token 已过期，正在自动重新登录…")
                    await self.close()
                    self._jwt_token = None
                    client = await self._ensure_client()
                    last_exc = e
                    continue
                # 其他 4xx 不重试（客户端错误）
                if 400 <= e.response.status_code < 500:
                    detail = "Unknown error"
                    try:
                        detail = e.response.json().get("detail", e.response.text)
                    except Exception:
                        detail = e.response.text
                    raise RAGAPIError(e.response.status_code, detail) from e
                last_exc = e
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_exc = e

            # 指数退避
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF * (2 ** attempt)
                logger.warning(f"请求 {method} {path} 失败 (尝试 {attempt+1}/{MAX_RETRIES})，{wait:.1f}s 后重试: {last_exc}")
                await asyncio.sleep(wait)

        raise RAGAPIError(502, f"请求 {path} 在 {MAX_RETRIES} 次重试后仍然失败: {last_exc}")

    # ---- 便捷方法 ----

    async def post(self, path: str, body: Dict[str, Any], space_id: Optional[str] = None) -> Dict[str, Any]:
        return await self._request("POST", path, json_body=body, space_id=space_id)

    async def get(self, path: str, params: Optional[Dict[str, Any]] = None, space_id: Optional[str] = None) -> Any:
        return await self._request("GET", path, params=params, space_id=space_id)


class RAGAPIError(Exception):
    """RAG API 调用错误"""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[HTTP {status_code}] {detail}")


# ============================================================================
# 查询参数构建辅助
# ============================================================================

def _build_query_body(
    query: str,
    mode: str = "mix",
    top_k: int = 60,
    chunk_top_k: int = 20,
    max_entity_tokens: Optional[int] = None,
    max_relation_tokens: Optional[int] = None,
    max_total_tokens: Optional[int] = None,
    hl_keywords: Optional[List[str]] = None,
    ll_keywords: Optional[List[str]] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    enable_rerank: bool = True,
    enable_vlm_enhanced: bool = False,
    include_references: bool = True,
    include_chunk_content: bool = False,
    response_type: Optional[str] = None,
    user_prompt: Optional[str] = None,
    only_need_context: bool = False,
    only_need_prompt: bool = False,
    stream: bool = False,
) -> Dict[str, Any]:
    """构建 /query、/query/stream 或 /query/data 请求体，自动跳过 None 值"""
    body: Dict[str, Any] = {
        "query": query,
        "mode": mode,
        "top_k": top_k,
        "chunk_top_k": chunk_top_k,
        "enable_rerank": enable_rerank,
        "enable_vlm_enhanced": enable_vlm_enhanced,
        "include_references": include_references,
        "include_chunk_content": include_chunk_content,
        "stream": stream,
    }
    # 布尔字段仅在为 True 时才发送（减少请求体大小）
    if only_need_context:
        body["only_need_context"] = True
    if only_need_prompt:
        body["only_need_prompt"] = True
    # 可选字段：跳过 None 值
    optionals = {
        "max_entity_tokens": max_entity_tokens,
        "max_relation_tokens": max_relation_tokens,
        "max_total_tokens": max_total_tokens,
        "hl_keywords": hl_keywords,
        "ll_keywords": ll_keywords,
        "conversation_history": conversation_history,
        "response_type": response_type,
        "user_prompt": user_prompt,
    }
    for k, v in optionals.items():
        if v is not None:
            body[k] = v
    return body


# ============================================================================
# MCP 服务器 — 生命周期 & 实例
# ============================================================================

class RAGContext:
    """MCP 生命周期上下文，持有共享的 HTTP 客户端"""
    def __init__(self, client: RAGServiceClient):
        self.client = client


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[RAGContext]:
    """管理 RAGServiceClient 的生命周期"""
    cfg = server.config or {}
    client = RAGServiceClient(
        base_url=cfg.get("rag_base_url", DEFAULT_BASE_URL),
        api_key=cfg.get("rag_api_key"),
        username=cfg.get("rag_username"),
        password=cfg.get("rag_password"),
        timeout=float(cfg.get("timeout", DEFAULT_TIMEOUT)),
        default_space_id=cfg.get("default_space_id"),
    )
    auth_mode = "JWT登录" if client.username else ("API Key" if client.api_key else "无认证")
    logger.info(f"RAG MCP Server 已启动 → {client.base_url} (认证: {auth_mode})")
    try:
        yield RAGContext(client)
    finally:
        await client.close()
        logger.info("RAG MCP Server 已关闭")


mcp = FastMCP(name="RAG-MCP-Server", lifespan=server_lifespan)


def _get_client(ctx: Context) -> RAGServiceClient:
    """从 MCP Context 中提取 RAGServiceClient"""
    return ctx.request_context.lifespan_context.client


# ============================================================================
# MCP 工具 — 7 个生产级 RAG 工具
# ============================================================================

# ---- 工具 1: rag_query (LLM 生成式回答) ----

@mcp.tool()
async def rag_query(
    query: str,
    mode: str = "mix",
    top_k: int = 60,
    chunk_top_k: int = 10,
    enable_rerank: bool = False,
    enable_vlm_enhanced: bool = True,
    max_entity_tokens: Optional[int] = None,
    max_relation_tokens: Optional[int] = None,
    max_total_tokens: Optional[int] = None,
    response_type: Optional[str] = None,
    user_prompt: Optional[str] = None,
    only_need_context: bool = False,
    only_need_prompt: bool = False,
    include_references: bool = True,
    hl_keywords: Optional[List[str]] = None,
    ll_keywords: Optional[List[str]] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    space_id: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """通过知识库进行 LLM 生成式回答，返回自然语言答案和引用来源。

    适用场景：需要让 LLM 基于知识库内容生成完整答案的场景。
    支持多种检索模式、VLM视觉增强、重排序、Token预算控制等高级功能。

    参数：
        query: 自然语言问题（至少3个字符）
        mode: 检索模式。可选值：
              - mix（推荐，混合检索）
              - local（局部实体检索）
              - global（全局关系检索）
              - hybrid（混合local+global）
              - naive（朴素向量检索）
              - bypass（直接转发LLM，不使用知识库）
        top_k: 检索的实体/关系数量（默认60）
        chunk_top_k: 检索的文本块数量（默认5）
        enable_rerank: 是否启用重排序以提高检索质量（默认True）
        enable_vlm_enhanced: 是否启用VLM视觉增强查询，自动识别上下文中的图片并发送给视觉模型理解（默认False）
        max_entity_tokens: 实体上下文的最大Token数（可选，用于精细控制Token预算）
        max_relation_tokens: 关系上下文的最大Token数（可选）
        max_total_tokens: 整个查询上下文的总Token预算上限（可选）
        response_type: 响应格式，如 "Multiple Paragraphs"、"Single Paragraph"、"Bullet Points"（可选）
        user_prompt: 自定义用户提示词，覆盖默认的Prompt模板（可选）
        only_need_context: 是否仅返回检索到的上下文，不生成LLM回答（默认False）
        only_need_prompt: 是否仅返回生成的完整Prompt，不产生回答（默认False）
        include_references: 是否在响应中包含引用来源列表（默认True）
        hl_keywords: 高层级关键词列表，用于引导检索方向（可选，留空则由LLM自动生成）
        ll_keywords: 低层级关键词列表，用于精炼检索焦点（可选，留空则由LLM自动生成）
        conversation_history: 对话历史，格式为 [{"role": "user/assistant", "content": "消息"}]，仅用于LLM上下文（可选）
        space_id: 多租户空间ID（可选）

    返回：LLM 生成的答案文本（含引用来源）
    """
    if mode not in VALID_QUERY_MODES:
        return f"❌ 无效模式: {mode}。可选: {', '.join(VALID_QUERY_MODES)}"
    client = _get_client(ctx)
    try:
        body = _build_query_body(
            query=query, mode=mode, top_k=top_k, chunk_top_k=chunk_top_k,
            enable_rerank=enable_rerank, enable_vlm_enhanced=enable_vlm_enhanced,
            max_entity_tokens=max_entity_tokens,
            max_relation_tokens=max_relation_tokens,
            max_total_tokens=max_total_tokens,
            response_type=response_type, user_prompt=user_prompt,
            only_need_context=only_need_context, only_need_prompt=only_need_prompt,
            include_references=include_references,
            hl_keywords=hl_keywords, ll_keywords=ll_keywords,
            conversation_history=conversation_history,
        )
        result = await client.post("/query", body, space_id=space_id)
        response_text = result.get("response", "")
        return response_text if response_text else "(空响应)"
    except RAGAPIError as e:
        return f"❌ RAG 查询失败: {e}"
    except Exception as e:
        logger.exception("rag_query 异常")
        return f"❌ 查询异常: {e}"


# ---- 工具 2: rag_query_data (结构化数据检索) ----

@mcp.tool()
async def rag_query_data(
    query: str,
    mode: str = "mix",
    top_k: int = 60,
    chunk_top_k: int = 10,
    enable_rerank: bool = False,
    enable_vlm_enhanced: bool = True,
    max_entity_tokens: Optional[int] = None,
    max_relation_tokens: Optional[int] = None,
    max_total_tokens: Optional[int] = None,
    user_prompt: Optional[str] = None,
    include_chunk_content: bool = True,
    hl_keywords: Optional[List[str]] = None,
    ll_keywords: Optional[List[str]] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    space_id: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """从知识库检索结构化数据：实体、关系、文本块和引用来源。

    返回 JSON 格式的结构化检索结果，适合程序化处理。
    当需要获取知识图谱中的实体关系信息（而非LLM生成的回答）时使用此工具。

    参数：
        query: 自然语言查询（至少3个字符）
        mode: 检索模式。可选值：
              - mix（推荐，混合检索）
              - local（局部实体检索）
              - global（全局关系检索）
              - hybrid（混合local+global）
              - naive（朴素向量检索）
              - bypass（直接转发LLM，不使用知识库）
        top_k: 检索的实体/关系数量（默认60）
        chunk_top_k: 检索的文本块数量（默认5）
        enable_rerank: 是否启用重排序以提高检索质量（默认True）
        enable_vlm_enhanced: 是否启用VLM视觉增强查询（默认False）
        max_entity_tokens: 实体上下文的最大Token数（可选）
        max_relation_tokens: 关系上下文的最大Token数（可选）
        max_total_tokens: 整个查询上下文的总Token预算上限（可选）
        user_prompt: 自定义用户提示词（可选）
        include_chunk_content: 是否在引用中包含文本块的完整内容（默认True）
        hl_keywords: 高层级关键词列表（可选）
        ll_keywords: 低层级关键词列表（可选）
        conversation_history: 对话历史 [{"role": "user/assistant", "content": "消息"}]（可选）
        space_id: 多租户空间ID（可选）

    返回：JSON 格式的结构化数据（实体、关系、文本块、引用来源）
    """
    if mode not in VALID_QUERY_MODES:
        return json.dumps({"error": f"无效模式: {mode}"}, ensure_ascii=False)
    client = _get_client(ctx)
    try:
        body = _build_query_body(
            query=query, mode=mode, top_k=top_k, chunk_top_k=chunk_top_k,
            enable_rerank=enable_rerank, enable_vlm_enhanced=enable_vlm_enhanced,
            max_entity_tokens=max_entity_tokens,
            max_relation_tokens=max_relation_tokens,
            max_total_tokens=max_total_tokens,
            user_prompt=user_prompt,
            include_references=True, include_chunk_content=include_chunk_content,
            hl_keywords=hl_keywords, ll_keywords=ll_keywords,
            conversation_history=conversation_history,
        )
        result = await client.post("/query/data", body, space_id=space_id)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except RAGAPIError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        logger.exception("rag_query_data 异常")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ---- 工具 3: rag_graph_search (知识图谱实体搜索) ----

@mcp.tool()
async def rag_graph_search(
    query: str,
    limit: int = 50,
    space_id: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """在知识图谱中模糊搜索实体标签。

    适用场景：查找知识图谱中的特定实体，如模块、接口、组件等。

    参数：
        query: 实体名称或关键词（模糊匹配）
        limit: 返回的最大结果数量（默认50，最大100）
        space_id: 多租户空间ID（可选）

    返回：JSON 格式的匹配标签列表
    """
    client = _get_client(ctx)
    try:
        params = {"q": query, "limit": min(limit, 100)}
        result = await client.get("/graph/label/search", params=params, space_id=space_id)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except RAGAPIError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        logger.exception("rag_graph_search 异常")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ---- 工具 4: rag_graph_get (获取实体子图) ----

@mcp.tool()
async def rag_graph_get(
    entity_name: str,
    max_depth: int = 3,
    space_id: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """获取指定实体周围的知识子图（实体 + 关系网络）。

    适用场景：探索某个实体的上下游关系和关联网络。

    参数：
        entity_name: 实体名称（精确匹配）
        max_depth: 子图探索深度（1-3，默认3）
        space_id: 多租户空间ID（可选）

    返回：JSON 格式的子图数据（节点和边）
    """
    client = _get_client(ctx)
    try:
        params = {"label": entity_name, "max_depth": min(max(max_depth, 1), 3)}
        result = await client.get("/graphs", params=params, space_id=space_id)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except RAGAPIError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        logger.exception("rag_graph_get 异常")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# ---- 工具 5: rag_graph_labels (列出图谱标签) ----

@mcp.tool()
async def rag_graph_labels(
    space_id: Optional[str] = None,
    ctx: Context = None,
) -> str:
    """列出知识图谱中所有实体类型标签。

    适用场景：了解知识图谱的整体结构和实体分类。

    参数：
        space_id: 多租户空间ID（可选）

    返回：JSON 格式的标签列表
    """
    client = _get_client(ctx)
    try:
        result = await client.get("/graph/label/list", space_id=space_id)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except RAGAPIError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        logger.exception("rag_graph_labels 异常")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# # ---- 工具 6: rag_document_status (文档处理状态) ----

# @mcp.tool()
# async def rag_document_status(
#     space_id: Optional[str] = None,
#     ctx: Context = None,
# ) -> str:
#     """查询文档索引管线的处理状态。

#     适用场景：监控文档处理进度、检查管线是否繁忙。

#     参数：
#         space_id: 多租户空间ID（可选）

#     返回：JSON 格式的管线状态（busy/进度/消息等）
#     """
#     client = _get_client(ctx)
#     try:
#         result = await client.get("/documents/pipeline_status", space_id=space_id)
#         return json.dumps(result, ensure_ascii=False, indent=2)
#     except RAGAPIError as e:
#         return json.dumps({"error": str(e)}, ensure_ascii=False)
#     except Exception as e:
#         logger.exception("rag_document_status 异常")
#         return json.dumps({"error": str(e)}, ensure_ascii=False)


# # ---- 工具 7: rag_health (健康检查) ----

# @mcp.tool()
# async def rag_health(
#     ctx: Context = None,
# ) -> str:
#     """检查 RAG 服务的健康状态。

#     适用场景：确认后端服务是否正常运行。

#     返回：JSON 格式的健康状态
#     """
#     client = _get_client(ctx)
#     try:
#         result = await client.get("/health")
#         return json.dumps(result, ensure_ascii=False, indent=2)
#     except RAGAPIError as e:
#         return json.dumps({"status": "unhealthy", "error": str(e)}, ensure_ascii=False)
#     except Exception as e:
#         return json.dumps({"status": "unreachable", "error": str(e)}, ensure_ascii=False)


# ============================================================================
# 主入口点
# ============================================================================

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="RAG MCP Server — 生产级多租户 RAG 查询服务")
    parser.add_argument(
        "--rag-url", type=str, default=DEFAULT_BASE_URL,
        help=f"LightRAG 服务器 URL (默认: {DEFAULT_BASE_URL})"
    )
    parser.add_argument(
        "--rag-api-key", type=str, default=None,
        help="LightRAG API 密钥（与 --username/--password 二选一）"
    )
    parser.add_argument(
        "--username", type=str, default="admin",
        help="多租户登录用户名（也可设 RAG_USERNAME 环境变量）"
    )
    parser.add_argument(
        "--password", type=str, default="admin123",
        help="多租户登录密码（也可设 RAG_PASSWORD 环境变量）"
    )
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT,
        help=f"请求超时时间/秒 (默认: {DEFAULT_TIMEOUT})"
    )
    parser.add_argument(
        "--space-id", type=str, default="cmp_space",
        help="默认多租户空间ID"
    )
    parser.add_argument(
        "--transport", type=str, default="sse", choices=["sse", "stdio"],
        help="MCP 传输方式 (默认: sse)"
    )
    parser.add_argument(
        "--port", type=int, default=8008,
        help="SSE 服务器端口号 (默认: 8008)"
    )
    return parser.parse_args()


def main():
    """主入口点"""
    load_dotenv()
    args = parse_arguments()

    mcp.config = {
        "rag_base_url": os.environ.get("RAG_BASE_URL", args.rag_url),
        "rag_api_key": os.environ.get("RAG_API_KEY", args.rag_api_key),
        "rag_username": os.environ.get("RAG_USERNAME", args.username),
        "rag_password": os.environ.get("RAG_PASSWORD", args.password),
        "timeout": float(os.environ.get("RAG_TIMEOUT", args.timeout)),
        "default_space_id": os.environ.get("RAG_SPACE_ID", args.space_id),
    }

    if args.transport == "sse":
        mcp.run(transport="sse", port=args.port, host="0.0.0.0")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
