"""
文件夹相关的 Pydantic 模型

基于 BrowserStack Test Management API 的文件夹接口设计
参考: https://www.browserstack.com/docs/test-management/api-reference/folders
"""

from typing import Optional, List
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.common import BaseResponse


class APIEndpointSummary(BaseModel):
    """API 端点简要信息（用于文件夹树展示）"""
    id: UUID = Field(..., description="端点 ID")
    display_name: str = Field(..., description="显示名称")
    method: str = Field(..., description="HTTP 方法")
    path: str = Field(..., description="API 路径")
    tag_group: Optional[str] = Field(None, description="标签分组")
    total_test_cases: int = Field(default=0, description="该接口的测试用例数量")
    total_test_runs: int = Field(default=0, description="该接口被执行的次数")

    class Config:
        from_attributes = True

# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVV0dmN3PT06OTM3ZjYwMzk=

class FolderType(str, Enum):
    """文件夹类型"""
    TEST_CASE = "test_case"  # 测试用例文件夹
    API_TEST = "api_test"    # API测试文件夹
    WEB_TEST = "web_test"    # Web测试文件夹
    ANDROID_TEST = "android_test"  # Android测试文件夹
    SCENARIO_TEST = "scenario_test"  # 场景测试文件夹


class FolderBase(BaseModel):
    """文件夹基础模型"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="文件夹名称"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="文件夹描述"
    )
    folder_type: FolderType = Field(
        default=FolderType.TEST_CASE,
        description="文件夹类型：test_case 或 api_test"
    )
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVV0dmN3PT06OTM3ZjYwMzk=


class FolderCreate(FolderBase):
    """
    创建文件夹请求模型

    用于创建新文件夹的请求体
    """
    parent_id: Optional[UUID] = Field(
        default=None,
        description="父文件夹 ID，为空则创建在根目录"
    )


class FolderUpdate(BaseModel):
    """
    更新文件夹请求模型
    
    用于更新文件夹信息的请求体
    """
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="文件夹名称"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="文件夹描述"
    )


class FolderMove(BaseModel):
    """
    移动文件夹请求模型

    用于移动文件夹到新位置的请求体
    参考: https://www.browserstack.com/docs/test-management/api-reference/folders#move-a-folder
    """
    parent_id: Optional[UUID] = Field(
        default=None,
        description="目标父文件夹 ID，为空则移动到根目录"
    )


class FolderLinks(BaseModel):
    """
    文件夹相关链接

    参考 BrowserStack API: 只包含 sub_folders 链接
    """
    sub_folders: Optional[str] = Field(
        default=None,
        description="子文件夹列表链接"
    )
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVV0dmN3PT06OTM3ZjYwMzk=


class FolderInfo(FolderBase):
    """
    文件夹信息模型

    用于返回文件夹详细信息
    参考: https://www.browserstack.com/docs/test-management/api-reference/folders

    显示格式: 直接用例数(总用例数)
    例如: 2(10) 表示该目录直接有2条用例，该目录及所有子目录共10条用例
    """
    id: UUID = Field(..., description="文件夹 ID")
    parent_id: Optional[UUID] = Field(
        default=None,
        description="父文件夹 ID"
    )
    project_identifier: Optional[str] = Field(
        default=None,
        description="项目标识符"
    )
    direct_cases_count: int = Field(
        default=0,
        description="直接在该文件夹中的测试用例数量（不含子文件夹）"
    )
    cases_count: int = Field(
        default=0,
        description="该文件夹及所有子文件夹的测试用例总数"
    )
    sub_folders_count: int = Field(
        default=0,
        description="直接子文件夹数量"
    )
    endpoints_count: int = Field(
        default=0,
        description="该文件夹及所有子文件夹的 API 端点总数（仅 API_TEST 类型文件夹有意义）"
    )
    links: Optional[FolderLinks] = Field(
        default=None,
        description="相关资源链接"
    )
    api_endpoints: Optional[List[APIEndpointSummary]] = Field(
        default_factory=list,
        description="该文件夹下的 API 端点列表（仅用于 API_TEST 类型文件夹）"
    )
    # WEB_TEST 类型文件夹特有：关联的 Web 功能列表
    web_functions: Optional[List[dict]] = Field(
        default=None,
        description="该文件夹下的 Web 功能列表（仅用于 WEB_TEST 类型文件夹）"
    )
    total_sub_functions: Optional[int] = Field(
        default=None,
        description="该文件夹下所有功能的子功能总数（仅用于 WEB_TEST 类型文件夹）"
    )

    class Config:
        from_attributes = True


class FolderResponse(BaseResponse):
    """
    单个文件夹响应模型
    """
    success: bool = Field(default=True, description="API 调用成功")
    folder: FolderInfo = Field(..., description="文件夹信息")


class FolderListResponse(BaseResponse):
    """
    文件夹列表响应模型
    """
    success: bool = Field(default=True, description="API 调用成功")
    folders: list[FolderInfo] = Field(
        default_factory=list,
        description="文件夹列表"
    )


class FolderDeleteResponse(BaseResponse):
    """
    删除文件夹响应模型
    """
    success: bool = Field(default=True, description="API 调用成功")
    message: str = Field(..., description="删除结果消息")

# noqa  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VVV0dmN3PT06OTM3ZjYwMzk=

class FolderMoveResponse(BaseResponse):
    """
    移动文件夹响应模型
    """
    success: bool = Field(default=True, description="API 调用成功")
    message: str = Field(..., description="移动结果消息")
    folder: FolderInfo = Field(..., description="移动后的文件夹信息")

