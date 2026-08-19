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

    def test_auto_scan_scoped_to_project_dir(self, tmp_workspace):
        """自动扫描必须限定在项目目录内，不得计入其他项目/根目录的历史用例"""
        proj_dir = tmp_workspace / "PROJ-1"
        self._write_jsonl(proj_dir / "feature_matrix.jsonl", [_feature()])
        self._write_jsonl(proj_dir / "test_cases_module_01.jsonl", [_case()])
        # 历史遗留：根目录和另一项目目录下的用例文件
        self._write_jsonl(tmp_workspace / "test_cases_login.jsonl", [_case()])
        self._write_jsonl(tmp_workspace / "PROJ-OLD" / "test_cases_old.jsonl", [_case()])

        result = _call(compute_coverage_report, project_identifier="PROJ-1")

        assert result["success"] is True
        assert result["total_cases"] == 1
        assert all("PROJ-1" in f and "PROJ-OLD" not in f for f in result["case_files_used"])
        # 自动扫描模式必须给出遗留风险提示与文件清单
        assert any("自动扫描模式" in w and "历史会话" in w for w in result["warnings"])

    def test_explicit_case_files_no_auto_scan_warning(self, tmp_workspace):
        """显式传 case_files 时不应出现自动扫描提示"""
        proj_dir = tmp_workspace / "PROJ-1"
        self._write_jsonl(proj_dir / "feature_matrix.jsonl", [_feature()])
        case_file = proj_dir / "test_cases_module_01.jsonl"
        self._write_jsonl(case_file, [_case()])

        result = _call(
            compute_coverage_report,
            project_identifier="PROJ-1",
            case_files=[str(case_file)],
        )

        assert result["success"] is True
        assert not any("自动扫描模式" in w for w in result["warnings"])

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

    def test_auto_scan_req_alignment_filters_cross_req_fp_refs(self, tmp_workspace):
        """自动扫描：跨 REQ 用例的 FP 编号撞车引用不计入覆盖（防虚高）。

        FP 编号是需求级的（各需求都从 FP-001 起编），自动扫描池混入其他需求
        的遗留用例时，其"显式引用"是假阳性——REQ 主题错位的一律剔除。
        """
        proj_dir = tmp_workspace / "PROJ-1"
        feature = _feature()
        feature["source"] = "REQ-LOGIN-001 登录需求"
        self._write_jsonl(proj_dir / "feature_matrix.jsonl", [feature])
        # 本需求用例（主题对齐，但内容未覆盖 FP-001）
        aligned_case = _case(name="权限不足提示", remarks="关联 REQ-LOGIN-002")
        aligned_case["test_case_steps"] = [
            {"step": "以只读账号访问后台地址", "result": "页面提示无访问权限"}
        ]
        # 其他需求遗留用例：文本恰好也引用 FP-001（编号撞车）
        cross_case = _case(
            number="TC-PROJ-PLACE-001",
            name="新增地点-合法提交",
            module="地点管理",
            remarks="关联 REQ-PLACE-001 / FP-001",
        )
        self._write_jsonl(proj_dir / "test_cases_module_01.jsonl", [aligned_case])
        self._write_jsonl(proj_dir / "test_cases_place_legacy.jsonl", [cross_case])

        result = _call(compute_coverage_report, project_identifier="PROJ-1")

        assert result["success"] is True
        assert result["total_cases"] == 1  # 跨 REQ 用例已被剔除
        assert result["covered"] == 0      # 撞车引用不计入覆盖
        assert any("REQ 需求级对齐" in w for w in result["warnings"])

    def test_explicit_case_files_skip_req_alignment(self, tmp_workspace):
        """显式 case_files 模式不做 REQ 过滤：文件由模型明确指定为本次产出，
        无 REQ 引用的用例（W6 违规但合法存在）不得被误杀。"""
        proj_dir = tmp_workspace / "PROJ-1"
        feature = _feature()
        feature["source"] = "REQ-LOGIN-001 登录需求"
        self._write_jsonl(proj_dir / "feature_matrix.jsonl", [feature])
        case_file = proj_dir / "test_cases_module_01.jsonl"
        self._write_jsonl(case_file, [_case()])

        result = _call(
            compute_coverage_report,
            project_identifier="PROJ-1",
            case_files=[str(case_file)],
        )

        assert result["success"] is True
        assert result["total_cases"] == 1
        assert result["covered"] == 1
        assert not any("REQ 需求级对齐" in w for w in result["warnings"])

    def test_stale_matrix_detected_when_modules_disjoint(self, tmp_workspace):
        """矩阵与用例模块零交集且零覆盖 → 疑似其他需求的遗留矩阵，给出降级指引。

        回归：同一 project_identifier 下不同需求共享 feature_matrix.jsonl，
        上一需求的遗留矩阵会让本需求的评审报告贴入一份无关的 0% 对照表。
        """
        proj_dir = tmp_workspace / "PROJ-1"
        self._write_jsonl(
            proj_dir / "feature_matrix.jsonl",
            [_feature("FP-001", module="地点管理", feature="列表字段展示")],
        )
        self._write_jsonl(
            proj_dir / "cases.jsonl",
            [_case(module="装扮弹窗", name="合并弹窗-0.5s内多件合并展示")],
        )

        result = _call(compute_coverage_report, project_identifier="PROJ-1")

        assert result["success"] is True
        assert result["covered"] == 0
        assert result["stale_matrix_suspected"] is True
        assert "历史遗留矩阵" in result["message"]
        assert "无结构化矩阵" in result["message"]
        assert any("历史遗留矩阵" in w for w in result["warnings"])

    def test_stale_matrix_not_flagged_when_modules_overlap(self, tmp_workspace):
        """模块有交集时的零覆盖是真实缺口，不误报遗留矩阵。"""
        proj_dir = tmp_workspace / "PROJ-1"
        self._write_jsonl(
            proj_dir / "feature_matrix.jsonl",
            [_feature("FP-001", module="用户认证", feature="图形验证码校验")],
        )
        # 同模块但内容与功能点不相关 → 真实未覆盖
        self._write_jsonl(
            proj_dir / "cases.jsonl",
            [
                {
                    "name": "订单导出-大数据量分批下载",
                    "case_number": "TC-PROJ-ORDER-001",
                    "module": "用户认证",
                    "priority": "P1",
                    "test_data": {"size": 10000},
                    "test_case_steps": [
                        {"step": "点击导出按钮", "result": "生成下载任务"}
                    ],
                }
            ],
        )

        result = _call(compute_coverage_report, project_identifier="PROJ-1")

        assert result["covered"] == 0
        assert result["stale_matrix_suspected"] is False
        assert "覆盖对照完成" in result["message"]

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
