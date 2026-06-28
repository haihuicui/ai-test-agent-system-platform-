"""
测试计划相关的 Pydantic 模型

基于 BrowserStack Test Management API 的测试计划接口设计
参考: https://www.browserstack.com/docs/test-management/api-reference/test-plans
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.enums import TestPlanStatus, TestPlanActiveState
# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1dGeVl3PT06ZGVkOTY2ZmY=


class TestPlanLinks(BaseModel):
    """测试计划相关链接"""
    self_link: Optional[str] = Field(default=None, alias="self", description="自身链接")
    test_runs: Optional[str] = Field(default=None, description="关联的测试运行链接")
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1dGeVl3PT06ZGVkOTY2ZmY=
    
    model_config = {"populate_by_name": True}


class TestRunBrief(BaseModel):
    """测试运行简要信息（用于测试计划中展示）"""
    identifier: str = Field(..., description="测试运行标识符")
    name: str = Field(..., description="测试运行名称")


class TestRunsCount(BaseModel):
    """测试运行状态计数"""
    active: int = Field(default=0, description="活跃的测试运行数量")
    closed: int = Field(default=0, description="已关闭的测试运行数量")


class TestPlanCreate(BaseModel):
    """
    创建测试计划请求模型
    
    用于创建新的测试计划
    """
    name: str = Field(..., min_length=1, max_length=500, description="测试计划名称")
    description: Optional[str] = Field(default=None, description="测试计划描述")
    plan_status: TestPlanStatus = Field(default=TestPlanStatus.DRAFT, description="计划状态")
    start_date: Optional[date] = Field(default=None, description="开始日期")
    end_date: Optional[date] = Field(default=None, description="结束日期")
    owner: Optional[str] = Field(default=None, description="负责人邮箱")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    custom_fields: Optional[dict] = Field(default=None, description="自定义字段")

# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1dGeVl3PT06ZGVkOTY2ZmY=

class TestPlanUpdate(BaseModel):
    """
    更新测试计划请求模型
    
    用于部分更新测试计划
    """
    name: Optional[str] = Field(default=None, min_length=1, max_length=500, description="测试计划名称")
    description: Optional[str] = Field(default=None, description="测试计划描述")
    plan_status: Optional[TestPlanStatus] = Field(default=None, description="计划状态")
    active_state: Optional[TestPlanActiveState] = Field(default=None, description="活跃状态")
    start_date: Optional[date] = Field(default=None, description="开始日期")
    end_date: Optional[date] = Field(default=None, description="结束日期")
    owner: Optional[str] = Field(default=None, description="负责人邮箱")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    custom_fields: Optional[dict] = Field(default=None, description="自定义字段")


class TestPlanInfo(BaseModel):
    """
    测试计划完整信息模型

    用于返回测试计划详细信息（Get Test Plan Details）
    """
    id: UUID = Field(..., description="测试计划 ID")
    identifier: str = Field(..., description="测试计划标识符，如 TP-123")
    name: str = Field(..., description="测试计划名称")
    description: Optional[str] = Field(default=None, description="测试计划描述")
    plan_status: TestPlanStatus = Field(..., description="计划状态")
    active_state: TestPlanActiveState = Field(..., description="活跃状态")
    project_id: str = Field(..., description="所属项目标识符")
    start_date: Optional[datetime] = Field(default=None, description="开始日期")
    end_date: Optional[datetime] = Field(default=None, description="结束日期")
    owner: Optional[str] = Field(default=None, description="负责人邮箱")
    test_runs_count: TestRunsCount = Field(default_factory=TestRunsCount, description="测试运行数量统计")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    custom_fields: Optional[dict] = Field(default=None, description="自定义字段")
    test_runs: Optional[list[TestRunBrief]] = Field(default=None, description="关联的测试运行")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")
    links: Optional[TestPlanLinks] = Field(default=None, description="相关资源链接")
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2V1dGeVl3PT06ZGVkOTY2ZmY=


class TestPlanListInfo(BaseModel):
    """
    测试计划列表项模型

    用于列表返回简化的信息
    """
    id: UUID = Field(..., description="测试计划 ID")
    identifier: str = Field(..., description="测试计划标识符")
    name: str = Field(..., description="测试计划名称")
    plan_status: TestPlanStatus = Field(..., description="计划状态")
    active_state: TestPlanActiveState = Field(..., description="活跃状态")
    test_runs_count: TestRunsCount = Field(default_factory=TestRunsCount, description="测试运行数量统计")
    start_date: Optional[datetime] = Field(default=None, description="开始日期")
    end_date: Optional[datetime] = Field(default=None, description="结束日期")
    created_at: datetime = Field(..., description="创建时间")

