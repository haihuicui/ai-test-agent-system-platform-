"""会话级 workspace 路径隔离测试。

覆盖 workspace_paths.apply_session_scope 的规范化矩阵，以及各工具模块
路径解析函数在会话作用域下的端到端行为（含 contextvar 回退旧行为）。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.agents.tools.testcase.runtime_context import set_session_scope
from app.agents.tools.testcase.workspace_paths import (
    apply_session_scope,
    sanitize_path_segment,
    session_scope_segments,
)


@pytest.fixture(autouse=True)
def _clean_session_scope():
    """每个测试前后清空会话作用域 contextvar，避免串扰。"""
    set_session_scope(None, None)
    yield
    set_session_scope(None, None)


# ═════════════════════════════════════════════════════════════════════════════
# session_scope_segments
# ═════════════════════════════════════════════════════════════════════════════

class TestSessionScopeSegments:
    def test_empty_when_no_scope(self):
        assert session_scope_segments() == ("", "")

    def test_explicit_project_wins_over_contextvar(self):
        set_session_scope("ctx-project", "t-1")
        project, thread = session_scope_segments("param-project")
        assert project == "param-project"
        assert thread == "t-1"

    def test_project_from_contextvar(self):
        set_session_scope("ctx-project", "t-1")
        assert session_scope_segments() == ("ctx-project", "t-1")

    def test_illegal_chars_sanitized(self):
        set_session_scope('proj/abc:test?', "t-1")
        project, thread = session_scope_segments()
        assert project == "proj_abc_test_"

    def test_invalid_project_falls_back_to_empty(self):
        set_session_scope("..", "t-1")
        project, thread = session_scope_segments()
        assert project == ""
        assert thread == "t-1"

    def test_thread_sanitized_defensively(self):
        set_session_scope("PR-1", "bad/thread")
        _, thread = session_scope_segments()
        assert thread == "bad_thread"


# ═════════════════════════════════════════════════════════════════════════════
# apply_session_scope
# ═════════════════════════════════════════════════════════════════════════════

class TestApplySessionScope:
    def test_no_scope_returns_rel_unchanged(self):
        rel = Path("feature_matrix.jsonl")
        assert apply_session_scope(rel) == rel

    def test_project_only_legacy_behavior(self):
        """无 thread（非平台环境）时退化为项目级隔离（旧行为）。"""
        rel = apply_session_scope(Path("feature_matrix.jsonl"), "PR-1")
        assert rel == Path("PR-1") / "feature_matrix.jsonl"

    def test_full_session_prefix_added(self):
        set_session_scope("PR-1", "thread-abc")
        rel = apply_session_scope(Path("feature_matrix.jsonl"))
        assert rel == Path("PR-1") / "thread-abc" / "feature_matrix.jsonl"

    def test_project_prefix_gets_thread_inserted(self):
        """模型按旧习惯传 <project>/<name> 时，插入 thread 层。"""
        set_session_scope("PR-1", "thread-abc")
        rel = apply_session_scope(Path("PR-1") / "feature_matrix.jsonl")
        assert rel == Path("PR-1") / "thread-abc" / "feature_matrix.jsonl"

    def test_full_prefix_is_idempotent(self):
        """已含完整会话前缀的路径（read_path 回传）原样保留。"""
        set_session_scope("PR-1", "thread-abc")
        original = Path("PR-1") / "thread-abc" / "test_cases_module_01.jsonl"
        assert apply_session_scope(original) == original

    def test_explicit_subdirectory_kept_under_scope(self):
        """自定义子目录保留在会话前缀之下。"""
        set_session_scope("PR-1", "thread-abc")
        rel = apply_session_scope(Path("custom") / "subdir" / "matrix.jsonl")
        assert rel == Path("PR-1") / "thread-abc" / "custom" / "subdir" / "matrix.jsonl"

    def test_other_project_directory_is_rescoped(self):
        """模型误传其他项目目录时，仍被收进当前会话前缀。"""
        set_session_scope("PR-1", "thread-abc")
        rel = apply_session_scope(Path("PR-2") / "cases.jsonl")
        assert rel == Path("PR-1") / "thread-abc" / "PR-2" / "cases.jsonl"

    def test_two_threads_isolated(self):
        """同项目两个会话解析同一名文件，得到不同路径（核心隔离目标）。"""
        set_session_scope("PR-1", "thread-A")
        path_a = apply_session_scope(Path("feature_matrix.jsonl"))
        set_session_scope("PR-1", "thread-B")
        path_b = apply_session_scope(Path("feature_matrix.jsonl"))
        assert path_a != path_b
        assert path_a.parts[1] == "thread-A"
        assert path_b.parts[1] == "thread-B"


class TestSanitizePathSegment:
    def test_rejects_dotdot(self):
        with pytest.raises(ValueError):
            sanitize_path_segment("..")

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            sanitize_path_segment("   ")


# ═════════════════════════════════════════════════════════════════════════════
# 工具模块路径解析的端到端行为（monkeypatch 各模块 _WORKSPACE_ROOT）
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_workspace(monkeypatch):
    """临时目录替代各工具模块的 workspace_root。"""
    with tempfile.TemporaryDirectory(prefix="test_session_ws_") as tmpdir:
        resolved = Path(tmpdir).resolve()
        from app.agents.tools.testcase import excel_tools, feature_matrix_tools, module_check_tools

        originals = {
            mod: mod._WORKSPACE_ROOT
            for mod in (feature_matrix_tools, excel_tools, module_check_tools)
        }
        for mod, orig in originals.items():
            monkeypatch.setattr(mod, "_WORKSPACE_ROOT", resolved)
        yield resolved


class TestToolPathResolutionWithSession:
    def test_matrix_path_scoped_to_session(self, temp_workspace):
        from app.agents.tools.testcase.feature_matrix_tools import resolve_feature_matrix_path

        set_session_scope("PR-1", "thread-abc")
        path = resolve_feature_matrix_path(project_identifier="PR-1")
        assert path.relative_to(temp_workspace) == (
            Path("PR-1") / "thread-abc" / "feature_matrix.jsonl"
        )

    def test_matrix_path_read_path_roundtrip(self, temp_workspace):
        """保存返回的 read_path 风格路径回传时幂等（读写同一路径）。"""
        from app.agents.tools.testcase.feature_matrix_tools import resolve_feature_matrix_path

        set_session_scope("PR-1", "thread-abc")
        first = resolve_feature_matrix_path(project_identifier="PR-1")
        second = resolve_feature_matrix_path(
            output_file="/PR-1/thread-abc/feature_matrix.jsonl",
            project_identifier="PR-1",
        )
        assert first == second

    def test_export_path_scoped_to_session(self, temp_workspace):
        from app.agents.tools.testcase.excel_tools import _resolve_workspace_path

        set_session_scope("PR-1", "thread-abc")
        path = _resolve_workspace_path("测试用例.xlsx")
        assert path.relative_to(temp_workspace) == (
            Path("PR-1") / "thread-abc" / "测试用例.xlsx"
        )

    def test_input_path_scoped_to_session(self, temp_workspace):
        from app.agents.tools.testcase.excel_tools import _resolve_input_path

        set_session_scope("PR-1", "thread-abc")
        path = _resolve_input_path("test_cases_module_01.jsonl")
        assert path.relative_to(temp_workspace) == (
            Path("PR-1") / "thread-abc" / "test_cases_module_01.jsonl"
        )

    def test_case_file_path_scoped_to_session(self, temp_workspace):
        from app.agents.tools.testcase.module_check_tools import _resolve_case_file_path

        set_session_scope("PR-1", "thread-abc")
        path = _resolve_case_file_path("test_cases_module_01.jsonl")
        assert path.relative_to(temp_workspace) == (
            Path("PR-1") / "thread-abc" / "test_cases_module_01.jsonl"
        )

    def test_manifest_path_scoped_to_session(self, temp_workspace):
        from app.agents.tools.testcase.module_check_tools import _resolve_manifest_path

        set_session_scope("PR-1", "thread-abc")
        path = _resolve_manifest_path("test_case_manifest.json")
        assert path.relative_to(temp_workspace) == (
            Path("PR-1") / "thread-abc" / "test_case_manifest.json"
        )

    def test_fallback_to_project_level_without_thread(self, temp_workspace):
        """无 thread_id（直调/非平台环境）时回退为项目级隔离（旧行为）。"""
        from app.agents.tools.testcase.feature_matrix_tools import resolve_feature_matrix_path

        set_session_scope("PR-1", None)
        path = resolve_feature_matrix_path(project_identifier="PR-1")
        assert path.relative_to(temp_workspace) == Path("PR-1") / "feature_matrix.jsonl"

    def test_fallback_to_root_without_scope(self, temp_workspace):
        """完全无会话作用域时保持旧行为（落根目录）。"""
        from app.agents.tools.testcase.excel_tools import _resolve_workspace_path

        path = _resolve_workspace_path("测试用例.xlsx")
        assert path.relative_to(temp_workspace) == Path("测试用例.xlsx")

    def test_traversal_still_rejected_under_session(self, temp_workspace):
        """会话隔离不削弱越权防护。"""
        from app.agents.tools.testcase.excel_tools import _resolve_input_path

        set_session_scope("PR-1", "thread-abc")
        with pytest.raises(ValueError):
            _resolve_input_path("../../../../etc/passwd")
