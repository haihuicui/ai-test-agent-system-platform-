"""
文档解析工具

提供从 URL 下载并解析文档内容的功能，支持 PDF、图片、TXT 等格式。
"""

import logging
from typing import Optional

import httpx
from langchain_core.tools import tool

from app.agents.tools.testcase.pdf_processor import PDFProcessor
from app.utils.sync_executor import run_sync
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WTJ4c05BPT06M2RjZTI1Zjk=

logger = logging.getLogger(__name__)

_pdf_processor = PDFProcessor(enable_cache=True)


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

    Args:
        url: 文档的 URL (通常是 MinIO 预签名 URL)
        document_type: 文档 MIME 类型 (可选，用于优化解析策略)

    Returns:
        dict: 包含解析结果的字典
            - success: bool, 是否成功
            - content: str, 解析的文本内容
            - document_type: str, 文档类型
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
            return {
                "success": True,
                "content": text_content,
                "document_type": "pdf",
                "size_bytes": len(content_data),
            }

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

            return {
                "success": True,
                "content": text,
                "document_type": "text",
                "size_bytes": len(content_data),
            }
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


async def get_rag_tools() -> list:
    """获取 RAG MCP 工具。

    Returns:
        RAG 工具列表
    """
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        client = MultiServerMCPClient({
            "rag-server": {
                "url": "http://192.168.60.103:8008/sse",
                "transport": "sse",
            }
        })
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WTJ4c05BPT06M2RjZTI1Zjk=

        tools = await client.get_tools()
        return tools
    except Exception as e:
        logger.warning(f"Failed to load RAG MCP tools: {e}")
        return []
