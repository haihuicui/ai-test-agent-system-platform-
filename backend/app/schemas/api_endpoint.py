"""
API 端点相关的 Pydantic Schemas
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2Vm1oc2JBPT06MDNjNjg4YjQ=

class APIEndpointBase(BaseModel):
    """API 端点基础 Schema"""
    display_name: str = Field(..., description="显示名称：方法 + 路径")
    path: str = Field(..., description="API 路径")
    method: str = Field(..., description="HTTP 方法")
    summary: str | None = Field(None, description="端点摘要")
    description: str | None = Field(None, description="端点详细描述")

# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2Vm1oc2JBPT06MDNjNjg4YjQ=

class APIEndpointCreate(APIEndpointBase):
    """创建 API 端点 Schema"""
    project_id: UUID = Field(..., description="项目 ID")
    folder_id: UUID | None = Field(None, description="文件夹 ID")
    schema_file_id: UUID | None = Field(None, description="Schema 文件 ID")
    tag_group: str | None = Field(None, description="标签分组")
    parameters: list[dict] | None = Field(None, description="参数定义")
    request_body: dict | None = Field(None, description="请求体定义")
    responses: dict | None = Field(None, description="响应定义")
    security: list[dict] | None = Field(None, description="安全配置")
    tags: list[str] | None = Field(None, description="标签列表")


class APIEndpointUpdate(BaseModel):
    """更新 API 端点 Schema"""
    display_name: str | None = None
    path: str | None = None
    method: str | None = None
    summary: str | None = None
    description: str | None = None
    tag_group: str | None = None
    parameters: list[dict] | None = None
    request_body: dict | None = None
    responses: dict | None = None
    custom_config: dict | None = None


class APIEndpointResponse(APIEndpointBase):
    """API 端点响应 Schema"""
    id: UUID
    project_id: UUID
    folder_id: UUID | None
    schema_file_id: UUID | None

    # 详细信息
    tag_group: str | None
    parameters: list[dict] | None
    request_body: dict | None
    responses: dict | None
    security: list[dict] | None
    tags: list[str] | None
    custom_config: dict | None
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2Vm1oc2JBPT06MDNjNjg4YjQ=

    # 统计信息
    total_test_cases: int
    total_test_runs: int
    last_run_status: str | None

    # 时间戳
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class OpenAPIParseResult(BaseModel):
    """OpenAPI 解析结果 Schema"""
    schema_title: str = Field(..., description="Schema 标题")
    schema_version: str = Field(..., description="Schema 版本")
    total_endpoints: int = Field(..., description="端点总数")
    tag_folders: list[dict] = Field(..., description="创建的标签文件夹列表")
    endpoints: list[dict] = Field(..., description="创建的端点列表")

# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2Vm1oc2JBPT06MDNjNjg4YjQ=

class OpenAPIUploadRequest(BaseModel):
    """上传 OpenAPI 文件请求 Schema"""
    project_identifier: str = Field(..., description="项目标识符")
    parent_folder_id: UUID | None = Field(None, description="父文件夹 ID（可选）")
    file_content: dict = Field(..., description="OpenAPI JSON 内容")
    create_structure: bool = Field(True, description="是否自动创建文件夹结构")
