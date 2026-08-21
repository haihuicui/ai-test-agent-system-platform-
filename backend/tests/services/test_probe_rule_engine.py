"""
ProbeRuleEngine 单元测试

覆盖基于 OpenAPI schema 生成单字段异常探测请求的逻辑。
"""

import pytest

from app.services.probe_rule_engine import generate_probe_requests


class TestProbeRuleEngine:
    def test_required_missing_for_required_body_field(self):
        request_body = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["email"],
                        "properties": {
                            "email": {"type": "string", "format": "email"},
                        },
                    }
                }
            },
            "required": True,
        }
        probes = generate_probe_requests(
            endpoint_path="/api/users",
            method="POST",
            parameters=[],
            request_body=request_body,
        )
        conditions = {p["condition"] for p in probes}
        assert "required_missing" in conditions
        req_missing = next(p for p in probes if p["condition"] == "required_missing")
        assert req_missing["field_path"] == "body.email"
        assert "email" not in req_missing["request_data"]["body"]

    def test_type_error_for_integer_field(self):
        request_body = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["age"],
                        "properties": {
                            "age": {"type": "integer"},
                        },
                    }
                }
            }
        }
        probes = generate_probe_requests(
            endpoint_path="/api/users",
            method="POST",
            parameters=[],
            request_body=request_body,
        )
        type_error = next(p for p in probes if p["condition"] == "type_error")
        assert type_error["request_data"]["body"]["age"] == "not-a-number"

    def test_format_error_for_email_field(self):
        request_body = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["email"],
                        "properties": {
                            "email": {"type": "string", "format": "email"},
                        },
                    }
                }
            }
        }
        probes = generate_probe_requests(
            endpoint_path="/api/users",
            method="POST",
            parameters=[],
            request_body=request_body,
        )
        fmt_error = next(p for p in probes if p["condition"] == "format_error")
        assert fmt_error["request_data"]["body"]["email"] == "not-an-email"

    def test_length_constraints_for_string_field(self):
        request_body = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string", "minLength": 2, "maxLength": 10},
                        },
                    }
                }
            }
        }
        probes = generate_probe_requests(
            endpoint_path="/api/users",
            method="POST",
            parameters=[],
            request_body=request_body,
        )
        conditions = {p["condition"] for p in probes}
        assert "length_exceeded" in conditions
        assert "length_below" in conditions

        exceeded = next(p for p in probes if p["condition"] == "length_exceeded")
        assert len(exceeded["request_data"]["body"]["name"]) == 11

        below = next(p for p in probes if p["condition"] == "length_below")
        assert len(below["request_data"]["body"]["name"]) == 1

    def test_out_of_range_for_integer_field(self):
        request_body = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["age"],
                        "properties": {
                            "age": {"type": "integer", "minimum": 18, "maximum": 60},
                        },
                    }
                }
            }
        }
        probes = generate_probe_requests(
            endpoint_path="/api/users",
            method="POST",
            parameters=[],
            request_body=request_body,
        )
        oor = next(p for p in probes if p["condition"] == "out_of_range")
        assert oor["request_data"]["body"]["age"] == 17

    def test_invalid_enum_for_enum_field(self):
        request_body = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["status"],
                        "properties": {
                            "status": {"type": "string", "enum": ["active", "inactive"]},
                        },
                    }
                }
            }
        }
        probes = generate_probe_requests(
            endpoint_path="/api/users",
            method="POST",
            parameters=[],
            request_body=request_body,
        )
        enum_probe = next(p for p in probes if p["condition"] == "invalid_enum")
        assert enum_probe["request_data"]["body"]["status"] not in {"active", "inactive"}

    def test_query_parameter_probes(self):
        parameters = [
            {"name": "page", "in": "query", "required": True, "schema": {"type": "integer"}},
            {"name": "size", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100}},
        ]
        probes = generate_probe_requests(
            endpoint_path="/api/users",
            method="GET",
            parameters=parameters,
            request_body=None,
        )
        field_paths = {p["field_path"] for p in probes}
        assert "query.page" in field_paths
        assert "query.size" in field_paths

    def test_legacy_body_parameter_merge(self):
        """旧格式 parameters 中 in: body 应被识别为请求体"""
        from app.services.probe_executor import ProbeExecutor

        parameters = [
            {"name": "payload", "in": "body", "required": True, "schema": {
                "type": "object",
                "required": ["email"],
                "properties": {
                    "email": {"type": "string", "format": "email"},
                },
            }},
        ]
        request_body = ProbeExecutor._merge_legacy_body_params(parameters, None)
        assert request_body is not None
        assert "content" in request_body

    def test_budget_truncation(self):
        request_body = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["a", "b", "c", "d", "e"],
                        "properties": {
                            "a": {"type": "string"},
                            "b": {"type": "string"},
                            "c": {"type": "string"},
                            "d": {"type": "string"},
                            "e": {"type": "string"},
                        },
                    }
                }
            }
        }
        probes = generate_probe_requests(
            endpoint_path="/api/users",
            method="POST",
            parameters=[],
            request_body=request_body,
            budget=3,
        )
        assert len(probes) == 3

    def test_nested_object_one_level_deep(self):
        request_body = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["profile"],
                        "properties": {
                            "profile": {
                                "type": "object",
                                "required": ["nickname"],
                                "properties": {
                                    "nickname": {"type": "string", "minLength": 1},
                                },
                            },
                        },
                    }
                }
            }
        }
        probes = generate_probe_requests(
            endpoint_path="/api/users",
            method="POST",
            parameters=[],
            request_body=request_body,
        )
        field_paths = {p["field_path"] for p in probes}
        assert "body.profile.nickname" in field_paths
