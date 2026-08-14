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

    def test_backtick_segments_split(self):
        """反引号分别包裹的多段引用拆为独立引文（矛盾举证的自然格式）。"""
        body = """#### B1 | TC-PR1-MENU-001 | 断言矛盾
- **位置**：步骤 1/2 预期
- **原文**：`"result": "侧边导航保留「调试」菜单项"` 与 `"result": "侧边导航不存在「调试」菜单项"`
- **误判场景**：互斥断言必有一次误报
- **修复建议**：拆分"""
        findings = _extract_blocker_quotes(_review_md(body))
        assert findings[0]["quotes"] == [
            '"result": "侧边导航保留「调试」菜单项"',
            '"result": "侧边导航不存在「调试」菜单项"',
        ]

    def test_no_blocker_section_returns_empty(self):
        assert _extract_blocker_quotes("## 随便一份文件\n没有任何阻断段") == []

    def test_h2_blocker_section_extracted(self):
        """阻断段标题为 H2（## 🚫）时同样可提取——E2E 实证模型对段落层级选择不稳定，
        文件大标题占 H1 时章节自然落 H2，写死 H3 会整段漏提（12 条阻断全灭事故）。"""
        md = f"""# 对抗性评审 — 串口与调试窗口

## 🚫 阻断发现

{_blocker("B1")}

## 📎 附录发现（计数：1）
| # | 涉及用例 | 缺陷类型 |
|---|---------|---------|
| 1 | TC-PR1-MENU-003 | 措辞模糊 |
"""
        findings = _extract_blocker_quotes(md)
        assert len(findings) == 1
        assert findings[0]["finding"] == "B1"
        assert findings[0]["quotes"] == [HIT_QUOTE]

    def test_h4_finding_head_does_not_reset_section(self):
        """B 头（#### H4）不得被当作段落边界重置阻断段状态——
        否则同一阻断段内第二条发现起全部漏提。"""
        body = _blocker("B1") + "\n\n" + _blocker("B2", quote=MISS_QUOTE)
        findings = _extract_blocker_quotes(_review_md(body))
        assert [f["finding"] for f in findings] == ["B1", "B2"]


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

    def test_backtick_segments_each_must_hit(self):
        """反引号多段引用：全部命中才证实，任一未命中即未证实。"""
        body = """#### B1 | TC-PR1-MENU-001 | 断言矛盾
- **位置**：步骤 1/2 预期
- **原文**：`显示 5 个子项：整机测试/单模块测试/队列进样/历史列表/老化调试` 与 `这段不存在于任何文件的引用文字`
- **误判场景**：互斥断言
- **修复建议**：拆分"""
        result = self._run(body)
        assert result["verified"] == 0
        assert result["unverified"] == 1
        assert result["unverified_items"][0]["reason"] == "not_found"

    def test_backtick_segments_all_hit_verified(self):
        body = """#### B1 | TC-PR1-MENU-001 | 断言矛盾
- **位置**：步骤 1/2 预期
- **原文**：`显示 5 个子项：整机测试/单模块测试/队列进样/历史列表/老化调试` 与 `断言"调试"菜单保留`
- **误判场景**：互斥断言
- **修复建议**：拆分"""
        result = self._run(body)
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

    def test_duplicate_findings_across_files_deduped(self):
        """同一阻断出现在多个文件（排障副本 *_contract.md）只计一次——
        E2E 实证：5 模块 12 条阻断因副本被重复计为 24 条。"""
        body = _blocker("B1")
        result = verify_citations(
            {
                "adversarial_review_m01.md": _review_md(body),
                "adversarial_review_m01_contract.md": _review_md(body),
            },
            CASE_CORPUS,
        )
        assert result["total_blockers"] == 1
        assert result["verified"] == 1
        assert result["unverified"] == 0

    def test_duplicate_key_any_verified_version_wins(self):
        """副本间引文为子集关系（排障转写删节了一段）：交集非空 → 同组，
        逐字完整版命中即证实——失真删节版不再拖垮整条阻断。"""
        full = """#### B1 | TC-PR1-MENU-001 | 断言矛盾
- **位置**：步骤 1/2 预期
- **原文**：`显示 5 个子项：整机测试/单模块测试/队列进样/历史列表/老化调试` 与 `这段不存在于任何文件的引用文字`
- **误判场景**：互斥断言
- **修复建议**：拆分"""
        abridged = _blocker("B1", quote=HIT_QUOTE)  # 子集：只保留逐字那段
        result = verify_citations(
            {
                "adversarial_review_m01.md": _review_md(full),
                "adversarial_review_m01_contract.md": _review_md(abridged),
            },
            CASE_CORPUS,
        )
        assert result["total_blockers"] == 1
        assert result["verified"] == 1
        assert result["unverified"] == 0

    def test_disjoint_quotes_same_case_type_not_merged(self):
        """同用例同缺陷类型但引文无交集：是两条独立阻断，不得误并。"""
        result = verify_citations(
            {
                "adversarial_review_m01.md": _review_md(
                    _blocker("B1", quote=HIT_QUOTE) + "\n\n" + _blocker("B2", quote=MISS_QUOTE)
                ),
            },
            CASE_CORPUS,
        )
        assert result["total_blockers"] == 2
        assert result["verified"] == 1
        assert result["unverified"] == 1

    def test_substring_quotes_merged(self):
        """分段结构被抹平的转写（两段连成一段）与原单段形成子串关系 → 同组——
        E2E 实证：md 版引文「A 与 B」连成一条，contract 版仅「A」。"""
        flattened = _blocker("B1", quote=f"{HIT_QUOTE} 与 断言\"调试\"菜单保留")  # 两段连成一条
        single = _blocker("B1", quote=HIT_QUOTE)  # 原单段
        result = verify_citations(
            {
                "adversarial_review_m01.md": _review_md(flattened),
                "adversarial_review_m01_contract.md": _review_md(single),
            },
            CASE_CORPUS,
        )
        assert result["total_blockers"] == 1
        assert result["verified"] == 1  # 逐字单段版本命中，整组证实

    def test_unverified_duplicate_files_merged_in_report(self):
        """重复文件的未证实明细：file 字段合并全部来源，只报一次。"""
        body = _blocker("B1", quote=MISS_QUOTE)
        result = verify_citations(
            {
                "adversarial_review_m01.md": _review_md(body),
                "adversarial_review_m01_contract.md": _review_md(body),
            },
            CASE_CORPUS,
        )
        assert result["total_blockers"] == 1
        assert result["unverified"] == 1
        assert len(result["unverified_items"]) == 1
        assert "m01.md" in result["unverified_items"][0]["file"]
        assert "m01_contract.md" in result["unverified_items"][0]["file"]


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

    def test_feature_matrix_included_in_corpus(self, tmp_workspace):
        """feature_matrix.jsonl 必须纳入语料——零覆盖类发现的举证对象就是矩阵。"""
        proj_dir = tmp_workspace / "PROJ-1"
        self._write_jsonl(
            proj_dir / "feature_matrix.jsonl",
            [{"id": "FP-001", "feature": "整机测试队列进样历史列表老化调试的功能点"}],
        )
        proj_dir.joinpath("adversarial_review_m01.md").write_text(
            _review_md(_blocker("B1", quote="整机测试队列进样历史列表老化调试的功能点")),
            encoding="utf-8",
        )
        # 无用例文件时：矩阵本身即构成语料，引文命中矩阵内容 → 已证实
        result = _call(verify_review_citations, project_identifier="PROJ-1")
        assert result["success"] is True
        assert result["verified"] == 1

        # 引文既不在矩阵也不在用例中 → 未证实
        self._write_jsonl(proj_dir / "test_cases_module_01_menu.jsonl", [_case()])
        proj_dir.joinpath("adversarial_review_m01.md").write_text(
            _review_md(_blocker("B1", quote="完全不存在于任何文件的引文内容片段")),
            encoding="utf-8",
        )
        result = _call(verify_review_citations, project_identifier="PROJ-1")
        assert result["success"] is True
        assert result["unverified"] == 1
        assert result["unverified_items"][0]["reason"] == "not_found"

    def test_no_review_files_fails(self, tmp_workspace):
        proj_dir = tmp_workspace / "PROJ-1"
        self._write_jsonl(proj_dir / "test_cases_module_01_menu.jsonl", [_case()])

        result = _call(verify_review_citations, project_identifier="PROJ-1")

        assert result["success"] is False
        assert "adversarial_review_m*.md" in result["error"]

    def test_jsonl_only_reviews_gets_conversion_hint(self, tmp_workspace):
        """目录下只有 JSONL 版评审结果时：报错须分流为「格式转换」指引，
        禁止暗示重新发起评审 task（结果已落盘，重跑是白白返工）。"""
        proj_dir = tmp_workspace / "PROJ-1"
        self._write_jsonl(proj_dir / "test_cases_module_01_menu.jsonl", [_case()])
        self._write_jsonl(
            proj_dir / "adversarial_review_m01.jsonl",
            [{"module": "菜单", "case_number": "TC-PR1-MENU-001", "severity": "blocker"}],
        )

        result = _call(verify_review_citations, project_identifier="PROJ-1")

        assert result["success"] is False
        assert "adversarial_review_m01.jsonl" in result["message"]
        assert "禁止重新发起隔离评审" in result["message"]

    def test_review_jsonl_excluded_from_corpus(self, tmp_workspace):
        """评审 JSONL 不得进入引文搜索空间——否则引文可对评审文件自证，
        反幻觉校验落空（幻觉引文引的是评审文件而非用例）。"""
        proj_dir = tmp_workspace / "PROJ-1"
        self._write_jsonl(proj_dir / "test_cases_module_01_menu.jsonl", [_case()])
        phantom_quote = "仅存在于评审文件中而任何用例都没有的断言片段"
        self._write_jsonl(
            proj_dir / "adversarial_review_m01.jsonl",
            [{"module": "菜单", "severity": "blocker", "quote": phantom_quote}],
        )
        (proj_dir / "adversarial_review_m01.md").write_text(
            _review_md(_blocker("B1", quote=phantom_quote)),
            encoding="utf-8",
        )

        result = _call(verify_review_citations, project_identifier="PROJ-1")

        assert result["success"] is True
        assert result["verified"] == 0
        assert result["unverified"] == 1
        assert result["unverified_items"][0]["reason"] == "not_found"

    def test_missing_dir_fails(self, tmp_workspace):
        result = _call(verify_review_citations, project_identifier="NOPE-9")
        assert result["success"] is False

    def test_review_dir_traversal_rejected(self, tmp_workspace):
        result = _call(verify_review_citations, review_dir="/../outside")
        assert result["success"] is False
        assert "越权" in result["error"]
