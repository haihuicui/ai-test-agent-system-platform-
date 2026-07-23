"""Tests for module-level self-check and offline manifest tools."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from app.agents.tools.testcase import module_check_tools, excel_tools
from app.agents.tools.testcase.module_check_tools import (
    module_self_check_tool,
    save_test_case_manifest_tool,
)


@pytest.fixture
def workspace_root(monkeypatch, tmp_path: Path):
    """把模块自检与 excel 工具的工作目录指向临时目录，避免污染真实 workspace。"""
    resolved = tmp_path.resolve()
    monkeypatch.setattr(excel_tools, "_WORKSPACE_ROOT", resolved)
    monkeypatch.setattr(module_check_tools, "_WORKSPACE_ROOT", resolved)
    return resolved


def _run_tool(tool, args: dict[str, Any]):
    """通过 ainvoke 调用 LangChain 工具对象。"""
    return asyncio.run(tool.ainvoke(args))


def _write_jsonl(path: Path, cases: list[dict[str, Any]]) -> None:
    """将用例列表写入 JSONL 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")


def _valid_case(number: str = "TC-PROJ-MOD-001") -> dict[str, Any]:
    return {
        "name": "示例用例",
        "case_number": number,
        "module": "示例模块",
        "priority": "critical",
        "test_data": {"field": "value"},
        "test_case_steps": [
            {"step": "执行操作", "result": "页面显示结果字段=value"}
        ],
    }


class TestModuleSelfCheckTool:
    def test_valid_module_passes(self, workspace_root: Path):
        cases = [
            _valid_case("TC-PROJ-MOD-001"),
            {**_valid_case("TC-PROJ-MOD-002"), "priority": "high"},
        ]
        file_path = workspace_root / "test_cases_module.jsonl"
        _write_jsonl(file_path, cases)

        result = _run_tool(
            module_self_check_tool,
            {
                "input_files": [str(file_path.name)],
                "expected_module": "示例模块",
                "min_p0_count": 1,
            },
        )

        assert result["passed"] is True
        assert result["total"] == 2
        assert result["p0_count"] == 1
        assert not [v for v in result["violations"] if v["level"] == "error"]

    def test_missing_file_returns_error(self, workspace_root: Path):
        result = _run_tool(
            module_self_check_tool,
            {
                "input_files": ["not_exist.jsonl"],
                "expected_module": "示例模块",
            },
        )
        assert result["passed"] is False
        assert "不存在" in result["summary"]

    def test_duplicate_case_number_in_same_file(self, workspace_root: Path):
        cases = [
            _valid_case("TC-PROJ-MOD-001"),
            _valid_case("TC-PROJ-MOD-001"),
        ]
        file_path = workspace_root / "dup.jsonl"
        _write_jsonl(file_path, cases)

        result = _run_tool(
            module_self_check_tool,
            {
                "input_files": [str(file_path.name)],
                "expected_module": "示例模块",
            },
        )

        assert result["passed"] is False
        assert any("重复" in " ".join(v["messages"]) for v in result["violations"])

    def test_module_mismatch_fails(self, workspace_root: Path):
        cases = [_valid_case("TC-PROJ-MOD-001")]
        file_path = workspace_root / "mismatch.jsonl"
        _write_jsonl(file_path, cases)

        result = _run_tool(
            module_self_check_tool,
            {
                "input_files": [str(file_path.name)],
                "expected_module": "错误模块",
            },
        )

        assert result["passed"] is False
        assert any("模块归属不一致" in " ".join(v["messages"]) for v in result["violations"])

    def test_core_quality_gate_is_reused(self, workspace_root: Path):
        case = _valid_case("TC-PROJ-MOD-001")
        case["test_data"] = {"field": "有效数据"}  # 占位词
        case["test_case_steps"] = [{"step": "s1", "result": "成功"}]
        file_path = workspace_root / "bad.jsonl"
        _write_jsonl(file_path, [case])

        result = _run_tool(
            module_self_check_tool,
            {
                "input_files": [str(file_path.name)],
                "expected_module": "示例模块",
            },
        )

        assert result["passed"] is False
        messages = " ".join(
            m for v in result["violations"] for m in v["messages"]
        )
        assert "占位" in messages
        assert "不可客观判定" in messages

    def test_duplicate_across_other_files(self, workspace_root: Path):
        existing = [_valid_case("TC-PROJ-MOD-001")]
        existing_path = workspace_root / "existing.jsonl"
        _write_jsonl(existing_path, existing)

        new_cases = [_valid_case("TC-PROJ-MOD-001")]
        new_path = workspace_root / "new.jsonl"
        _write_jsonl(new_path, new_cases)

        result = _run_tool(
            module_self_check_tool,
            {
                "input_files": [str(new_path.name)],
                "expected_module": "示例模块",
            },
        )

        assert result["passed"] is False
        assert any(
            "与已保存的其他模块用例重复" in " ".join(v["messages"])
            for v in result["violations"]
        )

    def test_p0_warning(self, workspace_root: Path):
        cases = [
            {**_valid_case("TC-PROJ-MOD-001"), "priority": "high"},
        ]
        file_path = workspace_root / "low_p0.jsonl"
        _write_jsonl(file_path, cases)

        result = _run_tool(
            module_self_check_tool,
            {
                "input_files": [str(file_path.name)],
                "expected_module": "示例模块",
                "min_p0_count": 3,
            },
        )

        # P0 不足是 warning，不阻塞 passed
        assert result["passed"] is True
        assert any("P0 用例数量偏少" in " ".join(v["messages"]) for v in result["violations"])

    def test_atomicity_warning(self, workspace_root: Path):
        case = _valid_case("TC-PROJ-MOD-001")
        case["test_case_steps"] = [
            {
                "step": "选择数据",
                "result": "按钮 A 可点击且按钮 B 灰显",
            }
        ]
        file_path = workspace_root / "atomic.jsonl"
        _write_jsonl(file_path, [case])

        result = _run_tool(
            module_self_check_tool,
            {
                "input_files": [str(file_path.name)],
                "expected_module": "示例模块",
            },
        )

        assert result["passed"] is True
        assert any("包含连接词" in " ".join(v["messages"]) for v in result["violations"])


