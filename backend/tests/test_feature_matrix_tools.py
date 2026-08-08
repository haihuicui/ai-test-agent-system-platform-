"""Tests for save_feature_matrix_tool 功能矩阵结构化存储工具。

覆盖：合法数据写入、字段校验、枚举校验、边界条件。
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from app.agents.tools.testcase.feature_matrix_tools import (
    _normalize_test_types,
    _validate_feature_point,
    load_feature_matrix,
    resolve_feature_matrix_path,
    save_feature_matrix_tool,
)


# ── 合法基线数据 ──
VALID_FEATURE = {
    "id": "FP-001",
    "module": "用户认证",
    "feature": "手机号登录",
    "test_points": ["验证码有效期5min", "验证码发送频率限制", "错误次数锁定"],
    "priority": "P0",
    "risk_level": "高",
    "test_type": ["功能", "安全"],
    "source": "需求原文 §2.1",
}


# ── 辅助：同步调用 async StructuredTool ──
def _call(tool, **kwargs):
    """通过 tool.ainvoke() 调用，避免依赖 pytest-asyncio 插件。"""
    return asyncio.run(tool.ainvoke(kwargs))


# ═════════════════════════════════════════════════════════════════════════════
# TestValidateFeaturePoint
# ═════════════════════════════════════════════════════════════════════════════

class TestValidateFeaturePoint:
    def test_valid_feature_passes(self):
        assert _validate_feature_point(VALID_FEATURE, 0) == []

    def test_missing_required_field(self):
        fp = {**VALID_FEATURE}
        del fp["module"]
        errors = _validate_feature_point(fp, 0)
        assert any("缺少必填字段 'module'" in e for e in errors)

    def test_empty_string_field(self):
        fp = {**VALID_FEATURE, "module": ""}
        errors = _validate_feature_point(fp, 0)
        assert any("缺少必填字段 'module'" in e for e in errors)

    def test_empty_test_points_list(self):
        fp = {**VALID_FEATURE, "test_points": []}
        errors = _validate_feature_point(fp, 0)
        assert any("'test_points' 为空列表" in e for e in errors)

    def test_wrong_type(self):
        fp = {**VALID_FEATURE, "test_points": "not_a_list"}
        errors = _validate_feature_point(fp, 0)
        assert any("'test_points' 类型错误" in e for e in errors)

    def test_invalid_priority(self):
        fp = {**VALID_FEATURE, "priority": "XYZ"}
        errors = _validate_feature_point(fp, 0)
        assert any("priority='XYZ' 不合法" in e for e in errors)

    def test_priority_with_spaces(self):
        """修复 #2：空格应被 strip 后通过"""
        fp = {**VALID_FEATURE, "priority": " P0 "}
        errors = _validate_feature_point(fp, 0)
        assert not any("priority" in e for e in errors)

    def test_risk_level_with_spaces(self):
        """修复 #2：空格应被 strip"""
        fp = {**VALID_FEATURE, "risk_level": " 高 "}
        errors = _validate_feature_point(fp, 0)
        assert not any("risk_level" in e for e in errors)

    def test_risk_level_english_accepted(self):
        """修复 #3：英文风险等级应被接受"""
        for val in ["High", "Medium", "Low", "high", "medium", "low"]:
            fp = {**VALID_FEATURE, "risk_level": val}
            errors = _validate_feature_point(fp, 0)
            assert not any("risk_level" in e for e in errors), f"{val}: {errors}"

    def test_risk_level_unknown_rejected(self):
        fp = {**VALID_FEATURE, "risk_level": "Critical"}
        errors = _validate_feature_point(fp, 0)
        assert any("risk_level='Critical' 不合法" in e for e in errors)

    def test_test_type_unknown_rejected(self):
        """修复 #4：test_type 非法值不应静默通过"""
        fp = {**VALID_FEATURE, "test_type": ["functional_test"]}
        errors = _validate_feature_point(fp, 0)
        assert any("test_type 包含未知值" in e for e in errors)

    def test_test_type_valid_passes(self):
        fp = {**VALID_FEATURE, "test_type": ["功能", "安全", "边界"]}
        errors = _validate_feature_point(fp, 0)
        assert not any("test_type" in e for e in errors)

    def test_test_type_rule_permission_state_valid(self):
        """规则/权限/状态 是功能测试常见细分维度，应为合法取值"""
        fp = {**VALID_FEATURE, "test_type": ["功能", "规则", "权限", "状态"]}
        errors = _validate_feature_point(fp, 0)
        assert not any("test_type" in e for e in errors)

    def test_invalid_id_format(self):
        fp = {**VALID_FEATURE, "id": "USER-001"}
        errors = _validate_feature_point(fp, 0)
        assert any("'USER-001' 格式不正确" in e for e in errors)

    def test_id_missing(self):
        fp = {**VALID_FEATURE}
        del fp["id"]
        errors = _validate_feature_point(fp, 0)
        assert any("缺少必填字段 'id'" in e for e in errors)

    def test_none_field_value(self):
        fp = {**VALID_FEATURE, "module": None}
        errors = _validate_feature_point(fp, 0)
        assert any("缺少必填字段 'module'" in e for e in errors)

    def test_multiple_errors_accumulated(self):
        """一条记录有多个问题时，应全部返回"""
        fp = {
            "id": "", "module": None, "feature": "f", "test_points": [],
            "priority": "INVALID", "risk_level": "未知", "test_type": ["bad_type"],
        }
        errors = _validate_feature_point(fp, 0)
        assert len(errors) >= 5, f"expected >= 5 errors, got {len(errors)}: {errors}"


