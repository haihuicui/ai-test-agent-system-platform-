"""
测试用例版本历史模型

使用 MongoDB 存储测试用例的版本历史记录
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# pylint: disable  MC8zOmFIVnBZMlhsdEpUbXRiZm92b2s2V0hGaGFRPT06YjJlZTIyYzQ=

class TestCaseVersionHistory(BaseModel):
    """
    测试用例版本历史
    
    记录测试用例每次修改的完整快照
    """
    test_case_id: UUID = Field(..., description="测试用例 ID")
    version: int = Field(..., description="版本号")
    snapshot: dict[str, Any] = Field(..., description="测试用例快照数据")
    changed_by: UUID = Field(..., description="修改者 ID")
    changed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="修改时间"
    )
    change_description: Optional[str] = Field(
        default=None,
        description="修改说明"
    )
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }
    
    @classmethod
    def collection_name(cls) -> str:
        """获取 MongoDB 集合名称"""
        return "test_case_versions"
# fmt: off  MS8zOmFIVnBZMlhsdEpUbXRiZm92b2s2V0hGaGFRPT06YjJlZTIyYzQ=
    
    def to_document(self) -> dict:
        """转换为 MongoDB 文档"""
        return {
            "test_case_id": str(self.test_case_id),
            "version": self.version,
            "snapshot": self.snapshot,
            "changed_by": str(self.changed_by),
            "changed_at": self.changed_at,
            "change_description": self.change_description,
        }


class TestCaseVersionListItem(BaseModel):
    """版本历史列表项"""
    version: int = Field(..., description="版本号")
    changed_by: str = Field(..., description="修改者邮箱")
    changed_at: datetime = Field(..., description="修改时间")
    change_description: Optional[str] = Field(default=None, description="修改说明")
# type: ignore  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b2s2V0hGaGFRPT06YjJlZTIyYzQ=