class TestSaveTestCaseManifestTool:
    def test_creates_new_manifest(self, workspace_root: Path):
        result = _run_tool(
            save_test_case_manifest_tool,
            {
                "project_identifier": "PROJ-001",
                "entries": [
                    {
                        "module": "模块A",
                        "file": "a.jsonl",
                        "count": 5,
                        "persisted": True,
                        "pending_import": False,
                    }
                ],
            },
        )

        assert result["success"] is True
        manifest_path = workspace_root / "test_case_manifest.json"
        assert manifest_path.is_file()
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert data["project_identifier"] == "PROJ-001"
        assert len(data["modules"]) == 1
        assert data["modules"][0]["module"] == "模块A"

    def test_updates_existing_manifest_by_module_file(self, workspace_root: Path):
        manifest_path = workspace_root / "test_case_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "project_identifier": "PROJ-001",
                    "modules": [
                        {
                            "module": "模块A",
                            "file": "a.jsonl",
                            "count": 5,
                            "persisted": True,
                            "pending_import": False,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = _run_tool(
            save_test_case_manifest_tool,
            {
                "project_identifier": "PROJ-001",
                "entries": [
                    {
                        "module": "模块A",
                        "file": "a.jsonl",
                        "count": 6,
                        "persisted": False,
                        "pending_import": True,
                    }
                ],
            },
        )

        assert result["success"] is True
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert len(data["modules"]) == 1
        assert data["modules"][0]["count"] == 6
        assert data["modules"][0]["pending_import"] is True

    def test_custom_manifest_path(self, workspace_root: Path):
        result = _run_tool(
            save_test_case_manifest_tool,
            {
                "project_identifier": "PROJ-002",
                "entries": [{"module": "M", "file": "m.jsonl", "count": 1}],
                "manifest_path": "sub/manifest.json",
            },
        )

        assert result["success"] is True
        assert (workspace_root / "sub" / "manifest.json").is_file()
