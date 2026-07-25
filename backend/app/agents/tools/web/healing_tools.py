"""Web 测试修复知识图谱工具。

提供跨会话的修复经验持久化和检索能力：
- search_healing_knowledge: 搜索匹配的修复策略（含可操作性评估）
- record_healing_result: 记录修复结果（置信度自适应更新）
"""

import json
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select, func

from app.config.database import async_session_factory
from app.models.web_test import WebHealingKnowledge


# ---- 错误签名规范化 ----

# 动态值模式：UUID、timestamp、数字 ID、引号内动态文本、文件路径
_DYNAMIC_PATTERNS = [
    (re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"), "<UUID>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"), "<TIMESTAMP>"),
    # 文件路径中的动态名称（spec 文件、目录名）
    (re.compile(r"(?:tests?/)?[\w-]+\.spec\.(?:ts|js|mjs)"), "<SPEC_FILE>"),
    (re.compile(r"(?:in|at)\s+\S+[/\\]\S+"), "<LOCATION>"),
    (re.compile(r"`[^`]+`"), "<VALUE>"),
    (re.compile(r"'[^']*?'"), "<VALUE>"),
    (re.compile(r'"[^"]*?"'), "<VALUE>"),
    (re.compile(r"\d{3,}"), "<NUM>"),
    (re.compile(r"0x[0-9a-fA-F]+"), "<HEX>"),
    (re.compile(r"ref=e\d+"), "ref=<REF>"),
]


def _normalize_error(error_message: str) -> str:
    """规范化错误信息，去除动态值，生成稳定签名。

    将 UUID、时间戳、数字 ID、动态引号内容替换为占位符，
    使得相同模式的不同实例能匹配同一条知识库记录。

    Args:
        error_message: 原始错误信息

    Returns:
        规范化后的错误签名（<500 chars）
    """
    signature = error_message[:500]  # 截断
    for pattern, replacement in _DYNAMIC_PATTERNS:
        signature = pattern.sub(replacement, signature)
    return signature.strip()


def _categorize_error(error_message: str) -> str:
    """根据错误信息推断错误类别。

    Returns:
        selector / timing / assertion / environment / application 之一。
    """
    msg_lower = error_message.lower()
    if any(k in msg_lower for k in ("selector", "locator", "resolved to 0", "not found", "element not", "getByTestId", "getByRole", "getByLabel", "getByText")):
        return "selector"
    if any(k in msg_lower for k in ("timeout", "timed out", "loading", "networkidle", "waitfor", "to be visible")):
        return "timing"
    if any(k in msg_lower for k in ("expect", "assert", "expected", "to have", "to contain", "to equal", "tobe", "totext")):
        return "assertion"
    if any(k in msg_lower for k in ("auth", "login", "credential", "session", "401", "403", "permission", "denied")):
        return "environment"
    return "application"


# ---- 辅助函数 ----


_HEALABLE_CONFIDENCE = 0.85
_HEALABLE_MIN_APPLY = 5


def _format_match(m: WebHealingKnowledge, match_type: str) -> dict:
    """格式化知识图谱匹配结果，附加可操作性评估（healable + action）。"""
    has_template = bool(m.fix_code_template)
    conf_ok = m.confidence >= _HEALABLE_CONFIDENCE
    apply_ok = m.apply_count >= _HEALABLE_MIN_APPLY

    if conf_ok and apply_ok and has_template:
        healable = "recommended"
        action = (
            f"高置信度 ({m.confidence:.0%}) + 足够样本 ({m.apply_count} 次) + 有代码模板。"
            f"请手动参考 fix_code_template 修改脚本，修复验证后调用 record_healing_result。"
            f"代码模板: {m.fix_code_template}"
        )
    elif has_template:
        healable = "reference"
        parts = []
        if not conf_ok:
            parts.append(f"置信度 {m.confidence:.0%} < {_HEALABLE_CONFIDENCE:.0%}")
        if not apply_ok:
            parts.append(f"应用次数 {m.apply_count} < {_HEALABLE_MIN_APPLY}")
        action = (
            f"有代码模板但{'且'.join(parts)}。"
            f"可参考 fix_code_template 手动应用，修复验证后调用 record_healing_result。"
            f"代码模板: {m.fix_code_template}"
        )
    else:
        healable = "manual"
        action = f"无代码模板，需手动诊断。修复策略参考: {m.fix_strategy}"

    return {
        "id": str(m.id),
        "error_signature": m.error_signature,
        "error_category": m.error_category,
        "fix_strategy": m.fix_strategy,
        "fix_code_template": m.fix_code_template,
        "confidence": round(m.confidence, 2),
        "apply_count": m.apply_count,
        "success_count": m.success_count,
        "match_type": match_type,
        "healable": healable,
        "action": action,
    }


# ---- 工具定义 ----


@tool
async def search_healing_knowledge(
    error_message: str,
    project_identifier: str = "",
    top_k: int = 3,
) -> str:
    """在修复知识库中搜索匹配的修复策略（持久化、跨会话共享）。

    对错误信息做规范化签名后，先在知识库中精确匹配，未命中再模糊匹配。
    返回按置信度降序的策略列表。

    Args:
        error_message: 完整的错误信息（含堆栈的尾部也接受，会自动截断至前 500 字符）
        project_identifier: 项目标识符（可选，用于项目级隔离；为空则搜索全局条目）
        top_k: 返回的最大匹配数（默认 3）

    Returns:
        JSON 格式搜索结果，包含 matches 列表（每项含策略描述、置信度、代码模板等）。
        无匹配时 matches 为空列表。
    """
    try:
        signature = _normalize_error(error_message)
        category = _categorize_error(error_message)

        matches: list[dict] = []

        async with async_session_factory() as session:
            # 1. 精确签名匹配（同类别优先）
            exact_query = select(WebHealingKnowledge).where(
                WebHealingKnowledge.error_signature == signature,
                WebHealingKnowledge.error_category == category,
            ).order_by(WebHealingKnowledge.confidence.desc()).limit(top_k)
            exact_result = await session.execute(exact_query)
            exact_matches = exact_result.scalars().all()

            for m in exact_matches:
                matches.append(_format_match(m, "exact"))

            # 2. 模糊匹配：子串包含 + 同类别，按置信度排序
            if len(matches) < top_k:
                remaining = top_k - len(matches)
                # 取签名前 100 字符做 LIKE 查询
                short_sig = signature[:100]
                fuzzy_query = (
                    select(WebHealingKnowledge)
                    .where(
                        WebHealingKnowledge.error_signature.contains(short_sig[:60]),
                        WebHealingKnowledge.error_category == category,
                        WebHealingKnowledge.id.notin_([m["id"] for m in matches]) if matches else True,
                    )
                    .order_by(WebHealingKnowledge.confidence.desc())
                    .limit(remaining)
                )
                fuzzy_result = await session.execute(fuzzy_query)
                fuzzy_matches = fuzzy_result.scalars().all()
                for m in fuzzy_matches:
                    matches.append(_format_match(m, "fuzzy"))

        return json.dumps({
            "success": True,
            "signature": signature,
            "category": category,
            "matches": matches,
            "total": len(matches),
            "recommendation": (
                f"找到 {len(matches)} 条匹配策略。"
                f"若最高置信度 > 0.9，可直接应用其代码模板。"
                if matches else
                "未找到匹配策略，请走完整诊断流程。修复成功后记得调用 record_healing_result 记录经验。"
            ),
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"搜索修复知识库失败: {str(e)}",
            "matches": [],
        }, ensure_ascii=False, indent=2)


@tool
async def record_healing_result(
    error_signature: str,
    error_category: str,
    fix_strategy: str,
    fix_code_template: str = "",
    success: bool = True,
    project_identifier: str = "",
) -> str:
    """记录一次修复结果到知识图谱（持久化、跨会话共享）。

    自动规范化签名、去重（相同签名+类别+策略的条目会合并更新置信度）、
    更新统计。多次成功修复同一签名会累加置信度。

    Args:
        error_signature: 规范化错误指纹（如果是从 search 结果中拿到的，直接传入）
        error_category: 错误类别 (selector/timing/assertion/environment/application)
        fix_strategy: 使用的修复策略描述
        fix_code_template: 可复用的代码模板（如 'test.use({ testIdAttribute: \"data-test\" })'）
        success: 修复是否成功
        project_identifier: 项目标识符（可选）

    Returns:
        JSON 格式结果，包含 recorded 状态和更新后的置信度。
    """
    try:
        signature = _normalize_error(error_signature)
        category = error_category.lower()[:50]

        # 校验类别
        valid_categories = {"selector", "timing", "assertion", "environment", "application"}
        if category not in valid_categories:
            category = _categorize_error(error_signature)

        async with async_session_factory() as session:
            # 查找已有记录（相同签名+类别+策略）
            existing = (await session.execute(
                select(WebHealingKnowledge).where(
                    WebHealingKnowledge.error_signature == signature,
                    WebHealingKnowledge.error_category == category,
                    WebHealingKnowledge.fix_strategy == fix_strategy,
                )
            )).scalar_one_or_none()

            if existing:
                # 更新已有记录
                existing.apply_count += 1
                if success:
                    existing.success_count += 1
                    # 置信度递增（每成功一次 +0.03，上限 0.98）
                    existing.confidence = min(0.98, existing.confidence + 0.03)
                else:
                    # 置信度递减（每次失败 -0.1，下限 0.1）
                    existing.confidence = max(0.1, existing.confidence - 0.1)
                # 更新代码模板（如果本次提供了更完整的模板）
                if fix_code_template and (not existing.fix_code_template or success):
                    existing.fix_code_template = fix_code_template
                existing.updated_at = datetime.now(timezone.utc)
                knowledge = existing
                action = "updated"
            else:
                # 创建新记录
                knowledge = WebHealingKnowledge(
                    error_signature=signature,
                    error_category=category,
                    fix_strategy=fix_strategy,
                    fix_code_template=fix_code_template or None,
                    confidence=0.55 if success else 0.40,  # 初始置信度
                    apply_count=1,
                    success_count=1 if success else 0,
                )
                session.add(knowledge)
                action = "created"

            await session.commit()
            await session.refresh(knowledge)

            return json.dumps({
                "success": True,
                "recorded": True,
                "action": action,
                "id": str(knowledge.id),
                "error_signature": knowledge.error_signature,
                "error_category": knowledge.error_category,
                "confidence": round(knowledge.confidence, 2),
                "apply_count": knowledge.apply_count,
                "success_count": knowledge.success_count,
                "message": (
                    f"修复经验已{action}，当前置信度 {knowledge.confidence:.0%}"
                    f"（{knowledge.success_count}/{knowledge.apply_count} 次成功）"
                ),
            }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"记录修复结果失败: {str(e)}",
        }, ensure_ascii=False, indent=2)

