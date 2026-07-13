"""
执行日志格式化工具

为统一脚本执行引擎的各执行器提供人类可读的日志格式化能力。
"""

import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# pragma: no cover  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2ZEVRME9BPT06NmVkNmVmNDQ=

logger = logging.getLogger(__name__)

# 单条日志硬上限，防止 Text 列/前端内存过载
_MAX_LOG_LENGTH = 100_000


def format_scenario_log(
    scenario_run: Any,
    step_results: Sequence[Any],
    settings: Any,
) -> Tuple[str, str]:
    """
    将场景运行记录格式化为 (stdout, stderr) 执行日志。

    stdout: 人类可读的场景摘要与各步骤请求/响应/断言/提取信息。
    stderr: 失败步骤的错误信息及场景级错误信息。
    """
    lines: List[str] = []
    stderr_lines: List[str] = []

    lines.append("=== 场景执行日志 ===")
    lines.extend(_format_summary(scenario_run))
    lines.append("")

    for idx, step_result in enumerate(step_results, start=1):
        step_stdout, step_stderr = _format_step(step_result, idx, settings)
        lines.append(step_stdout)
        if step_stderr:
            stderr_lines.append(step_stderr)

    stdout = "\n".join(lines)
    stdout = _truncate_text(stdout, _MAX_LOG_LENGTH)

    # 场景级错误信息放在 stderr 最前面
    run_error = getattr(scenario_run, "error_message", None) or ""
    if run_error:
        stderr_lines.insert(0, f"场景执行失败: {run_error}")

    stderr = "\n\n".join(stderr_lines)
    stderr = _truncate_text(stderr, _MAX_LOG_LENGTH)

    return stdout, stderr


def _format_summary(scenario_run: Any) -> List[str]:
    """格式化场景级摘要"""
    scenario_name = getattr(scenario_run, "scenario_name", None) or "未知场景"
    identifier = getattr(scenario_run, "identifier", "") or ""
    status = getattr(scenario_run, "status", "unknown")
    duration_ms = getattr(scenario_run, "duration_ms", None) or 0
    total_steps = getattr(scenario_run, "total_steps", 0) or 0
    passed_steps = getattr(scenario_run, "passed_steps", 0) or 0
    failed_steps = getattr(scenario_run, "failed_steps", 0) or 0
    skipped_steps = getattr(scenario_run, "skipped_steps", 0) or 0

    return [
        f"场景: {scenario_name}",
        f"运行编号: {identifier}",
        f"状态: {status}",
        f"步骤统计: 总计 {total_steps} | 通过 {passed_steps} | 失败 {failed_steps} | 跳过 {skipped_steps}",
        f"耗时: {duration_ms} ms",
    ]


def _format_step(step_result: Any, index: int, settings: Any) -> Tuple[str, Optional[str]]:
    """格式化单个步骤，返回 (stdout_block, stderr_block)"""
    name = getattr(step_result, "step_name", None) or f"步骤 {getattr(step_result, 'step_order', index)}"
    status = getattr(step_result, "status", "unknown")
    duration_ms = getattr(step_result, "duration_ms", None) or 0
    full_url = getattr(step_result, "full_url", "") or ""
    request_data = getattr(step_result, "request_data", None) or {}
    response_data = getattr(step_result, "response_data", None) or {}
    assertion_results = getattr(step_result, "assertion_results", None) or []
    extracted_data = getattr(step_result, "extracted_data", None) or {}
    error_message = getattr(step_result, "error_message", None) or ""
    error_stack = getattr(step_result, "error_stack", None) or ""

    method = (request_data.get("method") or "GET").upper()

    lines: List[str] = []
    lines.append(f"--- 步骤 {index}: {name} ---")
    lines.append(f"状态: {status} | 耗时: {duration_ms} ms")
    if full_url:
        lines.append(f"请求: {method} {full_url}")

    # 请求信息
    sanitized_request = _sanitize_data(request_data, settings)
    if sanitized_request.get("headers"):
        lines.append("请求头:")
        lines.append(_indent(_format_dict(sanitized_request["headers"])))
    if "body" in sanitized_request and sanitized_request["body"] is not None:
        lines.append("请求体:")
        lines.append(_indent(_format_body(sanitized_request["body"])))

    # 响应信息
    sanitized_response = _sanitize_data(response_data, settings)
    if sanitized_response.get("status") is not None:
        lines.append(f"响应状态: {sanitized_response['status']}")
    if sanitized_response.get("headers"):
        lines.append("响应头:")
        lines.append(_indent(_format_dict(sanitized_response["headers"])))
    if "body" in sanitized_response and sanitized_response["body"] is not None:
        lines.append("响应体:")
        lines.append(_indent(_format_body(sanitized_response["body"])))

    # 断言结果
    if assertion_results:
        lines.append("断言结果:")
        for assertion in assertion_results:
            passed = assertion.get("passed", False)
            symbol = "✓" if passed else "✗"
            msg = assertion.get("message", "断言")
            lines.append(f"  {symbol} {msg}")
            if not passed:
                actual = assertion.get("actual")
                expected = assertion.get("expected")
                lines.append(f"    实际值: {actual}")
                lines.append(f"    期望值: {expected}")

    # 提取变量
    if extracted_data:
        lines.append("提取变量:")
        lines.append(_indent(_format_dict(extracted_data)))

    stdout_block = "\n".join(lines)

    # 错误信息归入 stderr
    stderr_block: Optional[str] = None
    if error_message or error_stack:
        stderr_parts = [f"步骤 {index} ({name}) 错误:"]
        if error_message:
            stderr_parts.append(error_message)
        if error_stack and error_stack != error_message:
            stderr_parts.append(error_stack)
        stderr_block = "\n".join(stderr_parts)

    return stdout_block, stderr_block


