"""
annotation_tools 单元测试

覆盖标注序列化和工具参数校验逻辑；DB 依赖部分通过 mock 验证。
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agents.tools.api.annotation_tools import _annotation_to_dict


class TestAnnotationToDict:
    def test_serializes_all_fields(self):
        ann = SimpleNamespace(
            id=uuid4(),
            project_id=uuid4(),
            endpoint_id=uuid4(),
            annotation_type="business_error_code",
            source="trace",
            http_status=400,
            business_code="4009",
            field_path="body.email",
            condition="format_error",
            message_pattern="邮箱格式不正确",
            expected_value={"code": "4009"},
            confidence=0.8,
            hit_count=3,
            enabled=True,
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            last_verified_at=datetime.now(timezone.utc),
            source_metadata={"test_result_id": str(uuid4())},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        data = _annotation_to_dict(ann)

        assert data["annotation_type"] == "business_error_code"
        assert data["business_code"] == "4009"
        assert data["field_path"] == "body.email"
        assert data["expected_value"] == {"code": "4009"}
        assert data["source_metadata"]["test_result_id"] == ann.source_metadata["test_result_id"]
        assert data["id"] == str(ann.id)

    def test_handles_null_endpoint(self):
        ann = SimpleNamespace(
            id=uuid4(),
            project_id=uuid4(),
            endpoint_id=None,
            annotation_type="business_success_code",
            source="trace",
            http_status=200,
            business_code="0",
            field_path=None,
            condition=None,
            message_pattern=None,
            expected_value=None,
            confidence=0.5,
            hit_count=1,
            enabled=True,
            first_seen_at=None,
            last_seen_at=None,
            last_verified_at=None,
            source_metadata=None,
            created_at=None,
            updated_at=None,
        )

        data = _annotation_to_dict(ann)

        assert data["endpoint_id"] is None
        assert data["first_seen_at"] is None
        assert data["source_metadata"] is None


class TestGetEndpointAnnotationsValidation:
    @pytest.mark.asyncio
    async def test_invalid_uuid_returns_error(self):
        from app.agents.tools.api.annotation_tools import get_endpoint_annotations

        result = await get_endpoint_annotations.ainvoke({"endpoint_id": "not-a-uuid"})
        parsed = __import__("json").loads(result)

        assert parsed["success"] is False
        assert "无效" in parsed["error"]


class TestHarvestAnnotationsValidation:
    @pytest.mark.asyncio
    async def test_invalid_since_returns_error(self):
        from app.agents.tools.api.annotation_tools import harvest_annotations_from_traces

        result = await harvest_annotations_from_traces.ainvoke({
            "project_identifier": "PR-1",
            "since": "not-iso",
        })
        parsed = __import__("json").loads(result)

        assert parsed["success"] is False
        assert "时间格式" in parsed["error"]

    @pytest.mark.asyncio
    async def test_invalid_endpoint_id_returns_error(self):
        from app.agents.tools.api.annotation_tools import harvest_annotations_from_traces

        result = await harvest_annotations_from_traces.ainvoke({
            "project_identifier": "PR-1",
            "endpoint_id": "bad-uuid",
        })
        parsed = __import__("json").loads(result)

        assert parsed["success"] is False
        assert "端点 ID" in parsed["error"]
