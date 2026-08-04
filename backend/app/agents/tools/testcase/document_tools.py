"""
文档解析工具

提供从 URL 下载并解析文档内容的功能，支持 PDF、图片、TXT 等格式。
"""

import asyncio
import hashlib
import logging
import os
import re
import threading
import urllib.parse
from pathlib import Path
from typing import Any, Optional

import httpx
from langchain_core.tools import tool

from app.agents.tools.testcase.pdf_processor import PDFProcessor
from app.config.settings import settings
from app.utils.sync_executor import run_sync
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WTJ4c05BPT06M2RjZTI1Zjk=

logger = logging.getLogger(__name__)

_pdf_processor = PDFProcessor(enable_cache=True)

# ── 大文档落盘：解析结果超过阈值时不内联返回 ──
# 中文 1 token ≈ 1~1.5 字符，30K 字符 ≈ 2 万+ 真实 token；接口文档类 PDF 提取
# 文本普遍 10 万+ 字符，内联返回会在几步之内耗尽 128K 上下文窗口并导致 run
# 被 API 拒绝而中断。超过阈值时全文写入 workspace，只回传「统计 + 目录 +
# 预览 + 分段读取指引」指针。
DOC_OFFLOAD_THRESHOLD_CHARS = int(os.environ.get("DOC_OFFLOAD_THRESHOLD_CHARS", "30000"))
_PARSED_DOCS_DIR = "parsed_docs"
_PREVIEW_HEAD_LINES = 40
_PREVIEW_MAX_LINE_CHARS = 300
_TOC_MAX_ENTRIES = 60


def _sanitize_doc_name(url: str) -> str:
    """从 URL 提取安全的文件名片段（保留中文，去掉路径与查询串）。"""
    try:
        path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
        stem = Path(path).stem
    except Exception:  # noqa: BLE001
        stem = ""
    safe = re.sub(r"[^\w一-鿿.-]+", "_", stem).strip("._")
    return safe[:50] or "document"


def _build_toc(text: str) -> list[str]:
    """提取 markdown 标题作为目录，带行号方便 read_file(offset=...) 直接跳转。"""
    toc: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            toc.append(f"L{lineno}: {stripped[:120]}")
            if len(toc) >= _TOC_MAX_ENTRIES:
                break
    return toc


def _offload_full_text(text: str, url: str, document_type: str) -> dict[str, Any]:
    """把大文档全文写入 workspace，返回「指针 + 目录 + 预览」的工具结果。

    同一文档（文件名 + 内容 hash）重复解析时覆盖同一文件，不会在
    large_tool_results 里堆积多份重复卸载（历史事故：同一接口文档一天被
    重复逐出 5+ 次）。
    """
    workspace_root = Path(settings.testcase_workspace_root).resolve()
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    filename = f"{_sanitize_doc_name(url)}_{digest}.md"
    abs_path = workspace_root / _PARSED_DOCS_DIR / filename
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_text(text, encoding="utf-8")

    virtual_path = f"/{_PARSED_DOCS_DIR}/{filename}"
    lines = text.splitlines()
    total_lines = len(lines)
    head = "\n".join(line[:_PREVIEW_MAX_LINE_CHARS] for line in lines[:_PREVIEW_HEAD_LINES])
    toc = _build_toc(text)
    toc_block = (
        "\n".join(toc)
        if toc
        else "（未检测到 markdown 标题，请用 grep 按关键词（如接口名、\"请求参数\"、\"错误码\"）定位章节）"
    )

    pointer = f"""文档解析成功（共 {total_lines} 行 / {len(text)} 字符）。内容较大，全文已保存到工作区文件：
{virtual_path}

【阅读指引 — 必须遵守】
1. 不要一次性读取全文（会超出上下文窗口，导致会话中断）；按下方目录定位章节后分段阅读
2. 分段读取示例：read_file(file_path="{virtual_path}", offset=0, limit=800)
3. 关键词定位：用 grep 工具搜索接口名 / "请求参数" / "错误码" 等字面关键词
4. 分析时结合目录规划要覆盖的章节，遗漏章节会导致功能矩阵不完整

【文档目录】（L<行号>: 标题；read_file 的 offset 传 行号-1 即可跳转到该章节）
{toc_block}

【开头预览（前 {_PREVIEW_HEAD_LINES} 行）】
{head}
...（后续内容请按上述指引分段读取）"""

    return {
        "success": True,
        "content": pointer,
        "document_type": document_type,
        "full_text_path": virtual_path,
        "total_chars": len(text),
        "total_lines": total_lines,
        "offloaded": True,
    }