# ═════════════════════════════════════════════════════════════════════════════
# TestNormalizeTestTypes
# ═════════════════════════════════════════════════════════════════════════════

class TestNormalizeTestTypes:
    def test_ui_synonym(self):
        normalized, warnings = _normalize_test_types(["界面"], 0)
        assert normalized == ["UI"]
        assert any("界面" in w and "UI" in w for w in warnings)

    def test_functional_synonyms(self):
        for val in ["功能测试", "功能性", "功能性测试"]:
            normalized, _ = _normalize_test_types([val], 0)
            assert normalized == ["功能"], f"{val} 应映射为 功能"

    def test_security_and_performance_synonyms(self):
        normalized, _ = _normalize_test_types(["安全测试", "性能测试"], 0)
        assert normalized == ["安全", "性能"]

    def test_multiple_mixed_values(self):
        normalized, warnings = _normalize_test_types(
            ["界面", "功能测试", "API", "边界值"], 1
        )
        assert normalized == ["UI", "功能", "接口", "边界"]
        assert len(warnings) == 4
        assert any("第 2 条" in w for w in warnings)

    def test_standard_values_unchanged(self):
        normalized, warnings = _normalize_test_types(["功能", "UI", "安全"], 0)
        assert normalized == ["功能", "UI", "安全"]
        assert warnings == []

    def test_non_string_value_converted(self):
        normalized, _ = _normalize_test_types([123, None], 0)
        assert normalized == ["123", "None"]

    def test_combined_value_split(self):
        """LLM 高频输出 "功能+规则" 形式的组合值，应拆分为独立取值"""
        normalized, warnings = _normalize_test_types(["功能+规则"], 0)
        assert normalized == ["功能", "规则"]
        assert any("组合值拆分" in w for w in warnings)

    def test_combined_value_various_separators(self):
        normalized, _ = _normalize_test_types(
            ["功能+权限", "功能/状态", "功能、边界"], 0
        )
        assert normalized == ["功能", "权限", "状态", "边界"]

    def test_combined_value_with_synonyms(self):
        """组合值拆分后各部分仍应做同义词映射"""
        normalized, _ = _normalize_test_types(["功能测试+权限校验"], 0)
        assert normalized == ["功能", "权限"]

    def test_split_dedupes_values(self):
        normalized, _ = _normalize_test_types(["功能+边界", "功能"], 0)
        assert normalized == ["功能", "边界"]

    def test_rule_permission_state_synonyms(self):
        normalized, _ = _normalize_test_types(
            ["规则校验", "权限测试", "状态流转"], 0
        )
        assert normalized == ["规则", "权限", "状态"]


# ═════════════════════════════════════════════════════════════════════════════
# TestSaveFeatureMatrixTool
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_workspace(monkeypatch):
    """使用临时目录替代真实 workspace_root。"""
    with tempfile.TemporaryDirectory(prefix="test_matrix_") as tmpdir:
        from app.agents.tools.testcase import feature_matrix_tools as fmt
        original = fmt._WORKSPACE_ROOT
        resolved = Path(tmpdir).resolve()
        monkeypatch.setattr(fmt, "_WORKSPACE_ROOT", resolved)
        yield resolved
        monkeypatch.setattr(fmt, "_WORKSPACE_ROOT", original)


