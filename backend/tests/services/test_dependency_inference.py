"""dependency_inference 依赖推断单元测试

覆盖 infer_endpoint_dependencies 纯函数的 producer-consumer 匹配规则：
- 路径参数 {xxxId} / {id} 与创建接口（集合路径 POST）的配对
- 请求体 *Ids 字段（如 samplingSiteIds）的跨资源引用
- 创建响应不含 ID 时的 lookup 提示（id_source=none → 列表按 name 定位）
- 文档声明（linked_endpoints）优先于推断
- 非 ID 字段不误判（valid / page 等）

不依赖数据库。
"""

from app.services.dependency_inference import (
    _id_ref_entity,
    _is_collection_path,
    _normalize_entity,
    _parent_collection_path,
    _response_id_path,
    infer_endpoint_dependencies,
)


def _ep(endpoint_id, method, path, parameters=None, request_body=None, responses=None, links=None):
    return {
        "endpoint_id": endpoint_id,
        "method": method,
        "path": path,
        "parameters": parameters or [],
        "request_body": request_body,
        "responses": responses or {},
        "linked_endpoints": links,
    }


def _json_response(status, properties):
    """构造含 application/json schema 的 responses 片段"""
    return {
        str(status): {
            "description": "ok",
            "content": {"application/json": {"schema": {"type": "object", "properties": properties}}},
        }
    }


def _json_body(properties, required=None):
    return {
        "required": bool(required),
        "content": {
            "application/json": {
                "schema": {"type": "object", "properties": properties, "required": required or []}
            }
        },
    }


class TestHelpers:
    def test_id_ref_entity_matches_id_suffixes(self):
        assert _id_ref_entity("customerId") == "customer"
        assert _id_ref_entity("customer_id") == "customer"
        assert _id_ref_entity("customerID") == "customer"
        assert _id_ref_entity("samplingSiteIds") == "samplingSite"
        assert _id_ref_entity("id") == ""

    def test_id_ref_entity_rejects_plain_words(self):
        assert _id_ref_entity("valid") is None
        assert _id_ref_entity("grid") is None
        assert _id_ref_entity("pid") is None
        assert _id_ref_entity("name") is None
        assert _id_ref_entity("") is None

    def test_normalize_entity(self):
        assert _normalize_entity("customerId") == "customerid"
        assert _normalize_entity("sampling-site") == "samplingsite"
        assert _normalize_entity("customer_id") == "customerid"

    def test_collection_path(self):
        assert _is_collection_path("/api/customers") is True
        assert _is_collection_path("/api/customers/{id}") is False
        assert _parent_collection_path("/api/customers/{id}") == "/api/customers"
        assert _parent_collection_path("/api/customers") is None

    def test_response_id_path_unwraps_data(self):
        responses = _json_response(200, {"code": {}, "message": {}, "data": {"properties": {"id": {}, "name": {}}}})
        assert _response_id_path(responses, "customer") == "$.data.id"

    def test_response_id_path_none_when_only_code_message(self):
        responses = _json_response(200, {"code": {}, "message": {}})
        assert _response_id_path(responses, "customer") is None


