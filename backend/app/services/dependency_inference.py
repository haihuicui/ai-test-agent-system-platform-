"""
API 接口依赖确定性推断（RESTler 风格 producer-consumer 匹配）

在 OpenAPI 导入时，从端点的 parameters / request_body / responses 静态推断
接口间依赖关系，写入 api_annotations（annotation_type='dependency'，
source='openapi_inferred'），供 scenario agent 编排步骤时直接查询，
避免每次会话用 LLM 重复推断同一组依赖。

推断规则（保守优先，宁缺毋滥）：
1. 消费方收集：路径参数 {xxxId} / {id}、请求体中 *Id/*Ids 字段，视为资源引用
2. 生产方匹配：集合同路径上的 POST（创建接口），按实体名归一化匹配
   （camelCase / snake_case / kebab-case / 单复数）
3. ID 获取方式：检查生产方 2xx 响应 schema 是否含 id 类字段；
   不含（仅 code/message 包装）时标记 id_source='none' 并给出
   lookup 提示（同集合 GET 列表接口，按 name 定位）
4. 文档声明优先：消费方 linked_endpoints（OpenAPI links）已声明该参数
   的来源时，跳过推断（声明高于推断）

写入策略：幂等 upsert——重复导入不新增记录、不膨胀置信度；
同自然键的 manual 标注存在时跳过（人工修正优先于推断）。
"""

import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_annotation import APIAnnotation

# 推断标注的固定字段
ANNOTATION_TYPE = "dependency"
SOURCE = "openapi_inferred"
CONDITION = "requires_resource"
INFERRED_CONFIDENCE = 0.6

# 版本/通用路径段，不参与实体名匹配
_NON_ENTITY_SEGMENTS = {"api", "v1", "v2", "v3", "v4", "rest", "open", "openapi", "internal", "admin", "web"}

# 响应包装层，解包一层找 id 字段
_RESPONSE_WRAPPERS = ("data", "result", "payload", "body")
_ID_FIELD_NAMES = ("id", "ID", "Id")


def _id_ref_entity(name: str) -> Optional[str]:
    """判断字段名是否为资源 ID 引用，返回实体前缀（未归一化）。

    匹配 customerId / customer_id / customerID / samplingSiteIds / id；
    不匹配 valid / grid / pid 等恰巧以 id 结尾的普通单词。
    """
    if not name:
        return None
    if name == "id":
        return ""
    for suffix in ("_ids", "_IDs", "Ids"):
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    for suffix in ("_id", "_ID", "Id", "ID"):
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return None


def _normalize_entity(raw: str) -> str:
    """实体名归一化：去分隔符、转小写。customer_id / customerId / customer-id → customerid"""
    return re.sub(r"[-_\s]", "", raw).lower()


def _entity_variants(entity: str) -> set[str]:
    """实体名的单复数变体集合（归一化后）"""
    base = _normalize_entity(entity)
    variants = {base}
    if base.endswith("ies"):
        variants.add(base[:-3] + "y")
    elif base.endswith("es"):
        variants.add(base[:-2])
    elif base.endswith("s"):
        variants.add(base[:-1])
    else:
        variants.add(base + "s")
    return variants


def _static_segments(path: str) -> list[str]:
    """路径的静态段（跳过 {param} 与版本/通用段），保持顺序"""
    segments = []
    for seg in (path or "").strip("/").split("/"):
        if not seg or seg.startswith("{"):
            continue
        norm = _normalize_entity(seg)
        if norm and norm not in _NON_ENTITY_SEGMENTS:
            segments.append(norm)
    return segments


def _is_collection_path(path: str) -> bool:
    """集合路径：最后一段不是 {param}，如 /api/customers"""
    parts = (path or "").strip("/").split("/")
    return bool(parts) and not parts[-1].startswith("{")


def _parent_collection_path(path: str) -> Optional[str]:
    """/api/customers/{id} → /api/customers；非参数结尾的路径返回 None"""
    parts = (path or "").strip("/").split("/")
    if len(parts) >= 2 and parts[-1].startswith("{"):
        return "/" + "/".join(parts[:-1])
    return None


def _schema_properties(schema: Any) -> Optional[dict]:
    """从原始（可能含 $ref）schema 中取 properties；$ref 未解析返回 None"""
    if not isinstance(schema, dict) or "$ref" in schema:
        return None
    props = schema.get("properties")
    return props if isinstance(props, dict) else None


