"""
BDD 测试用例导出服务

提供 BDD 测试用例导出为 .feature 文件的功能
"""

import io
import zipfile
from datetime import datetime
from typing import Optional, Tuple
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.test_case import (
    ExportBDDRequest, ExportBDDResponse, ExportStatusResponse
)
from app.schemas.enums import ExportStatus
from app.utils.exceptions import NotFoundException, BadRequestException
from app.config.settings import settings
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2T1ZNeVNRPT06MGUyODlmMTE=


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

