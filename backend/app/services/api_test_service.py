"""
API 测试服务

处理 API 测试相关的业务逻辑
"""

import json
from datetime import datetime
from typing import Optional, Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_test import APITest, APITestRun, APITestResult
from app.repositories.api_test_repo import (
    APITestRepository,
    APITestRunRepository,
    APITestResultRepository,
)
from app.repositories.project_repo import ProjectRepository
from app.repositories.test_case_repo import TestCaseRepository
from app.schemas.enums import TestResultStatus
from app.utils.exceptions import NotFoundException, BadRequestException
from app.config.minio_client import MinIOClient
from app.config.settings import settings
from app.services.api_test_executor import APITestExecutor


class APITestService:
    """API 测试服务类"""

    def __init__(self, session: AsyncSession, mongodb=None):
        self.session = session
        self.mongodb = mongodb
        self.api_test_repo = APITestRepository(session)
        self.api_test_run_repo = APITestRunRepository(session)
        self.api_test_result_repo = APITestResultRepository(session)
        self.project_repo = ProjectRepository(session)
        self.test_case_repo = TestCaseRepository(session)

    async def _get_project_by_identifier(self, identifier: str):
        """获取项目，不存在则抛出异常"""
        project = await self.project_repo.get_by_identifier(identifier)
        if not project:
            raise NotFoundException(resource_type="项目", resource_id=identifier)
        return project

    async def _resolve_test_case_id(
        self, identifier: Optional[str], project_id: UUID
    ) -> Optional[UUID]:
        """把 TC-x identifier 解析为 test_cases.id"""
        if not identifier:
            return None
        tc = await self.test_case_repo.get_by_identifier(identifier)
        if not tc or tc.project_id != project_id:
            raise BadRequestException(
                message=f"测试用例 '{identifier}' 不存在或不属于该项目"
            )
        return tc.id

    # ==================== API 测试管理 ====================

    async def create_api_test(
        self,
        project_identifier: str,
        name: str,
        schema_path: str,
        script_path: str,
        script_format: str = "playwright",
        script_language: str = "typescript",
        schema_url: Optional[str] = None,
        description: Optional[str] = None,
        test_config: Optional[dict] = None,
        total_endpoints: int = 0,
        total_scenarios: int = 0,
        generation_params: Optional[dict] = None,
        test_case_id: Optional[str] = None,
    ) -> dict:
        """
        创建 API 测试

        Args:
            project_identifier: 项目标识符
            name: API 测试名称
            schema_path: Schema 文件路径 (MinIO)
            script_path: 脚本文件路径 (MinIO)
            script_format: 脚本格式
            script_language: 脚本语言
            schema_url: Schema URL（可选）
            description: 描述
            test_config: 测试配置
            total_endpoints: 端点总数
            total_scenarios: 场景总数
            generation_params: 生成参数
            test_case_id: 关联的测试用例标识符（可选）

        Returns:
            dict: 创建的 API 测试信息
        """
        project = await self._get_project_by_identifier(project_identifier)
        identifier = await self.api_test_repo.get_next_identifier(project.id)
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YkZSTU13PT06NmFjMWU3Nzk=

        resolved_tc_id = await self._resolve_test_case_id(test_case_id, project.id)

        api_test = await self.api_test_repo.create(
            project_id=project.id,
            identifier=identifier,
            name=name,
            description=description,
            schema_url=schema_url,
            schema_path=schema_path,
            schema_type="openapi",
            script_path=script_path,
            script_format=script_format,
            script_language=script_language,
            test_config=test_config or {},
            generated_by_agent="api_agent",
            generation_params=generation_params,
            total_endpoints=total_endpoints,
            total_scenarios=total_scenarios,
            test_case_id=resolved_tc_id,
        )

        return {
            "id": str(api_test.id),
            "identifier": api_test.identifier,
            "name": api_test.name,
            "description": api_test.description,
            "script_format": api_test.script_format,
            "script_language": api_test.script_language,
            "total_endpoints": api_test.total_endpoints,
            "total_scenarios": api_test.total_scenarios,
            "test_case_id": api_test.test_case_id,
            "created_at": api_test.created_at.isoformat(),
        }

    async def get_api_test(
        self,
        project_identifier: str,
        api_test_id: str,
    ) -> dict:
        """获取 API 测试详情"""
        project = await self._get_project_by_identifier(project_identifier)
        api_test = await self.api_test_repo.get_by_id_with_relations(UUID(api_test_id))

        if not api_test or api_test.project_id != project.id:
            raise NotFoundException(resource_type="API 测试", resource_id=api_test_id)

        return {
            "id": str(api_test.id),
            "identifier": api_test.identifier,
            "name": api_test.name,
            "description": api_test.description,
            "schema_url": api_test.schema_url,
            "schema_path": api_test.schema_path,
            "schema_type": api_test.schema_type,
            "script_path": api_test.script_path,
            "script_format": api_test.script_format,
            "script_language": api_test.script_language,
            "test_config": api_test.test_config,
            "total_endpoints": api_test.total_endpoints,
            "total_scenarios": api_test.total_scenarios,
            "test_case_id": api_test.test_case_id,
            "created_at": api_test.created_at.isoformat(),
            "updated_at": api_test.updated_at.isoformat() if api_test.updated_at else None,
        }

    async def list_api_tests(
        self,
        project_identifier: str,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        script_format: Optional[str] = None,
    ) -> dict:
        """获取 API 测试列表"""
        project = await self._get_project_by_identifier(project_identifier)
        offset = (page - 1) * page_size
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YkZSTU13PT06NmFjMWU3Nzk=

        items, total = await self.api_test_repo.get_by_project(
            project.id,
            offset=offset,
            limit=page_size,
            search=search,
            script_format=script_format,
        )

        return {
            "items": [
                {
                    "id": str(item.id),
                    "identifier": item.identifier,
                    "name": item.name,
                    "description": item.description,
                    "script_format": item.script_format,
                    "total_endpoints": item.total_endpoints,
                    "total_scenarios": item.total_scenarios,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def list_api_tests_by_folder(
        self,
        project_identifier: str,
        folder_id: str,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
    ) -> dict:
        """
        获取文件夹下的 API 测试列表

        Args:
            project_identifier: 项目标识符
            folder_id: 文件夹 ID
            page: 页码
            page_size: 每页数量
            search: 搜索关键词

        Returns:
            dict: API 测试列表
        """
        project = await self._get_project_by_identifier(project_identifier)
        folder_uuid = UUID(folder_id)

        # 验证文件夹存在且属于该项目
        from app.repositories.folder_repo import FolderRepository
        folder_repo = FolderRepository(self.session)
        folder = await folder_repo.get_by_id(folder_uuid)

        if not folder or folder.project_id != project.id:
            raise NotFoundException(resource_type="文件夹", resource_id=folder_id)

        offset = (page - 1) * page_size

        items, total = await self.api_test_repo.get_by_folder(
            folder_uuid,
            offset=offset,
            limit=page_size,
            search=search,
        )

        return {
            "items": [
                {
                    "id": str(item.id),
                    "identifier": item.identifier,
                    "name": item.name,
                    "description": item.description,
                    "script_format": item.script_format,
                    "total_endpoints": item.total_endpoints,
                    "total_scenarios": item.total_scenarios,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def update_api_test(
        self,
        project_identifier: str,
        api_test_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        test_config: Optional[dict] = None,
        test_case_id: Optional[str] = None,
    ) -> dict:
        """更新 API 测试"""
        project = await self._get_project_by_identifier(project_identifier)
        api_test = await self.api_test_repo.get_by_id(UUID(api_test_id))

        if not api_test or api_test.project_id != project.id:
            raise NotFoundException(resource_type="API 测试", resource_id=api_test_id)

        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if test_config is not None:
            update_data["test_config"] = test_config
        if test_case_id is not None:
            resolved_tc_id = await self._resolve_test_case_id(
                test_case_id if test_case_id else None, project.id
            )
            update_data["test_case_id"] = resolved_tc_id

        updated = await self.api_test_repo.update(api_test, **update_data)

        return {
            "id": str(updated.id),
            "identifier": updated.identifier,
            "name": updated.name,
            "description": updated.description,
            "test_config": updated.test_config,
            "test_case_id": updated.test_case_id,
            "updated_at": updated.updated_at.isoformat() if updated.updated_at else None,
        }

    async def delete_api_test(
        self,
        project_identifier: str,
        api_test_id: str,
    ) -> None:
        """删除 API 测试"""
        project = await self._get_project_by_identifier(project_identifier)
        api_test = await self.api_test_repo.get_by_id(UUID(api_test_id))

        if not api_test or api_test.project_id != project.id:
            raise NotFoundException(resource_type="API 测试", resource_id=api_test_id)

        await self.api_test_repo.delete(api_test)

    # ==================== 测试脚本管理 ====================

    async def get_test_script(
        self,
        project_identifier: str,
        api_test_id: str,
    ) -> str:
        """获取测试脚本内容"""
        project = await self._get_project_by_identifier(project_identifier)
        api_test = await self.api_test_repo.get_by_id(UUID(api_test_id))

        if not api_test or api_test.project_id != project.id:
            raise NotFoundException(resource_type="API 测试", resource_id=api_test_id)

        # 从 MinIO 下载脚本
        script_content = MinIOClient.download_file(api_test.script_path)
        return script_content.decode("utf-8")

    async def update_test_script(
        self,
        project_identifier: str,
        api_test_id: str,
        script_content: str,
    ) -> dict:
        """更新测试脚本内容"""
        project = await self._get_project_by_identifier(project_identifier)
        api_test = await self.api_test_repo.get_by_id(UUID(api_test_id))

        if not api_test or api_test.project_id != project.id:
            raise NotFoundException(resource_type="API 测试", resource_id=api_test_id)

        # 更新 MinIO 中的脚本
        script_bytes = script_content.encode("utf-8")
        MinIOClient.upload_bytes(
            object_name=api_test.script_path,
            data=script_bytes,
            content_type="text/plain",
        )

        # TODO: 保存版本历史到 MongoDB

        return {"success": True, "message": "脚本更新成功"}

    # ==================== 测试运行管理 ====================
# noqa  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YkZSTU13PT06NmFjMWU3Nzk=

    async def run_api_test(
        self,
        project_identifier: str,
        api_test_id: str,
        execution_config: Optional[dict] = None,
    ) -> dict:
        """
        执行 API 测试（异步）

        Args:
            project_identifier: 项目标识符
            api_test_id: API 测试 ID
            execution_config: 执行配置

        Returns:
            dict: 运行信息
        """
        project = await self._get_project_by_identifier(project_identifier)
        api_test = await self.api_test_repo.get_by_id(UUID(api_test_id))

        if not api_test or api_test.project_id != project.id:
            raise NotFoundException(resource_type="API 测试", resource_id=api_test_id)

        # 使用测试执行器执行测试
        executor = APITestExecutor(self.session, self.mongodb)
        run_id = await executor.execute_test(
            api_test_id=api_test.id,
            execution_config=execution_config or {},
        )
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YkZSTU13PT06NmFjMWU3Nzk=

        # 获取运行记录以返回信息
        test_run = await self.api_test_run_repo.get_by_id(UUID(run_id))

        return {
            "run_id": str(test_run.id),
            "identifier": test_run.identifier,
            "status": test_run.status,
            "message": "测试已加入执行队列",
        }

    async def get_test_runs(
        self,
        project_identifier: str,
        api_test_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取测试运行历史"""
        project = await self._get_project_by_identifier(project_identifier)
        api_test = await self.api_test_repo.get_by_id(UUID(api_test_id))

        if not api_test or api_test.project_id != project.id:
            raise NotFoundException(resource_type="API 测试", resource_id=api_test_id)

        offset = (page - 1) * page_size
        items, total = await self.api_test_run_repo.get_by_api_test(
            api_test.id,
            offset=offset,
            limit=page_size,
        )

        return {
            "items": [
                {
                    "id": str(item.id),
                    "identifier": item.identifier,
                    "status": item.status,
                    "total_tests": item.total_tests,
                    "passed_tests": item.passed_tests,
                    "failed_tests": item.failed_tests,
                    "skipped_tests": item.skipped_tests,
                    "duration_ms": item.duration_ms,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_test_run(
        self,
        project_identifier: str,
        api_test_id: str,
        run_id: str,
    ) -> dict:
        """获取测试运行详情"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self.api_test_run_repo.get_by_id(UUID(run_id))

        if not test_run or test_run.project_id != project.id:
            raise NotFoundException(resource_type="测试运行", resource_id=run_id)

        # 计算进度
        progress = 0
        if test_run.total_tests > 0:
            progress = int(
                ((test_run.passed_tests + test_run.failed_tests + test_run.skipped_tests) / test_run.total_tests) * 100
            )

        return {
            "id": str(test_run.id),
            "identifier": test_run.identifier,
            "status": test_run.status,
            "total_tests": test_run.total_tests,
            "passed_tests": test_run.passed_tests,
            "failed_tests": test_run.failed_tests,
            "skipped_tests": test_run.skipped_tests,
            "duration_ms": test_run.duration_ms,
            "progress": progress,
            "error_message": test_run.error_message,
            "report_path": test_run.report_path,
            "stdout": test_run.stdout,
            "stderr": test_run.stderr,
            "created_at": test_run.created_at.isoformat(),
            "updated_at": test_run.updated_at.isoformat() if test_run.updated_at else None,
        }

    async def get_test_results(
        self,
        project_identifier: str,
        api_test_id: str,
        run_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """获取测试结果列表"""
        project = await self._get_project_by_identifier(project_identifier)
        test_run = await self.api_test_run_repo.get_by_id(UUID(run_id))

        if not test_run or test_run.project_id != project.id:
            raise NotFoundException(resource_type="测试运行", resource_id=run_id)

        offset = (page - 1) * page_size
        items, total = await self.api_test_result_repo.get_by_test_run(
            UUID(run_id),
            offset=offset,
            limit=page_size,
        )

        return {
            "items": [
                {
                    "id": str(item.id),
                    "scenario_name": item.scenario_name,
                    "endpoint": item.endpoint,
                    "method": item.method,
                    "status": item.status.value,
                    "duration_ms": item.duration_ms,
                    "retry_count": item.retry_count,
                    "error_message": item.error_message,
                    "request_summary": item.request_summary,
                    "response_summary": item.response_summary,
                    "request_data": item.request_data,
                    "response_data": item.response_data,
                    "assertion_results": item.assertion_results,
                    "detail_log_id": item.detail_log_id,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_endpoint_run_results(
        self,
        endpoint_id: str,
        run_id: str,
        api_test_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """
        获取 API 端点某次运行的测试结果明细。

        用于前端“执行结果”面板直接按 endpoint + run 查询。
        """
        from app.models.api_endpoint import APIEndpoint

        endpoint_uuid = UUID(endpoint_id)
        run_uuid = UUID(run_id)

        endpoint = await self.session.get(APIEndpoint, endpoint_uuid)
        if not endpoint:
            raise NotFoundException(resource_type="API 端点", resource_id=endpoint_id)

        test_run = await self.api_test_run_repo.get_by_id(run_uuid)
        if not test_run:
            raise NotFoundException(resource_type="测试运行", resource_id=run_id)

        if api_test_id is not None:
            # 优先使用前端传入的 api_test_id 直接校验，绕开 endpoint.api_test_ids
            # 这个 JSONB 反规范化字段在并发写入下可能被覆盖，导致左右两侧快照不一致
            if test_run.api_test_id != UUID(api_test_id):
                raise NotFoundException(
                    message=f"测试运行 '{run_id}' 不属于该 api_test"
                )
        else:
            # 向后兼容：旧调用未传 api_test_id 时，仍按 endpoint.api_test_ids 兜底
            api_test_ids: set[UUID] = set()
            for tid in (endpoint.api_test_ids or []):
                try:
                    api_test_ids.add(UUID(tid))
                except (ValueError, TypeError):
                    continue

            if test_run.api_test_id not in api_test_ids:
                raise NotFoundException(
                    message=f"测试运行 '{run_id}' 不属于该 endpoint"
                )

        offset = (page - 1) * page_size
        items, total = await self.api_test_result_repo.get_by_test_run(
            run_uuid,
            offset=offset,
            limit=page_size,
        )

        return {
            "items": [
                {
                    "id": str(item.id),
                    "scenario_name": item.scenario_name,
                    "endpoint": item.endpoint,
                    "method": item.method,
                    "status": item.status.value,
                    "duration_ms": item.duration_ms,
                    "retry_count": item.retry_count,
                    "error_message": item.error_message,
                    "request_summary": item.request_summary,
                    "response_summary": item.response_summary,
                    "request_data": item.request_data,
                    "response_data": item.response_data,
                    "assertion_results": item.assertion_results,
                    "detail_log_id": item.detail_log_id,
                    "created_at": item.created_at.isoformat(),
                }
                for item in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ==================== Schema 上传 ====================

    async def upload_schema(
        self,
        project_identifier: str,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> dict:
        """
        上传 Schema 文件到 MinIO

        Args:
            project_identifier: 项目标识符
            filename: 文件名
            content: 文件内容
            content_type: 内容类型

        Returns:
            dict: 上传结果
        """
        project = await self._get_project_by_identifier(project_identifier)

        # 生成对象名称
        import time
        timestamp = int(time.time())
        object_name = f"api-schemas/{project.id}/{timestamp}-{filename}"

        # 上传到 MinIO
        MinIOClient.upload_bytes(
            object_name=object_name,
            data=content,
            content_type=content_type,
        )

        # 生成公共 URL（如果配置了）
        schema_url = None
        if settings.minio_public_url:
            schema_url = f"{settings.minio_public_url}/{object_name}"

        return {
            "schema_path": object_name,
            "schema_url": schema_url,
        }
