"""
大语言模型统一配置中心。

采用具体 SDK 类创建模型，确保可控性和兼容性：
- 文本模型：ChatDeepSeek（深度求索）
- 图片/多模态模型：ChatOpenAI（OpenAI 兼容接口，如豆包、阿里云等）
"""

import logging
from functools import lru_cache
# pylint: disable  MC8zOmFIVnBZMlhsdEpUbXRiZm92b2s2Y214MWVBPT06ODkzY2FhOWI=

from langchain_core.language_models import ModelProfile

from app.config.settings import settings

logger = logging.getLogger(__name__)

# pragma: no cover  MS8zOmFIVnBZMlhsdEpUbXRiZm92b2s2Y214MWVBPT06ODkzY2FhOWI=

@lru_cache(maxsize=1)
def get_text_model():
    """创建文本处理模型（DeepSeek）。

    适用于纯文本对话、代码生成、测试用例设计、策略分析等场景。
    通过 ChatDeepSeek 直接对接 DeepSeek API，支持 temperature 等原生参数。

    Returns:
        配置好 ModelProfile 的 ChatDeepSeek 实例
    """
    from langchain_deepseek import ChatDeepSeek
    try:
        model = ChatDeepSeek(
            api_key=settings.deepseek_api_key,
            model=settings.llm_model,
            temperature=0.3,
        )
        model.profile = ModelProfile(max_input_tokens=128000)
        logger.info(f"Text model ready: deepseek/{settings.llm_model}")
        return model
    except ImportError:
        logger.error("langchain_deepseek not installed. Run: pip install langchain-deepseek")
        raise
    except Exception as e:
        logger.error(f"Failed to create text model: {e}")
        raise


@lru_cache(maxsize=1)
def get_image_model():
    """创建图片处理模型（OpenAI 兼容接口）。

    适用于图片理解、图文混合需求分析、PDF 多模态解析等场景。
    通过 ChatOpenAI 对接任意兼容 OpenAI 接口的视觉模型（如豆包 Vision、通义千问 VL 等）。

    Returns:
        ChatOpenAI 实例
    """
    from langchain_openai import ChatOpenAI
    try:
        model = ChatOpenAI(
            base_url=settings.image_parser_api_base,
            api_key=settings.image_parser_api_key,
            model=settings.image_parser_model,
        )
        logger.info(f"Image model ready: {settings.image_parser_model}")
        return model
    except Exception as e:
        logger.error(f"Failed to create image model: {e}")
        raise
# noqa  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b2s2Y214MWVBPT06ODkzY2FhOWI=


# 全局模型实例（供各 Agent 直接导入使用）
text_model = get_text_model()
image_model = get_image_model()