def _response_id_path(responses: Optional[dict], entity: str) -> Optional[str]:
    """检查 2xx 响应 schema 是否含 id 类字段，返回 JSONPath（如 $.data.id）。

    $ref 未解析或找不到时返回 None。
    """
    if not isinstance(responses, dict):
        return None
    for status, resp in responses.items():
        if not str(status).startswith("2") or not isinstance(resp, dict):
            continue
        content = resp.get("content") or {}
        if not isinstance(content, dict):
            continue
        media = content.get("application/json") or next(iter(content.values()), None)
        if not isinstance(media, dict):
            continue
        props = _schema_properties(media.get("schema"))
        if props is None:
            continue
        # 顶层直接含 id
        for id_field in _ID_FIELD_NAMES:
            if id_field in props:
                return f"$.{id_field}"
        entity_id = f"{entity}Id" if entity else None
        if entity_id and entity_id in props:
            return f"$.{entity_id}"
        # 解包一层 data/result
        for wrapper in _RESPONSE_WRAPPERS:
            inner = _schema_properties(props.get(wrapper))
            if not inner:
                continue
            for id_field in _ID_FIELD_NAMES:
                if id_field in inner:
                    return f"$.{wrapper}.{id_field}"
            if entity_id and entity_id in inner:
                return f"$.{wrapper}.{entity_id}"
    return None


def _response_schema_known(responses: Optional[dict]) -> bool:
    """2xx 响应 schema 是否可判读（存在非 $ref 的 properties）"""
    if not isinstance(responses, dict):
        return False
    for status, resp in responses.items():
        if not str(status).startswith("2") or not isinstance(resp, dict):
            continue
        content = resp.get("content") or {}
        if not isinstance(content, dict):
            continue
        media = content.get("application/json") or next(iter(content.values()), None)
        if isinstance(media, dict) and _schema_properties(media.get("schema")) is not None:
            return True
    return False


def _request_body_properties(request_body: Optional[dict]) -> dict:
    """从原始 requestBody 中取 JSON schema properties；取不到返回空 dict"""
    if not isinstance(request_body, dict):
        return {}
    content = request_body.get("content") or {}
    if not isinstance(content, dict):
        return {}
    media = content.get("application/json") or next(iter(content.values()), None)
    if not isinstance(media, dict):
        return {}
    return _schema_properties(media.get("schema")) or {}


def _declared_link_params(linked_endpoints: Optional[list]) -> set[str]:
    """消费方已声明的 link 目标参数名集合（这些参数的依赖以文档声明为准）"""
    params: set[str] = set()
    for link in linked_endpoints or []:
        if not isinstance(link, dict) or not link.get("target"):
            continue
        for key in (link.get("parameters") or {}).keys():
            params.add(str(key))
    return params


