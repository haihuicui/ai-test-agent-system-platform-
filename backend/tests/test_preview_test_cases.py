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

    async def test_file_not_found(self):
        result = await preview_test_cases.ainvoke({"source": "/not_exist_cases.jsonl"})

        assert result["success"] is False
        assert "文件不存在" in result["message"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
