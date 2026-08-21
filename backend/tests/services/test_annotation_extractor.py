"""
AnnotationExtractor 单元测试

覆盖从 APITestResult 提取业务码、消息、字段级错误、枚举含义等逻辑。
"""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.services.annotation_service import AnnotationExtractor


class TestAnnotationExtractor:
    def _make_result(
        self,
        endpoint: str = "/api/users",
        method: str = "POST",
        status: int = 200,
        body: dict | None = None,
        request_data: dict | None = None,
    ):
        return SimpleNamespace(
            id=uuid4(),
            test_run_id=uuid4(),
            api_test_id=uuid4(),
            scenario_name="unit-test",
            endpoint=endpoint,
            method=method,
            response_data={"status": status, "status_code": status, "body": body},
            request_data=request_data or {},
        )

    @pytest.fixture
    def extractor(self):
        endpoint_map = {
            ("/API/USERS", "POST"): UUID("12345678-1234-5678-1234-567812345678"),
        }
        return AnnotationExtractor(endpoint_map)

    def test_success_code_extracted(self, extractor):
        result = self._make_result(
            status=200,
            body={"code": 0, "message": "ok", "data": {"id": "1"}},
        )
        annotations = extractor.extract(result)
        assert len(annotations) == 1
        assert annotations[0]["annotation_type"] == "business_success_code"
        assert annotations[0]["business_code"] == "0"
        assert annotations[0]["http_status"] == 200

    def test_error_code_extracted(self, extractor):
        result = self._make_result(
            status=400,
            body={"code": "4009", "message": "参数不能为空"},
        )
        annotations = extractor.extract(result)
        assert len(annotations) == 1
        assert annotations[0]["annotation_type"] == "business_error_code"
        assert annotations[0]["business_code"] == "4009"
        assert annotations[0]["http_status"] == 400
        assert annotations[0]["message_pattern"] == "参数不能为空"

    def test_field_errors_extracted(self, extractor):
        result = self._make_result(
            status=400,
            body={
                "code": "4001",
                "message": "请求参数错误",
                "errors": [
                    {"field": "email", "code": "4002", "message": "邮箱格式不正确"},
                    {"field": "age", "code": "4003", "message": "年龄超出范围"},
                ],
            },
            request_data={"body": {"name": "test"}},
        )
        annotations = extractor.extract(result)
        types = {ann["annotation_type"] for ann in annotations}
        assert "business_error_code" in types
        assert "field_validation" in types

        field_anns = [ann for ann in annotations if ann["annotation_type"] == "field_validation"]
        assert len(field_anns) == 2
        email_ann = next(ann for ann in field_anns if ann["field_path"] == "body.email")
        assert email_ann["business_code"] == "4002"
        assert email_ann["message_pattern"] == "邮箱格式不正确"

    def test_enum_meaning_extracted(self, extractor):
        result = self._make_result(
            status=200,
            body={"code": 0, "status": "pending", "type": "vip"},
        )
        annotations = extractor.extract(result)
        enum_anns = [ann for ann in annotations if ann["annotation_type"] == "enum_meaning"]
        assert len(enum_anns) == 2
        paths = {ann["field_path"] for ann in enum_anns}
        assert "body.status" in paths
        assert "body.type" in paths

    def test_unknown_endpoint_returns_empty(self):
        extractor = AnnotationExtractor({})
        result = self._make_result()
        annotations = extractor.extract(result)
        assert annotations == []

    def test_string_body_is_ignored(self, extractor):
        result = self._make_result(
            status=200,
            body='{"code":0}',
        )
        annotations = extractor.extract(result)
        assert annotations == []

    def test_infer_required_missing(self, extractor):
        result = self._make_result(
            status=400,
            body={
                "code": "4001",
                "errors": [
                    {"field": "email", "message": "email is required"},
                ],
            },
            request_data={"body": {}},
        )
        annotations = extractor.extract(result)
        field_ann = next(
            ann for ann in annotations if ann["annotation_type"] == "field_validation"
        )
        assert field_ann["condition"] == "required_missing"

    def test_business_code_field_variants(self, extractor):
        """测试多种业务码字段名都能被识别"""
        for field in ("code", "errorCode", "error_code", "errCode", "status"):
            result = self._make_result(
                status=400,
                body={field: f"{field}-value", "message": "bad"},
            )
            annotations = extractor.extract(result)
            assert annotations[0]["business_code"] == f"{field}-value"
