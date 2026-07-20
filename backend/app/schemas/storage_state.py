"""
Web 登录态生成相关 Schema
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LoginSelectors(BaseModel):
    """表单登录定位器配置"""

    login_url: str = Field(..., description="登录页 URL")
    username_selector: str = Field(
        default="input[name='username']",
        description="用户名输入框 CSS 选择器",
    )
    password_selector: str = Field(
        default="input[name='password']",
        description="密码输入框 CSS 选择器",
    )
    captcha_selector: Optional[str] = Field(
        default=None,
        description="验证码输入框 CSS 选择器，可选",
    )
    submit_selector: str = Field(
        default="button[type='submit']",
        description="提交按钮 CSS 选择器",
    )
    success_selector: str = Field(
        default=".dashboard",
        description="登录成功后页面可见元素的 CSS 选择器",
    )


class StorageStateGenerateRequest(BaseModel):
    """触发生成 storageState 的请求"""

    username: Optional[str] = Field(default=None, description="登录用户名；不传则从环境配置读取")
    password: str = Field(..., description="登录密码，不会被持久化")
    captcha: Optional[str] = Field(default=None, description="验证码值，不会被持久化")
    headless: bool = Field(default=True, description="是否使用无头浏览器")
    selectors: Optional[LoginSelectors] = Field(
        default=None,
        description="登录配置；不传则从 ProjectEnvironment.auth_config.form_login 读取",
    )
    save_attachment: bool = Field(default=True, description="是否归档到 MinIO")


class StorageStateJobInfo(BaseModel):
    """生成任务信息"""

    job_id: UUID = Field(..., description="任务 ID")
    project_id: UUID = Field(..., description="所属项目 ID")
    environment_id: Optional[UUID] = Field(default=None, description="使用的环境配置 ID")
    status: str = Field(..., description="任务状态: pending/running/completed/failed")
    output_path: Optional[str] = Field(default=None, description="生成的 storageState.json 本地路径")
    attachment_id: Optional[UUID] = Field(default=None, description="MinIO 附件 ID")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    stdout: Optional[str] = Field(default=None, description="Playwright 标准输出")
    stderr: Optional[str] = Field(default=None, description="Playwright 标准错误")
    started_at: Optional[datetime] = Field(default=None, description="开始执行时间")
    completed_at: Optional[datetime] = Field(default=None, description="执行完成时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")

    model_config = {"from_attributes": True}


class StorageStateLatestInfo(BaseModel):
    """最近一次成功生成的登录态信息"""

    job_id: UUID
    environment_id: Optional[UUID]
    output_path: Optional[str]
    attachment_id: Optional[UUID]
    generated_at: Optional[datetime]
    object_name: Optional[str] = Field(default=None, description="MinIO 对象路径")
