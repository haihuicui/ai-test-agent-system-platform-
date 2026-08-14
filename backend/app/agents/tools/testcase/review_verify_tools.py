"""对抗性评审举证校验工具。

Phase 4 隔离评审（adversarial-reviewer 子代理）的阻断发现按输出契约必须携带
「原文」举证——从用例 JSONL 文件中逐字复制的片段。本工具把「举证是否真实」
从人工核实变成确定性校验：

- 扫描会话工作目录下的 adversarial_review_m*.md（仅「🚫 阻断发现」段落）；
- 提取每条发现的原文引文（`- **原文**：` 行）；
- 归一化（去空白 / JSON 转义差异）后在该会话全部用例 JSONL 文本中做子串匹配；
- 匹配失败或缺失引文 → 判定「未证实」——评审 Agent 幻觉举证的典型信号
  （如引用不存在的用例编号、凭记忆复述而非逐字复制）。

主 Agent 在收到子代理摘要后、read_file 整合结果前调用本工具：
未证实的发现不得进入评审报告的阻断清单，降级附录处理并计数说明。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from app.agents.tools.testcase.workspace_paths import session_scope_segments
from app.config.settings import settings

logger = logging.getLogger(__name__)

_WORKSPACE_ROOT = Path(settings.testcase_workspace_root).resolve()

# 评审结果文件名模式（summary 文件 adversarial_review_summary.md 不匹配 m*，天然排除）
_REVIEW_FILE_GLOB = "adversarial_review_m*.md"

# 段落与发现格式（与 adversarial-reviewer 系统提示的结果文件格式契约一一对应）
# 段落标题层级兼容 H1~H3（模型对「阻断发现」段的层级选择不稳定：文件大标题用 H1 时
# 章节自然落到 H2，旧实现写死 H3 导致真实评审文件整段提取失败——E2E 实证）；
# B 头兼容 H3/H4（同一漂移的镜像：段落落 H2 时 B 头自然落 H3——E2E 实证 A4b 失败），
# 故段落边界正则必须排除 ####（负向前瞻），且阻断段内 B 头优先于段落边界匹配，
# 否则 H3 B 头会被误当段落边界重置阻断段状态。
_SECTION_RE = re.compile(r"^#{1,3}\s+(?!#)")
_BLOCKER_SECTION_RE = re.compile(r"^#{1,3}\s+🚫\s*阻断发现")
_FINDING_HEAD_RE = re.compile(r"^#{3,4}\s+(B\d+)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*$")
_QUOTE_RE = re.compile(r"^-\s*\*\*原文\*\*：(.+?)\s*$")

# 引文归一化后的最小字符数：低于此长度不具备举证辨识度，不参与匹配
_MIN_QUOTE_CHARS = 10

# 用例语料排除项（卸载区不是评审输入）
# 注意：feature_matrix.jsonl 不排除——「P0 test_point 零覆盖」类发现的举证对象
# 恰恰是功能矩阵（引 test_points 原文证明无对应用例），排除会导致真实举证被误杀。
_EXCLUDED_DIR_NAMES = {"large_tool_results"}
_EXCLUDED_FILE_NAMES: set[str] = set()

# 评审结果文件自身不得进入引文搜索空间——否则幻觉引文可对评审文件「自证」
# （引文实际引的是评审文件而非用例），反幻觉校验落空。
_EXCLUDED_FILE_PREFIXES = ("adversarial_review_",)

# 反引号包裹的引文片段：子代理多段引用时的自然格式（`"a"` 与 `"b"`）
_BACKTICK_RE = re.compile(r"`([^`]+)`")


def _normalize(text: str) -> str:
    """归一化文本用于引文匹配：抹平 JSON 转义与全部空白差异。

    子代理 read_file 看到的是 JSONL 原始文本（含 \\" \\n 等转义），
    逐字复制时可能做格式清理；两边同构归一后做子串匹配，
    容忍转义差异但仍能识别纯编造的引文。
    """
    text = (
        text.replace('\\"', '"')
        .replace("\\n", "")
        .replace("\\t", "")
        .replace("\\/", "/")
    )
    return re.sub(r"\s+", "", text)


def _split_quotes(raw: str) -> list[str]:
    """把一条「原文」行拆成独立引文片段（纯函数）。

    子代理多段引用时的自然格式是用反引号分别包裹、以「与」/「、」连接
    （如 `` `"result": "保留"` 与 `"result": "不存在"` `` ——矛盾举证本来就
    需要两段都真实存在）。有反引号组时逐组作为独立引文，全部命中才证实；
    无反引号时整行作为一条引文。
    """
    groups = [g.strip() for g in _BACKTICK_RE.findall(raw) if g.strip()]
    return groups if groups else [raw]


def _extract_blocker_quotes(review_text: str) -> list[dict[str, Any]]:
    """从评审结果文件中提取阻断发现的举证引文（纯函数，供工具和测试复用）。

    仅扫描「### 🚫 阻断发现」段落（附录表格、待确认假设段落不含举证义务）；
    每条发现以 `#### B# | 用例编号 | 缺陷类型` 开头，
    其下 `- **原文**：` 行为举证引文（允许多行，每行再按反引号拆段，
    全部通过才算已证实）。
    """
    findings: list[dict[str, Any]] = []
    in_blocker_section = False
    current: dict[str, Any] | None = None

    for line in review_text.splitlines():
        # 阻断段内优先识别 B 头（H3/H4 兼容）——H3 B 头会被 _SECTION_RE 当作
        # 段落边界重置阻断段状态，必须先于段落边界匹配
        if in_blocker_section:
            head = _FINDING_HEAD_RE.match(line)
            if head:
                current = {
                    "finding": head.group(1),
                    "case_ref": head.group(2).strip(),
                    "defect_type": head.group(3).strip(),
                    "quotes": [],
                }
                findings.append(current)
                continue
        if _SECTION_RE.match(line):
            in_blocker_section = bool(_BLOCKER_SECTION_RE.match(line))
            current = None
            continue
        if not in_blocker_section:
            continue
        quote = _QUOTE_RE.match(line)
        if quote and current is not None:
            current["quotes"].extend(_split_quotes(quote.group(1).strip()))
    return findings


def _quotes_overlap(a: set[str], b: set[str]) -> bool:
    """两版本引文集是否指向同一阻断：集合相交，或任一引文互为子串
    （排障转写会把反引号分段结构抹掉——两段连成一段后与原单段形成
    前缀/包含关系，集合交集捕获不到，子串规则兜底）。"""
    if a & b:
        return True
    return any(x in y or y in x for x in a for y in b)


def verify_citations(
    review_texts: dict[str, str],
    case_corpus: str,
) -> dict[str, Any]:
    """校验各评审文件阻断发现的引文是否真实存在于用例语料（纯函数）。

    Args:
        review_texts: {评审文件名: 文件内容}
        case_corpus: 全部用例 JSONL 拼接后的原始文本（未归一化）

    Returns:
        total_blockers / verified / unverified / too_short / no_evidence /
        unverified_items（含文件、发现号、涉及用例、引文预览、原因）

    跨文件去重：排障过程中产生的副本文件（如 *_contract.md）会让同一阻断
    在多个文件中重复出现，而副本间引文常有删节差异（E2E 实证：5 模块 12 条
    阻断因副本被重复计为 24 条）。合并规则：同 (用例编号, 缺陷类型) 且
    **引文集重叠**（集合相交，或任一引文互为子串——删节与分段结构抹平两种
    典型形态，见 _quotes_overlap）的版本视为同一阻断合并计数，任一版本
    引文全部命中即证实；引文无重叠的版本是各自独立的阻断
    （同用例同缺陷类型可存在多条不同缺陷点的发现，不得误并）。
    """
    corpus = _normalize(case_corpus)

    # 第一遍：各文件版本独立校验
    all_versions: list[dict[str, Any]] = []
    for file_name, text in sorted(review_texts.items()):
        for f in _extract_blocker_quotes(text):
            failures: list[dict[str, Any]] = []
            if not f["quotes"]:
                failures.append({
                    "reason": "no_evidence",
                    "quote_preview": "",
                })
            for quote in f["quotes"]:
                norm_quote = _normalize(quote)
                if len(norm_quote) < _MIN_QUOTE_CHARS:
                    failures.append({"reason": "too_short", "quote_preview": quote[:60]})
                elif norm_quote not in corpus:
                    failures.append({"reason": "not_found", "quote_preview": quote[:60]})
            all_versions.append({
                "file": file_name,
                "finding": f["finding"],
                "case_ref": f["case_ref"],
                "defect_type": f["defect_type"],
                "norm_quotes": {_normalize(q) for q in f["quotes"]},
                "failures": failures,
            })

    # 第二遍：同 (用例编号, 缺陷类型) 内按引文集交集做连通分量合并
    groups: list[list[dict[str, Any]]] = []
    for v in all_versions:
        intersecting = [
            i for i, g in enumerate(groups)
            if g[0]["case_ref"] == v["case_ref"]
            and g[0]["defect_type"] == v["defect_type"]
            and any(_quotes_overlap(v["norm_quotes"], member["norm_quotes"]) for member in g)
        ]
        if not intersecting:
            groups.append([v])
            continue
        # 与多个组相交时把它们并成一组（传递连通）
        target = intersecting[0]
        groups[target].append(v)
        for i in reversed(intersecting[1:]):
            groups[target].extend(groups.pop(i))

    # 第三遍：按组聚合——组内任一版本全引文命中即证实
    total = verified = unverified = too_short = no_evidence = 0
    unverified_items: list[dict[str, Any]] = []
    for versions in groups:
        total += 1
        if any(not v["failures"] for v in versions):
            verified += 1
            continue
        unverified += 1
        # 未证实：取失败最少的版本作为代表明细，文件字段合并全部来源
        representative = min(versions, key=lambda v: len(v["failures"]))
        files = "、".join(dict.fromkeys(v["file"] for v in versions))
        for failure in representative["failures"]:
            if failure["reason"] == "too_short":
                too_short += 1
            elif failure["reason"] == "no_evidence":
                no_evidence += 1
            unverified_items.append({
                "file": files,
                "finding": representative["finding"],
                "case_ref": representative["case_ref"],
                "defect_type": representative["defect_type"],
                "reason": failure["reason"],
                "quote_preview": failure["quote_preview"],
            })

    return {
        "total_blockers": total,
        "verified": verified,
        "unverified": unverified,
        "too_short": too_short,
        "no_evidence": no_evidence,
        "unverified_items": unverified_items,
    }


def _load_case_corpus(scan_dir: Path) -> tuple[str, list[str], list[str]]:
    """读取扫描目录下全部 JSONL（含 feature_matrix.jsonl），拼接为原始语料。

    语料 = 子代理在评审任务中可能引用的一切输入文件：用例 JSONL + 功能矩阵。
    """
    warnings: list[str] = []
    sources: list[str] = []
    parts: list[str] = []
    for path in sorted(scan_dir.rglob("*.jsonl")):
        if _EXCLUDED_DIR_NAMES.intersection(path.parts):
            continue
        if path.name in _EXCLUDED_FILE_NAMES:
            continue
        if path.name.startswith(_EXCLUDED_FILE_PREFIXES):
            continue
        try:
            parts.append(path.read_text(encoding="utf-8"))
            sources.append(str(path))
        except Exception as e:
            warnings.append(f"读取用例文件失败：{path}（{e}）")
    return "\n".join(parts), sources, warnings


@tool
async def verify_review_citations(
    project_identifier: str = "",
    review_dir: str = "",
) -> dict[str, Any]:
    """校验对抗性评审阻断发现的举证引文是否真实存在于用例文件中。

    Phase 4 隔离评审结果整合的**第一步**（收到 adversarial-reviewer 摘要后、
    read_file 逐模块整合前）调用。阻断发现的「原文」举证必须能在本次
    Phase 3 生成的用例 JSONL 中找到（归一化子串匹配）：
    - 找不到 / 缺失引文 / 引文过短 → 判定「未证实」（幻觉举证信号），
      该发现不得进入评审报告阻断清单，降级附录并在报告中计数说明；
    - 全部通过 → 按契约整合阻断清单。

    Args:
        project_identifier: 项目标识符（与 save_feature_matrix_tool 传入的一致）。
        review_dir: 评审结果文件所在目录（Agent 虚拟路径，即「会话工作目录」，
            形如 /<项目>/<会话ID>/）。不传时按当前会话作用域自动定位。

    Returns:
        {
          "success": bool,
          "review_files": [...],        # 扫描到的评审结果文件
          "case_files_used": [...],     # 参与匹配的用例 JSONL
          "total_blockers": int,        # 阻断发现总数
          "verified": int,              # 引文全部命中的发现数
          "unverified": int,            # 未证实发现数（含缺引文/过短/未命中）
          "unverified_items": [ {file, finding, case_ref, defect_type, reason, quote_preview} ],
          "warnings": [...],
          "message": str,
          "error": str                  # 仅失败时
        }
    """
    if review_dir:
        raw = Path(review_dir)
        parts = raw.parts[1:] if raw.anchor else raw.parts
        scan_dir = (_WORKSPACE_ROOT / Path(*parts)).resolve()
        if not scan_dir.is_relative_to(_WORKSPACE_ROOT):
            return {
                "success": False,
                "error": f"评审目录越权：{review_dir} 解析后超出工作目录 {_WORKSPACE_ROOT}",
            }
    else:
        project, thread = session_scope_segments(project_identifier)
        scan_dir = _WORKSPACE_ROOT
        if project:
            scan_dir = scan_dir / project
            if thread:
                scan_dir = scan_dir / thread

    if not scan_dir.is_dir():
        return {
            "success": False,
            "error": f"评审目录不存在：{scan_dir}",
            "message": (
                "未找到评审结果目录。请确认 adversarial-reviewer 子代理已按契约 "
                "将会话工作目录写入 adversarial_review_m*.md，或通过 review_dir 显式指定。"
            ),
        }

    review_files = sorted(scan_dir.glob(_REVIEW_FILE_GLOB))
    if not review_files:
        # 报错分流：目录下可能已有 JSONL 格式的评审结果（主 Agent 发起评审 task 时
        # 未按 .md 契约指定输出格式的常见后果）——此时重新发起评审是白白返工，
        # 正确动作是把既有结果转换为 .md 契约格式。
        jsonl_reviews = sorted(scan_dir.glob("adversarial_review_*.jsonl"))
        if jsonl_reviews:
            names = "、".join(p.name for p in jsonl_reviews[:6])
            return {
                "success": False,
                "error": f"目录 {scan_dir} 下未找到 adversarial_review_m*.md",
                "message": (
                    f"发现 JSONL 格式的评审结果（{names}），但举证校验要求 .md 契约格式。"
                    "评审结果已落盘，**禁止重新发起隔离评审 task**——请用 read_file 读取 "
                    "JSONL 结果，按 .md 契约转换后用 write_file 写入同名 .md 文件："
                    "阻断发现段落标题 `## 🚫 阻断发现`（H2/H3 均可），"
                    "每条发现以 `#### B# | 用例编号 | 缺陷类型` 开头（H4），"
                    "其下 `- **原文**：` 行放从用例 JSONL 逐字复制的引文。"
                ),
            }
        return {
            "success": False,
            "error": f"目录 {scan_dir} 下未找到 adversarial_review_m*.md",
            "message": (
                "评审结果文件缺失。请按 Skill 指引按模块拆分后重新发起隔离评审 task "
                "（每次只审 1~2 个模块，输出契约明确为 .md 格式），禁止原样整体重试。"
            ),
        }

    warnings: list[str] = []
    review_texts: dict[str, str] = {}
    for path in review_files:
        try:
            review_texts[path.name] = path.read_text(encoding="utf-8")
        except Exception as e:
            warnings.append(f"读取评审文件失败：{path}（{e}）")

    corpus, case_sources, case_warnings = _load_case_corpus(scan_dir)
    warnings.extend(case_warnings)
    if not corpus.strip():
        return {
            "success": False,
            "error": "未找到任何用例 JSONL 文件作为校验语料",
            "warnings": warnings,
            "message": "请确认 Phase 3 已将用例写入会话工作目录。",
        }

    result = verify_citations(review_texts, corpus)

    if result["total_blockers"] == 0:
        warnings.append(
            "未提取到任何阻断发现举证——若评审文件声称存在阻断发现，"
            "请核对其结果文件是否符合格式契约：阻断发现段落标题 `## 🚫 阻断发现`"
            "（H2/H3 均可，但必须带 🚫 与「阻断发现」字样），"
            "每条发现以 `#### B# | 用例 | 类型` 开头（H4，B 后数字），"
            "其下须有 `- **原文**：` 引文行（全角冒号）。"
        )

    return {
        "success": True,
        "review_files": [str(p) for p in review_files],
        "case_files_used": case_sources,
        "warnings": warnings,
        **result,
        "message": (
            f"举证校验完成：阻断发现 {result['total_blockers']} 条，"
            f"已证实 {result['verified']} 条，未证实 {result['unverified']} 条"
            "（明细见 unverified_items 的 reason：no_evidence=缺引文 / "
            "too_short=引文过短 / not_found=引文未命中用例文件）。"
            "未证实发现不得进入阻断清单——整合时降级附录并在评审报告中计数说明；"
            "已证实发现按契约逐条渲染进阻断清单。"
        ),
    }
