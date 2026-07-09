"""
工具错误处理包装器

将工具错误转换为错误消息，而不是抛出异常，防止 Agent 执行中断。
"""

from functools import wraps
from typing import Any
from langchain_core.tools import BaseTool, StructuredTool, ToolException
import logging
import json

from app.utils.sync_executor import run_sync

logger = logging.getLogger(__name__)
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWxCc1ZnPT06YWViYjkxMzU=


# ---------------------------------------------------------------------------
# 全局补丁：让 @tool 装饰的 sync 工具在 ainvoke 时也走我们的共享线程池。
# StructuredTool.ainvoke 对 sync 工具会绕过 _arun，直接使用默认 executor
# 调用 self.invoke。这里把它改道到 run_sync，从而统一线程池并避免阻塞。
# ---------------------------------------------------------------------------
_original_structured_ainvoke = StructuredTool.ainvoke


async def _patched_structured_ainvoke(self, input, config=None, **kwargs):
    if not getattr(self, "coroutine", None):
        return await run_sync(self.invoke, input, config, **kwargs)
    return await _original_structured_ainvoke(self, input, config, **kwargs)


StructuredTool.ainvoke = _patched_structured_ainvoke


# 记录已包装的工具 id，避免对同一个（模块级单例）工具实例重复包装。
# 工具实例在多次 make_agent() 调用间复用，重复包装会让 functools.wraps 在
# _arun/_run 上不断叠加 __wrapped__ 链，最终触发 inspect.unwrap 的
# "wrapper loop when unwrapping ..." 错误。
_wrapped_tool_ids: set[int] = set()


def _is_sync_tool(tool: BaseTool, original_arun) -> bool:
    """判断工具是否实际没有 async 实现，需要在线程池中运行 sync 版本。

    LangChain 的 @tool 装饰器：
    - 对 async 函数生成 StructuredTool，其 self.coroutine 不为 None。
    - 对 sync 函数也生成 StructuredTool，但 self.coroutine 为 None，
      _arun 会委托给 BaseTool._arun，最终在线程中执行 _run。
    我们通过 self.coroutine 是否为 None 来识别 sync 工具，避免依赖 qualname。
    """
    try:
        # StructuredTool 用 coroutine 属性区分 sync/async
        if hasattr(tool, "coroutine"):
            return tool.coroutine is None
        # 自定义 BaseTool 子类：如果 _arun 仍是基类默认实现，也按 sync 处理
        return original_arun.__qualname__.endswith("BaseTool._arun")
    except Exception:
        return False


def wrap_tool_with_error_handling(tool: BaseTool) -> BaseTool:
    """
    包装工具，使其在出错时返回错误信息而不是抛出异常

    Args:
        tool: 原始工具

    Returns:
        包装后的工具
    """
    # 幂等保护：同一工具实例只包装一次。工具是模块级单例，会在多次
    # make_agent() 调用间复用，重复包装会累积 __wrapped__ 链并最终导致
    # inspect.unwrap 检测到 wrapper loop。
    if id(tool) in _wrapped_tool_ids:
        return tool

    original_run = tool._run
    original_arun = tool._arun
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWxCc1ZnPT06YWViYjkxMzU=

    @wraps(original_run)
    def wrapped_run(*args: Any, **kwargs: Any) -> Any:
        try:
            return original_run(*args, **kwargs)
        except ToolException as e:
            error_msg = f"Tool '{tool.name}' encountered an error: {str(e)}"
            logger.warning(error_msg)
            # 返回元组格式 (content, artifact)，符合 response_format='content_and_artifact'
            error_info = {
                "success": False,
                "error": str(e),
                "error_type": "ToolException",
                "message": error_msg,
                "note": "This error was caught and returned as a message. You can analyze the error and try a different approach."
            }
            error_json = json.dumps(error_info, ensure_ascii=False)
            # 返回元组：(content, artifact)
            return (error_json, {"error": True, "tool": tool.name})
        except Exception as e:
            error_msg = f"Tool '{tool.name}' encountered an unexpected error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # 返回元组格式 (content, artifact)
            error_info = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "message": error_msg,
                "note": "This error was caught and returned as a message. You can analyze the error and try a different approach."
            }
            error_json = json.dumps(error_info, ensure_ascii=False)
            # 返回元组：(content, artifact)
            return (error_json, {"error": True, "tool": tool.name})

    @wraps(original_arun)
    async def wrapped_arun(*args: Any, **kwargs: Any) -> Any:
        try:
            # sync 工具没有真正的 async 实现，通过线程池运行 original_run，
            # 避免阻塞事件循环。
            if _is_sync_tool(tool, original_arun):
                return await run_sync(original_run, *args, **kwargs)
            return await original_arun(*args, **kwargs)
        except ToolException as e:
            error_msg = f"Tool '{tool.name}' encountered an error: {str(e)}"
            logger.warning(error_msg)
            # 返回元组格式 (content, artifact)
            error_info = {
                "success": False,
                "error": str(e),
                "error_type": "ToolException",
                "message": error_msg,
                "note": "This error was caught and returned as a message. You can analyze the error and try a different approach."
            }
            error_json = json.dumps(error_info, ensure_ascii=False)
            # 返回元组：(content, artifact)
            return (error_json, {"error": True, "tool": tool.name})
        except Exception as e:
            error_msg = f"Tool '{tool.name}' encountered an unexpected error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # 返回元组格式 (content, artifact)
            error_info = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "message": error_msg,
                "note": "This error was caught and returned as a message. You can analyze the error and try a different approach."
            }
            error_json = json.dumps(error_info, ensure_ascii=False)
            # 返回元组：(content, artifact)
            return (error_json, {"error": True, "tool": tool.name})

    # 替换工具的运行方法
    tool._run = wrapped_run
    tool._arun = wrapped_arun

    _wrapped_tool_ids.add(id(tool))

    return tool


def wrap_tools_with_error_handling(tools: list[BaseTool],
                                   tool_patterns: list[str] | None = None) -> list[BaseTool]:
    """
    批量包装工具

    Args:
        tools: 工具列表
        tool_patterns: 需要包装的工具名称模式列表（如 ["browser_", "playwright-test/"]）
                      如果为 None，则包装所有工具

    Returns:
        包装后的工具列表
    """
    wrapped_tools = []
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWxCc1ZnPT06YWViYjkxMzU=

    for tool in tools:
        should_wrap = False

        if tool_patterns is None:
            # 包装所有工具
            should_wrap = True
        else:
            # 检查工具名称是否匹配任何模式
            for pattern in tool_patterns:
                if pattern in tool.name:
                    should_wrap = True
                    break
# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2UWxCc1ZnPT06YWViYjkxMzU=

        if should_wrap:
            logger.info(f"Wrapping tool '{tool.name}' with error handling")
            wrapped_tools.append(wrap_tool_with_error_handling(tool))
        else:
            wrapped_tools.append(tool)

    return wrapped_tools
