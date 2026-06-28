"""
分页模型

基于 BrowserStack Test Management API 的分页设计
参考: https://www.browserstack.com/docs/test-management/api-reference/pagination
"""

from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field, AliasChoices

from app.config.settings import settings


T = TypeVar("T")
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjI5c1JRPT06ZmNmMGZhNzE=

# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjI5c1JRPT06ZmNmMGZhNzE=

class PaginationParams(BaseModel):
    """
    分页查询参数

    用于接收分页请求的查询参数
    """
    p: int = Field(
        default=1,
        ge=1,
        description="页码，从 1 开始"
    )
    page_size: int = Field(
        default=settings.default_page_size,
        ge=1,
        le=settings.max_page_size,
        description=f"每页数量，默认 {settings.default_page_size}，最大 {settings.max_page_size}"
    )

    @property
    def page(self) -> int:
        """获取当前页码（别名，兼容 p 属性）"""
        return self.p

    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.p - 1) * self.page_size

    @property
    def limit(self) -> int:
        """获取限制数量"""
        return self.page_size


class TestCaseFilterParams(PaginationParams):
    """
    测试用例过滤参数
    
    扩展分页参数，添加测试用例特定的过滤条件
    """
    test_case_id: Optional[str] = Field(
        default=None,
        description="测试用例 ID 过滤"
    )
    updated_after: Optional[datetime] = Field(
        default=None,
        description="更新时间晚于指定时间"
    )
    updated_before: Optional[datetime] = Field(
        default=None,
        description="更新时间早于指定时间"
    )
    issue_ids: Optional[str] = Field(
        default=None,
        description="关联问题 ID 列表，逗号分隔"
    )
    issue_type: Optional[str] = Field(
        default=None,
        description="关联问题类型"
    )


class PaginationInfo(BaseModel):
    """
    分页信息

    包含在分页响应中的分页元数据
    """
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    count: Optional[int] = Field(default=None, description="当前页返回的记录数")
    total: int = Field(..., description="总记录数")
    prev: Optional[str] = Field(default=None, description="上一页链接")
    next: Optional[str] = Field(default=None, description="下一页链接")
    
    @classmethod
    def create(
        cls,
        page: int,
        page_size: int,
        total: int,
        base_url: str,
    ) -> "PaginationInfo":
        """
        创建分页信息
        
        Args:
            page: 当前页码
            page_size: 每页数量
            total: 总记录数
            base_url: 基础 URL
            
        Returns:
            PaginationInfo: 分页信息实例
        """
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        count = min(page_size, max(0, total - (page - 1) * page_size))
        
        prev_url = None
        next_url = None
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjI5c1JRPT06ZmNmMGZhNzE=
        
        if page > 1:
            prev_url = f"{base_url}?p={page - 1}&page_size={page_size}"
        
        if page < total_pages:
            next_url = f"{base_url}?p={page + 1}&page_size={page_size}"
        
        return cls(
            page=page,
            page_size=page_size,
            count=count,
            total=total,
            prev=prev_url,
            next=next_url,
        )


class PaginatedResponse(BaseModel, Generic[T]):
    """
    分页响应模型

    用于返回分页数据的通用响应结构
    支持 info 或 pagination 作为分页信息字段名（兼容不同使用场景）
    """
    success: bool = Field(default=True, description="API 调用成功")
    info: PaginationInfo = Field(
        default=None,
        validation_alias=AliasChoices("info", "pagination"),
        serialization_alias="info",
        description="分页信息",
    )
    data: list[T] = Field(default_factory=list, description="数据列表")

    model_config = {"populate_by_name": True}

# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WjI5c1JRPT06ZmNmMGZhNzE=