class TestSaveFeatureMatrixTool:
    def test_save_valid_features(self, temp_workspace):
        """正常保存 3 个功能点 → 成功"""
        features = [
            {**VALID_FEATURE},
            {**VALID_FEATURE, "id": "FP-002", "module": "订单管理", "feature": "创建订单"},
            {**VALID_FEATURE, "id": "FP-003", "module": "订单管理", "feature": "取消订单"},
        ]
        result = _call(save_feature_matrix_tool,
            features=features,
            output_file="test_matrix.jsonl")

        assert result["success"] is True
        assert result["count"] == 3
        assert "用户认证" in result["modules"]
        assert "订单管理" in result["modules"]
        assert result["priority_distribution"]["P0"] == 3

        saved_file = temp_workspace / "test_matrix.jsonl"
        assert saved_file.is_file()
        lines = saved_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3
        for line in lines:
            obj = json.loads(line)
            assert obj["id"].startswith("FP-")
            assert "saved_at" in obj

    def test_empty_features(self, temp_workspace):
        """空列表 → 返回失败"""
        result = _call(save_feature_matrix_tool, features=[])
        assert result["success"] is False
        assert "为空" in result.get("message", "")

    def test_validation_failure(self, temp_workspace):
        """校验失败 → 返回 errors 列表，文件不写入"""
        features = [
            {**VALID_FEATURE, "id": "FP-001"},
            {"id": "FP-002"},                     # 缺少大量必填字段
            {**VALID_FEATURE, "id": "FP-001"},     # 与第一条 id 重复
        ]
        result = _call(save_feature_matrix_tool, features=features)
        assert result["success"] is False
        assert "errors" in result
        assert result["error_count"] >= 2
        saved_file = temp_workspace / "feature_matrix.jsonl"
        assert not saved_file.exists()

    def test_duplicate_ids_in_batch(self, temp_workspace):
        """同批次内 id 重复 → 校验失败"""
        features = [
            {**VALID_FEATURE, "id": "FP-001"},
            {**VALID_FEATURE, "id": "FP-001"},
        ]
        result = _call(save_feature_matrix_tool, features=features)
        assert result["success"] is False
        assert any("重复" in e for e in result.get("errors", []))

    def test_non_dict_element(self, temp_workspace):
        """列表中有非 dict 元素 → Pydantic 校验失败（先于内部校验拦截）"""
        with pytest.raises(Exception):
            _call(save_feature_matrix_tool, features=[{**VALID_FEATURE}, "not_a_dict"])

    def test_output_to_subdirectory(self, temp_workspace):
        """输出到子目录 → 自动创建目录"""
        result = _call(save_feature_matrix_tool,
            features=[{**VALID_FEATURE}],
            output_file="subdir/matrix.jsonl")
        assert result["success"] is True
        assert (temp_workspace / "subdir" / "matrix.jsonl").is_file()

    def test_default_output_file(self, temp_workspace):
        """不传 output_file → 使用默认路径"""
        result = _call(save_feature_matrix_tool, features=[{**VALID_FEATURE}])
        assert result["success"] is True
        assert (temp_workspace / "feature_matrix.jsonl").is_file()

    def test_project_identifier_injected(self, temp_workspace):
        """传入 project_identifier → 每条记录应注入该字段，并隔离到项目目录"""
        result = _call(save_feature_matrix_tool,
            features=[{**VALID_FEATURE}],
            project_identifier="test-project-123")
        assert result["success"] is True
        # 路径隔离：文件应位于 workspace/test-project-123/feature_matrix.jsonl
        assert "test-project-123" in result["file"]

        saved_file = temp_workspace / "test-project-123" / "feature_matrix.jsonl"
        assert saved_file.is_file()
        data = json.loads(saved_file.read_text(encoding="utf-8").strip())
        assert data["project_identifier"] == "test-project-123"

    def test_project_identifier_isolates_default_path(self, temp_workspace):
        """默认 output_file + project_identifier → 隔离到项目子目录"""
        result = _call(save_feature_matrix_tool,
            features=[{**VALID_FEATURE}],
            project_identifier="order-system")
        assert result["success"] is True
        saved_file = Path(result["file"])
        assert saved_file.relative_to(temp_workspace) == Path("order-system") / "feature_matrix.jsonl"
        assert saved_file.is_file()
        # 未提供 project_identifier 时不应污染 order-system 目录
        assert not (temp_workspace / "feature_matrix.jsonl").exists()

    def test_save_result_includes_virtual_read_path(self, temp_workspace):
        """保存结果必须携带 Agent 虚拟 FS 的 read_path，禁止模型拿宿主机绝对路径去 read_file"""
        result = _call(save_feature_matrix_tool,
            features=[{**VALID_FEATURE}],
            project_identifier="PR-1")
        assert result["success"] is True
        assert result["read_path"] == "/PR-1/feature_matrix.jsonl"
        assert "read_path" in result["note"]
        # 未传 project_identifier 时 read_path 指向根目录下的文件
        result2 = _call(save_feature_matrix_tool,
            features=[{**VALID_FEATURE}],
            output_file="plain_matrix.jsonl")
        assert result2["success"] is True
        assert result2["read_path"] == "/plain_matrix.jsonl"

    def test_explicit_subdirectory_not_isolated(self, temp_workspace):
        """显式指定 output_file 子目录时，尊重原路径，不追加 project_identifier"""
        result = _call(save_feature_matrix_tool,
            features=[{**VALID_FEATURE}],
            output_file="custom/subdir/matrix.jsonl",
            project_identifier="order-system")
        assert result["success"] is True
        saved_file = Path(result["file"])
        assert saved_file.relative_to(temp_workspace) == Path("custom") / "subdir" / "matrix.jsonl"
        assert saved_file.is_file()
        # 不应在项目隔离目录下创建副本
        assert not (temp_workspace / "order-system" / "matrix.jsonl").exists()

    def test_project_identifier_sanitization(self, temp_workspace):
        """project_identifier 含非法字符时应被清理为合法目录名"""
        result = _call(save_feature_matrix_tool,
            features=[{**VALID_FEATURE}],
            project_identifier="proj/abc:test?")
        assert result["success"] is True
        saved_file = Path(result["file"])
        # 非法字符被替换为下划线
        assert saved_file.relative_to(temp_workspace) == Path("proj_abc_test_") / "feature_matrix.jsonl"
        assert saved_file.is_file()

    def test_synonyms_are_normalized_on_save(self, temp_workspace):
        """test_type 同义词应被自动修正为标准值并保存"""
        features = [
            {**VALID_FEATURE, "test_type": ["界面", "功能测试", "API"]},
            {**VALID_FEATURE, "id": "FP-002", "test_type": ["安全性", "边界值"]},
        ]
        result = _call(save_feature_matrix_tool, features=features)
        assert result["success"] is True
        assert result["count"] == 2
        # 应返回自动修正警告
        assert len(result.get("warnings", [])) == 5
        assert any("界面" in w for w in result["warnings"])

        saved_file = temp_workspace / "feature_matrix.jsonl"
        lines = saved_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["test_type"] == ["UI", "功能", "接口"]
        second = json.loads(lines[1])
        assert second["test_type"] == ["安全", "边界"]


