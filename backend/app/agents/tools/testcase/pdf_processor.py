"""
PDF 文档处理器，支持文本提取和缓存
"""

import tempfile
import os
import re
import logging
import hashlib
import time
from typing import Optional

from app.config.settings import settings

logger = logging.getLogger(__name__)

_pdf_cache = {}

# PyMuPDF 内建 OCR 层（系统 Tesseract，缺中文语言包）对图片页产生的乱码文本块。
# 多模态视觉解析已输出高质量图片摘要，OCR 层纯属冗余噪声（实测 s52需求.pdf
# 中占全文 33%），且乱码会误导模型把 "AARP RUS" 之类当成真实标题，故直接剥离。
_PICTURE_TEXT_BLOCK_RE = re.compile(
    r"<!--\s*Start of picture text\s*-->.*?<!--\s*End of picture text\s*-->",
    re.DOTALL,
)


def _safe_delete_temp_file(file_path: str, max_retries: int = 3, delay: float = 0.1):
    """安全删除临时文件，处理 Windows 文件锁定问题。"""
    if not os.path.exists(file_path):
        return

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
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WmxkTE1RPT06YzhhMDFkMGY=

    def __init__(self, enable_cache: bool = True):
        self.enable_cache = enable_cache
        self.cache = _pdf_cache if enable_cache else {}

    def extract_text(self, pdf_data: bytes, filename: str = "unknown.pdf") -> str:
        """从 PDF 字节数据中提取文本。"""
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


def _make_safe_image_parser_cls():
    """构建带防护 + 并发识别的视觉图片解析器（延迟导入，避免模块加载期硬依赖）。

    原生 LLMImageBlobParser 的三个问题（实测 s52需求.pdf，96 张图）：
    1. 过小图片（如 20x9px）触发视觉 API 400（最小 14px），异常直接终止
       整个 PDF 的解析；
    2. 任意单张图片识别失败都会向上抛出，拖垮整篇文档；
    3. pymupdf4llm 串行逐图调用，96 张图 × ~5s = 8 分钟以上的解析静默。

    防护与加速策略：
    - 小图直接跳过（基本是图标/分隔线，无分析价值）；
    - 解析阶段不立即调 API：图片压缩登记为 JPEG 字节并返回占位符，整篇
      文档结构解析完成后由 flush() 用线程池并发识别，再按占位符回填——
      图片在 markdown 中的位置不变，96 张图从 ~8 分钟压到 ~2 分钟；
    - 单图失败降级为空描述，继续处理其余图片。
    """
    import io
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from langchain_community.document_loaders.parsers import LLMImageBlobParser
    from PIL import Image

    class SafeLLMImageBlobParser(LLMImageBlobParser):
        # 视觉 API 最小 14px，留一倍余量
        MIN_IMAGE_DIM = 28
        # 延迟登记图片的最大边长：视觉 API 自身会缩放，1568px 足以保留流程图
        # 文字细节；同时把大批量图片的内存占用从 ~1GB 压到 ~30MB（JPEG 字节）
        MAX_DEFER_DIM = 1568

        def __init__(self, *, model, max_workers: int = 4, **kwargs):
            super().__init__(model=model, **kwargs)
            self._max_workers = max(1, max_workers)
            self._pending: list[tuple[str, bytes]] = []  # (占位符, JPEG 字节)
            self._seq = 0

        def _analyze_image(self, img) -> str:  # type: ignore[override]
            width, height = img.size
            if width < self.MIN_IMAGE_DIM or height < self.MIN_IMAGE_DIM:
                logger.debug("跳过过小图片 (%dx%d)", width, height)
                return ""
            self._seq += 1
            placeholder = f"__IMG_DEFER_{self._seq:04d}__"
            self._pending.append((placeholder, self._to_jpeg(img)))
            return placeholder

        def _to_jpeg(self, img) -> bytes:
            img = img.copy()
            img.thumbnail((self.MAX_DEFER_DIM, self.MAX_DEFER_DIM))
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return buf.getvalue()

        def _vision_call(self, jpeg: bytes) -> str:
            """flush 线程池中的单图识别：失败降级为空串，不再抛出。"""
            img = Image.open(io.BytesIO(jpeg))
            try:
                return super()._analyze_image(img)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "单张图片视觉识别失败 (%dx%d)，已跳过: %s",
                    img.size[0], img.size[1], e,
                )
                return ""

        def flush(self) -> dict[str, str]:
            """并发识别所有登记图片，返回 {占位符: 描述文本}（保持调用方线程）。"""
            if not self._pending:
                return {}
            total = len(self._pending)
            logger.info("开始并发视觉识别 %d 张图片（%d 线程）", total, self._max_workers)
            results: dict[str, str] = {}
            done = 0
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                futures = {
                    pool.submit(self._vision_call, jpeg): placeholder
                    for placeholder, jpeg in self._pending
                }
                for fut in as_completed(futures):
                    results[futures[fut]] = fut.result()
                    done += 1
                    if done % 10 == 0 or done == total:
                        logger.info("视觉识别进度 %d/%d", done, total)
            self._pending.clear()
            return results

    return SafeLLMImageBlobParser


