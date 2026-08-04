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
    save_test_cases_file,
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

    def test_duplicate_across_other_files_is_not_error(self, workspace_root: Path):
        """跨会话/跨文件的编号重复不再视为错误。

        工作区保留所有历史会话的用例文件，新会话与历史文件编号重复是
        预期行为（统一入库时按 case_number 去重兜底），全工作区扫描只会
        制造误报并诱发编号迁移螺旋。
        """
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

        assert not any(
            "与已保存的其他模块用例重复" in " ".join(v["messages"])
            for v in result["violations"]
        )

    def test_duplicate_within_batch_is_error(self, workspace_root: Path):
        """当前批次内部的编号重复仍然是硬错误。"""
        cases = [_valid_case("TC-PROJ-MOD-001"), _valid_case("TC-PROJ-MOD-001")]
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
        assert any(
            "在当前模块内重复" in " ".join(v["messages"])
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


class TestSaveTestCasesFile:
    """save_test_cases_file：覆盖写 + 解析校验 + JSONL 规范化。"""

    def test_write_new_file(self, workspace_root: Path):
        cases = [_valid_case("TC-PROJ-MOD-001"), _valid_case("TC-PROJ-MOD-002")]
        content = "\n".join(json.dumps(c, ensure_ascii=False) for c in cases)

        result = _run_tool(
            save_test_cases_file,
            {"file_path": "test_cases_module_01.jsonl", "content": content},
        )

        assert result["success"] is True
        assert result["cases_count"] == 2
        written = (workspace_root / "test_cases_module_01.jsonl").read_text(encoding="utf-8")
        assert len(written.strip().splitlines()) == 2
        # 每行都是合法 JSON（规范化效果）
        for line in written.strip().splitlines():
            json.loads(line)

    def test_overwrite_existing_file(self, workspace_root: Path):
        """历史遗留同名文件直接覆盖（通用 write_file 不可覆盖的替代）。"""
        old_path = workspace_root / "module_01.jsonl"
        _write_jsonl(old_path, [_valid_case("TC-PROJ-MOD-001")])

        new_cases = [_valid_case("TC-PROJ-MOD-101"), _valid_case("TC-PROJ-MOD-102")]
        content = "\n".join(json.dumps(c, ensure_ascii=False) for c in new_cases)
        result = _run_tool(
            save_test_cases_file,
            {"file_path": "module_01.jsonl", "content": content},
        )

        assert result["success"] is True
        assert "覆盖" in result["message"]
        written = old_path.read_text(encoding="utf-8")
        assert "TC-PROJ-MOD-101" in written
        assert "TC-PROJ-MOD-001" not in written

    def test_invalid_json_rejected(self, workspace_root: Path):
        result = _run_tool(
            save_test_cases_file,
            {"file_path": "bad.jsonl", "content": "{这不是合法JSON"},
        )

        assert result["success"] is False
        assert not (workspace_root / "bad.jsonl").exists()

    def test_quality_violations_reported_but_written(self, workspace_root: Path):
        """红线快检不阻塞写入，只返回 violations 供后续自检参考。"""
        case = _valid_case("TC-PROJ-MOD-001")
        case["test_data"] = {}  # 空测试数据 → 红线违规
        content = json.dumps(case, ensure_ascii=False)

        result = _run_tool(
            save_test_cases_file,
            {"file_path": "warn.jsonl", "content": content},
        )

        assert result["success"] is True
        assert len(result["violations"]) == 1
        assert (workspace_root / "warn.jsonl").is_file()

    def test_json_array_content_normalized_to_jsonl(self, workspace_root: Path):
        """兼容 JSON 数组输入，落盘统一为每行一个对象。"""
        cases = [_valid_case("TC-PROJ-MOD-001"), _valid_case("TC-PROJ-MOD-002")]
        content = json.dumps(cases, ensure_ascii=False)

        result = _run_tool(
            save_test_cases_file,
            {"file_path": "arr.jsonl", "content": content},
        )

        assert result["success"] is True
        written = (workspace_root / "arr.jsonl").read_text(encoding="utf-8")
        assert len(written.strip().splitlines()) == 2

    def test_path_escape_rejected(self, workspace_root: Path):
        result = _run_tool(
            save_test_cases_file,
            {"file_path": "../evil.jsonl", "content": json.dumps(_valid_case())},
        )

        assert result["success"] is False
        assert "越权" in (result["message"] + result.get("error", ""))
