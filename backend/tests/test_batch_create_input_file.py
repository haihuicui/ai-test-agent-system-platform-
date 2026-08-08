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

        async def fake_impl(project_identifier, test_cases, folder_id=None, upsert=False):
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

        async def fake_impl(project_identifier, test_cases, folder_id=None, upsert=False):
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


class TestBatchCreateUpsert:
    """upsert=true：同编号整体替换（PATCH-first，404 转新建，保留 status）。"""

    async def test_existing_case_replaced_via_patch(self, monkeypatch):
        """同编号已存在 → PATCH 替换，不调用创建，且不传 status。"""
        update_kwargs: dict = {}

        async def fake_update(**kwargs):
            update_kwargs.update(kwargs)
            return {"success": True, "data": {"identifier": "TC-PROJ-LOGIN-001"}}

        create_called = False

        async def fake_create(**kwargs):
            nonlocal create_called
            create_called = True
            return {"success": True, "data": {}}

        monkeypatch.setattr(testcase_tools, "_update_test_case_impl", fake_update)
        monkeypatch.setattr(testcase_tools, "_create_test_case_impl", fake_create)

        result = await batch_create_test_cases_tool.ainvoke(
            {
                "project_identifier": "PROJ-001",
                "test_cases": [_valid_case(1)],
                "upsert": True,
            }
        )

        assert result["success"] is True
        assert create_called is False
        # PATCH 按 case_number 定位
        assert update_kwargs["test_case_identifier"] == "TC-PROJ-LOGIN-001"
        # 不传 status，保留原用例工作流状态
        assert "status" not in update_kwargs or update_kwargs.get("status") is None
        assert result["data"]["updated"] == 1
        assert result["data"]["created"] == 0
        assert "替换 1 条" in result["message"]

    async def test_missing_case_falls_back_to_create(self, monkeypatch):
        """PATCH 404（系统库不存在）→ 转为新建。"""

        async def fake_update(**kwargs):
            raise Exception("HTTP 404: 测试用例不存在")

        create_kwargs: dict = {}

        async def fake_create(**kwargs):
            create_kwargs.update(kwargs)
            return {"success": True, "data": {"identifier": "TC-PROJ-LOGIN-001"}}

        monkeypatch.setattr(testcase_tools, "_update_test_case_impl", fake_update)
        monkeypatch.setattr(testcase_tools, "_create_test_case_impl", fake_create)

        result = await batch_create_test_cases_tool.ainvoke(
            {
                "project_identifier": "PROJ-001",
                "test_cases": [_valid_case(1)],
                "upsert": True,
            }
        )

        assert result["success"] is True
        assert result["data"]["created"] == 1
        assert result["data"]["updated"] == 0
        # 新建时保留 case_number
        assert create_kwargs["case_number"] == "TC-PROJ-LOGIN-001"

    async def test_non_404_error_does_not_create(self, monkeypatch):
        """PATCH 出现非 404 错误（如 500）→ 记为失败，禁止降级为新建。"""

        async def fake_update(**kwargs):
            raise Exception("HTTP 500: 服务内部错误")

        create_called = False

        async def fake_create(**kwargs):
            nonlocal create_called
            create_called = True
            return {"success": True, "data": {}}

        monkeypatch.setattr(testcase_tools, "_update_test_case_impl", fake_update)
        monkeypatch.setattr(testcase_tools, "_create_test_case_impl", fake_create)

        result = await batch_create_test_cases_tool.ainvoke(
            {
                "project_identifier": "PROJ-001",
                "test_cases": [_valid_case(1)],
                "upsert": True,
            }
        )

        assert create_called is False
        assert result["data"]["failed"] == 1

    async def test_upsert_false_keeps_pure_create(self, monkeypatch):
        """upsert=false（默认）→ 纯新建，不尝试 PATCH。"""
        update_called = False

        async def fake_update(**kwargs):
            nonlocal update_called
            update_called = True
            return {"success": True}

        async def fake_create(**kwargs):
            return {"success": True, "data": {"identifier": "TC-PROJ-LOGIN-001"}}

        monkeypatch.setattr(testcase_tools, "_update_test_case_impl", fake_update)
        monkeypatch.setattr(testcase_tools, "_create_test_case_impl", fake_create)

        result = await batch_create_test_cases_tool.ainvoke(
            {
                "project_identifier": "PROJ-001",
                "test_cases": [_valid_case(1)],
            }
        )

        assert update_called is False
        assert result["success"] is True


