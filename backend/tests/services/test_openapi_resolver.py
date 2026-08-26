"""openapi_resolver 单元测试

覆盖 resolve_refs 的核心规则：
- 本地 $ref 展开（OAS3 components / Swagger 2.0 definitions）
- $ref 同级键合并（同级覆盖被引方同名字段）
- allOf 浅合并（继承式 schema）
- 循环引用保留 $ref 原样
- 外部引用原样保留
- 深度上限保护
- 无效指针原样保留
- 输入对象不被修改

纯函数测试，不依赖数据库。
"""

from app.services.openapi_resolver import resolve_refs


def _root():
    return {
        "components": {
            "schemas": {
                "Pet": {
                    "type": "object",
                    "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
                    "required": ["name"],
                },
                "Error": {
                    "type": "object",
                    "properties": {"code": {"type": "integer"}, "message": {"type": "string"}},
                },
                "Base": {
                    "type": "object",
                    "properties": {"id": {"type": "integer"}, "createdAt": {"type": "string"}},
                    "required": ["id"],
                },
                "Node": {
                    "type": "object",
                    "properties": {"child": {"$ref": "#/components/schemas/Node"}},
                },
            }
        },
        "definitions": {  # Swagger 2.0 风格
            "Legacy": {"type": "object", "properties": {"legacyId": {"type": "string"}}},
        },
    }


class TestLocalRefResolution:
    def test_resolves_component_schema_ref(self):
        node = {"schema": {"$ref": "#/components/schemas/Pet"}}
        result = resolve_refs(node, _root())
        assert result["schema"]["type"] == "object"
        assert "id" in result["schema"]["properties"]
        assert result["schema"]["required"] == ["name"]

    def test_resolves_swagger2_definitions_ref(self):
        node = {"schema": {"$ref": "#/definitions/Legacy"}}
        result = resolve_refs(node, _root())
        assert "legacyId" in result["schema"]["properties"]

    def test_nested_refs_resolved_recursively(self):
        root = _root()
        root["components"]["schemas"]["Wrapper"] = {
            "type": "object",
            "properties": {"pet": {"$ref": "#/components/schemas/Pet"}},
        }
        node = {"schema": {"$ref": "#/components/schemas/Wrapper"}}
        result = resolve_refs(node, root)
        assert "id" in result["schema"]["properties"]["pet"]["properties"]

    def test_sibling_keys_override_and_merge(self):
        node = {"schema": {"$ref": "#/components/schemas/Pet", "description": "宠物", "type": "object"}}
        result = resolve_refs(node, _root())
        # 同级 description 被保留/覆盖合并，$ref 键消失
        assert "$ref" not in result["schema"]
        assert result["schema"]["description"] == "宠物"

    def test_ref_inside_array_items(self):
        node = {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/Pet"}}}
        result = resolve_refs(node, _root())
        assert "name" in result["schema"]["items"]["properties"]


class TestSafetyGuards:
    def test_circular_ref_kept_as_is(self):
        node = {"schema": {"$ref": "#/components/schemas/Node"}}
        result = resolve_refs(node, _root())
        child = result["schema"]["properties"]["child"]
        assert child == {"$ref": "#/components/schemas/Node"}

    def test_external_ref_kept_as_is(self):
        node = {"schema": {"$ref": "https://example.com/schemas.json#/Pet"}}
        result = resolve_refs(node, _root())
        assert result["schema"]["$ref"].startswith("https://")

    def test_invalid_pointer_kept_as_is(self):
        node = {"schema": {"$ref": "#/components/schemas/NotExist"}}
        result = resolve_refs(node, _root())
        assert result["schema"]["$ref"] == "#/components/schemas/NotExist"

    def test_depth_cap_limits_ref_chain(self):
        """深度上限约束的是 $ref 链长度（A→B→C…），而非文档树嵌套层级"""
        root = {"components": {"schemas": {}}}
        # 构造 12 层 ref 链：S0 → S1 → ... → S11
        for i in range(12):
            nxt = {"$ref": f"#/components/schemas/S{i + 1}"} if i < 11 else {"type": "string"}
            root["components"]["schemas"][f"S{i}"] = {
                "type": "object",
                "properties": {"next": nxt},
            }
        node = {"schema": {"$ref": "#/components/schemas/S0"}}
        result = resolve_refs(node, root, max_depth=5)
        cursor = result["schema"]
        for _ in range(5):
            cursor = cursor["properties"]["next"]
        # 第 6 跳超出 ref 链预算，保留 $ref 原样
        assert cursor == {"$ref": "#/components/schemas/S5"}

    def test_input_not_mutated(self):
        node = {"schema": {"$ref": "#/components/schemas/Pet"}}
        resolve_refs(node, _root())
        assert node == {"schema": {"$ref": "#/components/schemas/Pet"}}


class TestAllOfFlatten:
    def test_all_of_merges_properties_and_required(self):
        node = {
            "schema": {
                "allOf": [
                    {"$ref": "#/components/schemas/Base"},
                    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
                ]
            }
        }
        result = resolve_refs(node, _root())
        schema = result["schema"]
        assert "allOf" not in schema
        assert set(schema["properties"]) == {"id", "createdAt", "name"}
        assert set(schema["required"]) == {"id", "name"}

    def test_all_of_with_unresolved_member_kept(self):
        node = {
            "schema": {
                "allOf": [
                    {"$ref": "https://example.com/x.json#/Base"},
                    {"type": "object", "properties": {"a": {"type": "string"}}},
                ]
            }
        }
        result = resolve_refs(node, _root())
        assert "allOf" in result["schema"]  # 含未解析成员，不合并
