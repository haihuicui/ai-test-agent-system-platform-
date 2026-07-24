"""
Web 登录态 storageState 静态校验工具

解析 Playwright 导出的 storageState.json，在注入浏览器上下文前判断
cookies / localStorage JWT 是否已过期，避免把失效凭据带入测试。
"""

import base64
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StorageStateValidationResult:
    """storageState 校验结果"""

    is_valid: bool
    reason: str
    earliest_expiry: Optional[datetime] = None


def _decode_base64url_segment(segment: str) -> bytes:
    """解码 JWT 中 base64url 编码的一段，自动补齐 padding。"""
    padding_needed = 4 - (len(segment) % 4)
    if padding_needed != 4:
        segment += "=" * padding_needed
    return base64.urlsafe_b64decode(segment)


def _looks_like_jwt(value: str) -> bool:
    """粗略判断字符串是否为 JWT：三段、每段非空、仅含 base64url 字符。"""
    if not value or value.count(".") != 2:
        return False
    parts = value.split(".")
    if any(not p for p in parts):
        return False
    # base64url 字符集，允许空 payload？一般 JWT payload 不会空，但保守允许
    pattern = re.compile(r"^[A-Za-z0-9_-]+$")
    return all(pattern.match(p) for p in parts)


def _decode_jwt_exp(value: str) -> Optional[float]:
    """尝试从 JWT payload 中读取 exp 字段，失败返回 None。"""
    try:
        payload = _decode_base64url_segment(value.split(".")[1])
        claims = json.loads(payload.decode("utf-8"))
        exp = claims.get("exp")
        if isinstance(exp, (int, float)) and exp > 0:
            return float(exp)
    except Exception:
        pass
    return None


def _parse_storage_state_json(data: Any) -> tuple[bool, str, Optional[datetime]]:
    """解析已加载的 storageState 字典，返回 (is_valid, reason, earliest_expiry)。"""
    now = datetime.now(timezone.utc)
    earliest_expiry: Optional[datetime] = None
    expired_items: list[str] = []

    # 1. 校验 cookies
    cookies = data.get("cookies") if isinstance(data, dict) else None
    if isinstance(cookies, list):
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue
            name = cookie.get("name") or "unnamed"
            expires = cookie.get("expires")
            if isinstance(expires, (int, float)):
                expires_dt = datetime.fromtimestamp(float(expires), tz=timezone.utc)
                if earliest_expiry is None or expires_dt < earliest_expiry:
                    earliest_expiry = expires_dt
                if expires_dt <= now:
                    expired_items.append(f"cookie '{name}' expired at {expires_dt.isoformat()}")

    # 2. 校验 origins 中的 localStorage JWT
    origins = data.get("origins") if isinstance(data, dict) else None
    if isinstance(origins, list):
        for origin_entry in origins:
            if not isinstance(origin_entry, dict):
                continue
            local_storage = origin_entry.get("localStorage")
            if not isinstance(local_storage, list):
                continue
            for item in local_storage:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or "unnamed"
                value = item.get("value")
                if not isinstance(value, str) or not _looks_like_jwt(value):
                    continue
                exp = _decode_jwt_exp(value)
                if exp is None:
                    continue
                exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
                if earliest_expiry is None or exp_dt < earliest_expiry:
                    earliest_expiry = exp_dt
                if exp_dt <= now:
                    expired_items.append(
                        f"localStorage JWT '{name}' expired at {exp_dt.isoformat()}"
                    )

    if expired_items:
        return False, "; ".join(expired_items), earliest_expiry

    if earliest_expiry is not None:
        return (
            True,
            f"storageState 有效，最早过期时间为 {earliest_expiry.isoformat()}",
            earliest_expiry,
        )
    return True, "storageState 未发现过期信息，视为有效", None


def validate_storage_state(path: str | Path) -> StorageStateValidationResult:
    """
    校验 Playwright storageState.json 是否仍有效。

    Args:
        path: storageState.json 文件路径。

    Returns:
        StorageStateValidationResult，包含 is_valid、reason、earliest_expiry。
    """
    try:
        p = Path(path)
        if not p.exists():
            return StorageStateValidationResult(
                is_valid=False, reason=f"storageState 文件不存在: {p}"
            )

        try:
            text = p.read_text(encoding="utf-8")
            data = json.loads(text)
        except json.JSONDecodeError as e:
            return StorageStateValidationResult(
                is_valid=False, reason=f"storageState JSON 解析失败: {e}"
            )
        except OSError as e:
            return StorageStateValidationResult(
                is_valid=False, reason=f"无法读取 storageState 文件: {e}"
            )

        is_valid, reason, earliest_expiry = _parse_storage_state_json(data)
        return StorageStateValidationResult(
            is_valid=is_valid, reason=reason, earliest_expiry=earliest_expiry
        )
    except Exception as e:
        logger.exception("校验 storageState 时发生未预期异常: %s", path)
        return StorageStateValidationResult(
            is_valid=False, reason=f"校验异常: {type(e).__name__}: {e}"
        )
