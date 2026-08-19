"""
大语言模型统一配置中心。

采用具体 SDK 类创建模型，确保可控性和兼容性：
- 文本模型：ChatDeepSeek（深度求索）
- 自部署文本模型：ChatOpenAI（OpenAI 兼容接口，vLLM 网关的千问）
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
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout,
            max_tokens=settings.llm_max_tokens,
            stream_chunk_timeout=settings.llm_stream_chunk_timeout,
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


def get_text_model_with_temperature(temperature: float = 0.3, max_tokens: int | None = None):
    """创建指定 temperature 的文本模型。

    用于按 Agent 阶段动态调整温度：
    - 分析/评审阶段（0.1-0.3）→ 确定性输出
    - 生成阶段（0.5）→ 增加多样性和创造性
    - 格式化阶段（0.0）→ 机械性输出

    Args:
        temperature: 采样温度
        max_tokens: 输出 token 上限；None 时使用 settings.llm_max_tokens。
            deepseek-v4 系列为推理模型，reasoning 也消耗该配额——
            长评审报告场景（如对抗性评审子代理）需显式调大，
            否则思考链会耗尽配额导致正文静默为空（finish_reason=length）。

    注意：此函数不使用 lru_cache，每次调用都新建实例；
    ChatDeepSeek 实例本身创建成本很低（仅配置参数，不建连）。
    """
    from langchain_deepseek import ChatDeepSeek
    try:
        model = ChatDeepSeek(
            api_key=settings.deepseek_api_key,
            model=settings.llm_model,
            temperature=temperature,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout,
            max_tokens=max_tokens if max_tokens is not None else settings.llm_max_tokens,
            stream_chunk_timeout=settings.llm_stream_chunk_timeout,
        )
        model.profile = ModelProfile(max_input_tokens=128000)
        return model
    except Exception as e:
        logger.warning(
            "Failed to create text model (t=%.1f), falling back to default: %s",
            temperature, e,
        )
        return text_model  # 降级到默认模型


@lru_cache(maxsize=1)
def get_qwen_model():
    """创建自部署千问文本模型（OpenAI 兼容接口）。

    适用于 DeepSeek 不可用时的备选文本模型，或需要本地数据不出网的场景。
    通过 ChatOpenAI 对接 vLLM 网关（10.1.0.29:8001）上的 qwen3.8-27b。

    Returns:
        配置好 ModelProfile 的 ChatOpenAI 实例

    Raises:
        RuntimeError: 未配置 qwen_api_base 时
    """
    if not settings.qwen_api_base:
        raise RuntimeError(
            "Qwen model not configured. Set QWEN_API_BASE/QWEN_API_KEY in .env"
        )
    from langchain_openai import ChatOpenAI
    try:
        model = ChatOpenAI(
            base_url=settings.qwen_api_base,
            api_key=settings.qwen_api_key,
            model=settings.qwen_model,
            temperature=0.3,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout,
            max_tokens=settings.llm_max_tokens,
            stream_chunk_timeout=settings.llm_stream_chunk_timeout,
        )
        # vLLM 侧 max_model_len=262144，预留 16K 输出配额后的可用输入上限
        model.profile = ModelProfile(max_input_tokens=245760)
        logger.info(f"Qwen model ready: {settings.qwen_model} @ {settings.qwen_api_base}")
        return model
    except Exception as e:
        logger.error(f"Failed to create qwen model: {e}")
        raise


def get_qwen_model_with_temperature(temperature: float = 0.3, max_tokens: int | None = None):
    """创建指定 temperature 的自部署千问模型。

    与 get_text_model_with_temperature 同契约，供 testcase Agent 按阶段调温。
    qwen3.8 同为推理模型，reasoning 与正文共享 max_tokens 配额——
    长评审场景需显式调大 max_tokens，否则正文静默为空（finish_reason=length）。

    注意：此函数不使用 lru_cache，每次调用都新建实例。
    """
    if not settings.qwen_api_base:
        raise RuntimeError(
            "Qwen model not configured. Set QWEN_API_BASE/QWEN_API_KEY in .env"
        )
    from langchain_openai import ChatOpenAI
    model = ChatOpenAI(
        base_url=settings.qwen_api_base,
        api_key=settings.qwen_api_key,
        model=settings.qwen_model,
        temperature=temperature,
        max_retries=settings.llm_max_retries,
        timeout=settings.llm_timeout,
        max_tokens=max_tokens if max_tokens is not None else settings.llm_max_tokens,
        stream_chunk_timeout=settings.llm_stream_chunk_timeout,
    )
    model.profile = ModelProfile(max_input_tokens=245760)
    return model


# 全局模型实例（供各 Agent 直接导入使用）
text_model = get_text_model()
image_model = get_image_model()