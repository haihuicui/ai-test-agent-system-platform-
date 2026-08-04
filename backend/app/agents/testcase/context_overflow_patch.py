"""上下文溢出异常翻译补丁。

DeepSeek / OpenAI 兼容网关在上下文超长时返回 HTTP 400（openai.BadRequestError），
但 langchain_deepseek / langchain_openai 不会把它转成 langchain_core 的
ContextOverflowError。deepagents 的 SummarizationMiddleware 只在捕获到
ContextOverflowError 时才会执行「摘要压缩 + 裁剪尾部大结果 + 重试」兜底；
异常类型对不上时兜底分支是死代码，整个 run 直接报错终止——用户侧表现为
"分析大文件时自动中断"，且炸弹消息留在 checkpoint 里，同一线程重试会再次失败。

本模块在模型调用最外层做异常翻译：识别各厂商 "context length exceeded" 类错误，
改抛 ContextOverflowError，让 summarization 兜底分支生效。与
tool_call_validation_middleware.patch_model_for_tool_call_adjacency 同款
monkey-patch 模式，仅影响错误路径，正常调用零开销。
"""
from __future__ import annotations

import logging
from typing import Any

from langchain_core.exceptions import ContextOverflowError

logger = logging.getLogger("app.context_overflow_patch")

# 各厂商 "context 超长" 错误消息特征（统一小写后子串匹配）
# - OpenAI / DeepSeek: "This model's maximum context length is N tokens. However, ..."
# - 其他 OpenAI 兼容网关: "context length exceeded" / "too many tokens" / "prompt is too long"
_OVERFLOW_PATTERNS = (
    "maximum context length",
    "context length",
    "context window",
    "too many tokens",
    "prompt is too long",
    "request too large",
    "reduce the length",
    "input is too long",
)

# 用于防止对同一模型实例重复 patch
_PATCHED_MODELS: set[int] = set()


def is_context_overflow_error(exc: BaseException) -> bool:
    """判断异常是否为「上下文超长」类错误。

    仅匹配消息特征不足以保证可靠（个别网关会把参数错误也写成类似文案），
    因此带 HTTP 状态码的异常只认 4xx；5xx 属于服务端故障，不应触发摘要兜底。
    """
    message = str(exc).lower()
    if not any(pattern in message for pattern in _OVERFLOW_PATTERNS):
        return False
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and status >= 500:
        return False
    return True


def _translate(exc: BaseException) -> BaseException:
    """是上下文溢出则返回 ContextOverflowError，否则原样返回。"""
    if is_context_overflow_error(exc):
        logger.warning(
            "检测到上下文溢出错误，翻译为 ContextOverflowError 以触发摘要兜底: %s",
            str(exc)[:200],
        )
        return ContextOverflowError(str(exc))
    return exc


def patch_model_for_context_overflow(model: Any) -> None:
    """Monkey-patch 一个 ChatModel，把上下文溢出 400 翻译为 ContextOverflowError。

    只需在模块加载时对全局模型实例调用一次；幂等。patch 只包裹错误路径，
    不改动正常调用的参数与返回值。
    """
    model_id = id(model)
    if model_id in _PATCHED_MODELS:
        logger.debug("Model %s already patched for context overflow, skipping", type(model).__name__)
        return
    _PATCHED_MODELS.add(model_id)

    logger.info("Patching %s for context-overflow translation", type(model).__name__)
    original_ainvoke = model.ainvoke
    original_invoke = model.invoke
    original_astream = getattr(model, "astream", None)
    original_stream = getattr(model, "stream", None)

    async def ainvoke_patched(input: Any, config: Any = None, **kwargs: Any) -> Any:
        try:
            return await original_ainvoke(input, config=config, **kwargs)
        except Exception as exc:
            translated = _translate(exc)
            if translated is exc:
                raise
            raise translated from exc

    def invoke_patched(input: Any, config: Any = None, **kwargs: Any) -> Any:
        try:
            return original_invoke(input, config=config, **kwargs)
        except Exception as exc:
            translated = _translate(exc)
            if translated is exc:
                raise
            raise translated from exc

    object.__setattr__(model, "ainvoke", ainvoke_patched)
    object.__setattr__(model, "invoke", invoke_patched)

    if original_astream is not None:
        async def astream_patched(input: Any, config: Any = None, **kwargs: Any) -> Any:
            # 流式调用的错误在迭代阶段才抛出，因此用异步生成器包裹整个迭代过程
            try:
                async for chunk in original_astream(input, config=config, **kwargs):
                    yield chunk
            except Exception as exc:
                translated = _translate(exc)
                if translated is exc:
                    raise
                raise translated from exc

        object.__setattr__(model, "astream", astream_patched)

    if original_stream is not None:
        def stream_patched(input: Any, config: Any = None, **kwargs: Any) -> Any:
            try:
                yield from original_stream(input, config=config, **kwargs)
            except Exception as exc:
                translated = _translate(exc)
                if translated is exc:
                    raise
                raise translated from exc

        object.__setattr__(model, "stream", stream_patched)