def infer_endpoint_dependencies(endpoints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """从端点集合静态推断 producer-consumer 依赖。

    Args:
        endpoints: [{endpoint_id, method, path, parameters, request_body,
                     responses, linked_endpoints}]，通常为同一次导入的端点

    Returns:
        [{consumer_endpoint_id, field_path, condition, message_pattern,
          expected_value}]，可直接写入 api_annotations
    """
    producers = [
        ep for ep in endpoints
        if (ep.get("method") or "").upper() == "POST" and _is_collection_path(ep.get("path") or "")
    ]

    candidates: list[dict[str, Any]] = []

    for ep in endpoints:
        path = ep.get("path") or ""
        consumer_id = ep.get("endpoint_id")
        if not consumer_id:
            continue
        declared = _declared_link_params(ep.get("linked_endpoints"))

        # ---- 消费方资源引用收集：(field_path, param_name, entity) ----
        refs: list[tuple[str, str, str]] = []
        for param in ep.get("parameters") or []:
            if not isinstance(param, dict) or param.get("in") != "path":
                continue
            pname = param.get("name")
            entity = _id_ref_entity(pname or "")
            if entity is not None:
                refs.append((f"path.{pname}", pname, entity))
        for field in _request_body_properties(ep.get("request_body")):
            entity = _id_ref_entity(field)
            if entity:  # 裸 'id' 字段不视为跨资源引用
                refs.append((f"body.{field}", field, entity))

        for field_path, param_name, entity in refs:
            if param_name in declared:
                continue  # 文档已声明，声明优先

            # ---- 生产方匹配 ----
            producer = None
            if entity == "":
                # {id}：生产方为父集合路径上的 POST
                parent = _parent_collection_path(path)
                if parent:
                    producer = next(
                        (p for p in producers if (p.get("path") or "").rstrip("/") == parent.rstrip("/")),
                        None,
                    )
            else:
                variants = _entity_variants(entity)
                for p in producers:
                    if p.get("endpoint_id") == consumer_id:
                        continue
                    segments = _static_segments(p.get("path") or "")
                    if segments and segments[-1] in variants:
                        producer = p
                        break

            if producer is None:
                continue

            # ---- ID 获取方式 ----
            entity_norm = _normalize_entity(entity)
            id_path = _response_id_path(producer.get("responses"), entity)
            lookup = None
            if id_path is None and _response_schema_known(producer.get("responses")):
                # 创建响应确定不含 ID（如仅 code/message）→ 需列表接口按 name 定位
                list_ep = next(
                    (
                        e for e in endpoints
                        if (e.get("method") or "").upper() == "GET"
                        and (e.get("path") or "").rstrip("/") == (producer.get("path") or "").rstrip("/")
                    ),
                    None,
                )
                lookup = {
                    "method": "GET",
                    "path": producer.get("path"),
                    "by": "name",
                    "endpoint_id": list_ep.get("endpoint_id") if list_ep else None,
                }

            producer_desc = f"{producer.get('method')} {producer.get('path')}"
            if id_path:
                how = f"从创建响应 {id_path} 提取"
            elif lookup:
                how = "创建响应不含资源 ID，需经列表接口按 name 定位"
            else:
                how = "创建响应 schema 未持久化（$ref），ID 提取路径待确认"

            candidates.append({
                "consumer_endpoint_id": consumer_id,
                "field_path": field_path,
                "condition": CONDITION,
                "message_pattern": f"{param_name} 依赖 {producer_desc} 创建的资源；{how}",
                "expected_value": {
                    "kind": "path_param" if field_path.startswith("path.") else "body_field",
                    "field": param_name,
                    "entity": entity_norm,
                    "producer": {
                        "endpoint_id": producer.get("endpoint_id"),
                        "method": producer.get("method"),
                        "path": producer.get("path"),
                    },
                    "id_source": "response" if id_path else ("none" if lookup else "unknown"),
                    "producer_id_path": id_path,
                    "lookup": lookup,
                },
            })

    return candidates


async def upsert_inferred_dependencies(
    db: AsyncSession,
    project_id: UUID,
    candidates: list[dict[str, Any]],
) -> dict[str, int]:
    """把推断依赖幂等写入 api_annotations。

    - 同自然键（endpoint_id + dependency + field_path + requires_resource）的
      manual 标注存在 → 跳过（人工修正优先）
    - 同自然键的非 manual 标注存在 → 更新内容，不新增、不膨胀置信度
    - 否则新建，confidence=0.6
    """
    created = updated = skipped_manual = 0
    now = datetime.now(timezone.utc)

    for cand in candidates:
        consumer_id = UUID(cand["consumer_endpoint_id"]) if isinstance(
            cand["consumer_endpoint_id"], str
        ) else cand["consumer_endpoint_id"]

        stmt = select(APIAnnotation).where(
            APIAnnotation.endpoint_id == consumer_id,
            APIAnnotation.annotation_type == ANNOTATION_TYPE,
            APIAnnotation.http_status.is_(None),
            APIAnnotation.business_code.is_(None),
            APIAnnotation.field_path == cand["field_path"],
            APIAnnotation.condition == cand["condition"],
        )
        result = await db.execute(stmt)
        existing = result.scalars().all()

        if any(a.source == "manual" for a in existing):
            skipped_manual += 1
            continue

        if existing:
            ann = existing[0]
            ann.expected_value = cand["expected_value"]
            ann.message_pattern = cand["message_pattern"]
            ann.source = SOURCE
            ann.enabled = True
            ann.last_seen_at = now
            updated += 1
        else:
            db.add(APIAnnotation(
                project_id=project_id,
                endpoint_id=consumer_id,
                annotation_type=ANNOTATION_TYPE,
                source=SOURCE,
                field_path=cand["field_path"],
                condition=cand["condition"],
                message_pattern=cand["message_pattern"],
                expected_value=cand["expected_value"],
                confidence=INFERRED_CONFIDENCE,
                hit_count=1,
                enabled=True,
                first_seen_at=now,
                last_seen_at=now,
            ))
            created += 1

    await db.flush()
    return {"created": created, "updated": updated, "skipped_manual": skipped_manual}
