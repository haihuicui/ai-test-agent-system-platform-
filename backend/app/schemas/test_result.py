"""
测试结果相关的 Pydantic 模型

基于 BrowserStack Test Management API 的测试结果接口设计
参考: https://www.browserstack.com/docs/test-management/api-reference/test-results
"""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.enums import TestResultStatus
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2TnpnM2RBPT06MzM5NWUyMTY=


class IssueTrackerConfig(BaseModel):
    """问题跟踪器配置"""
    name: str = Field(..., description="问题跟踪器名称，如 jira")
    host: str = Field(..., description="问题跟踪器地址")


class StepResultCreate(BaseModel):
    """
    步骤结果创建模型
    
    用于添加测试步骤的执行结果
    """
    step_id: Optional[int] = Field(
        default=None, 
        description="步骤 ID (永久标识符)，与 step_index 二选一"
    )
    step_index: Optional[int] = Field(
        default=None, 
        ge=1,
        description="步骤索引 (从 1 开始)，与 step_id 二选一"
    )
    status: TestResultStatus = Field(..., description="步骤执行状态")
    description: Optional[str] = Field(default=None, description="步骤结果描述/备注")
    issues: Optional[list[str]] = Field(default=None, description="关联的问题列表")


class TestResultData(BaseModel):
    """
    测试结果数据模型
    
    用于创建测试结果时的 test_result 对象
    """
    status: TestResultStatus = Field(..., description="测试结果状态")
    description: Optional[str] = Field(default=None, description="测试结果描述/备注")
    issues: Optional[list[str]] = Field(default=None, description="关联的问题列表")
    issue_tracker: Optional[IssueTrackerConfig] = Field(default=None, description="问题跟踪器配置")
    custom_fields: Optional[dict[str, Any]] = Field(default=None, description="自定义字段")
    step_results: Optional[list[StepResultCreate]] = Field(default=None, description="步骤结果列表")


class TestResultItem(BaseModel):
    """
    单个测试结果项

    用于单个添加或批量添加时的每个结果项
    """
    test_result: TestResultData = Field(..., description="测试结果数据")
    test_case_id: str = Field(..., description="测试用例标识符")
    configuration_id: Optional[int] = Field(default=None, description="配置 ID")


class TestResultCreate(BaseModel):
    """
    创建测试结果请求模型

    POST /test-runs/{test_run_id}/results

    支持两种格式:
    1. 单个结果: {"test_result": {...}, "test_case_id": "..."}
    2. 批量结果: {"results": [...]}

    根据 BrowserStack 官方 API，单个端点同时支持单个和批量操作
    """
    # 单个结果字段
    test_result: Optional[TestResultData] = Field(default=None, description="测试结果数据 (单个添加时使用)")
    test_case_id: Optional[str] = Field(default=None, description="测试用例标识符 (单个添加时使用)")
    configuration_id: Optional[int] = Field(default=None, description="配置 ID (单个添加时使用)")

    # 批量结果字段
    results: Optional[list[TestResultItem]] = Field(default=None, description="测试结果列表 (批量添加时使用)")

    # 验证参数
    validate_tc: Optional[bool] = Field(default=None, description="是否验证测试用例 ID")
# pylint: disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TnpnM2RBPT06MzM5NWUyMTY=


class ResultStatus(BaseModel):
    """结果状态对象 (符合 BrowserStack API 格式)"""
    field_value: str = Field(..., description="状态值，如 Passed, Failed 等")

# fmt: off  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TnpnM2RBPT06MzM5NWUyMTY=

class IssueInfo(BaseModel):
    """问题信息"""
    issue_id: str = Field(..., description="问题 ID")
    issue_type: Optional[str] = Field(default=None, description="问题类型，如 jira")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")


class CustomFieldValue(BaseModel):
    """自定义字段值"""
    field_name: str = Field(..., description="字段名称")
    value: Any = Field(..., description="字段值")


class StepResultInfo(BaseModel):
    """步骤结果信息"""
    step: Optional[str] = Field(default=None, description="步骤描述")
    result: Optional[str] = Field(default=None, description="步骤预期/实际结果")
    result_status: ResultStatus = Field(..., description="步骤执行状态")
    created_by: Optional[str] = Field(default=None, description="创建人邮箱")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    custom_fields: Optional[list[CustomFieldValue]] = Field(default=None, description="自定义字段")
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TnpnM2RBPT06MzM5NWUyMTY=


class TestResultInfo(BaseModel):
    """
    测试结果信息模型

    用于返回测试结果详细信息 (符合 BrowserStack API 格式)
    """
    id: UUID = Field(..., description="测试结果 ID")
    test_run_id: str = Field(..., description="测试运行标识符")
    test_case_id: str = Field(..., description="测试用例标识符")
    result_status: ResultStatus = Field(..., description="测试结果状态")
    description: Optional[str] = Field(default=None, description="测试结果描述/备注")
    created_by: Optional[str] = Field(default=None, description="创建人邮箱")
    issues: Optional[list[IssueInfo]] = Field(default=None, description="关联的问题列表")
    custom_fields: Optional[list[CustomFieldValue]] = Field(default=None, description="自定义字段")
    step_result: Optional[list[StepResultInfo]] = Field(default=None, description="步骤结果列表")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class TestResultListInfo(BaseModel):
    """
    测试结果列表项模型

    用于列表返回简化的信息 (符合 BrowserStack API 格式)
    """
    id: UUID = Field(..., description="测试结果 ID")
    test_run_id: str = Field(..., description="测试运行标识符")
    test_case_id: str = Field(..., description="测试用例标识符")
    result_status: ResultStatus = Field(..., description="测试结果状态")
    description: Optional[str] = Field(default=None, description="测试结果描述")
    created_by: Optional[str] = Field(default=None, description="创建人邮箱")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class TestResultHistoryInfo(BaseModel):
    """
    测试结果历史记录

    用于获取测试用例在测试运行中的历史结果
    """
    id: UUID = Field(..., description="测试结果 ID")
    result_status: ResultStatus = Field(..., description="测试结果状态")
    description: Optional[str] = Field(default=None, description="测试结果描述")
    created_by: Optional[str] = Field(default=None, description="创建人邮箱")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")

