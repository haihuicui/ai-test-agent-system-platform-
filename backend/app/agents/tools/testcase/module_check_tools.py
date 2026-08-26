"""模块级用例自检与离线 manifest 工具。

为测试用例生成 Agent 提供两个能力：
1. `module_self_check_tool`：在单个模块设计完成后做确定性轻量自检。
2. `save_test_case_manifest_tool`：当后端 API 不可用时，记录已保存 JSONL 的导入状态。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from app.agents.tools.testcase.coverage_tools import (
    compute_module_test_point_coverage,
)
from app.agents.tools.testcase.excel_tools import (
    _parse_json_objects,
    _resolve_input_path,
    _to_virtual_path,
)
from app.agents.tools.testcase.feature_matrix_tools import load_feature_matrix
from app.agents.tools.testcase.workspace_paths import apply_session_scope
from app.config.settings import settings
from app.utils.testcase_validation import _validate_case, normalize_case_type

logger = logging.getLogger(__name__)

_WORKSPACE_ROOT = Path(settings.testcase_workspace_root).resolve()

# 优先级 -> P0/P1/P2/P3 映射（兼容 agent 输出中可能直接出现的 P0/P1/P2/P3）
_PRIORITY_TO_LEVEL = {
    "critical": "P0",
    "high": "P1",
    "medium": "P2",
    "low": "P3",
    "P0": "P0",
    "P1": "P1",
    "P2": "P2",
    "P3": "P3",
}

# 原子性启发式：结果描述中出现这些连接词，可能把多个检查点写在了一步里
_ATOMICITY_HINT_WORDS = {"且", "同时", "分别", "以及"}

# Happy Path 偏斜检测：预期结果中频繁出现这些模式时，可能缺少边界/异常覆盖
_HAPPY_PATH_PATTERNS = (
    "保存成功", "添加成功", "创建成功", "操作成功", "显示正确",
    "回显正确", "刷新成功", "返回成功", "跳转成功", "提交成功",
    "加载成功", "导入成功", "导出成功", "删除成功", "修改成功",
    "正常显示", "正常跳转", "正常工作", "正常返回", "正常加载",
)


def _resolve_manifest_path(manifest_path: str) -> Path:
    """将 manifest 路径解析到 workspace_root 下，禁止越权。

    纯文件名/项目前缀路径自动隔离到当前会话目录 <project>/<thread_id>/，
    避免 manifest 落在 workspace 根目录被所有项目/会话共享互相覆盖。
    """
    raw = Path(manifest_path)

    if raw.anchor:
        try:
            if raw.is_absolute() and raw.resolve().is_relative_to(_WORKSPACE_ROOT):
                return raw.resolve()
        except (ValueError, OSError):
            pass
        anchor_len = len(Path(raw.anchor).parts)
        rel = Path(*raw.parts[anchor_len:]) if len(raw.parts) > anchor_len else Path()
    else:
        rel = raw

    if not rel.parts:
        raise ValueError(f"manifest 路径无效：{manifest_path}")

    rel = apply_session_scope(rel)

    resolved = (_WORKSPACE_ROOT / rel).resolve()
    if not resolved.is_relative_to(_WORKSPACE_ROOT):
        raise ValueError(
            f"manifest 路径越权：{manifest_path} 解析后超出工作目录 {_WORKSPACE_ROOT}"
        )
    return resolved


def _load_cases_from_file(path: str) -> list[dict[str, Any]]:
    """读取单个用例数据文件并返回用例对象列表。"""
    real_path = _resolve_input_path(path)
    if not real_path.is_file():
        raise FileNotFoundError(f"用例数据文件不存在：{path}（真实路径：{real_path}）")

    text = real_path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    cases = _parse_json_objects(text, str(path))
    invalid = [i for i, c in enumerate(cases) if not isinstance(c, dict)]
    if invalid:
        raise ValueError(
            f"用例数据文件存在非对象元素（下标 {invalid[:5]}...），每条用例必须是 JSON 对象。"
        )
    return cases  # type: ignore[return-value]


def _case_number_key(case: dict[str, Any]) -> Any:
    """提取用例编号作为去重/一致性 key；没有编号时返回 None。"""
    number = case.get("case_number") or case.get("case_id")
    return number if number else None


# ── _collect_existing_case_numbers 缓存 ──
# 大部分模块自检发生在同一对话内，JSONL 文件不会频繁变化。
# 缓存在文件 mtime 不变时复用，避免每次 rglob 全量扫描并解析所有 JSONL。
_scan_cache: dict[str, tuple[float, set[Any]]] = {}  # file_path_str -> (mtime, case_numbers)


def _collect_existing_case_numbers(
    current_files: set[Path],
) -> set[Any]:
    """扫描工作区中除当前文件外的其他用例数据文件，收集已有用例编号。

    通过文件 mtime 做缓存失效：同一文件在 mtime 未变时复用已解析结果。
    """
    existing_numbers: set[Any] = set()
    for f in _WORKSPACE_ROOT.rglob("*.jsonl"):
        if f.resolve() in current_files:
            continue
        try:
            cache_key = str(f.resolve())
            mtime = f.stat().st_mtime
            cached = _scan_cache.get(cache_key)
            if cached is not None and cached[0] == mtime:
                existing_numbers.update(cached[1])
                continue

            text = f.read_text(encoding="utf-8").strip()
            if not text:
                _scan_cache[cache_key] = (mtime, set())
                continue

            numbers: set[Any] = set()
            for case in _parse_json_objects(text, str(f)):
                if isinstance(case, dict):
                    key = _case_number_key(case)
                    if key is not None:
                        numbers.add(key)
            _scan_cache[cache_key] = (mtime, numbers)
            existing_numbers.update(numbers)
        except Exception:
            logger.warning("扫描已有用例文件失败：%s", f, exc_info=True)
    return existing_numbers


def _check_atomicity_heuristic(case: dict[str, Any]) -> list[str]:
    """启发式检查单条用例是否在一个步骤里堆砌多个检查点。"""
    warnings: list[str] = []
    steps = case.get("test_case_steps") or []
    if not isinstance(steps, list):
        return warnings

    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        result = str(step.get("result") or "")
        if not result:
            continue

        # 命中明显的连接词，提示可能包含多个判定点
        hits = [w for w in _ATOMICITY_HINT_WORDS if w in result]
        if hits:
            warnings.append(
                f"第 {idx} 步预期结果包含连接词 {hits}，可能同时描述了多个检查点，"
                "建议拆分为单检查点用例"
            )

    return warnings


def _check_happy_path_skew(cases: list[dict[str, Any]]) -> dict[str, Any] | None:
    """检测本批次用例是否存在 Happy Path 偏斜（缺少边界/异常覆盖）。

    启发式：如果本批次 ≥ 3 条用例且 ≥ 80% 的预期结果包含
    "xxx成功"/"正常xxx" 等纯正向模式，则提示可能缺少边界/异常用例。

    Returns:
        若触发偏斜则返回 violation dict（level=warning），否则返回 None。
    """
    if len(cases) < 3:
        return None

    happy_count = 0
    for case in cases:
        steps = case.get("test_case_steps") or []
        if not isinstance(steps, list):
            continue
        all_results = " ".join(
            str(s.get("result", "")) for s in steps if isinstance(s, dict)
        )
        # 也检查顶层 expected_result（如果有）
        top_expected = (
            case.get("expected_result")
            or case.get("expected")
            or case.get("预期结果")
        )
        if top_expected is not None:
            all_results += " " + str(top_expected)

        if any(p in all_results for p in _HAPPY_PATH_PATTERNS):
            happy_count += 1

    ratio = happy_count / len(cases)
    if ratio >= 0.8:
        return {
            "case_number": None,
            "case_name": None,
            "level": "warning",
            "messages": [
                f"本批次 {len(cases)} 条用例中 {happy_count} 条（{ratio:.0%}）预期结果以正向验证为主"
                "（如「保存成功」「正常显示」），建议至少补充 1 条边界值或异常输入用例。"
                "若本模块功能点确无边界值场景（如纯流程跳转），可忽略此提示。"
            ],
        }
    return None


def _priority_to_level(priority: Any) -> str | None:
    """把各种 priority 表示统一成 P0/P1/P2/P3。"""
    if not isinstance(priority, str):
        return None
    return _PRIORITY_TO_LEVEL.get(priority.strip().lower())


def _perform_module_self_check(
    cases: list[dict[str, Any]],
    expected_module: str,
    current_file_paths: set[Path] | None = None,
    min_p0_count: int = 3,
    check_cross_file_duplicates: bool = True,
    matrix_features: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    对内存中的用例列表执行模块级自检。

    本函数与文件读取解耦，供 ``module_self_check_tool`` 和
    ``ModuleSelfCheckMiddleware`` 复用，保证同一套规则。

    Args:
        check_cross_file_duplicates: 是否扫描工作区其他文件检查编号跨文件重复。
            中间件场景不掌握文件路径，可设为 False 避免误报。
        matrix_features: Phase 1 功能矩阵的功能点列表。传入时执行矩阵覆盖
            对照（第 8 节）；为 None 时跳过（中间件等不掌握矩阵的场景，
            行为与旧版一致）。
    """
    current_file_paths = current_file_paths or set()
    violations: list[dict[str, Any]] = []

    # 1. 复用核心质量红线校验
    for case in cases:
        core = _validate_case(case)
        if core:
            violations.append(
                {
                    "case_number": case.get("case_number") or case.get("case_id"),
                    "case_name": case.get("name"),
                    "level": "error",
                    "messages": core,
                }
            )

    # 2. 模块一致性
    for case in cases:
        module = case.get("module")
        if module != expected_module:
            violations.append(
                {
                    "case_number": case.get("case_number") or case.get("case_id"),
                    "case_name": case.get("name"),
                    "level": "error",
                    "messages": [
                        f"模块归属不一致：期望 '{expected_module}'，实际 '{module}'"
                    ],
                }
            )

    # 3. 编号唯一性（本文件内 + 已保存的其他文件）
    seen_numbers: set[Any] = set()
    for case in cases:
        number = _case_number_key(case)
        if number is None:
            continue
        if number in seen_numbers:
            violations.append(
                {
                    "case_number": number,
                    "case_name": case.get("name"),
                    "level": "error",
                    "messages": [f"用例编号 `{number}` 在当前模块内重复"],
                }
            )
        seen_numbers.add(number)

    if check_cross_file_duplicates:
        existing_numbers = _collect_existing_case_numbers(current_file_paths)
        for case in cases:
            number = _case_number_key(case)
            if number is None:
                continue
            if number in existing_numbers:
                violations.append(
                    {
                        "case_number": number,
                        "case_name": case.get("name"),
                        "level": "error",
                        "messages": [f"用例编号 `{number}` 与已保存的其他模块用例重复"],
                    }
                )

    # 4. 优先级分布
    p0_count = sum(
        1
        for case in cases
        if _priority_to_level(case.get("priority")) == "P0"
    )
    if p0_count < min_p0_count:
        violations.append(
            {
                "case_number": None,
                "case_name": None,
                "level": "warning",
                "messages": [
                    f"P0 用例数量偏少：当前 {p0_count} 条，建议不少于 {min_p0_count} 条"
                ],
            }
        )

    # 5. 原子性启发式（仅 warning，不阻塞）
    for case in cases:
        atomic_warnings = _check_atomicity_heuristic(case)
        if atomic_warnings:
            violations.append(
                {
                    "case_number": case.get("case_number") or case.get("case_id"),
                    "case_name": case.get("name"),
                    "level": "warning",
                    "messages": atomic_warnings,
                }
            )

    # 6. case_type 枚举校验（仅 warning，不阻断）
    # LLM 常输出 interface/接口/UI 等非 TestCaseType 枚举值；入库层虽已做
    # 自动映射兜底，但在模块自检阶段提示可促使模型把源文件修正为合法枚举。
    for case in cases:
        raw_type = case.get("case_type")
        if not isinstance(raw_type, str) or not raw_type.strip():
            continue
        normalized_type, type_changed = normalize_case_type(raw_type)
        if type_changed:
            violations.append(
                {
                    "case_number": case.get("case_number") or case.get("case_id"),
                    "case_name": case.get("name"),
                    "level": "warning",
                    "messages": [
                        f"case_type '{raw_type}' 非合法枚举，入库时将自动映射为 "
                        f"'{normalized_type}'（合法值：functional/security/performance/"
                        "compatibility/regression/smoke_sanity/acceptance/accessibility/"
                        "destructive/usability/other；接口测试请用 functional），"
                        "建议直接在文件中修正"
                    ],
                }
            )

    # 7. Happy Path 偏斜检测（仅 warning，不阻断）
    # 当一批用例的预期结果全是"xxx成功"/"正常xxx"时，提示可能缺少边界/异常覆盖
    happy_path_violation = _check_happy_path_skew(cases)
    if happy_path_violation is not None:
        violations.append(happy_path_violation)

    # 8. 功能矩阵覆盖对照（仅显式传入 matrix_features 时执行）
    # Phase 3 每模块 checkpoint 的确定性密度防线：SKILL 虽要求逐 test_point
    # 对照，但无 enforcement 时会被上下文压缩漂移（多需求合并成大文档后
    # 单功能点深度塌缩的根因之一）。
    # 分级策略：
    # - FP 级零覆盖（无任何用例归属）→ error：信号可靠（连模糊匹配都不命中
    #   基本是真没设计），直接拦截，防住塌缩的最严重形态；
    # - test_point 级未命中 → warning：test_point 为自由文本，用例措辞差异
    #   导致的误报代价高（会打断模块推进），留痕由模型自证或人工确认。
    matrix_checked = False
    if matrix_features:
        matrix_checked = True
        module_fps = [
            fp
            for fp in matrix_features
            if str(fp.get("module") or "").strip() == expected_module
        ]
        if not module_fps:
            violations.append(
                {
                    "case_number": None,
                    "case_name": None,
                    "level": "warning",
                    "messages": [
                        f"功能矩阵中未找到模块 '{expected_module}' 的功能点记录，"
                        "覆盖对照未执行。可能是矩阵属于其他需求（历史遗留）或模块命名"
                        "不一致，请确认当前会话的 feature_matrix.jsonl 内容"
                    ],
                }
            )
        else:
            cov_rows = compute_module_test_point_coverage(module_fps, cases)
            reported_uncovered_fp: set[str] = set()
            for row in cov_rows:
                fp_key = str(row["fp_id"])
                if row["fp_match_type"] is None:
                    if fp_key in reported_uncovered_fp:
                        continue
                    reported_uncovered_fp.add(fp_key)
                    violations.append(
                        {
                            "case_number": None,
                            "case_name": None,
                            "level": "error",
                            "messages": [
                                f"功能点 {row['fp_id']}（{row['feature']}，"
                                f"{row['priority']}）零用例覆盖：未在任何用例中发现"
                                "其编号引用或足够的文本重叠。请补充覆盖该功能点的用例"
                                "（在用例 remarks 中标注 FP 编号可消除匹配歧义），"
                                "或确认该功能点不属于本模块"
                            ],
                        }
                    )
                elif not row["covered"] and row["test_point"]:
                    violations.append(
                        {
                            "case_number": None,
                            "case_name": None,
                            "level": "warning",
                            "messages": [
                                f"功能点 {row['fp_id']}（{row['feature']}）的测试点"
                                f"疑似未覆盖：「{row['test_point']}」未在归属用例"
                                f"（{', '.join(row['case_numbers'][:3]) or '无'}）的文本"
                                "中体现。请确认已有用例覆盖了该测试点（在用例步骤/"
                                "预期结果中显式描述），或补充对应用例"
                            ],
                        }
                    )

    errors = [v for v in violations if v.get("level") == "error"]
    warnings = [v for v in violations if v.get("level") == "warning"]
    passed = len(errors) == 0

    summary_parts = [f"共检查 {len(cases)} 条用例，P0 {p0_count} 条"]
    if matrix_checked:
        summary_parts.append("已对照功能矩阵做覆盖核对")
    if errors:
        summary_parts.append(f"发现 {len(errors)} 个错误")
    if warnings:
        summary_parts.append(f"发现 {len(warnings)} 个警告")
    if passed:
        summary_parts.append("自检通过")
    else:
        summary_parts.append("请修正错误后重新自检")

    return {
        "passed": passed,
        "total": len(cases),
        "p0_count": p0_count,
        "matrix_checked": matrix_checked,
        "violations": violations,
        "summary": "；".join(summary_parts),
    }