def _sanitize_data(data: Optional[Dict[str, Any]], settings: Any) -> Dict[str, Any]:
    """对请求/响应数据进行脱敏与截断"""
    if not data:
        return {}

    sensitive_headers = set(
        (h.lower() for h in getattr(settings, "api_test_sensitive_headers", []))
    )
    sensitive_fields = set(
        (f.lower() for f in getattr(settings, "api_test_sensitive_body_fields", []))
    )
    truncate_threshold = getattr(settings, "api_test_body_truncate_threshold", 50_000)
    preview_length = getattr(settings, "api_test_body_preview_length", 2_000)

    sanitized: Dict[str, Any] = dict(data)

    # 脱敏 headers
    if "headers" in sanitized and isinstance(sanitized["headers"], dict):
        sanitized["headers"] = _redact_headers(sanitized["headers"], sensitive_headers)

    # 脱敏并截断 body
    for key in ("body",):
        if key in sanitized and sanitized[key] is not None:
            sanitized[key] = _redact_body(sanitized[key], sensitive_fields)
            sanitized[key] = _truncate_body(sanitized[key], truncate_threshold, preview_length)

    return sanitized


def _redact_headers(headers: Dict[str, Any], sensitive_headers: Iterable[str]) -> Dict[str, Any]:
    """将敏感请求/响应头值替换为 ***"""
    if not headers:
        return headers

    result: Dict[str, Any] = {}
    for key, value in headers.items():
        if key.lower() in sensitive_headers:
            result[key] = "***"
        else:
            result[key] = value
    return result


def _redact_body(body: Any, sensitive_fields: Iterable[str]) -> Any:
    """递归替换敏感字段值为 ***"""
    if body is None:
        return body

    sensitive_set = set(sensitive_fields)

    if isinstance(body, str):
        # 尝试解析 JSON 字符串进行脱敏
        try:
            parsed = json.loads(body)
            redacted = _redact_body(parsed, sensitive_set)
            return json.dumps(redacted, ensure_ascii=False)
        except Exception:
            return body

    if isinstance(body, (list, tuple)):
        return [_redact_body(item, sensitive_set) for item in body]

    if isinstance(body, dict):
        result: Dict[str, Any] = {}
        for key, value in body.items():
            if key.lower() in sensitive_set:
                result[key] = "***"
            else:
                result[key] = _redact_body(value, sensitive_set)
        return result

    return body


def _truncate_body(body: Any, threshold: int, preview_length: int) -> Any:
    """如果 body 序列化后超过阈值，则截断到预览长度"""
    if body is None:
        return body

    try:
        serialized = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    except Exception:
        serialized = str(body)

    if len(serialized) <= threshold:
        return body

    return _truncate_text(serialized, preview_length)


def _truncate_text(text: str, max_length: int) -> str:
    """截断文本并附加标记"""
    if not text or len(text) <= max_length:
        return text
    return text[:max_length] + "\n...[truncated]"


def _format_dict(value: Any) -> str:
    """将字典格式化为 JSON 字符串"""
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return str(value)


def _format_body(body: Any) -> str:
    """格式化 body，优先输出 JSON 样式"""
    if isinstance(body, str):
        return body
    return _format_dict(body)


def _indent(text: str, prefix: str = "  ") -> str:
    """对多行文本缩进"""
    if not text:
        return text
    return "\n".join(prefix + line for line in text.splitlines())
