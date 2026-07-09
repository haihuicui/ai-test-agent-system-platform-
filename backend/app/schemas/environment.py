"""
项目环境配置 Schema

定义环境配置的请求/响应数据模型
注意：按业务要求，auth_secret 明文传输、明文存储。
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class EnvironmentCreate(BaseModel):
    """创建环境配置请求"""
    name: str = Field(..., min_length=1, max_length=100, description="环境名称，如 dev/test/prod")
    base_url: HttpUrl = Field(..., description="API Base URL")
    auth_type: str = Field(default="none", description="认证类型：none/bearer/dynamic_bearer/api_key/oauth2")
    auth_secret: Optional[str] = Field(default=None, description="认证凭据（明文入参、明文存储）。bearer 为 token，api_key 为 key，oauth2 为 client_secret")
    auth_config: Optional[dict] = Field(default=None, description="非敏感认证配置；dynamic_bearer 的 token 请求配置也存于此")
    timeout_ms: int = Field(default=30000, ge=1000, description="默认请求超时（毫秒）")
    is_default: bool = Field(default=False, description="是否为项目默认环境")


class EnvironmentUpdate(BaseModel):
    """更新环境配置请求"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    base_url: Optional[HttpUrl] = Field(default=None)
    auth_type: Optional[str] = Field(default=None)
    auth_secret: Optional[str] = Field(default=None, description="传空字符串表示清除凭据")
    auth_config: Optional[dict] = Field(default=None)
    timeout_ms: Optional[int] = Field(default=None, ge=1000)
    is_default: Optional[bool] = Field(default=None)


class EnvironmentInfo(BaseModel):
    """环境配置响应（按业务要求返回明文 auth_secret）"""
    id: UUID
    name: str
    base_url: str
    auth_type: str
    auth_config: dict
    timeout_ms: int
    is_default: bool
    has_auth_secret: bool = Field(default=False, description="是否已配置认证凭据")
    auth_secret: Optional[str] = Field(default=None, description="认证凭据明文值")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