def _inline_or_offload(text: str, url: str, document_type: str, size_bytes: int) -> dict[str, Any]:
    """小文档内联返回（保持原行为），大文档落盘返回指针；落盘失败降级为截断内联。"""
    if len(text) <= DOC_OFFLOAD_THRESHOLD_CHARS:
        return {
            "success": True,
            "content": text,
            "document_type": document_type,
            "size_bytes": size_bytes,
        }
    try:
        result = _offload_full_text(text, url, document_type)
        result["size_bytes"] = size_bytes
        logger.info(
            "文档提取文本 %d 字符超过阈值 %d，已落盘 %s",
            len(text), DOC_OFFLOAD_THRESHOLD_CHARS, result["full_text_path"],
        )
        return result
    except Exception as e:  # noqa: BLE001
        logger.warning("大文档落盘失败，降级为截断内联返回: %s", e)
        return {
            "success": True,
            "content": (
                text[:DOC_OFFLOAD_THRESHOLD_CHARS]
                + f"\n\n[文档共 {len(text)} 字符，落盘失败（{e}），此处仅返回前 "
                f"{DOC_OFFLOAD_THRESHOLD_CHARS} 字符，后续内容缺失]"
            ),
            "document_type": document_type,
            "size_bytes": size_bytes,
            "truncated": True,
        }


@tool
async def parse_document_from_url(
    url: str,
    document_type: Optional[str] = None,
) -> dict[str, any]:
    """
    从 URL 下载并解析文档内容。

    支持的文档类型:
    - PDF: 使用 PyMuPDF4LLM (支持表格) 或 PyPDF2 (备用)
    - 图片: 返回图片信息，需要配合视觉模型使用
    - TXT: 纯文本解析

    大文档说明：解析结果超过阈值时不会内联返回全文，全文会自动保存到工作区
    文件（返回值的 full_text_path 字段），content 为「统计 + 目录 + 预览 +
    分段读取指引」。此时必须按指引用 read_file 分段阅读或用 grep 定位章节，
    禁止尝试一次性读入全文（会导致上下文溢出、会话中断）。

    Args:
        url: 文档的 URL (通常是 MinIO 预签名 URL)
        document_type: 文档 MIME 类型 (可选，用于优化解析策略)

    Returns:
        dict: 包含解析结果的字典
            - success: bool, 是否成功
            - content: str, 解析的文本内容（大文档时为指针+预览）
            - document_type: str, 文档类型
            - full_text_path: str, 大文档落盘后的工作区路径（仅大文档返回）
            - error: str, 错误信息 (如果失败)
    """
    try:
        logger.info(f"开始解析文档: {url} (类型: {document_type})")

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=60.0)
            response.raise_for_status()
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WTJ4c05BPT06M2RjZTI1Zjk=

        content_data = response.content
        detected_type = document_type or response.headers.get("content-type", "")

        logger.info(f"文档下载完成，大小: {len(content_data)} 字节，类型: {detected_type}")

        # 空文档拦截：避免把 0 字节内容交给 PDF 解析器，从而产生
        # "PDF 解析库未安装" 这类误导性的下游错误。
        if len(content_data) == 0:
            logger.warning(f"下载到的文档为空 (0 字节): {url}")
            return {
                "success": False,
                "error": (
                    "文档内容为空（0 字节）。通常是上传的源文件本身就是空文件，"
                    "或文件未完整下载。请重新上传一个有效的文档后再试。"
                ),
                "document_type": detected_type,
                "size_bytes": 0,
            }

        if detected_type == "application/pdf" or url.lower().endswith(".pdf"):
            text_content = await run_sync(
                _pdf_processor.extract_text, content_data, filename="document.pdf"
            )
            return _inline_or_offload(text_content, url, "pdf", len(content_data))

        elif detected_type.startswith("image/") or any(
            url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]
        ):
            return {
                "success": True,
                "content": f"这是一张图片文件。\n\n图片URL: {url}\n\n请使用支持视觉的模型来分析这张图片的内容。",
                "document_type": "image",
                "image_url": url,
                "size_bytes": len(content_data),
            }

        elif detected_type == "text/plain" or url.lower().endswith(".txt"):
            try:
                text = content_data.decode('utf-8')
            except UnicodeDecodeError:
                text = content_data.decode('gbk', errors='ignore')

            return _inline_or_offload(text, url, "text", len(content_data))
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WTJ4c05BPT06M2RjZTI1Zjk=

        else:
            return {
                "success": False,
                "error": f"不支持的文档类型: {detected_type}。建议将文档转换为 PDF 或 TXT 格式。",
                "document_type": detected_type,
            }

    except httpx.HTTPError as e:
        logger.error(f"下载文档失败: {e}")
        return {"success": False, "error": f"文档下载失败: {str(e)}"}
    except Exception as e:
        logger.error(f"文档解析失败: {e}", exc_info=True)
        return {"success": False, "error": f"文档解析失败: {str(e)}"}


