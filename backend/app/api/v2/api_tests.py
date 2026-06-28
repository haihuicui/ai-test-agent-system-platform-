"""
API 测试管理 API

提供 API 测试的 CRUD 操作接口
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query, UploadFile, File, Form
from fastapi.responses import Response, StreamingResponse

from app.api.deps import (
    APITestServiceDep,
    PaginationDep,
    DbSessionDep,
)
from app.schemas.common import SuccessResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.attachment import Attachment, AttachmentEntityType
from app.models.api_endpoint import APIEndpoint
from app.models.api_test import APITest
from app.repositories.api_test_repo import APITestRepository
from uuid import UUID
from datetime import datetime, timezone


router = APIRouter(prefix="/projects/{project_identifier}/api-tests")


# ============ API 测试管理接口 ============

@router.post(
    "",
    response_model=SuccessResponse,
    summary="创建 API 测试",
    description="创建新的 API 测试",
)
async def create_api_test(
    project_identifier: str,
    service: APITestServiceDep,
    name: str = Form(..., description="API 测试名称"),
    schema_path: str = Form(..., description="Schema 文件路径 (MinIO)"),
    script_path: str = Form(..., description="脚本文件路径 (MinIO)"),
    script_format: str = Form(default="playwright", description="脚本格式"),
    script_language: str = Form(default="typescript", description="脚本语言"),
    schema_url: Optional[str] = Form(None, description="Schema URL"),
    description: Optional[str] = Form(None, description="描述"),
    test_config: Optional[str] = Form(None, description="测试配置 (JSON)"),
    total_endpoints: int = Form(default=0, description="端点总数"),
    total_scenarios: int = Form(default=0, description="场景总数"),
    generation_params: Optional[str] = Form(None, description="生成参数 (JSON)"),
    test_case_id: Optional[str] = Form(None, description="关联的测试用例标识符 (TC-x)"),
):
    """创建 API 测试"""
    import json
    config = json.loads(test_config) if test_config else None
    gen_params = json.loads(generation_params) if generation_params else None

    result = await service.create_api_test(
        project_identifier=project_identifier,
        name=name,
        schema_path=schema_path,
        script_path=script_path,
        script_format=script_format,
        script_language=script_language,
        schema_url=schema_url,
        description=description,
        test_config=config,
        total_endpoints=total_endpoints,
        total_scenarios=total_scenarios,
        generation_params=gen_params,
        test_case_id=test_case_id,
    )

    return SuccessResponse(data=result, message="API 测试创建成功")

# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WldObllnPT06OGFkMjk0Nzc=

@router.get(
    "",
    response_model=SuccessResponse,
    summary="获取 API 测试列表",
    description="获取项目下的所有 API 测试列表，支持搜索和过滤",
)
async def list_api_tests(
    project_identifier: str,
    service: APITestServiceDep,
    pagination: PaginationDep,
    search: Optional[str] = Query(None, description="搜索关键词"),
    script_format: Optional[str] = Query(None, description="脚本格式过滤"),
):
    """获取 API 测试列表"""
    result = await service.list_api_tests(
        project_identifier=project_identifier,
        page=pagination.p,
        page_size=pagination.page_size,
        search=search,
        script_format=script_format,
    )

    return SuccessResponse(data=result)


@router.get(
    "/{api_test_id}",
    response_model=SuccessResponse,
    summary="获取 API 测试详情",
    description="获取指定 API 测试的详细信息",
)
async def get_api_test(
    project_identifier: str,
    api_test_id: str,
    service: APITestServiceDep,
):
    """获取 API 测试详情"""
    result = await service.get_api_test(
        project_identifier=project_identifier,
        api_test_id=api_test_id,
    )

    return SuccessResponse(data=result)


@router.patch(
    "/{api_test_id}",
    response_model=SuccessResponse,
    summary="更新 API 测试",
    description="更新 API 测试配置",
)
async def update_api_test(
    project_identifier: str,
    api_test_id: str,
    service: APITestServiceDep,
    name: Optional[str] = None,
    description: Optional[str] = None,
    test_config: Optional[dict] = None,
    test_case_id: Optional[str] = None,
):
    """更新 API 测试"""
    result = await service.update_api_test(
        project_identifier=project_identifier,
        api_test_id=api_test_id,
        name=name,
        description=description,
        test_config=test_config,
        test_case_id=test_case_id,
    )

    return SuccessResponse(data=result, message="API 测试更新成功")


@router.delete(
    "/{api_test_id}",
    response_model=SuccessResponse,
    summary="删除 API 测试",
    description="删除指定的 API 测试",
)
async def delete_api_test(
    project_identifier: str,
    api_test_id: str,
    service: APITestServiceDep,
):
    """删除 API 测试"""
    await service.delete_api_test(
        project_identifier=project_identifier,
        api_test_id=api_test_id,
    )

    return SuccessResponse(message="API 测试删除成功")
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WldObllnPT06OGFkMjk0Nzc=


# ============ Schema 上传接口 ============

@router.post(
    "/upload-schema",
    response_model=SuccessResponse,
    summary="上传 Schema 文件",
    description="上传 OpenAPI/Swagger/GraphQL Schema 文件到 MinIO",
)
async def upload_schema(
    project_identifier: str,
    service: APITestServiceDep,
    file: UploadFile = File(..., description="Schema 文件"),
):
    """上传 Schema 文件"""
    content = await file.read()
    content_type = file.content_type or "application/json"

    result = await service.upload_schema(
        project_identifier=project_identifier,
        filename=file.filename,
        content=content,
        content_type=content_type,
    )

    return SuccessResponse(data=result, message="Schema 文件上传成功")


@router.post(
    "/generate-from-schema",
    response_model=SuccessResponse,
    summary="从 Schema 生成 API 测试",
    description="使用 AI 智能体从 OpenAPI Schema 生成测试计划和脚本",
)
async def generate_from_schema(
    project_identifier: str,
    service: APITestServiceDep,
    schema_url: Optional[str] = Form(None, description="Schema URL（远程）"),
    schema_path: Optional[str] = Form(None, description="Schema 文件路径（已上传）"),
    script_format: str = Form(default="playwright", description="脚本格式"),
    script_language: str = Form(default="typescript", description="脚本语言"),
    include_auth: bool = Form(default=True, description="包含认证场景"),
    include_security: bool = Form(default=False, description="包含安全测试"),
    include_error_handling: bool = Form(default=True, description="包含错误处理"),
):
    """
    从 Schema 生成 API 测试（调用 api_agent）

    工作流程:
    1. 调用 api_agent.planner 生成测试计划
    2. 调用 api_agent.generator 生成测试脚本
    3. 返回生成的计划和脚本
    """
    import asyncio
    from app.agents.api.agent import agent

    # 准备参数
    params = {
        "schemaUrl": schema_url,
        "schemaPath": schema_path,
        "outputFormat": script_format,
        "language": script_language,
        "includeAuth": include_auth,
        "includeSecurity": include_security,
        "includeErrorHandling": include_error_handling,
        "outputPath": f"./api-test-plan-{project_identifier}.md",
    }

    # 构造用户消息
    if schema_url:
        user_message = f"为这个 API 生成测试计划: {schema_url}"
    elif schema_path:
        user_message = f"为这个 API Schema 文件生成测试计划: {schema_path}"
    else:
        return SuccessResponse(
            data=None,
            message="请提供 schema_url 或 schema_path"
        )

    try:
        # 调用 agent 生成测试计划
        planner_result = await agent.ainvoke({
            "messages": [user_message]
        })

        # 提取生成的测试计划内容
        # 注意: 实际实现需要解析 agent 的返回结果
        test_plan_content = planner_result.get("messages", [])[-1].content if planner_result else ""

        # TODO: 这里还需要调用 generator 生成实际的测试脚本
        # 暂时返回测试计划和占位符脚本
        result = {
            "test_plan": test_plan_content,
            "test_script": f"// Test script will be generated by api_agent.generator\n// Format: {script_format}\n// Language: {script_language}",
            "statistics": {
                "total_endpoints": 0,  # 从测试计划中提取
                "total_scenarios": 0,   # 从测试计划中提取
            }
        }

        return SuccessResponse(
            data=result,
            message="AI 生成成功"
        )

    except Exception as e:
        return SuccessResponse(
            data=None,
            message=f"AI 生成失败: {str(e)}"
        )

# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WldObllnPT06OGFkMjk0Nzc=

# ============ 测试脚本管理接口 ============

@router.get(
    "/{api_test_id}/script",
    response_class=Response,
    summary="获取测试脚本",
    description="下载 API 测试的脚本文件",
)
async def get_test_script(
    project_identifier: str,
    api_test_id: str,
    service: APITestServiceDep,
):
    """获取测试脚本内容"""
    script_content = await service.get_test_script(
        project_identifier=project_identifier,
        api_test_id=api_test_id,
    )

    return Response(
        content=script_content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=api-test-{api_test_id}.ts"
        }
    )


@router.put(
    "/{api_test_id}/script",
    response_model=SuccessResponse,
    summary="更新测试脚本",
    description="更新 API 测试的脚本内容",
)
async def update_test_script(
    project_identifier: str,
    api_test_id: str,
    service: APITestServiceDep,
    script_content: str = Form(..., description="脚本内容"),
):
    """更新测试脚本内容"""
    result = await service.update_test_script(
        project_identifier=project_identifier,
        api_test_id=api_test_id,
        script_content=script_content,
    )

    return SuccessResponse(data=result)


# ============ 测试执行接口 ============

@router.post(
    "/{api_test_id}/run",
    response_model=SuccessResponse,
    summary="执行 API 测试",
    description="异步执行 API 测试",
)
async def run_api_test(
    project_identifier: str,
    api_test_id: str,
    service: APITestServiceDep,
    execution_config: Optional[dict] = None,
):
    """执行 API 测试"""
    result = await service.run_api_test(
        project_identifier=project_identifier,
        api_test_id=api_test_id,
        execution_config=execution_config,
    )

    return SuccessResponse(data=result, message="API 测试已加入执行队列")


@router.get(
    "/{api_test_id}/runs",
    response_model=SuccessResponse,
    summary="获取测试运行历史",
    description="获取 API 测试的所有运行记录",
)
async def list_test_runs(
    project_identifier: str,
    api_test_id: str,
    service: APITestServiceDep,
    pagination: PaginationDep,
):
    """获取测试运行历史"""
    result = await service.get_test_runs(
        project_identifier=project_identifier,
        api_test_id=api_test_id,
        page=pagination.p,
        page_size=pagination.page_size,
    )

    return SuccessResponse(data=result)


@router.get(
    "/{api_test_id}/runs/{run_id}",
    response_model=SuccessResponse,
    summary="获取运行详情",
    description="获取指定测试运行的详细信息",
)
async def get_test_run(
    project_identifier: str,
    api_test_id: str,
    run_id: str,
    service: APITestServiceDep,
):
    """获取测试运行详情"""
    result = await service.get_test_run(
        project_identifier=project_identifier,
        api_test_id=api_test_id,
        run_id=run_id,
    )
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WldObllnPT06OGFkMjk0Nzc=

    return SuccessResponse(data=result)


@router.get(
    "/{api_test_id}/runs/{run_id}/results",
    response_model=SuccessResponse,
    summary="获取测试结果",
    description="获取测试运行的所有结果",
)
async def get_test_results(
    project_identifier: str,
    api_test_id: str,
    run_id: str,
    service: APITestServiceDep,
    pagination: PaginationDep,
):
    """获取测试结果列表"""
    result = await service.get_test_results(
        project_identifier=project_identifier,
        api_test_id=api_test_id,
        run_id=run_id,
        page=pagination.p,
        page_size=pagination.page_size,
    )

    return SuccessResponse(data=result)


@router.post(
    "/repair-from-artifacts",
    response_model=SuccessResponse,
    summary="修复历史脚本到 APITest",
    description="扫描项目中所有 API_TEST_SCRIPT 类型的 Attachment，为缺少 APITest 的 endpoint 创建对应记录",
)
async def repair_api_tests_from_artifacts(
    project_identifier: str,
    db: DbSessionDep,
):
    """将历史 Attachment 脚本批量同步为 APITest 记录"""
    from app.repositories.project_repo import ProjectRepository

    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_identifier(project_identifier)
    if not project:
        return SuccessResponse(success=False, message="项目不存在", data=None)

    # 查询项目中所有 API_TEST_SCRIPT 类型的 Attachment
    stmt = select(Attachment).where(
        Attachment.project_id == project.id,
        Attachment.entity_type == AttachmentEntityType.API_TEST_SCRIPT,
    )
    result = await db.execute(stmt)
    attachments = result.scalars().all()

    api_test_repo = APITestRepository(db)
    created_count = 0
    updated_count = 0
    skipped_count = 0

    for attachment in attachments:
        endpoint_id = attachment.entity_id
        if not endpoint_id:
            skipped_count += 1
            continue

        # 获取对应的 endpoint
        endpoint_stmt = select(APIEndpoint).where(APIEndpoint.id == endpoint_id)
        endpoint_result = await db.execute(endpoint_stmt)
        endpoint = endpoint_result.scalar_one_or_none()
        if not endpoint:
            skipped_count += 1
            continue

        # 检查 endpoint 是否已有有效的 APITest
        valid_test_ids: list[str] = []
        existing_api_test = None
        if endpoint.api_test_ids:
            test_stmt = select(APITest).where(
                APITest.id.in_([UUID(tid) for tid in endpoint.api_test_ids])
            )
            test_result = await db.execute(test_stmt)
            existing_tests = list(test_result.scalars().all())
            valid_test_ids = [str(t.id) for t in existing_tests]
            existing_api_test = existing_tests[0] if existing_tests else None

        if existing_api_test:
            # 更新现有 APITest 的 script_path（如果不同）
            if existing_api_test.script_path != attachment.object_name:
                existing_api_test.script_path = attachment.object_name
                existing_api_test.updated_at = datetime.now(timezone.utc)
                updated_count += 1
            else:
                skipped_count += 1
        else:
            # 创建新的 APITest
            identifier = await api_test_repo.get_next_identifier(endpoint.project_id)
            api_test = APITest(
                project_id=endpoint.project_id,
                folder_id=endpoint.folder_id,
                identifier=identifier,
                name=endpoint.display_name or f"API Test {identifier}",
                script_path=attachment.object_name,
                script_format="playwright",
                script_language="typescript",
                schema_type="openapi",
                generated_by_agent="api_agent",
            )
            db.add(api_test)
            await db.flush()

            # 更新 endpoint 关联
            current_ids = set(valid_test_ids)
            current_ids.add(str(api_test.id))
            endpoint.api_test_ids = list(current_ids)
            endpoint.updated_at = datetime.now(timezone.utc)
            created_count += 1

    await db.commit()

    return SuccessResponse(
        data={
            "total_attachments": len(attachments),
            "created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
        },
        message=f"修复完成：创建 {created_count} 个，更新 {updated_count} 个，跳过 {skipped_count} 个",
    )