def _resolve_case_file_path(file_path: str) -> Path:
    """将用例文件路径解析到 workspace_root 下，禁止越权。

    纯文件名/项目前缀路径自动隔离到当前会话目录 <project>/<thread_id>/，
    同项目并发会话的模块用例文件互不覆盖；已含会话前缀的路径幂等保留。
    """
    raw = Path(file_path)

    if raw.anchor:
        try:
            if raw.is_absolute() and raw.resolve().is_relative_to(_WORKSPACE_ROOT):
                return raw.resolve()
        except (ValueError, OSError):
            pass
        anchor_len = len(Path(raw.anchor).parts)
        rel = Path(*raw.parts[anchor_len:]) if len(raw.parts) > anchor_len else Path()
    else:
        rel = raw

    if not rel.parts:
        raise ValueError(f"用例文件路径无效：{file_path}")

    rel = apply_session_scope(rel)

    resolved = (_WORKSPACE_ROOT / rel).resolve()
    if not resolved.is_relative_to(_WORKSPACE_ROOT):
        raise ValueError(
            f"用例文件路径越权：{file_path} 解析后超出工作目录 {_WORKSPACE_ROOT}"
        )
    return resolved


def _classify_parse_failure(error: ValueError, text: str) -> dict[str, Any]:
    """把 JSONL 解析失败分类为「输出截断」或「语法错误」，给出针对性指引。

    背景（thread 6f08f7ab 实证）：
    - 单次序列化过多用例撞输出上限 → 内容尾部断弦（Unterminated string），
      通用报错让模型靠试错才收敛到分批；
    - 模型生成未转义双引号等非法 JSON → 通用报错缺少修复方向。

    _parse_json_objects 抛出的 ValueError 附带 parsed_count/fail_offset 等
    诊断属性；旧路径（无属性）回落通用文案，行为与此前一致。
    """
    parsed_count = getattr(error, "parsed_count", None)
    if parsed_count is None:
        return {
            "success": False,
            "error": str(error),
            "message": f"保存失败：用例内容不是合法 JSONL/JSON：{error}",
        }

    json_error = getattr(error, "json_error", "") or ""
    fail_offset = getattr(error, "fail_offset", 0) or 0
    text_length = getattr(error, "text_length", len(text)) or len(text)

    # 截断特征：Unterminated string（字符串没写完就断了），或断裂点在内容
    # 尾部 20% 且全文不以闭合括号收尾——均为「单次输出超长被截断」的典型指纹
    is_truncated = "Unterminated string" in json_error or (
        text_length > 0
        and fail_offset >= 0.8 * text_length
        and not text.rstrip().endswith(("}", "]"))
    )

    if is_truncated:
        return {
            "success": False,
            "error": str(error),
            "error_type": "truncated",
            "parsed_count": parsed_count,
            "message": (
                f"保存失败：内容在第 {parsed_count} 条用例之后被输出长度上限截断"
                f"（第 {parsed_count + 1} 条 JSON 不完整），本次未写入任何内容。"
                "这是单次序列化用例过多导致的。请改为分批保存：每次 "
                "save_test_cases_file 调用不超过 10 条用例，从第 "
                f"{parsed_count + 1} 条起重发；分批写入多个分片文件"
                "（如 test_cases_module_01_p1.jsonl、_p2.jsonl），"
                "后续导出/入库时把分片文件清单一并传给 input_file 即可。"
            ),
        }

    return {
        "success": False,
        "error": str(error),
        "error_type": "invalid_json",
        "parsed_count": parsed_count,
        "message": (
            f"保存失败：第 {parsed_count + 1} 条用例附近 JSON 语法错误"
            f"（{json_error}）。最常见原因是字符串值内含未转义的英文双引号"
            "——请改为中文引号「」或转义为 \\\"。本次未写入任何内容，"
            "请修正后重发（建议每批不超过 10 条）。"
        ),
    }


