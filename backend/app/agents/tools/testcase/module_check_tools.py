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

from app.agents.tools.testcase.excel_tools import (
    _parse_json_objects,
    _resolve_input_path,
)
from app.config.settings import settings
from app.utils.testcase_validation import _validate_case

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


def _resolve_manifest_path(manifest_path: str) -> Path:
    """将 manifest 路径解析到 workspace_root 下，禁止越权。"""
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


def _collect_existing_case_numbers(
    current_files: set[Path],
) -> set[Any]:
    """扫描工作区中除当前文件外的其他用例数据文件，收集已有用例编号。"""
    existing_numbers: set[Any] = set()
    for f in _WORKSPACE_ROOT.rglob("*.jsonl"):
        # 排除当前正在自检的文件
        if f.resolve() in current_files:
            continue
        try:
            text = f.read_text(encoding="utf-8").strip()
            if not text:
                continue
            for case in _parse_json_objects(text, str(f)):
                if isinstance(case, dict):
                    key = _case_number_key(case)
                    if key is not None:
                        existing_numbers.add(key)
        except Exception:
            # 扫描过程不应因单个文件损坏而中断
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
) -> dict[str, Any]:
    """
    对内存中的用例列表执行模块级自检。

    本函数与文件读取解耦，供 ``module_self_check_tool`` 和
    ``ModuleSelfCheckMiddleware`` 复用，保证同一套规则。

    Args:
        check_cross_file_duplicates: 是否扫描工作区其他文件检查编号跨文件重复。
            中间件场景不掌握文件路径，可设为 False 避免误报。
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

    errors = [v for v in violations if v.get("level") == "error"]
    warnings = [v for v in violations if v.get("level") == "warning"]
    passed = len(errors) == 0

    summary_parts = [f"共检查 {len(cases)} 条用例，P0 {p0_count} 条"]
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
        "violations": violations,
        "summary": "；".join(summary_parts),
    }


@tool
async def module_self_check_tool(
    input_files: list[str],
    expected_module: str,
    min_p0_count: int = 3,
) -> dict[str, Any]:
    """
    对单个模块的用例数据文件做轻量自检。

    在 Phase 3 每完成一个模块后调用，确认低级质量问题（编号、模块、数据、
    预期结果、原子性、优先级）已被拦截，通过后再进入下一模块。

    Args:
        input_files: 该模块的用例数据文件路径（.jsonl/.json），可传多个。
        expected_module: 期望的模块名称，用于校验 module 字段一致性。
        min_p0_count: 该模块最少 P0 用例数（critical 映射为 P0）。

    Returns:
        {
          "passed": bool,
          "total": int,
          "p0_count": int,
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

    return _perform_module_self_check(
        cases=cases,
        expected_module=expected_module,
        current_file_paths=current_file_paths,
        min_p0_count=min_p0_count,
    )


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
