"""
OpenAPI 本地 $ref 解引用（导入期一次性展开）

问题背景：端点的 parameters / request_body / responses 以原始片段存库，
真实企业文档（Knife4j/Apifox/Springfox 导出）几乎必用 $ref 引用
components/schemas（或 Swagger 2.0 的 definitions），不解引用时
字段级骨架推导、依赖推断、响应断言全部退化为「待补充」。

本模块在导入时把本地 $ref（#/... 开头的 JSON Pointer）就地展开：

- 仅解本地引用；外部引用（http://...、other.yaml#/...）原样保留
- 循环引用：撞环时保留 {"$ref": ...} 原样（下游骨架/推断有降级处理）
- 深度上限：默认 8 层，超限同样保留 $ref 原样
- $ref 同级键合并（OAS 3.1 语义；3.0 规范忽略同级，合并无害且更有用）
- allOf 浅合并：所有成员均解析为 object schema 时合并 properties/required
  （覆盖「继承式」schema 的主流写法；含未解析成员时放弃合并保留原样）

纯函数、不改动入参（返回新对象），便于单测。
"""

from typing import Any

_REF_KEY = "$ref"
MAX_REF_DEPTH = 8


def _resolve_pointer(ref: str, root: Any) -> Any:
    """解析本地 JSON Pointer（#/components/schemas/Pet）；失败返回 None"""
    if ref == "#":
        return root
    if not ref.startswith("#/"):
        return None
    current = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def _flatten_all_of(node: dict) -> dict:
    """allOf 浅合并：所有成员都是 object schema 时合并 properties/required"""
    all_of = node.get("allOf")
    if not isinstance(all_of, list) or not all_of:
        return node

    merged_props: dict = {}
    merged_required: list = []
    extras: dict = {}
    for member in all_of:
        if not isinstance(member, dict) or _REF_KEY in member:
            return node  # 有未解析成员，放弃合并
        mtype = member.get("type")
        if mtype not in (None, "object") and "properties" not in member:
            return node  # 非对象成员（如判别器/枚举），保守放弃
        merged_props.update(member.get("properties") or {})
        for req in member.get("required") or []:
            if req not in merged_required:
                merged_required.append(req)
        for key, value in member.items():
            if key not in ("properties", "required", "type"):
                extras.setdefault(key, value)

    result = {k: v for k, v in node.items() if k != "allOf"}
    result.setdefault("type", "object")
    if merged_props:
        result["properties"] = {**merged_props, **(result.get("properties") or {})}
    if merged_required:
        existing = result.get("required") or []
        result["required"] = existing + [r for r in merged_required if r not in existing]
    for key, value in extras.items():
        result.setdefault(key, value)
    return result


def _resolve(node: Any, root: Any, ref_stack: list, ref_depth: int, max_depth: int) -> Any:
    # ref_depth 只统计 $ref 链长度（A→B→C…），不随树层级增长——
    # 文档树本身被文档大小自然约束，URL 树嵌套不应消耗 ref 预算
    if not isinstance(node, (dict, list)):
        return node

    if isinstance(node, list):
        return [_resolve(item, root, ref_stack, ref_depth, max_depth) for item in node]

    ref = node.get(_REF_KEY)
    if isinstance(ref, str):
        if not ref.startswith("#"):
            return node  # 外部引用，保留原样
        if ref in ref_stack or ref_depth >= max_depth:
            return {_REF_KEY: ref}  # 循环引用/链超深：保留原样，下游降级
        target = _resolve_pointer(ref, root)
        if target is None:
            return node  # 指针无效，保留原样
        resolved = _resolve(target, root, ref_stack + [ref], ref_depth + 1, max_depth)
        if isinstance(resolved, dict):
            # 合并 $ref 同级键（同级覆盖被引方同名字段）
            siblings = {
                k: _resolve(v, root, ref_stack, ref_depth, max_depth)
                for k, v in node.items()
                if k != _REF_KEY
            }
            merged = dict(resolved)
            merged.update(siblings)
            return _flatten_all_of(merged)
        return resolved

    resolved_dict = {
        k: _resolve(v, root, ref_stack, ref_depth, max_depth)
        for k, v in node.items()
    }
    return _flatten_all_of(resolved_dict)


def resolve_refs(node: Any, root: Any, max_depth: int = MAX_REF_DEPTH) -> Any:
    """展开 node 中的本地 $ref，root 为完整 OpenAPI 文档。

    Args:
        node: 待展开的子树（通常是 paths 对象）
        root: 完整 OpenAPI 文档（JSON Pointer 的解析根）
        max_depth: 展开深度上限，超限保留 $ref 原样

    Returns:
        展开后的新对象（入参不被修改）
    """
    return _resolve(node, root, [], 0, max_depth)
