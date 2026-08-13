"""
API 测试执行辅助工具

仅保留测试结果解析等纯文本工具。

历史说明：``run_tests`` / ``run_test_suite`` 已移除——它们以无 cwd、无并发锁、
全量继承进程环境变量的方式 spawn 测试子进程（密钥泄露面），且功能完全被
``execute_api_script``（白名单 env + trace 捕获 + 结果落库 + 执行锁）覆盖。
"""

import json
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVV4aVR3PT06MjYzZDUyNWU=

from langchain_core.tools import tool


@tool
async def parse_test_results(
    result_output: str
) -> str:
    """
    解析测试输出并提取关键信息

    Args:
        result_output: 测试运行的原始输出

    Returns:
        JSON 格式的解析结果
    """
    try:
        # 尝试解析 JSON 输出
        if result_output.strip().startswith("{"):
            data = json.loads(result_output)
            return json.dumps({
                "success": True,
                "parsed": True,
                "data": data
            }, ensure_ascii=False, indent=2)

        # 解析文本输出
        lines = result_output.split("\n")
        passed = []
        failed = []
        skipped = []

        for line in lines:
            if "✓" in line or "PASS" in line or "passed" in line:
                passed.append(line.strip())
            elif "✗" in line or "FAIL" in line or "failed" in line:
                failed.append(line.strip())
            elif "○" in line or "skipped" in line:
                skipped.append(line.strip())

        return json.dumps({
            "success": True,
            "parsed": True,
            "summary": {
                "passed": len(passed),
                "failed": len(failed),
                "skipped": len(skipped)
            },
            "details": {
                "passed": passed[:10],  # 最多返回10个
                "failed": failed[:10],
                "skipped": skipped[:10]
            }
        }, ensure_ascii=False, indent=2)
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVV4aVR3PT06MjYzZDUyNWU=

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"解析测试结果失败: {str(e)}"
        }, ensure_ascii=False, indent=2)
