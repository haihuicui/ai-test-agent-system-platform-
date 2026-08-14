"""Tests for verify_review_citations 对抗性评审举证校验工具。

覆盖：
- _normalize 归一化（JSON 转义 / 空白抹平）
- _extract_blocker_quotes 段落提取（仅阻断段；忽略附录、待确认假设段）
- verify_citations 纯函数（命中 / 未命中 / 缺引文 / 过短 / 多引文任一失败）
- 工具端到端（tmp workspace 下的用例 JSONL + 评审 md）
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.agents.tools.testcase import review_verify_tools
from app.agents.tools.testcase.review_verify_tools import (
    _extract_blocker_quotes,
    _normalize,
    verify_citations,
    verify_review_citations,
)


def _case():
    return {
        "name": "调试菜单结构重组后导航项完整",
        "case_number": "TC-PR1-MENU-001",
        "module": "菜单结构重组",
        "priority": "critical",
        "remarks": '断言"调试"菜单保留',
        "test_data": {"menu": "调试"},
        "test_case_steps": [
            {
                "step": "展开调试菜单",
                "result": "显示 5 个子项：整机测试/单模块测试/队列进样/历史列表/老化调试",
            },
        ],
    }


# 命中语料的引文（对应 _case() 的 steps.result 字段值片段）
HIT_QUOTE = "显示 5 个子项：整机测试/单模块测试/队列进样/历史列表/老化调试"
MISS_QUOTE = "这段引文在任何用例文件中都不存在的文字"


def _review_md(blocker_body: str) -> str:
    """拼一份符合契约的评审结果文件（阻断段 + 假设段 + 附录段）。"""
    return f"""## 🔍 对抗性审查发现 — 菜单结构重组

### 🚫 阻断发现（2 条）
{blocker_body}

### ⏳ 待确认假设（1 条）
| # | 涉及用例 | 假设内容 | 影响用例数 |
|---|---------|---------|-----------|
| 1 | TC-PR1-MENU-001 | 备注 40 字符按字符计 | 3 |

### 📎 附录（1 条）
| # | 涉及用例 | 缺陷类型 | 详细描述 |
|---|---------|---------|---------|
| 1 | TC-PR1-MENU-003 | 措辞模糊 | 预期结果"正常显示"过于模糊 |
"""


def _blocker(bid="B1", case="TC-PR1-MENU-001", quote=HIT_QUOTE) -> str:
    return f"""#### {bid} | {case} | 断言矛盾