class TestInferEndpointDependencies:
    def test_path_param_matches_collection_post(self):
        """GET /customers/{customerId} 依赖 POST /customers，创建响应含 data.id"""
        endpoints = [
            _ep("c1", "POST", "/api/customers",
                responses=_json_response(200, {"code": {}, "data": {"properties": {"id": {}, "name": {}}}})),
            _ep("c2", "GET", "/api/customers/{customerId}",
                parameters=[{"name": "customerId", "in": "path", "required": True, "schema": {"type": "string"}}]),
        ]
        result = infer_endpoint_dependencies(endpoints)
        assert len(result) == 1
        dep = result[0]
        assert dep["consumer_endpoint_id"] == "c2"
        assert dep["field_path"] == "path.customerId"
        assert dep["expected_value"]["producer"]["endpoint_id"] == "c1"
        assert dep["expected_value"]["id_source"] == "response"
        assert dep["expected_value"]["producer_id_path"] == "$.data.id"

    def test_bare_id_param_uses_parent_collection(self):
        """DELETE /orders/{id} 依赖父集合 POST /orders"""
        endpoints = [
            _ep("p1", "POST", "/orders",
                responses=_json_response(201, {"id": {}, "status": {}})),
            _ep("p2", "DELETE", "/orders/{id}",
                parameters=[{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}]),
        ]
        result = infer_endpoint_dependencies(endpoints)
        assert len(result) == 1
        assert result[0]["expected_value"]["producer"]["endpoint_id"] == "p1"
        assert result[0]["expected_value"]["producer_id_path"] == "$.id"

    def test_body_field_reference_kebab_case_producer(self):
        """POST /customers 请求体 samplingSiteIds 依赖 POST /sampling-sites"""
        endpoints = [
            _ep("s1", "POST", "/api/sampling-sites",
                responses=_json_response(200, {"code": {}, "data": {"properties": {"id": {}}}})),
            _ep("c1", "POST", "/api/customers",
                request_body=_json_body({
                    "name": {"type": "string"},
                    "samplingSiteIds": {"type": "array", "items": {"type": "string"}},
                }, required=["name"])),
        ]
        result = infer_endpoint_dependencies(endpoints)
        assert len(result) == 1
        dep = result[0]
        assert dep["consumer_endpoint_id"] == "c1"
        assert dep["field_path"] == "body.samplingSiteIds"
        assert dep["expected_value"]["kind"] == "body_field"
        assert dep["expected_value"]["producer"]["endpoint_id"] == "s1"

    def test_no_id_in_create_response_yields_lookup_hint(self):
        """创建响应仅 code/message → id_source=none + lookup 列表按 name 定位"""
        endpoints = [
            _ep("s1", "POST", "/api/sites",
                responses=_json_response(200, {"code": {}, "message": {}})),
            _ep("s2", "GET", "/api/sites",
                responses=_json_response(200, {"code": {}, "data": {"properties": {"records": {}, "total": {}}}})),
            _ep("c1", "PUT", "/api/sites/{siteId}",
                parameters=[{"name": "siteId", "in": "path", "required": True, "schema": {"type": "string"}}]),
        ]
        result = infer_endpoint_dependencies(endpoints)
        assert len(result) == 1
        dep = result[0]
        assert dep["expected_value"]["id_source"] == "none"
        assert dep["expected_value"]["lookup"]["method"] == "GET"
        assert dep["expected_value"]["lookup"]["endpoint_id"] == "s2"
        assert "按 name 定位" in dep["message_pattern"]

    def test_declared_links_take_precedence(self):
        """linked_endpoints 已声明该参数来源时跳过推断"""
        endpoints = [
            _ep("c1", "POST", "/customers",
                responses=_json_response(201, {"id": {}})),
            _ep("c2", "GET", "/customers/{customerId}",
                parameters=[{"name": "customerId", "in": "path", "required": True, "schema": {"type": "string"}}],
                links=[{
                    "status": "201",
                    "link_name": "GetCustomer",
                    "operation_id": "getCustomer",
                    "operation_ref": None,
                    "target": "GET /customers/{customerId}",
                    "description": None,
                    "parameters": {"customerId": "$response.body#/id"},
                }]),
        ]
        result = infer_endpoint_dependencies(endpoints)
        assert result == []

    def test_non_id_fields_ignored(self):
        """valid / page / name 等普通字段不产生依赖"""
        endpoints = [
            _ep("c1", "POST", "/customers",
                responses=_json_response(201, {"id": {}})),
            _ep("c2", "GET", "/customers",
                parameters=[
                    {"name": "page", "in": "query", "schema": {"type": "integer"}},
                    {"name": "valid", "in": "query", "schema": {"type": "boolean"}},
                ]),
        ]
        assert infer_endpoint_dependencies(endpoints) == []

    def test_query_id_params_not_collected(self):
        """只有路径参数与请求体字段参与依赖推断，query 中的 id 不收集"""
        endpoints = [
            _ep("c1", "POST", "/customers",
                responses=_json_response(201, {"id": {}})),
            _ep("c2", "GET", "/orders",
                parameters=[{"name": "customerId", "in": "query", "schema": {"type": "string"}}]),
        ]
        assert infer_endpoint_dependencies(endpoints) == []

    def test_no_producer_no_candidate(self):
        """找不到匹配的创建接口时不产生依赖"""
        endpoints = [
            _ep("c1", "GET", "/api/orders/{orderId}",
                parameters=[{"name": "orderId", "in": "path", "required": True, "schema": {"type": "string"}}]),
        ]
        assert infer_endpoint_dependencies(endpoints) == []

    def test_plural_singular_variants(self):
        """customers / customer 单复数变体可匹配"""
        endpoints = [
            _ep("c1", "POST", "/api/customer",
                responses=_json_response(200, {"id": {}})),
            _ep("c2", "GET", "/api/orders/{customerId}",
                parameters=[{"name": "customerId", "in": "path", "required": True, "schema": {"type": "string"}}]),
        ]
        result = infer_endpoint_dependencies(endpoints)
        assert len(result) == 1
        assert result[0]["expected_value"]["producer"]["endpoint_id"] == "c1"
