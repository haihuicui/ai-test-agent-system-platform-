"""Tests for preview_test_cases 工具。

覆盖从 JSONL 文件、JSON 数组字符串、JSONL 内容字符串中抽样读取用例，
以及按 module/priority/case_type 过滤和返回字段截断。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.tools.testcase.testcase_tools import preview_test_cases
from app.config.settings import settings


@pytest.fixture
def workspace_tmp(tmp_path):
    """临时工作目录，用于写入测试用例 JSONL 文件。"""
    return tmp_path


async def _write_jsonl(workspace_tmp: Path, filename: str, cases: list[dict]) -> str:
    """在工作目录写入 JSONL 文件，返回虚拟路径。"""
    real_root = Path(settings.testcase_workspace_root).resolve()
    file_path = real_root / filename
    file_path.write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in cases),
        encoding="utf-8",
    )
    return f"/{filename}"


class TestPreviewTestCases:
    async def test_preview_from_jsonl_file(self, workspace_tmp):
        cases = [
            {
                "name": "正确凭证登录成功",
                "case_number": "TC-PROJ-LOGIN-001",
                "module": "登录模块",
                "priority": "high",
                "case_type": "functional",
                "test_data": {"username": "test001", "password": "Test@123"},
                "preconditions": ["账号已注册"],
                "test_case_steps": [
                    {"step": "输入用户名密码", "result": "页面跳转 /home"}
                ],
            },
            {
                "name": "空用户名登录失败",
                "case_number": "TC-PROJ-LOGIN-002",
                "module": "登录模块",
                "priority": "medium",
                "case_type": "functional",
                "test_data": {"username": "", "password": "Test@123"},
                "preconditions": [],
                "test_case_steps": [
                    {"step": "用户名为空点击登录", "result": "提示用户名不能为空"}
                ],
            },
        ]
        virtual_path = await _write_jsonl(workspace_tmp, "preview_cases.jsonl", cases)
        result = await preview_test_cases.ainvoke({"source": virtual_path, "limit": 2})

        assert result["success"] is True
        assert result["total"] == 2
        assert result["preview_count"] == 2
        assert len(result["cases"]) == 2
        assert result["cases"][0]["case_number"] == "TC-PROJ-LOGIN-001"

    async def test_filter_by_module(self, workspace_tmp):
        cases = [
            {"name": "登录用例", "case_number": "TC-001", "module": "登录模块", "priority": "high"},
            {"name": "订单用例", "case_number": "TC-002", "module": "订单模块", "priority": "high"},
        ]
        virtual_path = await _write_jsonl(workspace_tmp, "filter_module.jsonl", cases)
        result = await preview_test_cases.ainvoke(
            {"source": virtual_path, "module": "订单模块"}
        )

        assert result["success"] is True
        assert result["total"] == 1
        assert result["cases"][0]["case_number"] == "TC-002"

    async def test_filter_by_priority(self, workspace_tmp):
        cases = [
            {"name": "P0 用例", "case_number": "TC-001", "module": "登录模块", "priority": "critical"},
            {"name": "P1 用例", "case_number": "TC-002", "module": "登录模块", "priority": "high"},
        ]
        virtual_path = await _write_jsonl(workspace_tmp, "filter_priority.jsonl", cases)
        result = await preview_test_cases.ainvoke(
            {"source": virtual_path, "priority": "critical"}
        )

        assert result["success"] is True
        assert result["total"] == 1
        assert result["cases"][0]["case_number"] == "TC-001"

    async def test_json_array_string_source(self):
        cases = [
            {
                "name": "JSON 数组用例",
                "case_number": "TC-JSON-001",
                "module": "测试模块",
                "priority": "medium",
            }
        ]
        result = await preview_test_cases.ainvoke(
            {"source": json.dumps(cases, ensure_ascii=False)}
        )

        assert result["success"] is True
        assert result["total"] == 1
        assert result["cases"][0]["case_number"] == "TC-JSON-001"

    async def test_jsonl_string_source(self):
        cases = [
            {"name": "第一行", "case_number": "TC-001", "module": "测试模块", "priority": "medium"},
            {"name": "第二行", "case_number": "TC-002", "module": "测试模块", "priority": "medium"},
        ]
        content = "\n".join(json.dumps(c, ensure_ascii=False) for c in cases)
        result = await preview_test_cases.ainvoke({"source": content, "limit": 1})

        assert result["success"] is True
        assert result["total"] == 2
        assert result["preview_count"] == 1

    async def test_steps_truncation(self, workspace_tmp):
        cases = [
            {
                "name": "多步骤用例",
                "case_number": "TC-001",
                "module": "测试模块",
                "priority": "medium",
                "test_case_steps": [
                    {"step": f"步骤{i}", "result": f"结果{i}"} for i in range(1, 10)
                ],
            }
        ]
        virtual_path = await _write_jsonl(workspace_tmp, "truncate_steps.jsonl", cases)
        result = await preview_test_cases.ainvoke({"source": virtual_path})

        assert result["success"] is True
        preview_steps = result["cases"][0]["test_case_steps"]
        # 默认 _PREVIEW_MAX_STEPS = 5，加上提示还剩 4 步的占位，共 6 项
        assert len(preview_steps) == 6
        assert "后续还有" in str(preview_steps[-1])

    async def test_expected_result_aggregated_from_steps(self, workspace_tmp):
        """未提供顶层 expected_result 时，应从 step.result 聚合生成。"""
        cases = [
            {
                "name": "聚合预期结果",
                "case_number": "TC-PROJ-LOGIN-003",
                "module": "登录模块",
                "priority": "high",
                "test_case_steps": [
                    {"step": "输入用户名密码", "result": "页面跳转 /home"},
                    {"step": "点击退出", "result": "返回登录页"},
                ],
            }
        ]
        virtual_path = await _write_jsonl(workspace_tmp, "expected_result_aggregate.jsonl", cases)
        result = await preview_test_cases.ainvoke({"source": virtual_path})

        assert result["success"] is True
        assert result["cases"][0]["expected_result"] == "1. 页面跳转 /home\n2. 返回登录页"

    async def test_expected_result_from_top_level_field(self, workspace_tmp):
        """存在顶层 expected_result 字段时优先使用。"""
        cases = [
            {
                "name": "顶层预期结果",
                "case_number": "TC-PROJ-LOGIN-004",
                "module": "登录模块",
                "priority": "high",
                "expected_result": "账号锁定 30 分钟",
                "test_case_steps": [
                    {"step": "连续输错密码 5 次", "result": "提示账号已锁定"}
                ],
            }
        ]
        virtual_path = await _write_jsonl(workspace_tmp, "expected_result_top.jsonl", cases)
        result = await preview_test_cases.ainvoke({"source": virtual_path})

        assert result["success"] is True
        assert result["cases"][0]["expected_result"] == "账号锁定 30 分钟"

    async def test_expected_result_truncation(self, workspace_tmp):
        """预期结果超长时应截断。"""
        cases = [
            {
                "name": "超长预期结果",
                "case_number": "TC-PROJ-LOGIN-005",
                "module": "登录模块",
                "priority": "high",
                "expected_result": "A" * 1000,
                "test_case_steps": [{"step": "步骤1", "result": "结果1"}],
            }
        ]
        virtual_path = await _write_jsonl(workspace_tmp, "expected_result_long.jsonl", cases)
        result = await preview_test_cases.ainvoke({"source": virtual_path})

        assert result["success"] is True
        preview_result = result["cases"][0]["expected_result"]
        assert len(preview_result) < 1000
        assert preview_result.endswith("...")

    async def test_total_reflects_real_count_beyond_read_cutoff(self, workspace_tmp):
        """total 必须是数据源真实总数，与展示截断（limit）无关——
        E2E 实证 bug：无过滤时读取阶段截断 limit*2=6，13 条文件 total 显示 6，
        Agent 拿 total 核对保存条数时被误导。"""
        cases = [
            {
                "name": f"用例{i:02d}",
                "case_number": f"TC-{i:03d}",
                "module": "日志模块",
                "priority": "high",
            }
            for i in range(1, 14)  # 13 条，超过默认 limit*2=6
        ]
        virtual_path = await _write_jsonl(workspace_tmp, "total_real_count.jsonl", cases)
        result = await preview_test_cases.ainvoke({"source": virtual_path})

        assert result["success"] is True
        assert result["total"] == 13
        assert result["preview_count"] == 3  # 默认 limit=3，只展示 3 条
        assert len(result["cases"]) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
