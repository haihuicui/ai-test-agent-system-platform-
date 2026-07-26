"""功能测试矩阵结构化存储工具。

提供将 Phase 1 需求分析产出的功能测试矩阵保存为结构化 JSONL 文件的能力，
解决跨 Phase 信息断裂问题——Phase 3/4 可通过读取该文件做确定性覆盖对照，
不再依赖 LLM 在长对话中的记忆。
"""

from __future__ import annotations

import json
import logging
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
_VALID_TEST_TYPES = {
    "功能", "安全", "性能", "兼容", "接口", "UI", "数据",
    "异常", "边界", "单元", "集成", "端到端", "回归",
}


def _resolve_matrix_path(output_file: str) -> Path:
    """将输出文件路径解析到 workspace_root 下，禁止越权。"""
    raw = Path(output_file)

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
        raise ValueError(f"输出文件路径无效：{output_file}")

    resolved = (_WORKSPACE_ROOT / rel).resolve()
    if not resolved.is_relative_to(_WORKSPACE_ROOT):
        raise ValueError(
            f"输出文件路径越权：{output_file} 解析后超出工作目录 {_WORKSPACE_ROOT}"
        )
    return resolved


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

    在 Phase 1 需求分析完成后**必须调用本工具**，将功能测试矩阵从对话历史中
    持久化到磁盘文件。该文件是跨 Phase 信息传递的唯一可靠方式——Phase 3 用例设计
    和 Phase 4 质量评审均可读取该文件做确定性覆盖对照，不再依赖 LLM 记忆。

    Args:
        features: 功能点列表，每个元素必须包含：
            - id: 功能点编号 (如 "FP-001"，格式 FP-NNN)
            - module: 所属模块 (如 "用户认证")
            - feature: 功能点名称 (如 "手机号登录")
            - test_points: 测试要点列表 ["验证码有效期5min", ...]
            - priority: 优先级 (P0/P1/P2/P3)
            - risk_level: 风险等级 (高/中/低)
            - test_type: 测试类型列表 (如 ["功能", "安全"])
            - source: 来源标注 (可选, 如 "需求原文 §2.1")
        output_file: 输出文件路径 (默认 feature_matrix.jsonl)
        project_identifier: 项目标识符 (可选)

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

        # 1. 逐条校验（Pydantic args_schema 已保证 features 是 list[dict]）
        all_errors: list[str] = []
        seen_ids: set[str] = set()
        for i, fp in enumerate(features):
            errors = _validate_feature_point(fp, i)
            all_errors.extend(errors)
            fp_id = fp.get("id", "")
            if isinstance(fp_id, str) and fp_id.strip() in seen_ids:
                all_errors.append(f"第 {i + 1} 条 id='{fp_id}' 与前面的记录重复")
            if isinstance(fp_id, str) and fp_id.strip():
                seen_ids.add(fp_id.strip())

        if all_errors:
            return {
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

        # 2. 解析路径并写入
        resolved = _resolve_matrix_path(output_file)
        resolved.parent.mkdir(parents=True, exist_ok=True)

        # 统计信息
        modules: list[str] = []
        priority_dist: dict[str, int] = {}
        for fp in features:
            module = str(fp.get("module", "")).strip()
            if module and module not in modules:
                modules.append(module)
            priority = str(fp.get("priority", "")).strip()
            if priority:
                priority_dist[priority] = priority_dist.get(priority, 0) + 1

        # 写入 JSONL（每行一个 JSON 对象）
        lines: list[str] = []
        for fp in features:
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

        return {
            "success": True,
            "file": str(resolved),
            "count": len(features),
            "modules": modules,
            "priority_distribution": priority_dist,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
        }

    except Exception as e:
        logger.exception("save_feature_matrix_tool 执行失败")
        return {
            "success": False,
            "file": output_file,
            "error": str(e),
            "message": f"保存功能矩阵失败：{e}",
        }