@tool
async def save_test_cases_file(file_path: str, content: str) -> dict[str, Any]:
    """
    保存用例 JSONL 文件（覆盖写入 + 解析校验 + 格式规范化）。

    用于 Phase 3 保存或整体重写模块用例文件。与通用 write_file 的区别：
    - **允许覆盖已存在文件**：历史会话遗留的同名文件直接替换，
      无需逐行 edit（也避免了同一文件多次并行 edit 的写入竞争）
    - 写入前解析全部用例（容错 JSONL/JSON 数组/脏拼接），解析失败拒绝写入
    - 写入时规范化为标准 JSONL（每行一个 JSON 对象），消除脏格式
    - 逐条执行质量红线快检并返回 violations（不阻塞写入，供自检参考）

    Args:
        file_path: 用例文件路径（工作目录下的相对/虚拟路径，如
            "/PR-2/test_cases_module_01.jsonl"）
        content: 用例内容（JSONL，每行一条用例；也兼容 JSON 数组）

    Returns:
        {"success": bool, "file_path": "...", "cases_count": int,
         "violations": [...], "message": "..."}
    """
    try:
        resolved = _resolve_case_file_path(file_path)
    except ValueError as e:
        return {"success": False, "error": str(e), "message": str(e)}

    text = (content or "").strip()
    if not text:
        return {
            "success": False,
            "error": "内容为空",
            "message": "保存失败：content 为空，未写入任何内容",
        }

    # 解析校验（复用容错解析器）；解析失败拒绝写入，防止截断/脏数据落盘
    try:
        cases = _parse_json_objects(text, file_path)
    except ValueError as e:
        return _classify_parse_failure(e, text)

    invalid = [i for i, c in enumerate(cases) if not isinstance(c, dict)]
    if invalid:
        return {
            "success": False,
            "error": f"存在非对象元素（下标 {invalid[:5]}）",
            "message": "保存失败：每条用例必须是 JSON 对象",
        }

    # 规范化为标准 JSONL（每行一个对象）
    normalized = "\n".join(
        json.dumps(c, ensure_ascii=False) for c in cases
    )
    overwritten = resolved.exists()
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(normalized + "\n", encoding="utf-8")
    except OSError as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"保存失败：写入文件出错：{e}",
        }

    # 质量红线快检（不阻塞写入；正式门禁由 module_self_check_tool 执行）
    violations = []
    for case in cases:
        errors = _validate_case(case)
        if errors:
            violations.append(
                {
                    "case_number": case.get("case_number") or case.get("case_id"),
                    "name": case.get("name"),
                    "messages": errors,
                }
            )

    message = (
        f"已保存 {len(cases)} 条用例到 {file_path}"
        + ("（覆盖了已存在的同名文件）" if overwritten else "")
    )
    if violations:
        message += f"；{len(violations)} 条用例未通过质量红线快检（见 violations）"

    return {
        "success": True,
        "file_path": str(resolved),
        "read_path": _to_virtual_path(resolved),
        "cases_count": len(cases),
        "violations": violations[:20],
        "message": message,
    }