# ═════════════════════════════════════════════════════════════════════════════
# case_type 枚举归一化
# ═════════════════════════════════════════════════════════════════════════════

from app.utils.testcase_validation import normalize_case_type  # noqa: E402


class TestNormalizeCaseType:
    """normalize_case_type 单元测试：合法值原样、同义词映射、未知值回退。"""

    def test_valid_values_unchanged(self):
        for v in ["functional", "security", "performance", "compatibility",
                  "regression", "smoke_sanity", "acceptance", "accessibility",
                  "destructive", "usability", "other"]:
            assert normalize_case_type(v) == (v, False)

    def test_case_and_whitespace_insensitive(self):
        assert normalize_case_type(" Functional ") == ("functional", False)
        assert normalize_case_type("SECURITY") == ("security", False)

    def test_interface_maps_to_functional(self):
        """生产事故值：interface 无独立枚举，映射 functional"""
        assert normalize_case_type("interface") == ("functional", True)
        assert normalize_case_type("接口") == ("functional", True)
        assert normalize_case_type("接口测试") == ("functional", True)
        assert normalize_case_type("api") == ("functional", True)

    def test_chinese_synonyms(self):
        assert normalize_case_type("安全") == ("security", True)
        assert normalize_case_type("性能测试") == ("performance", True)
        assert normalize_case_type("兼容性") == ("compatibility", True)
        assert normalize_case_type("回归") == ("regression", True)

    def test_unknown_falls_back_to_functional(self):
        assert normalize_case_type("exploratory") == ("functional", True)

    def test_non_string_returns_functional_unchanged(self):
        assert normalize_case_type(None) == ("functional", False)
        assert normalize_case_type("") == ("functional", False)


class TestBatchCaseTypeNormalization:
    """批量入库路径：非法 case_type 自动映射为合法枚举，并在结果中可见。"""

    @pytest.mark.asyncio
    async def test_interface_case_type_normalized_on_create(self, monkeypatch):
        create_kwargs: dict = {}

        async def fake_create(**kwargs):
            create_kwargs.update(kwargs)
            return {"success": True, "data": {"identifier": "TC-PROJ-LOGIN-001"}}

        monkeypatch.setattr(testcase_tools, "_create_test_case_impl", fake_create)

        case = {**_valid_case(1), "case_type": "interface"}
        result = await batch_create_test_cases_tool.ainvoke(
            {"project_identifier": "PROJ-001", "test_cases": [case]}
        )

        assert result["success"] is True
        # 实际发给后端的必须是合法枚举
        assert create_kwargs["case_type"] == "functional"
        # 修正记录对模型可见
        notes = result["data"]["case_type_normalized"]
        assert len(notes) == 1
        assert "interface" in notes[0] and "functional" in notes[0]
        assert "自动映射" in result["message"]

    @pytest.mark.asyncio
    async def test_valid_case_type_no_notes(self, monkeypatch):
        async def fake_create(**kwargs):
            return {"success": True, "data": {"identifier": "TC-PROJ-LOGIN-001"}}

        monkeypatch.setattr(testcase_tools, "_create_test_case_impl", fake_create)

        result = await batch_create_test_cases_tool.ainvoke(
            {"project_identifier": "PROJ-001", "test_cases": [_valid_case(1)]}
        )

        assert result["success"] is True
        assert result["data"]["case_type_normalized"] == []
        assert "自动映射" not in result["message"]

    @pytest.mark.asyncio
    async def test_upsert_path_normalizes_case_type(self, monkeypatch):
        update_kwargs: dict = {}

        async def fake_update(**kwargs):
            update_kwargs.update(kwargs)
            return {"success": True, "data": {"identifier": "TC-PROJ-LOGIN-001"}}

        monkeypatch.setattr(testcase_tools, "_update_test_case_impl", fake_update)

        case = {**_valid_case(1), "case_type": "接口"}
        result = await batch_create_test_cases_tool.ainvoke(
            {"project_identifier": "PROJ-001", "test_cases": [case], "upsert": True}
        )

        assert result["success"] is True
        assert update_kwargs["case_type"] == "functional"
        assert len(result["data"]["case_type_normalized"]) == 1
