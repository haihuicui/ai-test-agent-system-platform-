"""
测试用例附件模型

使用 MongoDB 存储测试用例附件元数据
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

# pragma: no cover  MC8zOmFIVnBZMlhsdEpUbXRiZm92b2s2TjFKUlRBPT06NDIzYjI2Yjk=

class TestCaseAttachment(BaseModel):
    """
    测试用例附件
    
    存储附件的元数据信息，实际文件存储在文件系统或对象存储中
    """
    test_case_id: UUID = Field(..., description="测试用例 ID")
    filename: str = Field(..., description="文件名")
    original_filename: str = Field(..., description="原始文件名")
    file_type: str = Field(..., description="文件 MIME 类型")
    file_size: int = Field(..., description="文件大小（字节）")
    file_path: str = Field(..., description="文件存储路径")
    uploaded_by: UUID = Field(..., description="上传者 ID")
    uploaded_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="上传时间"
    )
    description: Optional[str] = Field(
        default=None,
        description="附件描述"
    )
    
    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }
    
    @classmethod
    def collection_name(cls) -> str:
        """获取 MongoDB 集合名称"""
        return "test_case_attachments"
# noqa  MS8zOmFIVnBZMlhsdEpUbXRiZm92b2s2TjFKUlRBPT06NDIzYjI2Yjk=
    
    def to_document(self) -> dict:
        """转换为 MongoDB 文档"""
        return {
            "test_case_id": str(self.test_case_id),
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "file_path": self.file_path,
            "uploaded_by": str(self.uploaded_by),
            "uploaded_at": self.uploaded_at,
            "description": self.description,
        }
# fmt: off  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b2s2TjFKUlRBPT06NDIzYjI2Yjk=


class AttachmentInfo(BaseModel):
    """附件信息响应模型"""
    id: str = Field(..., description="附件 ID")
    filename: str = Field(..., description="文件名")
    file_type: str = Field(..., description="文件类型")
    file_size: int = Field(..., description="文件大小")
    uploaded_by: str = Field(..., description="上传者邮箱")
    uploaded_at: datetime = Field(..., description="上传时间")
    download_url: str = Field(..., description="下载链接")

