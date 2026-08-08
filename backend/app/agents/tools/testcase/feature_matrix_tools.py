"""功能测试矩阵结构化存储工具。

提供将 Phase 1 需求分析产出的功能测试矩阵保存为结构化 JSONL 文件的能力，
解决跨 Phase 信息断裂问题——Phase 3/4 可通过读取该文件做确定性覆盖对照，
不再依赖 LLM 在长对话中的记忆。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from app.config.settings import settings

logger = logging.getLogger(__name__)

_WORKSPACE_ROOT = Path(settings.testcase_workspace_root).resolve()

# JSONL 每行必填字段及其类型
_REQUIRED_FIELDS: dict[str, type] = {
    "id": str,
    "module": str,
    "feature": str,
    "test_points": list,
    "priority": str,
    "risk_level": str,
    "test_type": list,
}

# 合法优先级枚举
_VALID_PRIORITIES = {"P0", "P1", "P2", "P3", "critical", "high", "medium", "low"}

# 合法风险等级枚举（兼容中英文，LLM 在中文上下文中偶尔输出英文）
_VALID_RISK_LEVELS = {
    "高", "中", "低",
    "High", "Medium", "Low",
    "high", "medium", "low",
}

# 合法测试类型枚举
# 规则/权限/状态 是功能测试的常见细分维度（业务规则校验、权限边界、状态流转），
# LLM 在功能矩阵中高频使用，列为合法值避免校验反复失败。
_VALID_TEST_TYPES = {
    "功能", "安全", "性能", "兼容", "接口", "UI", "数据",
    "异常", "边界", "单元", "集成", "端到端", "回归",
    "规则", "权限", "状态",
}

# test_type 常见同义词 → 标准值映射
# LLM 在中文上下文中常输出"界面""功能测试"等非标准值，自动映射可减少反复调用。
_TEST_TYPE_SYNONYMS: dict[str, str] = {
    "界面": "UI",
    "ui": "UI",
    "Ui": "UI",
    "功能测试": "功能",
    "功能性": "功能",
    "功能性测试": "功能",
    "安全测试": "安全",
    "安全性": "安全",
    "安全性测试": "安全",
    "性能测试": "性能",
    "兼容性": "兼容",
    "兼容测试": "兼容",
    "兼容性测试": "兼容",
    "接口测试": "接口",
    "api": "接口",
    "Api": "接口",
    "API": "接口",
    "数据测试": "数据",
    "异常场景": "异常",
    "异常测试": "异常",
    "异常流程": "异常",
    "边界值": "边界",
    "边界测试": "边界",
    "边界值测试": "边界",
    "单元测试": "单元",
    "集成测试": "集成",
    "端到端测试": "端到端",
    "e2e": "端到端",
    "E2E": "端到端",
    "回归测试": "回归",
    "规则测试": "规则",
    "业务规则": "规则",
    "规则校验": "规则",
    "权限测试": "权限",
    "权限校验": "权限",
    "状态测试": "状态",
    "状态流转": "状态",
    "状态机": "状态",
}

# test_type 组合值分隔符：LLM 常输出 "功能+规则" / "功能/权限" 形式的组合值，
# 归一化时先拆分为独立取值再做同义词映射。
_TEST_TYPE_SEPARATORS = re.compile(r"[+＋/／、,，]")


def _normalize_test_types(
    test_types: list[Any], index: int
) -> tuple[list[str], list[str]]:
    """将 test_type 中的组合值拆分、常见同义词映射到标准值。

    返回 (标准化后的列表, 自动修正警告列表)。无法识别的值保持原样，
    由后续 _validate_feature_point 统一报错，避免脏数据落盘。
    """
    normalized: list[str] = []
    warnings: list[str] = []
    for t in test_types:
        if not isinstance(t, str):
            normalized.append(str(t))
            continue
        t_stripped = t.strip()
        # 拆分 "功能+规则" 形式的组合值（LLM 高频输出），无分隔符时保持单值
        parts = [
            p.strip() for p in _TEST_TYPE_SEPARATORS.split(t_stripped) if p.strip()
        ]
        if len(parts) > 1:
            warnings.append(
                f"第 {index + 1} 条 test_type 组合值拆分：'{t_stripped}' → {parts}"
            )
        for part in parts or [t_stripped]:
            canonical = _TEST_TYPE_SYNONYMS.get(part, part)
            if canonical != part:
                warnings.append(
                    f"第 {index + 1} 条 test_type 自动修正：'{part}' → '{canonical}'"
                )
            if canonical not in normalized:
                normalized.append(canonical)
    return normalized, warnings


def _sanitize_project_identifier(project_identifier: str) -> str:
    """将项目标识符清理为可用作目录名的字符串。

    移除首尾空白，替换文件系统非法字符与路径分隔符为下划线，
    并拒绝 '.' / '..' 等会造成路径歧义的值。
    """
    cleaned = project_identifier.strip()
    # Windows/Unix 路径分隔符及非法字符统一替换为下划线
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", cleaned)
    if not cleaned or cleaned in (".", ".."):
        raise ValueError(f"无效的项目标识符：{project_identifier!r}")
    return cleaned


def _resolve_matrix_path(output_file: str, project_identifier: str = "") -> Path:
    """将输出文件路径解析到 workspace_root 下，禁止越权。

    若提供了 project_identifier 且 output_file 仅为文件名（未显式指定目录），
    则自动将文件隔离到 workspace_root/<project_identifier>/ 下，避免多项目冲突。
    若 output_file 显式包含子目录或是绝对路径，则尊重原有路径结构。
    """
    raw = Path(output_file)

    # 用户显式指定了目录结构（含子目录或绝对路径）时，不再追加项目隔离目录
    has_explicit_directory = bool(raw.anchor) or (
        len(raw.parts) > 1 and raw.parent.name not in ("", ".")
    )

    if project_identifier.strip() and not has_explicit_directory:
        safe_id = _sanitize_project_identifier(project_identifier)
        rel = Path(safe_id) / raw.name
    elif raw.anchor:
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
        raise ValueError(f"输出文件路径无效：{output_file}")

    resolved = (_WORKSPACE_ROOT / rel).resolve()
    if not resolved.is_relative_to(_WORKSPACE_ROOT):
        raise ValueError(
            f"输出文件路径越权：{output_file} 解析后超出工作目录 {_WORKSPACE_ROOT}"
        )
    return resolved


def resolve_feature_matrix_path(
    project_identifier: str = "",
    output_file: str = "feature_matrix.jsonl",
) -> Path:
    """解析功能矩阵文件在 workspace 中的实际路径。

    保存端和读取端共用同一套路径解析规则，确保 Phase 1 写入的位置与
    Phase 3/4 读取的位置一致。

    Args:
        project_identifier: 项目标识符。传入时文件会隔离到项目专属目录。
        output_file: 矩阵文件名，默认 feature_matrix.jsonl。

    Returns:
        解析后的绝对路径。
    """
    return _resolve_matrix_path(output_file, project_identifier)


def load_feature_matrix(
    project_identifier: str = "",
    output_file: str = "feature_matrix.jsonl",
) -> dict[str, Any]:
    """读取结构化功能测试矩阵 JSONL 文件。

    供 Phase 3/4 代码或工具使用，读取路径与 save_feature_matrix_tool 的
    保存路径保持完全一致。文件不存在时返回明确错误，不抛出异常。

    Args:
        project_identifier: 项目标识符。
        output_file: 矩阵文件名，默认 feature_matrix.jsonl。

    Returns:
        {
          "success": bool,
          "file": str,
          "features": list[dict],
          "count": int,
          "modules": ["模块1", ...],
          "error": str   # 仅失败时
        }
    """
    try:
        resolved = _resolve_matrix_path(output_file, project_identifier)
        if not resolved.exists():
            return {
                "success": False,
                "file": str(resolved),
                "features": [],
                "count": 0,
                "modules": [],
                "error": f"功能矩阵文件不存在：{resolved}",
            }

        features: list[dict[str, Any]] = []
        modules: list[str] = []
        for line in resolved.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "file": str(resolved),
                    "features": [],
                    "count": 0,
                    "modules": [],
                    "error": f"JSONL 解析失败：{e}",
                }
            if isinstance(record, dict):
                features.append(record)
                module = str(record.get("module", "")).strip()
                if module and module not in modules:
                    modules.append(module)

        return {
            "success": True,
            "file": str(resolved),
            "features": features,
            "count": len(features),
            "modules": modules,
        }
    except Exception as e:
        logger.exception("load_feature_matrix 执行失败")
        return {
            "success": False,
            "file": str(_resolve_matrix_path(output_file, project_identifier)),
            "features": [],
            "count": 0,
            "modules": [],
            "error": str(e),
        }


def _validate_feature_point(fp: dict[str, Any], index: int) -> list[str]:
    """校验单条功能点记录的字段完整性和合法性。返回错误消息列表。"""
    errors: list[str] = []

    # 必填字段检查
    for field, expected_type in _REQUIRED_FIELDS.items():
        value = fp.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"第 {index + 1} 条缺少必填字段 '{field}'")
        elif not isinstance(value, expected_type):
            errors.append(
                f"第 {index + 1} 条字段 '{field}' 类型错误："
                f"期望 {expected_type.__name__}，实际 {type(value).__name__}"
            )
        elif expected_type is list and isinstance(value, list) and len(value) == 0:
            errors.append(f"第 {index + 1} 条字段 '{field}' 为空列表")

    # 优先级枚举校验（先 strip 再比较，LLM 在 JSON 值中多加空格极其常见）
    priority = fp.get("priority", "")
    if isinstance(priority, str):
        priority = priority.strip()
        if priority not in _VALID_PRIORITIES:
            errors.append(
                f"第 {index + 1} 条 priority='{priority}' 不合法，"
                f"允许值：{sorted(_VALID_PRIORITIES)}"
            )

    # 风险等级枚举校验（先 strip，兼容中英文）
    risk = fp.get("risk_level", "")
    if isinstance(risk, str):
        risk = risk.strip()
        if risk not in _VALID_RISK_LEVELS:
            errors.append(
                f"第 {index + 1} 条 risk_level='{risk}' 不合法，"
                f"允许值：{sorted(_VALID_RISK_LEVELS)}"
            )

    # test_type 枚举校验：非法值直接报错，而非仅日志警告。
    # Phase 4 的覆盖匹配依赖 test_type 字段正确性，静默通过会导致脏数据落盘。
    # 注意：调用方应先用 _normalize_test_types 将常见同义词映射为标准值。
    test_types = fp.get("test_type", [])
    if isinstance(test_types, list):
        unknown = [t for t in test_types if t not in _VALID_TEST_TYPES]
        if unknown:
            errors.append(
                f"第 {index + 1} 条 test_type 包含未知值 {unknown}，"
                f"允许值：{sorted(_VALID_TEST_TYPES)}"
            )

    # id 去重检查（同批次内）
    fp_id = fp.get("id", "")
    if not isinstance(fp_id, str) or not fp_id.strip():
        errors.append(f"第 {index + 1} 条 id 为空或无效")
    elif not fp_id.strip().startswith("FP-"):
        errors.append(
            f"第 {index + 1} 条 id='{fp_id}' 格式不正确，"
            f"应以 'FP-' 开头（如 'FP-001'）"
        )

    return errors


@tool
async def save_feature_matrix_tool(
    features: list[dict[str, Any]],
    output_file: str = "feature_matrix.jsonl",
    project_identifier: str = "",
) -> dict[str, Any]:
    """将功能测试矩阵保存为结构化 JSONL 文件。

    在 Phase 1 需求分析完成后、**人工评审通过（或用户选择跳过）后**必须调用本工具，
    将功能测试矩阵从对话历史中持久化到磁盘文件。该文件是跨 Phase 信息传递的唯一
    可靠方式——Phase 3 用例设计和 Phase 4 质量评审均可读取该文件做确定性覆盖对照，
    不再依赖 LLM 记忆。

    重要顺序：请先输出阶段报告标题（`## 需求解析报告` / `## 功能测试矩阵`），
    等待系统弹出人工评审卡片；在收到用户通过/跳过决策后，再调用本工具保存矩阵。
    若将本工具调用与阶段报告标题放在同一条消息中，评审卡片会被系统跳过。

    Args:
        features: 功能点列表，每个元素必须包含：
            - id: 功能点编号 (如 "FP-001"，格式 FP-NNN)
            - module: 所属模块 (如 "用户认证")
            - feature: 功能点名称 (如 "手机号登录")
            - test_points: 测试要点列表 ["验证码有效期5min", ...]
            - priority: 优先级 (P0/P1/P2/P3)
            - risk_level: 风险等级 (高/中/低)
            - test_type: 测试类型列表，只能从以下取值中选择（可多选）：
              功能/安全/性能/兼容/接口/UI/数据/异常/边界/单元/集成/端到端/回归/规则/权限/状态。
              每个取值单独作为列表元素（如 ["功能", "边界"]），不要用 "功能+规则" 这类组合写法。
            - source: 来源标注 (可选, 如 "需求原文 §2.1")
        output_file: 输出文件路径 (默认 feature_matrix.jsonl)。
            若传入 project_identifier 且本参数仅为文件名，文件会自动隔离到
            workspace_root/<project_identifier>/ 目录下，避免多项目冲突。
        project_identifier: 项目标识符 (可选)。仅用于路径隔离和写入记录元数据。

    Returns:
        {
          "success": bool,
          "file": str,
          "count": int,
          "modules": ["模块1", "模块2", ...],
          "priority_distribution": {"P0": N, "P1": N, ...},
          "saved_at": "ISO timestamp",
          "summary": "已保存 N 个功能点到 feature_matrix.jsonl，覆盖 M 个模块",
          "errors": [...]   # 仅校验失败时
        }
    """
    try:
        if not features:
            return {
                "success": False,
                "file": output_file,
                "error": "features 列表为空，请先完成功能矩阵分析",
                "message": "功能点列表为空，无法保存。请先输出 ## 功能测试矩阵 后再调用本工具。",
            }

        # 0. 标准化 test_type 同义词，减少 LLM 因非标准值反复调用。
        # 深拷贝避免修改传入的原始对象，同时收集自动修正警告。
        normalized_features: list[dict[str, Any]] = []
        normalization_warnings: list[str] = []
        for i, fp in enumerate(features):
            fp_copy = dict(fp)
            if isinstance(fp_copy.get("test_type"), list):
                normalized_types, warns = _normalize_test_types(fp_copy["test_type"], i)
                fp_copy["test_type"] = normalized_types
                normalization_warnings.extend(warns)
            normalized_features.append(fp_copy)

        # 1. 逐条校验（Pydantic args_schema 已保证 features 是 list[dict]）
        all_errors: list[str] = []
        seen_ids: set[str] = set()
        for i, fp in enumerate(normalized_features):
            errors = _validate_feature_point(fp, i)
            all_errors.extend(errors)
            fp_id = fp.get("id", "")
            if isinstance(fp_id, str) and fp_id.strip() in seen_ids:
                all_errors.append(f"第 {i + 1} 条 id='{fp_id}' 与前面的记录重复")
            if isinstance(fp_id, str) and fp_id.strip():
                seen_ids.add(fp_id.strip())

        if all_errors:
            result: dict[str, Any] = {
                "success": False,
                "file": output_file,
                "count": len(features),
                "errors": all_errors[:20],  # 最多返回前 20 条错误
                "error_count": len(all_errors),
                "message": (
                    f"功能矩阵校验失败：{len(all_errors)} 个错误。"
                    f"请根据 errors 列表修正后重新调用。"
                ),
            }
            if normalization_warnings:
                result["warnings"] = normalization_warnings
            return result

        # 2. 解析路径并写入
        resolved = _resolve_matrix_path(output_file, project_identifier)
        resolved.parent.mkdir(parents=True, exist_ok=True)

        # 统计信息
        modules: list[str] = []
        priority_dist: dict[str, int] = {}
        for fp in normalized_features:
            module = str(fp.get("module", "")).strip()
            if module and module not in modules:
                modules.append(module)
            priority = str(fp.get("priority", "")).strip()
            if priority:
                priority_dist[priority] = priority_dist.get(priority, 0) + 1

        # 写入 JSONL（每行一个 JSON 对象）
        lines: list[str] = []
        for fp in normalized_features:
            # 补充元数据
            record = dict(fp)
            if "saved_at" not in record:
                record["saved_at"] = datetime.now(timezone.utc).isoformat()
            if project_identifier and "project_identifier" not in record:
                record["project_identifier"] = project_identifier
            lines.append(json.dumps(record, ensure_ascii=False))

        resolved.write_text("\n".join(lines) + "\n", encoding="utf-8")

        summary = (
            f"已保存 {len(features)} 个功能点到 {output_file}，"
            f"覆盖 {len(modules)} 个模块：{', '.join(modules)}"
        )

        logger.info(
            "功能矩阵已保存：%s，%d 个功能点，%d 个模块",
            resolved, len(features), len(modules),
        )

        # Agent 虚拟文件系统路径（read_file/glob 可见）。模型常把本结果里的
        # 宿主机绝对路径 file 直接拿去 read_file，虚拟 FS 下必然 not found——
        # 显式给出 read_path 并注明用途，避免 Phase 3/4 读矩阵时路径错误。
        try:
            read_path = "/" + resolved.relative_to(_WORKSPACE_ROOT).as_posix()
        except ValueError:
            read_path = "/" + resolved.name

        return {
            "success": True,
            "file": str(resolved),
            "read_path": read_path,
            "count": len(normalized_features),
            "modules": modules,
            "priority_distribution": priority_dist,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "warnings": normalization_warnings or [],
            "note": (
                f"后续 Phase 3/4 用 read_file 读取本矩阵时必须使用 read_path"
                f"（{read_path}，Agent 虚拟文件系统路径）；file 是宿主机绝对路径，"
                "仅供日志排查，read_file 无法按该路径访问。"
            ),
        }

    except Exception as e:
        logger.exception("save_feature_matrix_tool 执行失败")
        return {
            "success": False,
            "file": output_file,
            "error": str(e),
            "message": f"保存功能矩阵失败：{e}",
        }