@tool
async def module_self_check_tool(
    input_files: list[str],
    expected_module: str,
    min_p0_count: int = 3,
    project_identifier: str = "",
) -> dict[str, Any]:
    """
    对单个模块的用例数据文件做轻量自检。

    在 Phase 3 每完成一个模块后调用，确认低级质量问题（编号、模块、数据、
    预期结果、原子性、优先级）已被拦截，通过后再进入下一模块。

    编号唯一性只校验**当前批次内部**；与历史会话遗留文件或系统库中已有
    编号重复不是错误（统一入库时按 case_number 去重），无需为规避重复
    而发明特殊编号段或更换编号格式。

    Args:
        input_files: 该模块的用例数据文件路径（.jsonl/.json），可传多个。
        expected_module: 期望的模块名称，用于校验 module 字段一致性。
        min_p0_count: 该模块最少 P0 用例数（critical 映射为 P0）。
        project_identifier: 项目标识符。**传入时会加载 Phase 1 保存的功能矩阵，
            对本模块功能点做确定性覆盖对照**——功能点零用例覆盖将判 error
            拦截，测试点疑似未覆盖给出 warning；不传则跳过矩阵对照。

    Returns:
        {
          "passed": bool,
          "total": int,
          "p0_count": int,
          "matrix_checked": bool,   # 是否执行了功能矩阵覆盖对照
          "violations": [
            {"case_number": "...", "case_name": "...", "level": "error|warning",
             "messages": ["..."]}
          ],
          "summary": "..."
        }
    """
    try:
        current_file_paths: set[Path] = set()
        cases: list[dict[str, Any]] = []
        for path in input_files:
            real_path = _resolve_input_path(path)
            current_file_paths.add(real_path.resolve())
            cases.extend(_load_cases_from_file(path))
    except Exception as e:
        return {
            "passed": False,
            "total": 0,
            "p0_count": 0,
            "matrix_checked": False,
            "violations": [
                {
                    "case_number": None,
                    "case_name": None,
                    "level": "error",
                    "messages": [f"读取用例数据文件失败：{e}"],
                }
            ],
            "summary": f"自检异常：{e}",
        }

    # 矩阵覆盖对照：矩阵不可用时（Phase 1 被跳过/保存失败）降级为跳过对照，
    # 不阻塞其余校验；matrix_checked=False 提示模型在报告中自行标注。
    matrix_features: list[dict[str, Any]] | None = None
    matrix_note = ""
    if project_identifier.strip():
        matrix = load_feature_matrix(project_identifier=project_identifier)
        if matrix.get("success"):
            matrix_features = matrix["features"]
        else:
            matrix_note = (
                f"[无结构化矩阵] 功能矩阵不可用（{matrix.get('error')}），"
                "覆盖对照未执行，其余校验不受影响"
            )

    result = _perform_module_self_check(
        cases=cases,
        expected_module=expected_module,
        current_file_paths=current_file_paths,
        min_p0_count=min_p0_count,
        # 不做全工作区跨文件查重：工作区保留所有历史会话的用例文件，
        # 新会话编号与历史文件重复是预期行为（统一入库时按 case_number
        # 去重兜底），扫描只会制造"编号冲突"误报并诱发编号迁移螺旋。
        # 编号唯一性仍校验当前批次内部（见 _perform_module_self_check 第 3 节）。
        check_cross_file_duplicates=False,
        matrix_features=matrix_features,
    )
    if matrix_note:
        result["summary"] = f"{result['summary']}；{matrix_note}"
    return result


