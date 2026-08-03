"""Tests for compute_coverage_report 覆盖对照工具。

覆盖：纯函数 compute_coverage 的 explicit/fuzzy/未覆盖三级匹配，
以及工具端到端（tmp workspace 下的矩阵 + 用例文件）。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.agents.tools.testcase import coverage_tools, excel_tools, feature_matrix_tools
from app.agents.tools.testcase.coverage_tools import (
    _bigrams,
    _looks_like_case,
    compute_coverage,
    compute_coverage_report,
)


def _feature(fp_id="FP-001", module="用户认证", feature="手机号登录", priority="P0"):
    return {
        "id": fp_id,
        "module": module,
        "feature": feature,
        "test_points": ["验证码有效期5min"],
        "priority": priority,
        "risk_level": "高",
        "test_type": ["功能"],
    }


def _case(number="TC-PROJ-AUTH-001", module="用户认证", name="手机号登录-正确凭证登录", remarks=""):
    return {
        "name": name,
        "case_number": number,
        "module": module,
        "priority": "critical",
        "remarks": remarks,
        "test_data": {"phone": "13800000001"},
        "test_case_steps": [
            {"step": "输入手机号和验证码", "result": "页面跳转至 /home"},
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# compute_coverage 纯函数
# ═════════════════════════════════════════════════════════════════════════════

class TestComputeCoverage:
    def test_explicit_fp_reference_wins(self):
        case = _case(remarks="关联需求 FP-001")
        rows = compute_coverage([_feature()], [case])
        assert rows[0]["covered"] is True
        assert rows[0]["match_type"] == "explicit"
        assert rows[0]["case_numbers"] == ["TC-PROJ-AUTH-001"]

    def test_fuzzy_match_same_module(self):
        rows = compute_coverage([_feature()], [_case()])
        assert rows[0]["covered"] is True
        assert rows[0]["match_type"] == "fuzzy"

    def test_no_match_when_feature_absent(self):
        case = _case(name="订单列表分页查询", module="订单模块")
        rows = compute_coverage([_feature()], [case])
        assert rows[0]["covered"] is False
        assert rows[0]["match_type"] is None

    def test_fuzzy_respects_module_boundary(self):
        """不同模块的用例即使文本相似也不计入 fuzzy 覆盖。"""
        case = _case(module="订单模块")  # 名称含"手机号登录"但模块不同
        rows = compute_coverage([_feature()], [case])
        assert rows[0]["covered"] is False

    def test_uncovered_p0_identified(self):
        features = [_feature("FP-001"), _feature("FP-002", feature="图形验证码校验")]
        rows = compute_coverage(features, [_case()])
        by_id = {r["id"]: r for r in rows}
        assert by_id["FP-001"]["covered"] is True
        assert by_id["FP-002"]["covered"] is False


class TestHelpers:
    def test_bigrams_chinese(self):
        assert _bigrams("手机号") == {"手机", "机号"}
        assert _bigrams("") == set()

    def test_looks_like_case(self):
        assert _looks_like_case(_case()) is True
        assert _looks_like_case({"case_number": "TC-1"}) is True
        assert _looks_like_case(_feature()) is False  # 功能矩阵记录不算用例
        assert _looks_like_case("not-a-dict") is False


# ═════════════════════════════════════════════════════════════════════════════
# 工具端到端（tmp workspace）
# ═════════════════════════════════════════════════════════════════════════════

def _call(tool, **kwargs):
    return asyncio.run(tool.ainvoke(kwargs))


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    """把 coverage 链路涉及的 workspace 根统一指向临时目录。

    _resolve_input_path 在 excel_tools 中持有独立的 _WORKSPACE_ROOT，
    三个模块必须一起 patch，否则显式 case_files 会被判定为越权路径。
    """
    monkeypatch.setattr(coverage_tools, "_WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(feature_matrix_tools, "_WORKSPACE_ROOT", tmp_path)
    monkeypatch.setattr(excel_tools, "_WORKSPACE_ROOT", tmp_path)
    return tmp_path


class TestComputeCoverageReportTool:
    def _write_jsonl(self, path: Path, records: list[dict]):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
            encoding="utf-8",
        )

    def test_end_to_end(self, tmp_workspace):
        proj_dir = tmp_workspace / "PROJ-1"
        self._write_jsonl(proj_dir / "feature_matrix.jsonl", [_feature()])
        self._write_jsonl(proj_dir / "test_cases_module_01.jsonl", [_case()])

        result = _call(compute_coverage_report, project_identifier="PROJ-1")

        assert result["success"] is True
        assert result["total_features"] == 1
        assert result["covered"] == 1
        assert result["coverage_rate"] == 100.0
        assert result["uncovered_p0"] == []
        assert "FP-001" in result["markdown_table"]
        # 矩阵文件本身不应被当作用例文件扫描
        assert all("feature_matrix" not in f for f in result["case_files_used"])

    def test_uncovered_p0_listed(self, tmp_workspace):
        proj_dir = tmp_workspace / "PROJ-1"
        self._write_jsonl(proj_dir / "feature_matrix.jsonl", [_feature()])
        self._write_jsonl(
            proj_dir / "cases.jsonl",
            [_case(name="订单导出", module="订单模块")],
        )

        result = _call(compute_coverage_report, project_identifier="PROJ-1")

        assert result["success"] is True
        assert result["covered"] == 0
        assert result["uncovered_p0"] == ["FP-001"]
        assert "❌ 未覆盖" in result["markdown_table"]

    def test_matrix_missing_returns_guidance(self, tmp_workspace):
        result = _call(compute_coverage_report, project_identifier="NOPE")
        assert result["success"] is False
        assert "无结构化矩阵" in result["message"]

    def test_explicit_case_files_param(self, tmp_workspace):
        proj_dir = tmp_workspace / "PROJ-1"
        self._write_jsonl(proj_dir / "feature_matrix.jsonl", [_feature()])
        case_file = proj_dir / "a.jsonl"
        self._write_jsonl(case_file, [_case()])
        # 另一个不含用例的文件不应影响结果
        self._write_jsonl(proj_dir / "notes.jsonl", [{"memo": "x"}])

        result = _call(
            compute_coverage_report,
            project_identifier="PROJ-1",
            case_files=[str(case_file)],
        )
        assert result["success"] is True
        assert result["covered"] == 1
