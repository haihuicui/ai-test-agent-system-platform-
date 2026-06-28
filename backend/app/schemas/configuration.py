"""
配置相关的 Pydantic 模型

基于 BrowserStack Test Management API 的配置接口设计
参考: https://www.browserstack.com/docs/test-management/api-reference/configurations
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# fmt: off  MC8zOmFIVnBZMlhsdEpUbXRiZm92b2s2UzFCcVVRPT06Y2NhZTY4NzQ=

class ConfigurationCreate(BaseModel):
    """
    创建自定义配置请求模型
    """
    name: str = Field(..., min_length=1, max_length=500, description="配置名称")
    os: Optional[str] = Field(default=None, max_length=100, description="操作系统")
    os_version: Optional[str] = Field(default=None, max_length=100, description="操作系统版本")
    device: Optional[str] = Field(default=None, max_length=200, description="设备")
    browser: Optional[str] = Field(default=None, max_length=100, description="浏览器")
    browser_version: Optional[str] = Field(default=None, max_length=100, description="浏览器版本")
    description: Optional[str] = Field(default=None, description="配置描述")


class ConfigurationInfo(BaseModel):
    """
    配置信息响应模型
    
    用于返回配置详细信息 (符合 BrowserStack API 格式)
    """
    id: int = Field(..., description="配置 ID")
    name: str = Field(..., description="配置名称")
    os: Optional[str] = Field(default=None, description="操作系统")
    os_version: Optional[str] = Field(default=None, description="操作系统版本")
    device: Optional[str] = Field(default=None, description="设备")
    browser: Optional[str] = Field(default=None, description="浏览器")
    browser_version: Optional[str] = Field(default=None, description="浏览器版本")
    is_system: bool = Field(..., description="是否为系统定义配置")

# type: ignore  MS8zOmFIVnBZMlhsdEpUbXRiZm92b2s2UzFCcVVRPT06Y2NhZTY4NzQ=

class ConfigurationDetailInfo(ConfigurationInfo):
    """
    配置详细信息响应模型
    
    包含时间戳等额外信息
    """
    description: Optional[str] = Field(default=None, description="配置描述")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")

# fmt: off  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b2s2UzFCcVVRPT06Y2NhZTY4NzQ=

class ConfigurationCreateResponse(BaseModel):
    """
    创建配置响应模型 (符合 BrowserStack API 格式)
    """
    success: bool = Field(default=True, description="是否成功")
    id: int = Field(..., description="配置 ID")
    name: str = Field(..., description="配置名称")