@tool
async def save_test_case_manifest_tool(
    project_identifier: str,
    entries: list[dict[str, Any]],
    manifest_path: str = "test_case_manifest.json",
) -> dict[str, Any]:
    """
    更新测试用例离线 manifest。

    当后端 API 不可用时，用本工具记录哪些 JSONL 文件尚未导入系统，便于后续一键导入。

    Args:
        project_identifier: 当前项目标识符。
        entries: 要新增或更新的模块记录，每条建议包含：
                 module, file, count, persisted, pending_import。
        manifest_path: manifest 文件路径，默认 test_case_manifest.json。

    Returns:
        {"success": bool, "manifest_path": "...", "modules_count": int,
         "error": "..."}
    """
    try:
        resolved = _resolve_manifest_path(manifest_path)
        resolved.parent.mkdir(parents=True, exist_ok=True)

        manifest: dict[str, Any]
        if resolved.is_file():
            try:
                manifest = json.loads(resolved.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "manifest_path": str(resolved),
                    "modules_count": 0,
                    "error": f"读取已有 manifest 失败：{e}",
                }
        else:
            manifest = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "project_identifier": project_identifier,
                "modules": [],
            }

        modules: list[dict[str, Any]] = list(manifest.get("modules", []))

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            key = (entry.get("module"), entry.get("file"))
            # 按 (module, file) 去重更新
            modules = [
                m
                for m in modules
                if (m.get("module"), m.get("file")) != key
            ]
            modules.append(
                {
                    "module": entry.get("module"),
                    "file": entry.get("file"),
                    "count": entry.get("count", 0),
                    "persisted": entry.get("persisted", False),
                    "pending_import": entry.get("pending_import", False),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        manifest["project_identifier"] = project_identifier
        manifest["modules"] = modules

        resolved.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return {
            "success": True,
            "manifest_path": str(resolved),
            "modules_count": len(modules),
        }
    except Exception as e:
        return {
            "success": False,
            "manifest_path": manifest_path,
            "modules_count": 0,
            "error": f"保存 manifest 失败：{e}",
        }