# ═════════════════════════════════════════════════════════════════════════════
# TestResolveAndLoadFeatureMatrix
# ═════════════════════════════════════════════════════════════════════════════

class TestResolveAndLoadFeatureMatrix:
    def test_resolve_default_path_without_project(self, temp_workspace):
        """无 project_identifier 时，默认路径在 workspace_root 根目录"""
        path = resolve_feature_matrix_path()
        assert path.relative_to(temp_workspace) == Path("feature_matrix.jsonl")

    def test_resolve_isolated_path_with_project(self, temp_workspace):
        """有 project_identifier 时，路径隔离到项目子目录"""
        path = resolve_feature_matrix_path(project_identifier="billing-system")
        assert path.relative_to(temp_workspace) == Path("billing-system") / "feature_matrix.jsonl"

    def test_resolve_respects_explicit_subdirectory(self, temp_workspace):
        """显式子目录不应被 project_identifier 覆盖"""
        path = resolve_feature_matrix_path(
            project_identifier="billing-system",
            output_file="archived/matrix.jsonl")
        assert path.relative_to(temp_workspace) == Path("archived") / "matrix.jsonl"

    def test_load_feature_matrix_success(self, temp_workspace):
        """load_feature_matrix 应能读取 save_feature_matrix_tool 保存的文件"""
        features = [
            {**VALID_FEATURE},
            {**VALID_FEATURE, "id": "FP-002", "module": "订单管理", "feature": "创建订单"},
        ]
        save_result = _call(save_feature_matrix_tool,
            features=features,
            project_identifier="load-test")
        assert save_result["success"] is True

        load_result = load_feature_matrix(project_identifier="load-test")
        assert load_result["success"] is True
        assert load_result["count"] == 2
        assert {fp["id"] for fp in load_result["features"]} == {"FP-001", "FP-002"}
        assert "用户认证" in load_result["modules"]
        assert "订单管理" in load_result["modules"]

    def test_load_feature_matrix_not_found(self, temp_workspace):
        """文件不存在时返回明确错误"""
        result = load_feature_matrix(project_identifier="non-existent-project")
        assert result["success"] is False
        assert "不存在" in result.get("error", "")
        assert result["count"] == 0

    def test_load_feature_matrix_invalid_jsonl(self, temp_workspace):
        """JSONL 包含非法行时返回解析错误"""
        resolved = resolve_feature_matrix_path(project_identifier="bad-json")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text('{"id": "FP-001"}\n{not valid json}\n', encoding="utf-8")

        result = load_feature_matrix(project_identifier="bad-json")
        assert result["success"] is False
        assert "解析失败" in result.get("error", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
