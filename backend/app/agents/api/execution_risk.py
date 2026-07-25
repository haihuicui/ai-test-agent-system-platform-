"""
执行邀约风险评估

根据执行上下文（模式、端点数、操作类型）评估风险等级，
决定是否需要中断用户确认。

风险等级：
- LOW:    纯只读查询、少量用例 → 可自动执行
- MEDIUM: 含写操作、较多用例 → 简化确认面板
- HIGH:   场景测试、批量大量端点、DELETE 操作 → 强制确认（当前行为）
"""

from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ExecutionContext:
    mode: str = "api"          # "api" | "scenario" | "batch"
    endpoint_count: int = 1
    test_count: int = 0
    has_write_ops: bool = False   # POST/PUT/PATCH
    has_delete_ops: bool = False  # DELETE（更高风险）


def evaluate_risk(ctx: ExecutionContext) -> tuple[RiskLevel, str]:
    """评估执行风险等级。

    Returns:
        (RiskLevel, 原因描述)
    """
    # 场景测试始终高风险（多步骤数据依赖 + 副作用）
    if ctx.mode == "scenario":
        return RiskLevel.HIGH, "场景测试涉及多步骤数据依赖和副作用，建议确认后执行"

    # DELETE 操作始终高风险（可能造成数据丢失）
    if ctx.has_delete_ops:
        return RiskLevel.HIGH, "包含 DELETE 操作，可能造成数据丢失，请确认"

    # 批量操作按规模分级
    if ctx.mode == "batch":
        if ctx.endpoint_count > 10:
            return RiskLevel.HIGH, f"批量执行 {ctx.endpoint_count} 个端点，影响面较大"
        if ctx.has_write_ops and ctx.endpoint_count > 3:
            return RiskLevel.HIGH, f"批量执行包含 {ctx.endpoint_count} 个写操作端点"
        if ctx.has_write_ops:
            return RiskLevel.MEDIUM, f"批量执行包含写操作（{ctx.endpoint_count} 个端点）"
        if ctx.endpoint_count <= 10:
            return RiskLevel.LOW, f"批量执行 {ctx.endpoint_count} 个只读端点，低风险"
        return RiskLevel.MEDIUM, f"批量执行 {ctx.endpoint_count} 个端点"

    # 单端点
    if ctx.mode == "api":
        # 纯只读 + 少量用例 → 低风险
        if not ctx.has_write_ops and not ctx.has_delete_ops:
            if ctx.test_count <= 5:
                return RiskLevel.LOW, f"纯查询操作（{ctx.test_count} 个用例），低风险"
            return RiskLevel.MEDIUM, f"纯查询操作（{ctx.test_count} 个用例）"
        # 含写操作
        if ctx.has_write_ops:
            if ctx.test_count <= 5:
                return RiskLevel.MEDIUM, f"包含写操作的 {ctx.test_count} 个用例"
            return RiskLevel.HIGH, f"包含写操作的 {ctx.test_count} 个用例，建议确认"

    # 默认保守：高风险
    return RiskLevel.HIGH, "默认需确认"


def is_auto_executable(ctx: ExecutionContext) -> bool:
    """判断是否允许跳过中断自动执行。"""
    level, _ = evaluate_risk(ctx)
    return level == RiskLevel.LOW


def extract_risk_context(payload: dict) -> ExecutionContext:
    """从执行邀约 payload 中提取风险评估上下文。"""
    return ExecutionContext(
        mode=payload.get("mode", "api"),
        endpoint_count=payload.get("endpoint_count", 1),
        test_count=payload.get("test_count", 0),
        has_write_ops=payload.get("has_write_ops", False),
        has_delete_ops=payload.get("has_delete_ops", False),
    )