- **位置**：步骤 3 预期
- **原文**：{quote}
- **误判场景**：执行时实际表现与断言冲突 → 误报
- **修复建议**：拆分为两条用例"""


# ═════════════════════════════════════════════════════════════════════════════
# _normalize 归一化
# ═════════════════════════════════════════════════════════════════════════════

class TestNormalize:
    def test_strips_all_whitespace(self):
        assert _normalize("a b\tc\nd") == "abcd"

    def test_unescapes_json_quotes(self):
        # JSONL 原文中的 \" 与引文中的 " 归一后一致
        assert _normalize('断言\\"调试\\"菜单') == _normalize('断言"调试"菜单')

    def test_unescapes_json_newline(self):
        assert _normalize("第一行\\n第二行") == "第一行第二行"


# ═════════════════════════════════════════════════════════════════════════════
# _extract_blocker_quotes 段落提取
# ═════════════════════════════════════════════════════════════════════════════

class TestExtractBlockerQuotes:
    def test_extracts_findings_and_quotes(self):
        body = _blocker("B1") + "\n\n" + _blocker("B2", quote=MISS_QUOTE)
        findings = _extract_blocker_quotes(_review_md(body))
        assert len(findings) == 2
        assert findings[0]["finding"] == "B1"
        assert findings[0]["case_ref"] == "TC-PR1-MENU-001"
        assert findings[0]["defect_type"] == "断言矛盾"
        assert findings[0]["quotes"] == [HIT_QUOTE]
        assert findings[1]["quotes"] == [MISS_QUOTE]

    def test_ignores_appendix_and_assumption_sections(self):
        """附录表格与待确认假设段中的"原文"字样不得被提取。"""
        body = _blocker("B1")
        findings = _extract_blocker_quotes(_review_md(body))
        assert len(findings) == 1
        # 附录行里即使出现类似文本也不产生额外 finding/引文
        all_quotes = [q for f in findings for q in f["quotes"]]
        assert all_quotes == [HIT_QUOTE]

    def test_multiple_quotes_per_finding(self):
        body = _blocker("B1") + f"\n- **原文**：{MISS_QUOTE}"
        findings = _extract_blocker_quotes(_review_md(body))
        assert findings[0]["quotes"] == [HIT_QUOTE, MISS_QUOTE]

    def test_no_blocker_section_returns_empty(self):
        assert _extract_blocker_quotes("## 随便一份文件\n没有任何阻断段") == []


# ═════════════════════════════════════════════════════════════════════════════
# verify_citations 纯函数
# ═════════════════════════════════════════════════════════════════════════════

CASE_CORPUS = json.dumps(_case(), ensure_ascii=False)


class TestVerifyCitations:
    def _run(self, body: str, corpus: str = CASE_CORPUS):
        return verify_citations({"adversarial_review_m01.md": _review_md(body)}, corpus)

    def test_hit_is_verified(self):
        result = self._run(_blocker("B1"))
        assert result["total_blockers"] == 1
        assert result["verified"] == 1
        assert result["unverified"] == 0
        assert result["unverified_items"] == []

    def test_miss_is_unverified_not_found(self):
        result = self._run(_blocker("B1", quote=MISS_QUOTE))
        assert result["verified"] == 0
        assert result["unverified"] == 1
        item = result["unverified_items"][0]
        assert item["reason"] == "not_found"
        assert item["finding"] == "B1"
        assert item["case_ref"] == "TC-PR1-MENU-001"

    def test_missing_quote_is_no_evidence(self):
        body = """#### B1 | TC-PR1-MENU-001 | 覆盖盲区
- **位置**：test_data
- **误判场景**：漏报
- **修复建议**：补充"""
        result = self._run(body)
        assert result["unverified"] == 1
        assert result["no_evidence"] == 1
        assert result["unverified_items"][0]["reason"] == "no_evidence"

    def test_short_quote_is_too_short(self):
        result = self._run(_blocker("B1", quote="太短"))
        assert result["unverified"] == 1
        assert result["too_short"] == 1
        assert result["unverified_items"][0]["reason"] == "too_short"

    def test_any_failing_quote_fails_finding(self):
        """同一发现多条引文时，任一未命中即整发现未证实。"""
        body = _blocker("B1") + f"\n- **原文**：{MISS_QUOTE}"
        result = self._run(body)
        assert result["total_blockers"] == 1
        assert result["verified"] == 0
        assert result["unverified"] == 1

    def test_json_escape_tolerance(self):
        """语料中是 JSON 转义的 \\"，引文是未转义的引号——归一化后应命中。"""
        result = self._run(_blocker("B1", quote='断言"调试"菜单保留'))
        assert result["verified"] == 1

    def test_mixed_files_counts(self):
        hit = _review_md(_blocker("B1"))
        miss = _review_md(_blocker("B1", quote=MISS_QUOTE))
        result = verify_citations(
            {
                "adversarial_review_m01.md": hit,
                "adversarial_review_m02.md": miss,
            },
            CASE_CORPUS,
        )
        assert result["total_blockers"] == 2
        assert result["verified"] == 1
        assert result["unverified"] == 1


# ═════════════════════════════════════════════════════════════════════════════
# 工具端到端（tmp workspace）
# ═════════════════════════════════════════════════════════════════════════════

def _call(tool, **kwargs):
    return asyncio.run(tool.ainvoke(kwargs))


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(review_verify_tools, "_WORKSPACE_ROOT", tmp_path)
    return tmp_path


