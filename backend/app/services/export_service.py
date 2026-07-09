"""
BDD 测试用例导出服务

提供 BDD 测试用例导出为 .feature 文件的功能
"""

import io
import zipfile
from datetime import datetime
from typing import Any, Optional, Tuple
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.test_case import (
    ExportBDDRequest, ExportBDDResponse, ExportStatusResponse,
    ExportExcelRequest, ExportExcelResponse, TestCaseInfo
)
from app.schemas.enums import ExportStatus, TestCaseTemplate
from app.utils.exceptions import NotFoundException, BadRequestException
from app.config.settings import settings
from app.agents.tools.testcase.excel_tools import generate_test_cases_excel_bytes
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2T1ZNeVNRPT06MGUyODlmMTE=


def _test_case_info_to_excel_dict(tc: TestCaseInfo) -> dict[str, Any]:
    """将 TestCaseInfo 转为 Excel 工具可识别的字典"""
    # 用例编号优先使用 AI 自定义的 case_number，没有则使用系统自动生成的 identifier
    case_id = tc.case_number if tc.case_number else tc.identifier

    if tc.template == TestCaseTemplate.TEST_CASE_BDD:
        return {
            "id": case_id,
            "title": tc.name,
            "module": tc.module,
            "type": tc.case_type.value if tc.case_type else "",
            "priority": tc.priority.value if tc.priority else "",
            "preconditions": tc.background or tc.preconditions,
            "steps": tc.scenario,
            "test_data": tc.test_data,
            "expected_results": "",
            "remarks": tc.feature,
        }

    steps = tc.test_case_steps or []
    return {
        "id": case_id,
        "title": tc.name,
        "module": tc.module,
        "type": tc.case_type.value if tc.case_type else "",
        "priority": tc.priority.value if tc.priority else "",
        "preconditions": tc.preconditions,
        "steps": [{"seq": s.order, "action": s.step} for s in steps],
        "test_data": tc.test_data,
        "expected_results": [s.result for s in steps if s.result],
        "remarks": tc.description,
    }


