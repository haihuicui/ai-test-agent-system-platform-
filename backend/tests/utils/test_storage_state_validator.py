"""
StorageStateValidator 单元测试
"""

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.utils.storage_state_validator import (
    StorageStateValidationResult,
    validate_storage_state,
)


def _make_jwt(payload: dict) -> str:
    """构造一个不可签名的伪 JWT，仅用于 payload 解码测试。"""
    header = "eyJhbGciOiJub25lIn0"  # {"alg":"none"}
    payload_b64 = (
        json.dumps(payload)
        .encode("utf-8")
        .replace(b"=", b"")
        .replace(b"+", b"-")
        .replace(b"/", b"_")
    )
    # 上面替换不严谨，手动 base64url 编码
    import base64

    payload_segment = (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        .rstrip(b"=")
        .decode("ascii")
    )
    return f"{header}.{payload_segment}.signature"


def test_missing_file_is_invalid(tmp_path: Path):
    path = tmp_path / "not-exist.json"
    result = validate_storage_state(path)
    assert result.is_valid is False
    assert "不存在" in result.reason


def test_malformed_json_is_invalid(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    result = validate_storage_state(path)
    assert result.is_valid is False
    assert "JSON 解析失败" in result.reason


def test_empty_storage_state_is_valid(tmp_path: Path):
    path = tmp_path / "empty.json"
    path.write_text("{}", encoding="utf-8")
    result = validate_storage_state(path)
    assert result.is_valid is True
    assert result.earliest_expiry is None


def test_valid_cookie_in_future(tmp_path: Path):
    path = tmp_path / "valid-cookie.json"
    future_ts = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
    data = {
        "cookies": [
            {
                "name": "session",
                "value": "abc",
                "domain": ".example.com",
                "path": "/",
                "expires": future_ts,
            }
        ],
        "origins": [],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    result = validate_storage_state(path)
    assert result.is_valid is True
    assert result.earliest_expiry is not None


def test_expired_cookie_is_invalid(tmp_path: Path):
    path = tmp_path / "expired-cookie.json"
    past_ts = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
    data = {
        "cookies": [
            {
                "name": "session",
                "value": "abc",
                "domain": ".example.com",
                "path": "/",
                "expires": past_ts,
            }
        ],
        "origins": [],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    result = validate_storage_state(path)
    assert result.is_valid is False
    assert "cookie 'session' expired" in result.reason


def test_valid_jwt_in_local_storage(tmp_path: Path):
    path = tmp_path / "valid-jwt.json"
    future_exp = int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp())
    token = _make_jwt({"sub": "user", "exp": future_exp})
    data = {
        "cookies": [],
        "origins": [
            {
                "origin": "https://example.com",
                "localStorage": [{"name": "auth_token", "value": token}],
            }
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    result = validate_storage_state(path)
    assert result.is_valid is True
    assert result.earliest_expiry is not None


def test_expired_jwt_in_local_storage_is_invalid(tmp_path: Path):
    path = tmp_path / "expired-jwt.json"
    past_exp = int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp())
    token = _make_jwt({"sub": "user", "exp": past_exp})
    data = {
        "cookies": [],
        "origins": [
            {
                "origin": "https://example.com",
                "localStorage": [{"name": "auth_token", "value": token}],
            }
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    result = validate_storage_state(path)
    assert result.is_valid is False
    assert "localStorage JWT 'auth_token' expired" in result.reason


def test_non_jwt_local_storage_value_is_ignored(tmp_path: Path):
    path = tmp_path / "plain-value.json"
    data = {
        "cookies": [],
        "origins": [
            {
                "origin": "https://example.com",
                "localStorage": [
                    {"name": "theme", "value": "dark"},
                    {"name": "random", "value": "not.a.jwt"},
                ],
            }
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    result = validate_storage_state(path)
    assert result.is_valid is True
    assert result.earliest_expiry is None


def test_earliest_expiry_across_cookies_and_jwts(tmp_path: Path):
    path = tmp_path / "mixed.json"
    now = datetime.now(timezone.utc)
    cookie_ts = int((now + timedelta(hours=3)).timestamp())
    jwt_exp = int((now + timedelta(hours=1)).timestamp())
    token = _make_jwt({"exp": jwt_exp})
    data = {
        "cookies": [
            {
                "name": "session",
                "value": "abc",
                "domain": ".example.com",
                "path": "/",
                "expires": cookie_ts,
            }
        ],
        "origins": [
            {
                "origin": "https://example.com",
                "localStorage": [{"name": "auth_token", "value": token}],
            }
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    result = validate_storage_state(path)
    assert result.is_valid is True
    # earliest_expiry 应取 JWT 的 1 小时后
    assert result.earliest_expiry is not None
    assert abs(result.earliest_expiry.timestamp() - jwt_exp) < 2


def test_cookie_expires_as_float(tmp_path: Path):
    path = tmp_path / "float-expires.json"
    past_ts = time.time() - 3600.0
    data = {
        "cookies": [
            {
                "name": "session",
                "value": "abc",
                "domain": ".example.com",
                "path": "/",
                "expires": past_ts,
            }
        ],
        "origins": [],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    result = validate_storage_state(path)
    assert result.is_valid is False
