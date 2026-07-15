"""解析 Playwright JSON reporter 输出为结构化 stats / cases，并做状态映射。

供两条执行链路共用，保证解析口径一致：
- agent 工具链路：app.agents.tools.web.execution_tools
- 服务端链路：app.services.web_test_service

集中在此避免两处各自遍历 suites / 各自做状态映射导致口径漂移。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.schemas.enums import TestResultStatus


def map_playwright_status(status: Optional[str]) -> TestResultStatus:
    """Playwright 用例状态 → TestResultStatus。

    expected/flaky 记为通过（flaky 表示重试后最终通过）；unexpected 记为失败；
    skipped 记为跳过；其余未知状态记为阻塞，便于趋势分析时发现异常数据。
    """
    if status in ("expected", "flaky"):
        return TestResultStatus.PASSED
    if status == "unexpected":
        return TestResultStatus.FAILED
    if status == "skipped":
        return TestResultStatus.SKIPPED
    return TestResultStatus.BLOCKED


def parse_playwright_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """从 Playwright JSON reporter 的 dict 提取 stats 与用例级 cases。

    Args:
        data: `json.loads` 后的 Playwright JSON reporter 输出（含 suites / stats）。

    Returns:
        {
            "stats": {total, passed, failed, skipped, flaky, duration_ms},
            "cases": [{title, file, status, duration_ms, retries, error}, ...],
        }
        其中 passed 含 flaky（重试后最终通过），total 为四类之和。
    """
    stats_raw = data.get("stats") or {}
    expected = int(stats_raw.get("expected", 0) or 0)
    unexpected = int(stats_raw.get("unexpected", 0) or 0)
    flaky = int(stats_raw.get("flaky", 0) or 0)
    skipped = int(stats_raw.get("skipped", 0) or 0)
    stats = {
        "total": expected + unexpected + flaky + skipped,
        "passed": expected + flaky,
        "failed": unexpected,
        "skipped": skipped,
        "flaky": flaky,
        "duration_ms": int(stats_raw.get("duration", 0) or 0),
    }

    cases: List[Dict[str, Any]] = []

    def _walk(suite: Dict[str, Any], prefix: str) -> None:
        title = suite.get("title") or ""
        full = f"{prefix} > {title}".strip(" >") if title else prefix
        for spec in suite.get("specs", []) or []:
            tests = spec.get("tests", []) or []
            results = tests[0].get("results", []) if tests else []
            status = tests[0].get("status") if tests else None
            duration = sum(int(r.get("duration", 0) or 0) for r in results)
            error_msg = None
            for r in results:
                err = r.get("error") or {}
                if err.get("message"):
                    error_msg = err["message"]
                    break
            cases.append({
                "title": f"{full} > {spec.get('title', '')}".strip(" >"),
                "file": spec.get("file"),
                "status": status,
                "duration_ms": duration,
                "retries": max(0, len(results) - 1),
                "error": error_msg,
            })
        for child in suite.get("suites", []) or []:
            _walk(child, full)

    for top in data.get("suites", []) or []:
        _walk(top, "")

    return {"stats": stats, "cases": cases}
