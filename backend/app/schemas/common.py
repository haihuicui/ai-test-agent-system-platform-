"""
通用响应模型

定义 API 响应的通用结构
参考: https://www.browserstack.com/docs/test-management/api-reference/status-code
"""

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VTJkcWR3PT06MWY2ZmMxMWU=

from pydantic import BaseModel, Field


T = TypeVar("T")


class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = Field(..., description="API 调用是否成功")


class SuccessResponse(BaseResponse, Generic[T]):
    """成功响应模型"""
    success: bool = Field(default=True, description="API 调用成功")
    data: Optional[T] = Field(default=None, description="响应数据")


class MessageResponse(BaseResponse):
    """消息响应模型"""
    success: bool = Field(default=True, description="API 调用成功")
    message: str = Field(..., description="响应消息")
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VTJkcWR3PT06MWY2ZmMxMWU=


class ErrorDetail(BaseModel):
    """错误详情"""
    field: Optional[str] = Field(default=None, description="错误字段")
    message: str = Field(..., description="错误消息")
    code: Optional[str] = Field(default=None, description="错误代码")


class ErrorResponse(BaseResponse):
    """
    错误响应模型
    
    用于返回 API 错误信息
    """
    success: bool = Field(default=False, description="API 调用失败")
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    details: Optional[list[ErrorDetail]] = Field(
        default=None, 
        description="错误详情列表"
    )

# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VTJkcWR3PT06MWY2ZmMxMWU=

class LinkInfo(BaseModel):
    """
    链接信息
    
    用于 HATEOAS 风格的 API 响应
    """
    self: Optional[str] = Field(default=None, description="当前资源链接")
    project: Optional[str] = Field(default=None, description="所属项目链接")
    folder: Optional[str] = Field(default=None, description="所属文件夹链接")
    parent: Optional[str] = Field(default=None, description="父级资源链接")
    sub_folders: Optional[str] = Field(default=None, description="子文件夹链接")
    test_cases: Optional[str] = Field(default=None, description="测试用例链接")

# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VTJkcWR3PT06MWY2ZmMxMWU=

class TimestampMixin(BaseModel):
    """时间戳混入类"""
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class AuditMixin(TimestampMixin):
    """审计信息混入类"""
    created_by: str = Field(..., description="创建者邮箱")
    updated_by: Optional[str] = Field(default=None, description="更新者邮箱")

