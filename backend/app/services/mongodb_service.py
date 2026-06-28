"""
MongoDB 服务

处理版本历史、审计日志等 MongoDB 相关操作
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.mongodb.version_history import TestCaseVersionHistory
from app.models.mongodb.audit_log import AuditLog
from app.models.mongodb.attachment import TestCaseAttachment


class MongoDBService:
    """
    MongoDB 服务类
    
    处理版本历史、审计日志等操作
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.version_history = db.test_case_version_history
        self.audit_logs = db.audit_logs
        self.attachments = db.test_case_attachments
# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUdkVFlRPT06MGJhZWFlNzQ=
    
    # ==================== 版本历史 ====================
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUdkVFlRPT06MGJhZWFlNzQ=
    
    async def save_version_history(
        self,
        test_case_id: UUID,
        version: int,
        snapshot: dict,
        changed_by: UUID,
        change_summary: Optional[str] = None,
    ) -> str:
        """
        保存测试用例版本历史
        
        Args:
            test_case_id: 测试用例 ID
            version: 版本号
            snapshot: 测试用例快照
            changed_by: 修改者 ID
            change_summary: 变更摘要
            
        Returns:
            str: 插入的文档 ID
        """
        history = TestCaseVersionHistory(
            test_case_id=str(test_case_id),
            version=version,
            snapshot=snapshot,
            changed_by=str(changed_by),
            changed_at=datetime.utcnow(),
            change_summary=change_summary,
        )
        
        result = await self.version_history.insert_one(history.model_dump())
        return str(result.inserted_id)
    
    async def get_version_history(
        self,
        test_case_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """
        获取测试用例版本历史（分页）

        Args:
            test_case_id: 测试用例 ID
            page: 页码
            page_size: 每页数量

        Returns:
            dict: 包含历史记录和分页信息的字典
        """
        skip = (page - 1) * page_size

        cursor = self.version_history.find(
            {"test_case_id": test_case_id}
        ).sort("version", -1).skip(skip).limit(page_size)

        history = await cursor.to_list(length=page_size)

        # 获取总数
        total = await self.version_history.count_documents(
            {"test_case_id": test_case_id}
        )

        return {
            "history": history,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    
    async def get_specific_version(
        self,
        test_case_id: UUID,
        version: int,
    ) -> Optional[dict]:
        """
        获取特定版本的测试用例
        
        Args:
            test_case_id: 测试用例 ID
            version: 版本号
            
        Returns:
            Optional[dict]: 版本快照
        """
        return await self.version_history.find_one({
            "test_case_id": str(test_case_id),
            "version": version,
        })
    
    # ==================== 审计日志 ====================
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUdkVFlRPT06MGJhZWFlNzQ=
    
    async def log_action(
        self,
        entity_type: str,
        entity_id: UUID,
        action: str,
        performed_by: UUID,
        old_value: Optional[dict] = None,
        new_value: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """
        记录审计日志
        
        Args:
            entity_type: 实体类型（project, folder, test_case）
            entity_id: 实体 ID
            action: 操作类型（create, update, delete）
            performed_by: 操作者 ID
            old_value: 旧值
            new_value: 新值
            ip_address: IP 地址
            user_agent: 用户代理
            
        Returns:
            str: 插入的文档 ID
        """
        log = AuditLog(
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            old_value=old_value,
            new_value=new_value,
            performed_by=str(performed_by),
            performed_at=datetime.utcnow(),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        result = await self.audit_logs.insert_one(log.model_dump())
        return str(result.inserted_id)
    
    async def get_audit_logs(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        action: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        获取审计日志
        
        Args:
            entity_type: 实体类型过滤
            entity_id: 实体 ID 过滤
            action: 操作类型过滤
            limit: 限制数量
            
        Returns:
            list[dict]: 审计日志列表
        """
        query = {}
        if entity_type:
            query["entity_type"] = entity_type
        if entity_id:
            query["entity_id"] = str(entity_id)
        if action:
            query["action"] = action
        
        cursor = self.audit_logs.find(query).sort(
            "performed_at", -1
        ).limit(limit)
# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VUdkVFlRPT06MGJhZWFlNzQ=
        
        return await cursor.to_list(length=limit)