class TestVerifyReviewCitationsTool:
    def _write_jsonl(self, path: Path, records: list[dict]):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
            encoding="utf-8",
        )

    def _setup_session_dir(self, proj_dir: Path) -> Path:
        self._write_jsonl(proj_dir / "test_cases_module_01_menu.jsonl", [_case()])
        (proj_dir / "adversarial_review_m01.md").write_text(
            _review_md(_blocker("B1") + "\n\n" + _blocker("B2", quote=MISS_QUOTE)),
            encoding="utf-8",
        )
        return proj_dir

    def test_end_to_end(self, tmp_workspace):
        proj_dir = self._setup_session_dir(tmp_workspace / "PROJ-1")

        result = _call(verify_review_citations, project_identifier="PROJ-1")

        assert result["success"] is True
        assert result["total_blockers"] == 2
        assert result["verified"] == 1
        assert result["unverified"] == 1
        assert result["unverified_items"][0]["reason"] == "not_found"
        assert len(result["review_files"]) == 1

    def test_explicit_review_dir(self, tmp_workspace):
        """显式传会话工作目录的虚拟路径（/<项目>/）。"""
        self._setup_session_dir(tmp_workspace / "PROJ-1")

        result = _call(verify_review_citations, review_dir="/PROJ-1")

        assert result["success"] is True
        assert result["total_blockers"] == 2

    def test_summary_file_not_scanned(self, tmp_workspace):
        """summary 文件名不匹配 m* 模式，不参与引文提取。"""
        proj_dir = self._setup_session_dir(tmp_workspace / "PROJ-1")
        (proj_dir / "adversarial_review_summary.md").write_text(
            "### 📊 信任度评估\n低", encoding="utf-8"
        )

        result = _call(verify_review_citations, project_identifier="PROJ-1")

        assert result["success"] is True
        assert len(result["review_files"]) == 1
        assert all("summary" not in Path(f).name for f in result["review_files"])

    def test_feature_matrix_not_in_corpus(self, tmp_workspace):
        """feature_matrix.jsonl 不作为校验语料（引文仅在矩阵中 → 未命中）。"""
        proj_dir = tmp_workspace / "PROJ-1"
        self._write_jsonl(
            proj_dir / "feature_matrix.jsonl",
            [{"id": "FP-001", "feature": "整机测试队列进样历史列表老化调试的功能点"}],
        )
        proj_dir.joinpath("adversarial_review_m01.md").write_text(
            _review_md(_blocker("B1", quote="整机测试队列进样历史列表老化调试的功能点")),
            encoding="utf-8",
        )
        # 无用例文件时工具直接失败（语料为空）
        result = _call(verify_review_citations, project_identifier="PROJ-1")
        assert result["success"] is False

        self._write_jsonl(proj_dir / "test_cases_module_01_menu.jsonl", [_case()])
        result = _call(verify_review_citations, project_identifier="PROJ-1")
        assert result["success"] is True
        assert result["unverified"] == 1
        assert result["unverified_items"][0]["reason"] == "not_found"
        assert all("feature_matrix" not in Path(f).name for f in result["case_files_used"])

    def test_no_review_files_fails(self, tmp_workspace):
        proj_dir = tmp_workspace / "PROJ-1"
        self._write_jsonl(proj_dir / "test_cases_module_01_menu.jsonl", [_case()])

        result = _call(verify_review_citations, project_identifier="PROJ-1")

        assert result["success"] is False
        assert "adversarial_review_m*.md" in result["error"]

    def test_missing_dir_fails(self, tmp_workspace):
        result = _call(verify_review_citations, project_identifier="NOPE-9")
        assert result["success"] is False

    def test_review_dir_traversal_rejected(self, tmp_workspace):
        result = _call(verify_review_citations, review_dir="/../outside")
        assert result["success"] is False
        assert "越权" in result["error"]