class ExportService:
    """
    BDD 测试用例导出服务
    
    处理 BDD 测试用例导出为 .feature 文件的逻辑
    """
    
    COLLECTION_NAME = "export_jobs"
    
    def __init__(self, db: AsyncSession, mongodb: AsyncIOMotorDatabase):
        self.db = db
        self.mongodb = mongodb
    
    async def start_bdd_export(
        self,
        project_identifier: str,
        data: ExportBDDRequest
    ) -> ExportBDDResponse:
        """
        启动 BDD 测试用例导出任务
        
        Args:
            project_identifier: 项目标识符
            data: 导出请求数据
            
        Returns:
            ExportBDDResponse: 导出任务信息
        """
        export_id = str(uuid4())
        
        # 创建导出任务记录
        export_job = {
            "_id": export_id,
            "project_identifier": project_identifier,
            "test_case_ids": data.test_case_ids,
            "combine_into_one": data.combine_into_one,
            "combined_feature": data.combined_feature,
            "combined_background": data.combined_background,
            "status": ExportStatus.PENDING.value,
            "download_url": None,
            "file_content": None,
            "filename": None,
            "content_type": None,
            "error_message": None,
            "created_at": datetime.utcnow(),
            "completed_at": None,
        }

        if self.mongodb is None:
            raise BadRequestException("MongoDB 未连接，无法创建导出任务")

        await self.mongodb[self.COLLECTION_NAME].insert_one(export_job)
        
        # 异步处理导出任务（这里简化为同步处理）
        await self._process_export(export_id)
        
        status_url = f"{settings.api_prefix}/exports/{export_id}/status"
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2T1ZNeVNRPT06MGUyODlmMTE=
        
        return ExportBDDResponse(
            success=True,
            export_id=export_id,
            status=ExportStatus.PENDING,
            status_url=status_url
        )

    async def start_excel_export(
        self,
        project_identifier: str,
        data: ExportExcelRequest,
        test_case_service: "TestCaseService",
    ) -> ExportExcelResponse:
        """
        启动 Excel 测试用例导出任务

        Args:
            project_identifier: 项目标识符
            data: 导出请求数据
            test_case_service: 测试用例服务实例

        Returns:
            ExportExcelResponse: 导出任务信息
        """
        export_id = str(uuid4())

        # 创建导出任务记录
        export_job = {
            "_id": export_id,
            "project_identifier": project_identifier,
            "test_case_ids": data.test_case_ids,
            "folder_id": data.folder_id,
            "export_type": "excel",
            "status": ExportStatus.PENDING.value,
            "download_url": None,
            "file_content": None,
            "filename": None,
            "content_type": None,
            "error_message": None,
            "created_at": datetime.utcnow(),
            "completed_at": None,
        }

        if self.mongodb is None:
            raise BadRequestException("MongoDB 未连接，无法创建导出任务")

        await self.mongodb[self.COLLECTION_NAME].insert_one(export_job)

        # 异步处理导出任务（这里简化为同步处理）
        await self._process_excel_export(export_id, test_case_service)

        status_url = f"{settings.api_prefix}/exports/{export_id}/status"

        return ExportExcelResponse(
            success=True,
            export_id=export_id,
            status=ExportStatus.PENDING,
            status_url=status_url
        )

    async def _process_excel_export(
        self,
        export_id: str,
        test_case_service: "TestCaseService",
    ) -> None:
        """
        处理 Excel 导出任务

        Args:
            export_id: 导出任务 ID
            test_case_service: 测试用例服务实例
        """
        try:
            # 更新状态为处理中
            await self.mongodb[self.COLLECTION_NAME].update_one(
                {"_id": export_id},
                {"$set": {"status": ExportStatus.PROCESSING.value}}
            )

            # 获取导出任务信息
            job = await self.mongodb[self.COLLECTION_NAME].find_one({"_id": export_id})
            if not job:
                return

            folder_ids = [job["folder_id"]] if job.get("folder_id") else None
            test_cases = await test_case_service.get_test_cases_for_export(
                project_identifier=job["project_identifier"],
                test_case_ids=job.get("test_case_ids"),
                folder_ids=folder_ids,
            )

            if not test_cases:
                raise ValueError("未找到可导出的测试用例")

            case_dicts = [_test_case_info_to_excel_dict(tc) for tc in test_cases]
            file_content = generate_test_cases_excel_bytes(case_dicts, sheet_name="测试用例")

            filename = f"test_cases_{export_id[:8]}.xlsx"
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            download_url = f"{settings.api_prefix}/exports/{export_id}/download"

            # 更新任务状态为完成
            await self.mongodb[self.COLLECTION_NAME].update_one(
                {"_id": export_id},
                {
                    "$set": {
                        "status": ExportStatus.COMPLETED.value,
                        "download_url": download_url,
                        "file_content": file_content,
                        "filename": filename,
                        "content_type": content_type,
                        "completed_at": datetime.utcnow(),
                    }
                }
            )

        except Exception as e:
            # 更新任务状态为失败
            await self.mongodb[self.COLLECTION_NAME].update_one(
                {"_id": export_id},
                {
                    "$set": {
                        "status": ExportStatus.FAILED.value,
                        "error_message": str(e),
                        "completed_at": datetime.utcnow(),
                    }
                }
            )

    async def _process_export(self, export_id: str) -> None:
        """
        处理导出任务
        
        Args:
            export_id: 导出任务 ID
        """
        try:
            # 更新状态为处理中
            await self.mongodb[self.COLLECTION_NAME].update_one(
                {"_id": export_id},
                {"$set": {"status": ExportStatus.PROCESSING.value}}
            )
            
            # 获取导出任务信息
            job = await self.mongodb[self.COLLECTION_NAME].find_one({"_id": export_id})
            if not job:
                return
            
            # 获取测试用例数据（这里需要从数据库查询）
            # 简化实现：生成示例 .feature 文件内容
            feature_content = await self._generate_feature_content(job)
            
            # 根据是否合并决定文件格式
            if job["combine_into_one"]:
                filename = f"{job['combined_feature'].replace(' ', '_')}.feature"
                content_type = "text/plain"
                file_content = feature_content.encode('utf-8')
            else:
                # 多个文件打包为 zip
                filename = f"bdd_export_{export_id[:8]}.zip"
                content_type = "application/zip"
                file_content = await self._create_zip(job["test_case_ids"], feature_content)
            
            download_url = f"{settings.api_prefix}/exports/{export_id}/download"
            
            # 更新任务状态为完成
            await self.mongodb[self.COLLECTION_NAME].update_one(
                {"_id": export_id},
                {
                    "$set": {
                        "status": ExportStatus.COMPLETED.value,
                        "download_url": download_url,
                        "file_content": file_content,
                        "filename": filename,
                        "content_type": content_type,
                        "completed_at": datetime.utcnow(),
                    }
                }
            )
            
        except Exception as e:
            # 更新任务状态为失败
            await self.mongodb[self.COLLECTION_NAME].update_one(
                {"_id": export_id},
                {
                    "$set": {
                        "status": ExportStatus.FAILED.value,
                        "error_message": str(e),
                        "completed_at": datetime.utcnow(),
                    }
                }
            )
    
    async def _generate_feature_content(self, job: dict) -> str:
        """
        生成 .feature 文件内容
        
        Args:
            job: 导出任务信息
            
        Returns:
            str: .feature 文件内容
        """
        # TODO: 从数据库查询实际的测试用例数据
        # 这里生成示例内容
        lines = []
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2T1ZNeVNRPT06MGUyODlmMTE=
        
        if job["combine_into_one"]:
            lines.append(f"Feature: {job['combined_feature']}")
            if job.get("combined_background"):
                lines.append("")
                lines.append("  Background:")
                lines.append(f"    {job['combined_background']}")
            lines.append("")
            
            for tc_id in job["test_case_ids"]:
                lines.append(f"  Scenario: {tc_id}")
                lines.append("    Given 前置条件")
                lines.append("    When 执行操作")
                lines.append("    Then 验证结果")
                lines.append("")
        else:
            lines.append("Feature: 测试功能")
            lines.append("")
            lines.append("  Scenario: 测试场景")
            lines.append("    Given 前置条件")
            lines.append("    When 执行操作")
            lines.append("    Then 验证结果")
        
        return "\n".join(lines)
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2T1ZNeVNRPT06MGUyODlmMTE=
    
    async def _create_zip(self, test_case_ids: list, content: str) -> bytes:
        """
        创建 ZIP 压缩包
        
        Args:
            test_case_ids: 测试用例 ID 列表
            content: 文件内容
            
        Returns:
            bytes: ZIP 文件内容
        """
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for tc_id in test_case_ids:
                filename = f"{tc_id}.feature"
                zf.writestr(filename, content)
        buffer.seek(0)
        return buffer.read()
    
    async def get_export_status(self, export_id: str) -> ExportStatusResponse:
        """
        获取导出任务状态
        
        Args:
            export_id: 导出任务 ID
            
        Returns:
            ExportStatusResponse: 导出状态信息
        """
        job = await self.mongodb[self.COLLECTION_NAME].find_one({"_id": export_id})
        if not job:
            raise NotFoundException(f"导出任务 {export_id} 不存在")
        
        return ExportStatusResponse(
            success=True,
            export_id=export_id,
            status=ExportStatus(job["status"]),
            download_url=job.get("download_url"),
            error_message=job.get("error_message")
        )
    
    async def download_export(
        self, 
        export_id: str
    ) -> Tuple[bytes, str, str]:
        """
        下载导出文件
        
        Args:
            export_id: 导出任务 ID
            
        Returns:
            Tuple[bytes, str, str]: (文件内容, 文件名, 内容类型)
        """
        job = await self.mongodb[self.COLLECTION_NAME].find_one({"_id": export_id})
        if not job:
            raise NotFoundException(f"导出任务 {export_id} 不存在")
        
        if job["status"] != ExportStatus.COMPLETED.value:
            raise BadRequestException(f"导出任务尚未完成，当前状态: {job['status']}")
        
        return (
            job["file_content"],
            job["filename"],
            job["content_type"]
        )

