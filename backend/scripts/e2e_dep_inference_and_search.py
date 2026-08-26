"""
E2E 验证：list_api_endpoints 搜索优化 + 依赖推断全链路

Part 1（只读，跑在真实项目 PR-1 上）：
  - 裸拉全量 vs keyword+compact 的 token 体量对比
  - 归一化匹配（自动从项目里挑一个 kebab-case 路径做关键词）
  - limit 截断的 truncated/total_matched/hint

Part 2（临时项目 PR-E2E-DEP，跑完自动清理）：
  - 合成 OpenAPI（模拟 采样点/客户 跨模块依赖）→ OpenAPIParser 导入
  - 验证 api_annotations 写入 dependency 标注（含 id_source / lookup）
  - 验证幂等：重复 upsert 不新增
  - 验证 derive_test_skeleton 对 {customerId} 生成「不存在的资源」骨架点
  - 清理临时项目（CASCADE）

运行：backend/.venv/Scripts/python.exe backend/scripts/e2e_dep_inference_and_search.py
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, delete  # noqa: E402

from app.agents.tools.api.openapi_tools import list_api_endpoints  # noqa: E402
from app.agents.tools.api.skeleton_tools import derive_test_skeleton  # noqa: E402
from app.config.database import async_session_factory  # noqa: E402
from app.models.api_annotation import APIAnnotation  # noqa: E402
from app.models.api_endpoint import APIEndpoint  # noqa: E402
from app.models.folder import Folder  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.services.openapi_parser import OpenAPIParser  # noqa: E402

PASS, FAIL = "\033[92mPASS\033[0m", "\033[91mFAIL\033[0m"
_results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = ""):
    _results.append((ok, label))
    print(f"  [{PASS if ok else FAIL}] {label}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------- Part 1
async def part1_tool_search(project_identifier: str = "PR-1"):
    print(f"\n=== Part 1: list_api_endpoints 搜索优化（真实项目 {project_identifier}）===")

    # 1.1 全量（默认 limit）vs compact 体量对比
    full_raw = await list_api_endpoints.ainvoke({"project_identifier": project_identifier, "limit": 200})
    full = json.loads(full_raw)
    compact_raw = await list_api_endpoints.ainvoke(
        {"project_identifier": project_identifier, "limit": 200, "compact": True}
    )
    compact = json.loads(compact_raw)
    check(full["success"] and compact["success"], "全量/compact 调用成功")
    check(
        full["returned"] == compact["returned"],
        "compact 不丢条目",
        f"full={full['returned']} compact={compact['returned']} total_matched={full['total_matched']}",
    )
    ratio = len(full_raw) / max(len(compact_raw), 1)
    check(
        len(compact_raw) < len(full_raw),
        f"compact 显著省 token（{len(full_raw)}B → {len(compact_raw)}B，{ratio:.1f}x）",
    )

    endpoints = full["endpoints"]
    if not endpoints:
        check(False, f"{project_identifier} 无端点，跳过后续检查")
        return

    # 1.2 归一化匹配：挑一个含 - 或 _ 的路径段，转成 camelCase 当关键词
    kebab_ep = next(
        (e for e in endpoints if "-" in (e["path"].strip("/").split("/")[-1])),
        None,
    )
    if kebab_ep:
        last_seg = kebab_ep["path"].strip("/").split("/")[-1].replace("{", "").replace("}", "")
        camel_kw = last_seg.split("-")[0] + "".join(p.title() for p in last_seg.split("-")[1:])
        res = json.loads(await list_api_endpoints.ainvoke(
            {"project_identifier": project_identifier, "keyword": camel_kw, "compact": True}
        ))
        hit_paths = [e["path"] for e in res["endpoints"]]
        check(
            any(p == kebab_ep["path"] for p in hit_paths),
            f"归一化匹配：camelCase 关键词 '{camel_kw}' 命中 '{kebab_ep['path']}'",
            f"matched={res['total_matched']}, top={hit_paths[:3]}",
        )
    else:
        print("  (项目无 kebab-case 路径，跳过归一化匹配检查)")

    # 1.3 method + keyword 组合：找某资源的创建接口
    post_paths = [e["path"] for e in endpoints if e["method"] == "POST"]
    if post_paths:
        seg = post_paths[0].strip("/").split("/")[-1].replace("{", "").replace("}", "")
        kw = seg.split("-")[0].split("_")[0]
        res = json.loads(await list_api_endpoints.ainvoke(
            {"project_identifier": project_identifier, "method": "POST", "keyword": kw, "compact": True}
        ))
        check(
            res["total_matched"] >= 1 and any(p["method"] == "POST" for p in res["endpoints"]),
            f"降级链典型用法 method=POST + keyword='{kw}' 命中创建接口",
            f"matched={res['total_matched']}, top={[p['path'] for p in res['endpoints'][:3]]}",
        )

    # 1.4 limit 截断
    if full["total_matched"] > 2:
        res = json.loads(await list_api_endpoints.ainvoke(
            {"project_identifier": project_identifier, "limit": 2, "compact": True}
        ))
        check(
            res["truncated"] is True and res["returned"] == 2 and "hint" in res,
            "limit 截断显式报告 truncated + hint",
            f"total_matched={res['total_matched']} returned={res['returned']}",
        )

    # 1.5 相关性排序：段精确匹配应排第一
    first = endpoints[0]
    seg = first["path"].strip("/").split("/")[-1].replace("{", "").replace("}", "")
    res = json.loads(await list_api_endpoints.ainvoke(
        {"project_identifier": project_identifier, "keyword": seg, "compact": True}
    ))
    if res["total_matched"] >= 2:
        check(
            res["endpoints"][0]["path"] == first["path"],
            "相关性排序：段精确匹配排第一",
            f"top={res['endpoints'][0]['path']} score={res['endpoints'][0].get('match_score')}",
        )


# ---------------------------------------------------------------- Part 2
def _synthetic_spec() -> dict:
    """模拟「采样点 → 客户」跨模块依赖：创建不返 ID（采样点）vs 返 ID（客户）"""
    code_msg = {"type": "object", "properties": {"code": {"type": "integer"}, "message": {"type": "string"}}}
    return {
        "openapi": "3.0.0",
        "info": {"title": "E2E Dep API", "version": "1.0.0"},
        "paths": {
            "/api/sampling-sites": {
                "post": {
                    "tags": ["SamplingSite"],
                    "operationId": "createSite",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {
                        "type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}}},
                    "responses": {"200": {"description": "ok", "content": {"application/json": {"schema": code_msg}}}},
                },
                "get": {
                    "tags": ["SamplingSite"],
                    "operationId": "listSites",
                    "responses": {"200": {"description": "ok", "content": {"application/json": {"schema": {
                        "type": "object", "properties": {
                            "code": {"type": "integer"},
                            "data": {"type": "object", "properties": {"records": {"type": "array"}, "total": {"type": "integer"}}},
                        }}}}}},
                },
            },
            "/api/customers": {
                "post": {
                    "tags": ["Customer"],
                    "operationId": "createCustomer",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}, "samplingSiteIds": {"type": "array", "items": {"type": "string"}}},
                        "required": ["name"]}}}},
                    "responses": {"200": {"description": "ok", "content": {"application/json": {"schema": {
                        "type": "object", "properties": {
                            "code": {"type": "integer"},
                            "data": {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"}}},
                        }}}}}},
                },
            },
            "/api/customers/{customerId}": {
                "get": {
                    "tags": ["Customer"],
                    "operationId": "getCustomer",
                    "parameters": [{"name": "customerId", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "ok", "content": {"application/json": {"schema": code_msg}}}},
                },
                "delete": {
                    "tags": ["Customer"],
                    "operationId": "deleteCustomer",
                    "parameters": [{"name": "customerId", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "ok", "content": {"application/json": {"schema": code_msg}}}},
                },
            },
        },
    }


async def part2_dependency_inference():
    print("\n=== Part 2: 依赖推断全链路（临时项目 PR-E2E-DEP，自动清理）===")
    project_id = None
    try:
        async with async_session_factory() as session:
            # 建临时项目
            project = Project(
                name="E2E 依赖推断验证",
                identifier=f"PR-E2E-{uuid.uuid4().hex[:6].upper()}",
                description="e2e temp, auto cleanup",
                created_by=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            )
            session.add(project)
            await session.flush()
            project_id = project.id
            print(f"  临时项目: {project.identifier} ({project_id})")

            # 导入合成 OpenAPI
            parser = OpenAPIParser(session)
            result = await parser.parse_and_create_structure(
                project_id=project_id,
                parent_folder_id=None,
                schema_file_id=None,
                openapi_spec=_synthetic_spec(),
                user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            )
            dep_summary = result["summary"].get("dependencies_inferred", {})
            check(
                dep_summary.get("created", 0) >= 3,
                "导入时写入 dependency 标注（≥3 条：customerId×2 + samplingSiteIds）",
                json.dumps(dep_summary, ensure_ascii=False),
            )

            # 读回标注验证内容
            anns = (await session.execute(
                select(APIAnnotation).where(
                    APIAnnotation.project_id == project_id,
                    APIAnnotation.annotation_type == "dependency",
                )
            )).scalars().all()
            by_field = {a.field_path: a for a in anns}

            site_dep = by_field.get("body.samplingSiteIds")
            check(
                site_dep is not None
                and site_dep.expected_value["id_source"] == "none"
                and site_dep.expected_value["lookup"] is not None
                and site_dep.expected_value["producer"]["path"] == "/api/sampling-sites",
                "body.samplingSiteIds → producer=POST /api/sampling-sites，id_source=none + lookup 按 name 定位",
                site_dep.message_pattern if site_dep else "缺失",
            )
            check(
                site_dep is not None and site_dep.source == "openapi_inferred" and abs(site_dep.confidence - 0.6) < 1e-6,
                "标注来源 openapi_inferred，confidence=0.6",
            )

            cid_deps = [a for a in anns if a.field_path == "path.customerId"]
            check(
                len(cid_deps) == 2
                and all(a.expected_value["id_source"] == "response" for a in cid_deps)
                and all(a.expected_value["producer_id_path"] == "$.data.id" for a in cid_deps),
                "path.customerId（GET+DELETE）→ producer=POST /api/customers，id_source=response（$.data.id）",
            )

            # 幂等：再跑一次 upsert 不新增
            from app.services.dependency_inference import infer_endpoint_dependencies, upsert_inferred_dependencies
            endpoints = (await session.execute(
                select(APIEndpoint).where(APIEndpoint.project_id == project_id)
            )).scalars().all()
            ep_dicts = [{
                "endpoint_id": str(e.id), "method": e.method, "path": e.path,
                "parameters": e.parameters, "request_body": e.request_body,
                "responses": e.responses,
                "linked_endpoints": (e.custom_config or {}).get("linked_endpoints"),
            } for e in endpoints]
            again = await upsert_inferred_dependencies(session, project_id, infer_endpoint_dependencies(ep_dicts))
            check(
                again["created"] == 0 and again["updated"] == len(anns),
                "幂等：重复 upsert 不新增、不膨胀置信度",
                json.dumps(again),
            )

            # Invalid Dynamic Object 骨架点（真实端点走一遍工具）
            # 注意：derive_test_skeleton 自建 session 读库，必须先 commit 让端点可见
            await session.commit()

            cid_ep = next(e for e in endpoints if e.method == "GET" and "{customerId}" in e.path)
            skeleton = json.loads(await derive_test_skeleton.ainvoke({"endpoint_id": str(cid_ep.id)}))
            invalid = [s for s in skeleton.get("skeletons", []) if "不存在的资源" in s.get("name", "")]
            check(
                len(invalid) == 1 and invalid[0]["expected_status"] == 404,
                "derive_test_skeleton 对 {customerId} 生成「不存在的资源」骨架点（404，严禁 5xx）",
                skeleton.get("error", ""),
            )
    finally:
        # 清理：删项目（CASCADE 应带走 endpoints/annotations/folders）
        if project_id:
            async with async_session_factory() as session:
                await session.execute(delete(Project).where(Project.id == project_id))
                await session.commit()
            async with async_session_factory() as session:
                left = (await session.execute(
                    select(APIAnnotation).where(APIAnnotation.project_id == project_id)
                )).scalars().all()
                left_ep = (await session.execute(
                    select(APIEndpoint).where(APIEndpoint.project_id == project_id)
                )).scalars().all()
                check(not left and not left_ep, "临时项目已清理（CASCADE 删除端点与标注）")


# ---------------------------------------------------------------- Part 3
def _ref_spec() -> dict:
    """全 $ref 风格的文档（模拟 Knife4j/Apifox 真实导出）：
    请求体/响应全部引用 components.schemas，且跨模块依赖藏在 $ref 之后"""
    return {
        "openapi": "3.0.0",
        "info": {"title": "E2E Ref API", "version": "1.0.0"},
        "components": {
            "schemas": {
                "ApiResponse": {"type": "object", "properties": {
                    "code": {"type": "integer"}, "message": {"type": "string"}}},
                "SiteCreateRequest": {"type": "object", "required": ["name"], "properties": {
                    "name": {"type": "string"}, "location": {"type": "string"}}},
                "CustomerCreateRequest": {"type": "object", "required": ["name"], "properties": {
                    "name": {"type": "string"},
                    "samplingSiteIds": {"type": "array", "items": {"type": "string"}}}},
                "Customer": {"type": "object", "properties": {
                    "id": {"type": "string"}, "name": {"type": "string"}}},
                "CustomerCreated": {"type": "object", "properties": {
                    "code": {"type": "integer"},
                    "data": {"$ref": "#/components/schemas/Customer"}}},
            }
        },
        "paths": {
            "/api/sampling-sites": {
                "post": {
                    "tags": ["SamplingSite"], "operationId": "createSite",
                    "requestBody": {"required": True, "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/SiteCreateRequest"}}}},
                    "responses": {"200": {"description": "ok", "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/ApiResponse"}}}}},
                },
                "get": {
                    "tags": ["SamplingSite"], "operationId": "listSites",
                    "responses": {"200": {"description": "ok", "content": {"application/json": {
                        "schema": {"type": "object", "properties": {
                            "code": {"type": "integer"},
                            "data": {"type": "object", "properties": {
                                "records": {"type": "array"}, "total": {"type": "integer"}}}}}}}}},
                },
            },
            "/api/customers": {
                "post": {
                    "tags": ["Customer"], "operationId": "createCustomer",
                    "requestBody": {"required": True, "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/CustomerCreateRequest"}}}},
                    "responses": {"200": {"description": "ok", "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/CustomerCreated"}}}}},
                },
            },
            "/api/customers/{customerId}": {
                "get": {
                    "tags": ["Customer"], "operationId": "getCustomer",
                    "parameters": [{"name": "customerId", "in": "path", "required": True,
                                    "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "ok", "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/Customer"}}}}},
                },
                "delete": {
                    "tags": ["Customer"], "operationId": "deleteCustomer",
                    "parameters": [{"name": "customerId", "in": "path", "required": True,
                                    "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "ok", "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/ApiResponse"}}}}},
                },
            },
        },
    }


async def part3_ref_resolution_and_reimport():
    print("\n=== Part 3: $ref 解引用 + 幂等重导入（临时项目，自动清理）===")
    from app.models.openapi_spec_snapshot import OpenAPISpecSnapshot

    project_id = None
    try:
        async with async_session_factory() as session:
            project = Project(
                name="E2E Ref 验证",
                identifier=f"PR-REF-{uuid.uuid4().hex[:6].upper()}",
                description="e2e temp, auto cleanup",
                created_by=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            )
            session.add(project)
            await session.flush()
            project_id = project.id

            parser = OpenAPIParser(session)
            result = await parser.parse_and_create_structure(
                project_id=project_id, parent_folder_id=None, schema_file_id=None,
                openapi_spec=_ref_spec(),
                user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            )
            check(result["summary"].get("ref_resolution") == "ok", "$ref 解引用执行成功")

            endpoints = (await session.execute(
                select(APIEndpoint).where(APIEndpoint.project_id == project_id)
            )).scalars().all()
            create_customer = next(e for e in endpoints if e.method == "POST" and e.path == "/api/customers")

            # 1. 请求体 $ref 被展开（字段可见）
            body_schema = (create_customer.request_body["content"]["application/json"]["schema"])
            check(
                "$ref" not in body_schema and "samplingSiteIds" in (body_schema.get("properties") or {}),
                "请求体 $ref 已展开，samplingSiteIds 字段可见",
            )

            # 2. 关键价值：藏在 $ref 后的跨模块依赖被推断出来
            anns = (await session.execute(
                select(APIAnnotation).where(
                    APIAnnotation.project_id == project_id,
                    APIAnnotation.annotation_type == "dependency",
                )
            )).scalars().all()
            site_dep = next((a for a in anns if a.field_path == "body.samplingSiteIds"), None)
            check(
                site_dep is not None and site_dep.expected_value["id_source"] == "none",
                "藏在 $ref 后的 body.samplingSiteIds 依赖被推断（id_source=none）",
            )
            cid_deps = [a for a in anns if a.field_path == "path.customerId"]
            check(
                len(cid_deps) == 2
                and all(a.expected_value["producer_id_path"] == "$.data.id" for a in cid_deps),
                "响应 $ref（CustomerCreated→Customer.id）被穿透，producer_id_path=$.data.id",
            )

            # 3. spec 快照已留存
            snapshots = (await session.execute(
                select(OpenAPISpecSnapshot).where(OpenAPISpecSnapshot.project_id == project_id)
            )).scalars().all()
            check(
                len(snapshots) == 1 and snapshots[0].spec.get("info", {}).get("title") == "E2E Ref API",
                "完整 spec 快照已留存",
            )

            await session.commit()

        # 4. 幂等重导入（新 session 模拟第二次导入）
        async with async_session_factory() as session:
            parser = OpenAPIParser(session)
            spec2 = _ref_spec()
            spec2["paths"]["/api/customers"]["post"]["summary"] = "创建客户（V2）"
            result2 = await parser.parse_and_create_structure(
                project_id=project_id, parent_folder_id=None, schema_file_id=None,
                openapi_spec=spec2,
                user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            )
            summary2 = result2["summary"]
            check(
                summary2["endpoints_created"] == 0 and summary2["endpoints_updated"] == 5,
                "重导入幂等：0 新建 / 5 更新",
                f"created={summary2['endpoints_created']} updated={summary2['endpoints_updated']}",
            )
            endpoints2 = (await session.execute(
                select(APIEndpoint).where(APIEndpoint.project_id == project_id)
            )).scalars().all()
            folders2 = (await session.execute(
                select(Folder).where(Folder.project_id == project_id)
            )).scalars().all()
            check(len(endpoints2) == 5, "重导入后端点总数不变（无重复端点）")
            check(
                len(folders2) == 7,  # 2 个 tag 文件夹 + 5 个端点文件夹
                "重导入后文件夹无重复",
                f"folders={len(folders2)}",
            )
            updated_ep = next(e for e in endpoints2 if e.method == "POST" and e.path == "/api/customers")
            check(updated_ep.summary == "创建客户（V2）", "重导入就地更新端点字段（summary V2）")
            anns2 = (await session.execute(
                select(APIAnnotation).where(
                    APIAnnotation.project_id == project_id,
                    APIAnnotation.annotation_type == "dependency",
                )
            )).scalars().all()
            check(len(anns2) == 3, "重导入后 dependency 标注不重复（仍 3 条）")
            snapshots2 = (await session.execute(
                select(OpenAPISpecSnapshot).where(OpenAPISpecSnapshot.project_id == project_id)
            )).scalars().all()
            check(len(snapshots2) == 2, "每次导入追加一条快照（历史可审计）")
            await session.commit()
    finally:
        if project_id:
            async with async_session_factory() as session:
                await session.execute(delete(Project).where(Project.id == project_id))
                await session.commit()
            async with async_session_factory() as session:
                from app.models.openapi_spec_snapshot import OpenAPISpecSnapshot
                left = (await session.execute(
                    select(OpenAPISpecSnapshot).where(OpenAPISpecSnapshot.project_id == project_id)
                )).scalars().all()
                check(not left, "临时项目清理（快照随项目 CASCADE 删除）")


async def main():
    await part1_tool_search("PR-1")
    await part2_dependency_inference()
    await part3_ref_resolution_and_reimport()
    failed = [label for ok, label in _results if not ok]
    print(f"\n=== 结果: {len(_results) - len(failed)}/{len(_results)} 通过 ===")
    if failed:
        print("失败项:", *failed, sep="\n  - ")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
