"""
API 业务语义标注工具

提供标注查询、从历史 trace 中收割标注等功能。
Phase 2 会加入主动探测工具 probe_endpoint_validation。
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db
from app.models.api_endpoint import APIEndpoint
from app.models.project import Project
from app.repositories.api_annotation_repo import APIAnnotationRepository
from app.services.annotation_service import AnnotationService
from app.services.probe_executor import ProbeExecutor
from app.utils.exceptions import BadRequestException


def _project_identifier_to_id(
    session: AsyncSession,
    project_identifier: str,
) -> Optional[UUID]:
    """把项目标识符解析为项目 ID"""
    stmt = select(Project.id).where(Project.identifier == project_identifier)
    result = session.execute(stmt)
    row = result.scalar_one_or_none()
    return row


@tool
async def get_endpoint_annotations(
    endpoint_id: str,
    annotation_type: Optional[str] = None,
    include_disabled: bool = False,
) -> str:
    """
    获取 API 端点的业务语义标注

    返回该端点已沉淀的业务成功码、业务错误码、字段级校验规则、枚举含义等。
    生成用例前优先调用本工具，以生成更精确的成功/错误断言。

    Args:
        endpoint_id: API 端点 ID
        annotation_type: 可选，按标注类型过滤
            - business_success_code: 业务成功码
            - business_error_code: 业务错误码
            - field_validation: 字段级校验规则
            - enum_meaning: 枚举含义
            - dependency: 接口依赖
            - state_constraint: 状态约束
        include_disabled: 是否包含已失效标注

    Returns:
        JSON 格式的标注列表

    Example:
        >>> result = await get_endpoint_annotations(
        ...     endpoint_id="550e8400-e29b-41d4-a716-446655440000",
        ...     annotation_type="business_error_code"
        ... )
    """
    try:
        endpoint_uuid = UUID(endpoint_id)
    except ValueError:
        return json.dumps({
            "success": False,
            "error": f"无效的端点 ID: {endpoint_id}",
        }, ensure_ascii=False, indent=2)

    async for db in get_db():
        try:
            endpoint = await db.get(APIEndpoint, endpoint_uuid)
            if not endpoint:
                return json.dumps({
                    "success": False,
                    "error": f"端点 {endpoint_id} 不存在",
                }, ensure_ascii=False, indent=2)

            repo = APIAnnotationRepository(db)
            annotations = await repo.list_for_endpoint(
                project_id=endpoint.project_id,
                endpoint_id=endpoint_uuid,
                annotation_type=annotation_type,
                include_disabled=include_disabled,
            )

            data = [_annotation_to_dict(ann) for ann in annotations]
            return json.dumps({
                "success": True,
                "total": len(data),
                "endpoint_id": endpoint_id,
                "annotation_type": annotation_type,
                "annotations": data,
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"查询标注失败: {str(e)}",
            }, ensure_ascii=False, indent=2)


@tool
async def harvest_annotations_from_traces(
    project_identifier: str,
    endpoint_id: Optional[str] = None,
    since: Optional[str] = None,
    max_results: int = 200,
) -> str:
    """
    从历史 API 测试执行结果（trace）中自动提取业务语义标注

    扫描 APITestResult 中已有的请求/响应，提取业务成功码、业务错误码、
    字段级校验规则等，写入 api_annotations 标注库。

    Args:
        project_identifier: 项目标识符（如 PR-1）
        endpoint_id: 可选，只扫描指定端点
        since: 可选，ISO 格式时间字符串，只扫描该时间之后的结果
        max_results: 最大扫描结果数，默认 200

    Returns:
        JSON 格式的收割结果

    Example:
        >>> result = await harvest_annotations_from_traces(
        ...     project_identifier="PR-1",
        ...     max_results=100
        ... )
    """
    since_dt: Optional[datetime] = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            return json.dumps({
                "success": False,
                "error": f"无效的时间格式: {since}，请使用 ISO 格式",
            }, ensure_ascii=False, indent=2)

    endpoint_uuid: Optional[UUID] = None
    if endpoint_id:
        try:
            endpoint_uuid = UUID(endpoint_id)
        except ValueError:
            return json.dumps({
                "success": False,
                "error": f"无效的端点 ID: {endpoint_id}",
            }, ensure_ascii=False, indent=2)

    async for db in get_db():
        try:
            project_stmt = select(Project).where(Project.identifier == project_identifier)
            project_result = await db.execute(project_stmt)
            project = project_result.scalar_one_or_none()

            if not project:
                return json.dumps({
                    "success": False,
                    "error": f"项目 {project_identifier} 不存在",
                }, ensure_ascii=False, indent=2)

            service = AnnotationService(db)
            harvest_result = await service.harvest_from_test_results(
                project_id=project.id,
                endpoint_id=endpoint_uuid,
                since=since_dt,
                max_results=max_results,
            )

            await db.commit()

            return json.dumps({
                "success": True,
                "project_identifier": project_identifier,
                "project_id": str(project.id),
                **harvest_result,
            }, ensure_ascii=False, indent=2)

        except Exception as e:
            await db.rollback()
            return json.dumps({
                "success": False,
                "error": f"收割标注失败: {str(e)}",
            }, ensure_ascii=False, indent=2)


@tool
async def probe_endpoint_validation(
    project_identifier: str,
    endpoint_id: str,
    env_id: Optional[str] = None,
    probe_budget: int = 20,
    concurrency: int = 1,
    dry_run: bool = False,
) -> str:
    """
    对 API 端点执行主动验证层探测，从异常响应中沉淀业务语义标注

    本工具会基于 OpenAPI schema 生成单字段异常请求（如必填缺失、类型错误、
    格式错误、长度越界等），向测试环境发送，并将 4xx/5xx 响应中的业务码/
    错误信息写入 api_annotations。执行前受 HITL 确认，且仅允许 dev/test/
    staging/uat 等非生产环境。

    Args:
        project_identifier: 项目标识符（如 PR-1）
        endpoint_id: 要探测的 API 端点 ID
        env_id: 环境 ID（默认使用项目默认环境）
        probe_budget: 最大探测数，默认 20，上限 50
        concurrency: 并发数，默认 1，上限 3
        dry_run: 为 True 时只返回将要发送的请求列表，不实际执行

    Returns:
        JSON 格式的探测结果摘要

    Example:
        >>> result = await probe_endpoint_validation(
        ...     project_identifier="PR-1",
        ...     endpoint_id="550e8400-e29b-41d4-a716-446655440000",
        ...     dry_run=True
        ... )
    """
    try:
        endpoint_uuid = UUID(endpoint_id)
    except ValueError:
        return json.dumps({
            "success": False,
            "error": f"无效的端点 ID: {endpoint_id}",
        }, ensure_ascii=False, indent=2)

    async for db in get_db():
        try:
            executor = ProbeExecutor(db)
            result = await executor.probe_endpoint(
                project_identifier=project_identifier,
                endpoint_id=str(endpoint_uuid),
                env_id=env_id,
                probe_budget=probe_budget,
                concurrency=concurrency,
                dry_run=dry_run,
            )
            await db.commit()
            return json.dumps(result, ensure_ascii=False, indent=2, default=str)

        except BadRequestException as e:
            await db.rollback()
            return json.dumps({
                "success": False,
                "error": str(e),
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            await db.rollback()
            return json.dumps({
                "success": False,
                "error": f"主动探测失败: {str(e)}",
            }, ensure_ascii=False, indent=2)


def _annotation_to_dict(ann: Any) -> dict[str, Any]:
    """把 APIAnnotation 对象转为可序列化字典"""
    return {
        "id": str(ann.id),
        "project_id": str(ann.project_id),
        "endpoint_id": str(ann.endpoint_id) if ann.endpoint_id else None,
        "annotation_type": ann.annotation_type,
        "source": ann.source,
        "http_status": ann.http_status,
        "business_code": ann.business_code,
        "field_path": ann.field_path,
        "condition": ann.condition,
        "message_pattern": ann.message_pattern,
        "expected_value": ann.expected_value,
        "confidence": ann.confidence,
        "hit_count": ann.hit_count,
        "enabled": ann.enabled,
        "first_seen_at": ann.first_seen_at.isoformat() if ann.first_seen_at else None,
        "last_seen_at": ann.last_seen_at.isoformat() if ann.last_seen_at else None,
        "last_verified_at": ann.last_verified_at.isoformat() if ann.last_verified_at else None,
        "source_metadata": ann.source_metadata,
        "created_at": ann.created_at.isoformat() if ann.created_at else None,
        "updated_at": ann.updated_at.isoformat() if ann.updated_at else None,
    }
