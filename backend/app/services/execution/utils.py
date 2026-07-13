"""
执行引擎工具函数

集中处理 result_summary 计数兜底与失败分类，避免各执行器重复实现。
"""

from typing import Any, Dict, List, Optional, Tuple


def coerce_result_summary_counts(summary: Optional[Dict[str, Any]]) -> Tuple[Dict[str, int], bool]:
    """
    将 result_summary 中的计数安全地转换为整数，并把 None/缺失值兜底为 0。

    返回:
        coerced_summary: 包含 total/passed/failed/skipped/error 的字典
        has_missing_counts: 是否曾经出现 None 或缺失的计数
    """
    coerced: Dict[str, int] = {}
    has_missing = False
    for key in ("total", "passed", "failed", "skipped", "error"):
        raw = summary.get(key) if summary else None
        if raw is None:
            has_missing = True
            coerced[key] = 0
        else:
            try:
                coerced[key] = int(raw)
            except (TypeError, ValueError):
                has_missing = True
                coerced[key] = 0
    return coerced, has_missing


def classify_failure_category(
    *,
    success: bool,
    error_message: Optional[str] = None,
    failed_count: int = 0,
    error_count: int = 0,
    step_results: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """
    根据执行结果信号推断 failure_category。

    分类优先级:
    1. success -> None
    2. timeout 关键字 -> "timeout"
    3. 断言关键字 / 失败计数 / 错误计数 / 失败步骤 -> "assertion"
    4. 环境/基础设施关键字 -> "environment"
    5. 兜底 -> "infra"

    当旧数据导致计数为 NULL/0 时，会优先使用 error_message 关键字或步骤状态
    来避免把真正的断言失败误判为 environment/infra。
    """
    if success:
        return None

    error = (error_message or "").lower()

    # 1. timeout
    if "timeout" in error or "timed out" in error:
        return "timeout"

    # 2. environment signals
    environment_keywords = (
        "environment",
        "npx",
        "playwright",
        "browser",
        "driver",
        "connection refused",
        "network",
        "dns",
        "socket",
        "env",
    )
    if any(kw in error for kw in environment_keywords):
        return "environment"

    # 3. assertion signals
    assertion_keywords = (
        "assert",
        "expect",
        "expected",
        "actual",
        "mismatch",
        "断言",
    )
    has_assertion_keyword = any(kw in error for kw in assertion_keywords)

    has_failed_step = False
    if step_results:
        has_failed_step = any(
            str(sr.get("status", "")).lower() in ("failed", "error")
            for sr in step_results
        )

    if has_assertion_keyword or failed_count > 0 or error_count > 0 or has_failed_step:
        return "assertion"

    # 4. fallback
    return "infra"
