"""
skeleton_tools 单元测试

覆盖 _enrich_skeletons_with_annotations 对正向/异常/字段级校验的 enrich 逻辑，
以及 _derive_skeletons 的 Invalid Dynamic Object（不存在资源 ID）骨架点推导。
"""

from types import SimpleNamespace

from app.agents.tools.api.skeleton_tools import (
    _derive_skeletons,
    _enrich_skeletons_with_annotations,
    _is_id_like_param,
    _make_point,
)


class TestEnrichSkeletonsWithAnnotations:
    def _make_annotation(
        self,
        annotation_type,
        http_status=None,
        business_code=None,
        field_path=None,
        condition=None,
        message_pattern=None,
        expected_value=None,
        confidence=0.6,
        hit_count=2,
    ):
        return SimpleNamespace(
            annotation_type=annotation_type,
            http_status=http_status,
            business_code=business_code,
            field_path=field_path,
            condition=condition,
            message_pattern=message_pattern,
            expected_value=expected_value,
            confidence=confidence,
            hit_count=hit_count,
        )

    def test_empty_annotations_returns_skeletons_unchanged(self):
        skeletons = [_make_point("p1", "functional", "request", "ok", 200, "合法请求", [])]
        result = _enrich_skeletons_with_annotations(skeletons, [])
        assert result == skeletons

    def test_success_code_enriches_functional_point(self):
        skeletons = [_make_point("正向", "functional", "request", "ok", 200, "合法", [])]
        annotations = [
            self._make_annotation(
                "business_success_code",
                http_status=200,
                business_code="0",
                expected_value={"code": "0"},
                confidence=0.9,
            ),
        ]
        result = _enrich_skeletons_with_annotations(skeletons, annotations)
        assert result[0]["expected_business_code"] == "0"
        assert any("业务成功码" in hint for hint in result[0]["assertion_hints"])

    def test_error_code_enriches_exception_point_by_status(self):
        skeletons = [_make_point("异常", "exception", "email", "bad", 400, "非法", [])]
        annotations = [
            self._make_annotation(
                "business_error_code",
                http_status=400,
                business_code="4009",
                message_pattern="参数校验失败",
            ),
        ]
        result = _enrich_skeletons_with_annotations(skeletons, annotations)
        assert result[0]["expected_business_code"] == "4009"
        assert result[0]["expected_message_contains"] == "参数校验失败"

    def test_field_validation_enriches_matching_target(self):
        skeletons = [_make_point("异常", "exception", "email", "bad", 400, "非法", [])]
        annotations = [
            self._make_annotation(
                "field_validation",
                http_status=400,
                business_code="4002",
                field_path="body.email",
                condition="format_error",
                message_pattern="邮箱格式不正确",
            ),
        ]
        result = _enrich_skeletons_with_annotations(skeletons, annotations)
        assert result[0]["expected_business_code"] == "4002"
        assert result[0]["expected_message_contains"] == "邮箱格式不正确"
        assert result[0]["condition"] == "format_error"

    def test_non_matching_field_ignored(self):
        skeletons = [_make_point("异常", "exception", "phone", "bad", 400, "非法", [])]
        annotations = [
            self._make_annotation(
                "field_validation",
                field_path="body.email",
                business_code="4002",
            ),
        ]
        result = _enrich_skeletons_with_annotations(skeletons, annotations)
        assert "expected_business_code" not in result[0]


class TestIsIdLikeParam:
    def test_matches_id_suffixes(self):
        assert _is_id_like_param("id") is True
        assert _is_id_like_param("customerId") is True
        assert _is_id_like_param("customer_id") is True
        assert _is_id_like_param("siteID") is True
        assert _is_id_like_param("siteIds") is True

    def test_rejects_plain_words(self):
        assert _is_id_like_param("valid") is False
        assert _is_id_like_param("grid") is False
        assert _is_id_like_param("pid") is False
        assert _is_id_like_param("page") is False
        assert _is_id_like_param("") is False


class TestInvalidDynamicObjectSkeleton:
    """路径参数为资源 ID 时应自动追加「不存在的资源」骨架点（RESTler Invalid Dynamic Object）"""

    def _derive(self, parameters):
        return _derive_skeletons(
            method="GET",
            path="/api/customers/{customerId}",
            parameters=parameters,
            request_body=None,
            responses={"200": {"description": "ok"}},
            security=None,
        )

    def test_path_id_param_generates_not_found_point(self):
        result = self._derive([
            {"name": "customerId", "in": "path", "required": True, "schema": {"type": "string"}}
        ])
        points = [s for s in result["skeletons"] if s["target"] == "customerId"]
        invalid = [s for s in points if "不存在的资源" in s["name"]]
        assert len(invalid) == 1
        point = invalid[0]
        assert point["category"] == "exception"
        assert point["expected_status"] == 404
        assert any("5xx" in hint or "500" in hint for hint in point["assertion_hints"])

    def test_query_id_param_not_triggered(self):
        """只有路径参数触发，query 中的 id 类参数不生成该点"""
        result = self._derive([
            {"name": "customerId", "in": "query", "schema": {"type": "string"}}
        ])
        assert not any("不存在的资源" in s["name"] for s in result["skeletons"])

    def test_plain_path_param_not_triggered(self):
        """非 ID 路径参数（如 {valid}）不生成该点"""
        result = self._derive([
            {"name": "slug", "in": "path", "required": True, "schema": {"type": "string"}}
        ])
        assert not any("不存在的资源" in s["name"] for s in result["skeletons"])
