"""
PDF 文档处理器，支持文本提取和缓存"""

# 依赖安装: pip install -qU langchain-community langchain-pymupdf4llm

import tempfile
import os
import logging
import hashlib
import time
from typing import Optional

from app.config.settings import settings

logger = logging.getLogger(__name__)

# PDF 内容缓存，避免重复解析同一个文件
_pdf_cache = {}


def _safe_delete_temp_file(file_path: str, max_retries: int = 3, delay: float = 0.1):
    """
    安全删除临时文件，处理Windows文件锁定问题

    Args:
        file_path: 要删除的文件路径
        max_retries: 最大重试次数
        delay: 重试间隔（秒）
    """
    if not os.path.exists(file_path):
        return
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Ym01S05BPT06YjVjZjJhZWI=

    for attempt in range(max_retries):
        try:
            os.unlink(file_path)
            logger.debug(f"临时文件已删除: {file_path}")
            return
        except PermissionError as e:
            if attempt < max_retries - 1:
                logger.debug(f"删除临时文件失败（尝试 {attempt + 1}/{max_retries}），等待后重试: {e}")
                time.sleep(delay)
            else:
                logger.warning(f"无法删除临时文件（已重试{max_retries}次），文件将由系统清理: {file_path}")
        except Exception as e:
            logger.warning(f"删除临时文件时发生异常: {e}")
            break


class PDFProcessor:
    """PDF 处理器类"""
    
    def __init__(self, enable_cache: bool = True):
        self.enable_cache = enable_cache
        self.cache = _pdf_cache if enable_cache else {}
    
    def extract_text(self, pdf_data: bytes, filename: str = "unknown.pdf") -> str:
        """从PDF字节数据中提取文本"""
        return extract_pdf_text(pdf_data, filename, self.cache if self.enable_cache else None)
    
    def clear_cache(self):
        """清空缓存"""
        if self.enable_cache:
            self.cache.clear()
    
    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        return {
            "cache_enabled": self.enable_cache,
            "cached_files": len(self.cache) if self.enable_cache else 0,
            "cache_keys": list(self.cache.keys()) if self.enable_cache else []
        }

# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Ym01S05BPT06YjVjZjJhZWI=

def extract_pdf_text(pdf_data: bytes, filename: str = "unknown.pdf", cache: Optional[dict] = None) -> str:
    """
    从PDF字节数据中提取文本，使用缓存避免重复解析

    提取方法：
    1. PyMuPDF4LLM (推荐): 支持表格提取和多模态图片解析
       安装: pip install -qU langchain-community langchain-pymupdf4llm
    2. PyPDF2 (备用): 基础文本提取
       安装: pip install PyPDF2

    Args:
        pdf_data: PDF文件的字节数据
        filename: 文件名（用于日志和缓存）
        cache: 可选的缓存字典

    Returns:
        str: 提取的文本内容
    """
    # 生成PDF数据的哈希值作为缓存键
    pdf_hash = hashlib.md5(pdf_data).hexdigest()
    cache_key = f"{filename}_{pdf_hash}"

    # 检查缓存
    if cache is not None and cache_key in cache:
        logger.info(f"从缓存中获取PDF内容: {filename}")
        return cache[cache_key]

    # 创建临时文件（Windows需要先关闭文件句柄才能被其他程序访问）
    temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    try:
        temp_file.write(pdf_data)
        temp_file.flush()  # 确保数据写入磁盘
        os.fsync(temp_file.fileno())  # 强制同步到磁盘
        temp_file_path = temp_file.name
    finally:
        temp_file.close()  # 显式关闭文件句柄，释放文件锁

    text_content = ""

    try:
        # 优先尝试使用 PyMuPDF4LLM (功能更强大)
        logger.info(f"使用 PyMuPDF4LLM 解析PDF: {filename}")
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Ym01S05BPT06YjVjZjJhZWI=

        try:
            from langchain_pymupdf4llm import PyMuPDF4LLMLoader

            # 检查是否启用多模态图片解析
            enable_multimodal = getattr(settings, 'enable_pdf_multimodal', False)

            if enable_multimodal:
                try:
                    from langchain_community.document_loaders.parsers import LLMImageBlobParser
                    from langchain.chat_models import init_chat_model

                    # 使用豆包模型进行图片解析
                    doubao_api_key = os.getenv("DOUBAO_API_KEY", "")
                    if doubao_api_key:
                        image_llm = init_chat_model("doubao:doubao-vision", api_key=doubao_api_key)
                        image_parser = LLMImageBlobParser(model=image_llm)

                        loader = PyMuPDF4LLMLoader(
                            temp_file_path,
                            mode="single",
                            extract_images=True,
                            images_parser=image_parser,
                            table_strategy="lines"
                        )
                        logger.info("启用多模态图片解析")
                    else:
                        logger.warning("未配置 DOUBAO_API_KEY，禁用图片解析")
                        loader = PyMuPDF4LLMLoader(
                            temp_file_path,
                            mode="single",
                            table_strategy="lines"
                        )
                except ImportError as e:
                    logger.warning(f"多模态依赖未安装，使用基础模式: {e}")
                    loader = PyMuPDF4LLMLoader(
                        temp_file_path,
                        mode="single",
                        table_strategy="lines"
                    )
            else:
                # 基础模式：只提取文本和表格
                loader = PyMuPDF4LLMLoader(
                    temp_file_path,
                    mode="single",
                    table_strategy="lines"
                )

            documents = loader.load()

            if documents:
                text_content = documents[0].page_content
                logger.info(f"PyMuPDF4LLM 解析成功，内容长度: {len(text_content)} 字符")
            else:
                text_content = "PDF文件解析后内容为空"

        except ImportError:
            logger.warning("PyMuPDF4LLM 未安装，尝试使用 PyPDF2")
            raise  # 继续到备用方法

    except Exception as e:
        # 备用方法：使用 PyPDF2
        logger.warning(f"PyMuPDF4LLM 解析失败: {e}，尝试使用 PyPDF2")

        try:
            from PyPDF2 import PdfReader
            import io

            pdf_file = io.BytesIO(pdf_data)
            reader = PdfReader(pdf_file)

            # 提取所有页面的文本
            text_parts = []
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text.strip():
                    text_parts.append(f"### 第 {page_num} 页\n\n{text.strip()}")

            if text_parts:
                text_content = "\n\n".join(text_parts)
                logger.info(f"PyPDF2 解析成功，内容长度: {len(text_content)} 字符")
            else:
                text_content = "PDF文档解析成功，但未提取到文本内容。可能是扫描版PDF。"
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Ym01S05BPT06YjVjZjJhZWI=

        except ImportError:
            text_content = "错误: 未安装 PDF 解析库。请安装: pip install PyPDF2 或 pip install langchain-pymupdf4llm"
        except Exception as e2:
            logger.error(f"PyPDF2 解析也失败: {e2}")
            text_content = f"PDF文件处理出错: {str(e2)}"

    finally:
        # 清理临时文件（Windows上可能需要重试）
        _safe_delete_temp_file(temp_file_path)

    # 缓存结果
    if cache is not None and text_content:
        cache[cache_key] = text_content
        logger.info(f"PDF内容已缓存: {filename}")

    return text_content