# ── RAG MCP 客户端单例：避免每次 make_agent() 重建 SSE 连接 ──
# 使用 threading.Lock 而非 asyncio.Lock，因为 LangGraph 的 background
# workers 运行在 ThreadPoolExecutor 中，各自拥有独立的事件循环；
# 模块级 asyncio.Lock 会绑定到错误的 event loop，导致
# "is bound to a different event loop" 错误。
_rag_tools_cache: list | None = None
_rag_tools_cache_ts: float = 0.0  # 缓存写入时间戳（用于 TTL 过期重试）
_rag_tools_lock = threading.Lock()

# 失败缓存 TTL（秒）：超过此时间后允许重试连接 RAG MCP 服务
_RAG_CACHE_FAILURE_TTL = 60.0


async def get_rag_tools() -> list:
    """获取 RAG MCP 工具（单例模式，首次调用建立 SSE 连接后缓存复用）。

    SSE 地址通过环境变量 RAG_MCP_URL 配置；缺省回退到本机 rag_server.py
    默认地址 http://127.0.0.1:8008/sse（与 rag_server.py 的 --port 8008 保持一致）。
    连接失败时优雅降级为空工具列表，不影响 agent 启动。

    **失败重试**：连接失败后缓存空列表，但超过 _RAG_CACHE_FAILURE_TTL 秒后
    会自动重试，避免 RAG MCP 服务晚于 Agent 启动时永久不可用。

    Returns:
        RAG 工具列表
    """
    global _rag_tools_cache, _rag_tools_cache_ts
    import time as _time

    # 快速路径：缓存已就绪（非空），无锁读取
    if _rag_tools_cache is not None:
        # 检查失败缓存是否过期（空列表 != None）
        if len(_rag_tools_cache) == 0:
            elapsed = _time.monotonic() - _rag_tools_cache_ts
            if elapsed < _RAG_CACHE_FAILURE_TTL:
                return _rag_tools_cache
            # TTL 过期：清空缓存触发重试
            with _rag_tools_lock:
                if _rag_tools_cache is not None and len(_rag_tools_cache) == 0:
                    elapsed2 = _time.monotonic() - _rag_tools_cache_ts
                    if elapsed2 >= _RAG_CACHE_FAILURE_TTL:
                        logger.info("RAG MCP 失败缓存已过期（%.0fs），尝试重新连接", elapsed2)
                        _rag_tools_cache = None  # 重置，触发重连
        else:
            return _rag_tools_cache

    # 锁内二次检查 + 标记"连接中"，避免多个 worker 同时发起 SSE 连接
    with _rag_tools_lock:
        if _rag_tools_cache is not None:
            return _rag_tools_cache
        # 先写入哨兵值防止并发重入（后续成功/失败会覆盖）
        _rag_tools_cache = []

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient({
            "rag-server": {
                "url": os.environ.get("RAG_MCP_URL", "http://127.0.0.1:8008/sse"),
                "transport": "sse",
            }
        })

        tools = await client.get_tools()
        _rag_tools_cache = tools
        _rag_tools_cache_ts = _time.monotonic()
        logger.info("RAG MCP 客户端已初始化，共 %d 个工具", len(tools))
        return tools
    except Exception as e:
        logger.warning(f"Failed to load RAG MCP tools: {e}")
        _rag_tools_cache = []  # 缓存空列表，60s 后自动重试
        _rag_tools_cache_ts = _time.monotonic()
        return []
