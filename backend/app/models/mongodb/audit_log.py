"""
审计日志模型

使用 MongoDB 存储系统操作审计日志
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Vkc1cVZ3PT06OGE3Y2U3NjM=

from pydantic import BaseModel, Field


class AuditAction(str, Enum):
    """审计操作类型"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MOVE = "move"
    COPY = "copy"


class EntityType(str, Enum):
    """实体类型"""
    PROJECT = "project"
    FOLDER = "folder"
    TEST_CASE = "test_case"
    TEST_STEP = "test_step"
    TAG = "tag"
    USER = "user"
# noqa  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Vkc1cVZ3PT06OGE3Y2U3NjM=


class AuditLog(BaseModel):
    """
    审计日志
    
    记录系统中所有重要操作的日志
    """
    entity_type: EntityType = Field(..., description="实体类型")
    entity_id: UUID = Field(..., description="实体 ID")
    action: AuditAction = Field(..., description="操作类型")
    old_value: Optional[dict[str, Any]] = Field(
        default=None,
        description="操作前的值"
    )
    new_value: Optional[dict[str, Any]] = Field(
        default=None,
        description="操作后的值"
    )
    performed_by: UUID = Field(..., description="操作者 ID")
    performed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="操作时间"
    )
    ip_address: Optional[str] = Field(
        default=None,
        description="操作者 IP 地址"
    )
    user_agent: Optional[str] = Field(
        default=None,
        description="操作者 User-Agent"
    )
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }
# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Vkc1cVZ3PT06OGE3Y2U3NjM=
    
    @classmethod
    def collection_name(cls) -> str:
        """获取 MongoDB 集合名称"""
        return "audit_logs"
    
    def to_document(self) -> dict:
        """转换为 MongoDB 文档"""
        return {
            "entity_type": self.entity_type.value,
            "entity_id": str(self.entity_id),
            "action": self.action.value,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "performed_by": str(self.performed_by),
            "performed_at": self.performed_at,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }

# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Vkc1cVZ3PT06OGE3Y2U3NjM=