def extract_pdf_text(pdf_data: bytes, filename: str = "unknown.pdf", cache: Optional[dict] = None) -> str:
    """
    从 PDF 字节数据中提取文本，使用缓存避免重复解析。

    提取方法：
    1. PyMuPDF4LLM (推荐): 支持表格提取和多模态图片解析
    2. PyPDF2 (备用): 基础文本提取

    Args:
        pdf_data: PDF 文件的字节数据
        filename: 文件名（用于日志和缓存）
        cache: 可选的缓存字典

    Returns:
        str: 提取的文本内容
    """
    # 空数据拦截：0 字节的 PDF 无法解析，且会让 PyMuPDF4LLM 抛出
    # "Cannot open empty file"，再回退到（可能未安装的）PyPDF2，
    # 最终给出误导性的 "PDF 解析库未安装"。这里直接返回明确原因。
    if not pdf_data:
        logger.warning(f"PDF 内容为空 (0 字节): {filename}")
        return "错误: PDF 文档内容为空（0 字节），无法解析。请确认上传的文件本身不是空文件。"

    pdf_hash = hashlib.md5(pdf_data).hexdigest()
    cache_key = f"{filename}_{pdf_hash}"

    if cache is not None and cache_key in cache:
        logger.info(f"从缓存中获取 PDF 内容: {filename}")
        return cache[cache_key]

    temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    try:
        temp_file.write(pdf_data)
        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_file_path = temp_file.name
    finally:
        temp_file.close()

    text_content = ""
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WmxkTE1RPT06YzhhMDFkMGY=

    try:
        logger.info(f"使用 PyMuPDF4LLM 解析 PDF: {filename}")

        try:
            from langchain_pymupdf4llm import PyMuPDF4LLMLoader

            enable_multimodal = getattr(settings, 'enable_pdf_multimodal', False)
            image_parser = None

            if enable_multimodal:
                try:
                    from app.core.llms import get_image_model

                    image_llm = get_image_model()
                    max_workers = int(os.environ.get("PDF_VISION_MAX_WORKERS", "4"))
                    image_parser = _make_safe_image_parser_cls()(
                        model=image_llm, max_workers=max_workers
                    )

                    loader = PyMuPDF4LLMLoader(
                        temp_file_path,
                        mode="single",
                        extract_images=True,
                        images_parser=image_parser,
                        table_strategy="lines",
                        # 多模态必须用经典 rag 解析路径：layout 模式下图片框依赖
                        # 内建 OCR（系统 Tesseract 缺中文包只产乱码）才能暴露给
                        # images_parser；rag 路径原生输出图片引用供视觉解析，
                        # 无 OCR 乱码，且 table_strategy 在此路径才真正生效
                        use_layout=False,
                    )
                    logger.info("启用多模态图片解析（并发线程 %d）", max_workers)
                except ImportError as e:
                    logger.warning(f"多模态依赖未安装，使用基础模式: {e}")
                    loader = PyMuPDF4LLMLoader(
                        temp_file_path,
                        mode="single",
                        table_strategy="lines"
                    )
                except Exception as e:
                    logger.warning(f"多模态模型加载失败，使用基础模式: {e}")
                    loader = PyMuPDF4LLMLoader(
                        temp_file_path,
                        mode="single",
                        table_strategy="lines"
                    )
            else:
                loader = PyMuPDF4LLMLoader(
                    temp_file_path,
                    mode="single",
                    table_strategy="lines"
                )

            documents = loader.load()

            # 并发识别解析阶段延迟登记的图片，按占位符回填到 markdown 原位置
            if image_parser is not None and documents:
                deferred = image_parser.flush()
                if deferred:
                    merged = documents[0].page_content
                    for placeholder, summary in deferred.items():
                        merged = merged.replace(
                            placeholder,
                            summary.strip() if summary.strip() else "[图片内容无法识别]",
                        )
                    documents[0].page_content = merged
                    logger.info("视觉识别回填完成：%d 张图片", len(deferred))

            if documents:
                text_content = documents[0].page_content
                logger.info(f"PyMuPDF4LLM 解析成功，内容长度: {len(text_content)} 字符")
            else:
                text_content = "PDF 文件解析后内容为空"

        except ImportError:
            logger.warning("PyMuPDF4LLM 未安装，尝试使用 PyPDF2")
            raise
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WmxkTE1RPT06YzhhMDFkMGY=

    except Exception as e:
        logger.warning(f"PyMuPDF4LLM 解析失败: {e}，尝试使用 PyPDF2")
        primary_error = e

        try:
            try:
                from pypdf import PdfReader  # 维护中的后继库
            except ImportError:
                from PyPDF2 import PdfReader  # 旧名兼容
            import io

            pdf_file = io.BytesIO(pdf_data)
            reader = PdfReader(pdf_file)

            text_parts = []
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text()
                if text.strip():
                    text_parts.append(f"### 第 {page_num} 页\n\n{text.strip()}")
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WmxkTE1RPT06YzhhMDFkMGY=

            if text_parts:
                text_content = "\n\n".join(text_parts)
                logger.info(f"PyPDF2 解析成功，内容长度: {len(text_content)} 字符")
            else:
                text_content = "PDF 文档解析成功，但未提取到文本内容。可能是扫描版 PDF。"

        except ImportError:
            # 备用解析库未安装：此时真正的失败原因是主解析器(PyMuPDF4LLM)的错误，
            # 不应误报为"未安装 PDF 解析库"。
            logger.error(f"备用 PDF 解析库 (pypdf/PyPDF2) 未安装，主解析器错误: {primary_error}")
            text_content = f"PDF 解析失败: {primary_error}"
        except Exception as e2:
            logger.error(f"PyPDF2 解析也失败: {e2}")
            text_content = f"PDF 文件处理出错: {str(e2)}"

    finally:
        _safe_delete_temp_file(temp_file_path)

    # 剥离 OCR 乱码块（视觉摘要之外的纯噪声；剥离后为空时走下方空值处理）
    text_content = _PICTURE_TEXT_BLOCK_RE.sub("", text_content)

    # 最终结果仍为空：多为扫描版/图片型 PDF（无文字层），且多模态/OCR 未生效。
    # 返回明确可执行的提示，避免下游收到空串后报"解析返回空内容"这类含糊错误。
    if not text_content or not text_content.strip():
        logger.warning(f"PDF 解析最终结果为空（疑似扫描版/图片型 PDF）: {filename}")
        enabled = getattr(settings, "enable_pdf_multimodal", False)
        return (
            "PDF 解析未提取到任何文本，该文件很可能是扫描版/图片型 PDF（无文字层）。"
            + (
                "多模态图片解析已启用但未返回内容，请检查图片解析模型(IMAGE_PARSER_*)配置是否可用。"
                if enabled
                else "请在配置中开启 ENABLE_PDF_MULTIMODAL 并配置图片解析模型(IMAGE_PARSER_*)后重试。"
            )
        )

    if cache is not None and text_content:
        cache[cache_key] = text_content
        logger.info(f"PDF 内容已缓存: {filename}")

    return text_content
