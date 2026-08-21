"""OpenAPIParser 对 links / callbacks 的提取与依赖解析测试

覆盖两个纯函数：
- _group_endpoints_by_tag: 从 response 对象收集 links（按状态分组）与 operation 级 callbacks
- _resolve_linked_endpoints: 把 links 中的 operationId 解析为 "METHOD path"

不依赖数据库（_group_endpoints_by_tag 不触碰 self.db）。
"""

from app.services.openapi_parser import OpenAPIParser, _resolve_linked_endpoints


def _make_spec() -> dict:
    """含 links / callbacks / 无依赖端点的样例 OpenAPI 3.0 文档"""
    return {
        "openapi": "3.0.0",
        "info": {"title": "Orders API", "version": "1.0.0"},
        "paths": {
            "/orders": {
                "post": {
                    "tags": ["Orders"],
                    "operationId": "createOrder",
                    "summary": "Create order",
                    "responses": {
                        "201": {
                            "description": "Created",
                            "links": {
                                "GetOrder": {
                                    "operationId": "getOrder",
                                    "description": "Fetch the created order",
                                    "parameters": {"orderId": "$response.body#/id"},
                                },
                                "CancelOrder": {
                                    "operationRef": "#/paths/~1orders~1{orderId}~1delete",
                                },
                            },
                        },
                        "409": {
                            "description": "Conflict",
                            "links": {
                                "GetExisting": {"operationId": "getOrder"},
                            },
                        },
                    },
                }
            },
            "/orders/{id}": {
                "get": {
                    "tags": ["Orders"],
                    "operationId": "getOrder",
                    "responses": {"200": {"description": "OK"}},
                },
                "delete": {
                    "tags": ["Orders"],
                    "operationId": "deleteOrder",
                    "responses": {"204": {"description": "No Content"}},
                },
            },
            "/payments": {
                "post": {
                    "tags": ["Payments"],
                    "operationId": "createPayment",
                    "responses": {"202": {"description": "Accepted"}},
                    "callbacks": {
                        "onCompleted": {
                            "{$request.body#/callbackUrl}": {
                                "post": {"operationId": "handlePaymentCallback"}
                            }
                        }
                    },
                }
            },
            "/products": {
                "get": {
                    "tags": ["Products"],
                    "operationId": "listProducts",
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }


def _endpoints_by_path(parsed: dict) -> dict:
    """{path: endpoint_data} 便于断言"""
    result = {}
    for endpoints in parsed.values():
        for ep in endpoints:
            result[ep["path"]] = ep
    return result


class TestGroupEndpointsByTagLinks:
    def _group(self, spec: dict) -> dict:
        parser = OpenAPIParser(None)
        return parser._group_endpoints_by_tag(spec["paths"], spec.get("servers"))

    def test_links_collected_per_response_status(self):
        parsed = self._group(_make_spec())
        orders = _endpoints_by_path(parsed)["/orders"]
        assert set(orders["links"].keys()) == {"201", "409"}
        assert orders["links"]["201"]["GetOrder"]["parameters"] == {
            "orderId": "$response.body#/id"
        }
        assert orders["links"]["409"]["GetExisting"]["operationId"] == "getOrder"

    def test_callbacks_passed_through(self):
        parsed = self._group(_make_spec())
        payments = _endpoints_by_path(parsed)["/payments"]
        assert payments["callbacks"]["onCompleted"][
            "{$request.body#/callbackUrl}"
        ]["post"]["operationId"] == "handlePaymentCallback"

    def test_no_links_yields_none(self):
        parsed = self._group(_make_spec())
        products = _endpoints_by_path(parsed)["/products"]
        assert products["links"] is None
        assert products["callbacks"] is None

    def test_non_dict_response_and_link_ignored(self):
        spec = _make_spec()
        spec["paths"]["/products"]["get"]["responses"] = {
            "200": {"description": "OK", "links": "not-a-dict"},
            "201": "malformed-response",
        }
        parsed = self._group(spec)
        products = _endpoints_by_path(parsed)["/products"]
        # 原始列忠实保留 spec 原样：仅跳过非 dict 的 response（无法读取 .links），
        # 非法的 links 值不做清洗（忠实快照，供排查）
        assert products["links"] == {"200": "not-a-dict"}
        # 派生依赖清单对非法 link 条目做防御性过滤
        assert _resolve_linked_endpoints(products["links"], {}) == []


class TestResolveLinkedEndpoints:
    def test_resolves_operation_id_to_method_path(self):
        links = {
            "201": {
                "GetOrder": {
                    "operationId": "getOrder",
                    "description": "Fetch the created order",
                    "parameters": {"orderId": "$response.body#/id"},
                }
            }
        }
        targets = {"getOrder": "GET /orders/{id}", "createOrder": "POST /orders"}
        resolved = _resolve_linked_endpoints(links, targets)
        assert resolved == [
            {
                "status": "201",
                "link_name": "GetOrder",
                "operation_id": "getOrder",
                "operation_ref": None,
                "target": "GET /orders/{id}",
                "description": "Fetch the created order",
                "parameters": {"orderId": "$response.body#/id"},
            }
        ]

    def test_unresolvable_reference_kept_with_none_target(self):
        links = {
            "200": {
                "External": {"operationRef": "#/paths/~1other"},
                "Missing": {"operationId": "notInDoc"},
            }
        }
        resolved = _resolve_linked_endpoints(links, {"getOrder": "GET /orders/{id}"})
        by_name = {r["link_name"]: r for r in resolved}
        assert by_name["External"]["target"] is None
        assert by_name["External"]["operation_ref"] == "#/paths/~1other"
        assert by_name["Missing"]["target"] is None

    def test_malformed_entries_skipped(self):
        links = {
            "200": {"Good": {"operationId": "getOrder"}, "Bad": "oops"},
            "bad_status": "not-a-dict",
        }
        resolved = _resolve_linked_endpoints(links, {"getOrder": "GET /orders/{id}"})
        assert [r["link_name"] for r in resolved] == ["Good"]

    def test_empty_inputs(self):
        assert _resolve_linked_endpoints(None, {}) == []
        assert _resolve_linked_endpoints({}, {}) == []
