"""
文档解析工具

提供从 URL 下载并解析文档内容的功能
"""

import logging
import httpx
from typing import Optional

from app.agents.testcase.pdf_processor import PDFProcessor

logger = logging.getLogger(__name__)

# 初始化 PDF 处理器（全局单例，启用缓存）
_pdf_processor = PDFProcessor(enable_cache=True)

# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TUZsc1dBPT06NWYxZDllMjM=

async def parse_document_from_url(
    url: str,
    document_type: Optional[str] = None,
) -> dict[str, any]:
    """
    从 URL 下载并解析文档内容

    支持的文档类型:
    - PDF: 使用 PyMuPDF4LLM (支持表格) 或 PyPDF2 (备用)
    - 图片: 返回图片信息，需要配合视觉模型使用
    - TXT: 纯文本解析

    Args:
        url: 文档的 URL (通常是 MinIO 预签名 URL)
        document_type: 文档 MIME 类型 (可选，用于优化解析策略)

    Returns:
        dict: 包含解析结果的字典
            - success: bool, 是否成功
            - content: str, 解析的文本内容
            - document_type: str, 文档类型
            - error: str, 错误信息 (如果失败)

    Examples:
        >>> result = await parse_document_from_url("http://example.com/doc.pdf")
        >>> if result["success"]:
        >>>     print(result["content"])
    """
    try:
        logger.info(f"开始解析文档: {url} (类型: {document_type})")

        # 下载文档
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=60.0)
            response.raise_for_status()

        content_data = response.content
        detected_type = document_type or response.headers.get("content-type", "")

        logger.info(f"文档下载完成，大小: {len(content_data)} 字节，类型: {detected_type}")

        # 根据文档类型选择解析方法
        if detected_type == "application/pdf" or url.lower().endswith(".pdf"):
            # PDF 文档解析
            text_content = _pdf_processor.extract_text(content_data, filename="document.pdf")
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TUZsc1dBPT06NWYxZDllMjM=

            return {
                "success": True,
                "content": text_content,
                "document_type": "pdf",
                "size_bytes": len(content_data),
            }

        elif detected_type.startswith("image/") or any(url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
            # 图片文件
            return {
                "success": True,
                "content": f"这是一张图片文件。\n\n图片URL: {url}\n\n请使用支持视觉的模型来分析这张图片的内容。",
                "document_type": "image",
                "image_url": url,
                "size_bytes": len(content_data),
            }

        elif detected_type == "text/plain" or url.lower().endswith(".txt"):
            # 纯文本文件
            try:
                text = content_data.decode('utf-8')
            except UnicodeDecodeError:
                text = content_data.decode('gbk', errors='ignore')

            return {
                "success": True,
                "content": text,
                "document_type": "text",
                "size_bytes": len(content_data),
            }
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TUZsc1dBPT06NWYxZDllMjM=

        else:
            # 不支持的文档类型
            return {
                "success": False,
                "error": f"不支持的文档类型: {detected_type}。建议将文档转换为 PDF 或 TXT 格式。",
                "document_type": detected_type,
            }

    except httpx.HTTPError as e:
        logger.error(f"下载文档失败: {e}")
        return {
            "success": False,
            "error": f"文档下载失败: {str(e)}",
        }
    except Exception as e:
        logger.error(f"文档解析失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"文档解析失败: {str(e)}",
        }


async def get_rag_tools() -> list:
    """获取RAG MCP工具.

    Returns:
        RAG工具列表
    """

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient({
            "rag-server": {
                "url": "http://127.0.0.1:8002/sse",
                "transport": "sse",
            }
        })

        tools = await client.get_tools()
        return tools
    except Exception as e:
        print(f"Warning: Failed to load RAG MCP tools8888: {e}")
        return []
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TUZsc1dBPT06NWYxZDllMjM=
