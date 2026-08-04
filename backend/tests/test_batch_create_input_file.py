"""batch_create_test_cases_tool 的 input_file 文件导入模式测试。

覆盖：多文件合并、按 case_number 去重、质量红线校验拦截、
文件缺失时的自纠错提示。HTTP 创建层通过 monkeypatch 替换。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.tools.testcase import testcase_tools
from app.agents.tools.testcase.excel_tools import _WORKSPACE_ROOT
from app.agents.tools.testcase.testcase_tools import batch_create_test_cases_tool


def _valid_case(num: int, module: str = "登录") -> dict:
    return {
        "name": f"登录成功场景{num}",
        "case_number": f"TC-PROJ-LOGIN-{num:03d}",
        "module": module,
        "case_type": "functional",
        "priority": "high",
        "preconditions": "账号已注册",
        "test_data": {"username": f"user{num}", "password": "Test@123"},
        "test_case_steps": [{"step": "输入账号密码点击登录", "result": "跳转首页"}],
    }


@pytest.fixture
def workspace_file():
    """在真实 workspace 写临时 JSONL 文件（返回虚拟路径），测试后清理。"""
    written: list[Path] = []

    def _write(name: str, cases: list[dict]) -> str:
        path = _WORKSPACE_ROOT / name
        path.write_text(
            "\n".join(json.dumps(c, ensure_ascii=False) for c in cases),
            encoding="utf-8",
        )
        written.append(path)
        return f"/{name}"

    yield _write

    for path in written:
        path.unlink(missing_ok=True)


class TestBatchCreateInputFile:
    async def test_import_merges_and_dedups(self, workspace_file, monkeypatch):
        """多文件合并导入，按 case_number 去重（后出现覆盖先出现）。"""
        f1 = workspace_file("_test_import_a.jsonl", [_valid_case(1), _valid_case(2)])
        revised = _valid_case(2)
        revised["name"] = "登录成功场景2-修订版"
        f2 = workspace_file("_test_import_b.jsonl", [revised, _valid_case(3)])

        captured: dict = {}

        async def fake_impl(project_identifier, test_cases, folder_id=None):
            captured["cases"] = test_cases
            captured["folder_id"] = folder_id
            return {
                "success": True,
                "data": {"total": len(test_cases), "succeeded": len(test_cases), "failed": 0},
            }

        monkeypatch.setattr(testcase_tools, "_batch_create_test_cases_impl", fake_impl)

        result = await batch_create_test_cases_tool.ainvoke(
            {
                "project_identifier": "PROJ-001",
                "folder_id": "folder-1",
                "input_file": [f1, f2],
            }
        )

        assert result["success"] is True
        cases = captured["cases"]
        assert len(cases) == 3  # 4 条 → 去重后 3 条
        assert captured["folder_id"] == "folder-1"
        by_number = {c["case_number"]: c for c in cases}
        assert by_number["TC-PROJ-LOGIN-002"]["name"] == "登录成功场景2-修订版"

    async def test_import_quality_gate_blocks_invalid(self, workspace_file, monkeypatch):
        """质量红线违规的用例被拦截，不执行任何创建。"""
        bad = _valid_case(1)
        bad["test_data"] = {}  # 空测试数据 → 违反质量红线
        f1 = workspace_file("_test_import_bad.jsonl", [bad, _valid_case(2)])

        called = False

        async def fake_impl(project_identifier, test_cases, folder_id=None):
            nonlocal called
            called = True
            return {"success": True}

        monkeypatch.setattr(testcase_tools, "_batch_create_test_cases_impl", fake_impl)

        result = await batch_create_test_cases_tool.ainvoke(
            {
                "project_identifier": "PROJ-001",
                "input_file": f1,
            }
        )

        assert result["success"] is False
        assert called is False
        assert result["data"]["violation_count"] == 1
        assert result["data"]["violations"][0]["case_number"] == "TC-PROJ-LOGIN-001"
        # 违规清单应包含具体的红线描述，便于模型定位修复
        assert any("test_data" in m for m in result["data"]["violations"][0]["messages"])

    async def test_missing_file_returns_self_correcting_error(self):
        """文件不存在时返回自纠错提示（含工作目录可用文件清单）。"""
        result = await batch_create_test_cases_tool.ainvoke(
            {
                "project_identifier": "PROJ-001",
                "input_file": "/_test_not_exist_xyz_9z8y7x.jsonl",
            }
        )
        assert result["success"] is False
        assert "不存在" in (result["message"] + result.get("error", ""))

    async def test_inline_and_input_file_both_absent(self):
        """两种用例来源都未提供时返回明确错误。"""
        result = await batch_create_test_cases_tool.ainvoke(
            {"project_identifier": "PROJ-001"}
        )
        assert result["success"] is False
        assert "input_file" in result["message"]
