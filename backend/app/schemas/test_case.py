"""
测试用例相关的 Pydantic 模型

基于 BrowserStack Test Management API 的测试用例接口设计
参考: https://www.browserstack.com/docs/test-management/api-reference/test-cases
"""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import BaseResponse, LinkInfo
from app.schemas.enums import (
    Priority, TestCaseState, TestCaseType,
    TestCaseTemplate, AutomationStatus, BulkEditOperation, ExportStatus
)
# noqa  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VW5GTmVBPT06NzM3MDVjODQ=


class TestStepBase(BaseModel):
    """测试步骤基础模型"""
    step_number: int = Field(..., ge=1, alias="order", description="步骤序号")
    action: str = Field(..., min_length=1, alias="step", description="操作步骤描述")
    expected_result: Optional[str] = Field(
        default=None,
        alias="result",
        description="预期结果"
    )

    model_config = {"populate_by_name": True}


class TestStepCreate(BaseModel):
    """创建测试步骤请求模型"""
    step: str = Field(..., min_length=1, description="操作步骤描述（支持 HTML）")
    result: Optional[str] = Field(default=None, description="预期结果（支持 HTML）")


class TestStepInfo(BaseModel):
    """测试步骤信息模型"""
    id: UUID = Field(..., description="步骤 ID")
    order: int = Field(..., description="步骤序号")
    step: str = Field(..., description="操作步骤描述")
    result: Optional[str] = Field(default=None, description="预期结果")
    shared_step_id: Optional[int] = Field(default=None, description="共享步骤 ID")
    shared_step_detail_id: Optional[int] = Field(default=None, description="共享步骤详情 ID")

    model_config = {"from_attributes": True}


class TestCaseBase(BaseModel):
    """测试用例基础模型"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="测试用例名称"
    )
    description: Optional[str] = Field(
        default=None,
        description="测试用例描述（支持 HTML）"
    )
    preconditions: Optional[str] = Field(
        default=None,
        description="前置条件（支持 HTML）"
    )
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="优先级"
    )
    state: TestCaseState = Field(
        default=TestCaseState.NEW,
        alias="status",
        description="状态"
    )
    test_case_type: TestCaseType = Field(
        default=TestCaseType.FUNCTIONAL,
        alias="case_type",
        description="测试类型"
    )

    model_config = {"populate_by_name": True}


class TestCaseCreate(BaseModel):
    """
    创建测试用例请求模型

    支持普通测试用例和 BDD 测试用例
    """
    name: str = Field(..., min_length=1, max_length=500, description="测试用例名称")
    description: Optional[str] = Field(default=None, description="测试用例描述（支持 HTML）")
    preconditions: Optional[str] = Field(default=None, description="前置条件（支持 HTML）")
    priority: Priority = Field(default=Priority.MEDIUM, description="优先级")
    state: TestCaseState = Field(default=TestCaseState.NEW, alias="status", description="状态")
    test_case_type: TestCaseType = Field(default=TestCaseType.FUNCTIONAL, alias="case_type", description="测试类型")
    owner: Optional[str] = Field(default=None, description="负责人邮箱")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    issues: Optional[list[str]] = Field(default=None, description="关联的 Jira issues")
    automation_status: AutomationStatus = Field(default=AutomationStatus.NOT_AUTOMATED, description="自动化状态")
    custom_fields: Optional[dict[str, Any]] = Field(default=None, description="自定义字段")
    # 普通测试用例字段
    test_case_steps: Optional[list[TestStepCreate]] = Field(default=None, description="测试步骤列表")
    # BDD 测试用例字段
    template: TestCaseTemplate = Field(default=TestCaseTemplate.TEST_CASE, description="测试用例模板类型")
    feature: Optional[str] = Field(default=None, description="BDD Feature 描述")
    scenario: Optional[str] = Field(default=None, description="BDD Scenario 描述")
    background: Optional[str] = Field(default=None, description="BDD Background 描述")
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VW5GTmVBPT06NzM3MDVjODQ=

    model_config = {"populate_by_name": True}

    @model_validator(mode='after')
    def validate_template(self):
        """验证 BDD 测试用例必须包含 feature 和 scenario，不能包含 test_case_steps"""
        if self.template == TestCaseTemplate.TEST_CASE_BDD:
            if not self.feature:
                raise ValueError("BDD 测试用例必须提供 feature 字段")
            if not self.scenario:
                raise ValueError("BDD 测试用例必须提供 scenario 字段")
            if self.test_case_steps:
                raise ValueError("BDD 测试用例不能包含 test_case_steps 字段")
        return self


class TestCaseUpdate(BaseModel):
    """
    更新测试用例请求模型
    """
    name: Optional[str] = Field(default=None, max_length=500, description="测试用例名称")
    description: Optional[str] = Field(default=None, description="测试用例描述")
    preconditions: Optional[str] = Field(default=None, description="前置条件")
    priority: Optional[Priority] = Field(default=None, description="优先级")
    state: Optional[TestCaseState] = Field(default=None, alias="status", description="状态")
    test_case_type: Optional[TestCaseType] = Field(default=None, alias="case_type", description="测试类型")
    folder_id: Optional[UUID] = Field(default=None, description="所属文件夹 ID")
    owner: Optional[str] = Field(default=None, description="负责人邮箱")
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    issues: Optional[list[str]] = Field(default=None, description="关联的 Jira issues")
    automation_status: Optional[AutomationStatus] = Field(default=None, description="自动化状态")
    custom_fields: Optional[dict[str, Any]] = Field(default=None, description="自定义字段")
    test_case_steps: Optional[list[TestStepCreate]] = Field(default=None, description="测试步骤列表")
    # BDD 字段
    feature: Optional[str] = Field(default=None, description="BDD Feature 描述")
    scenario: Optional[str] = Field(default=None, description="BDD Scenario 描述")
    background: Optional[str] = Field(default=None, description="BDD Background 描述")

    model_config = {"populate_by_name": True}


class TestCaseInfo(BaseModel):
    """
    测试用例完整信息模型
    """
    id: UUID = Field(..., description="测试用例 ID")
    identifier: str = Field(..., description="测试用例标识符，如 TC-1234")
    name: str = Field(..., description="测试用例名称")
    description: Optional[str] = Field(default=None, description="测试用例描述")
    preconditions: Optional[str] = Field(default=None, description="前置条件")
    priority: Priority = Field(..., description="优先级")
    status: TestCaseState = Field(..., description="状态")
    case_type: TestCaseType = Field(..., description="测试类型")
    template: TestCaseTemplate = Field(default=TestCaseTemplate.TEST_CASE, description="模板类型")
    automation_status: AutomationStatus = Field(default=AutomationStatus.NOT_AUTOMATED, description="自动化状态")
    project_id: UUID = Field(..., description="所属项目 ID")
    folder_id: Optional[UUID] = Field(default=None, description="所属文件夹 ID")
    owner: Optional[str] = Field(default=None, description="负责人邮箱")
    created_by: str = Field(..., description="创建者邮箱")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")
    version: int = Field(default=1, description="版本号")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    issues: list[str] = Field(default_factory=list, description="关联的 Jira issues")
    custom_fields: Optional[dict[str, Any]] = Field(default=None, description="自定义字段")
    test_case_steps: list[TestStepInfo] = Field(default_factory=list, description="测试步骤")
    # BDD 字段
    feature: Optional[str] = Field(default=None, description="BDD Feature 描述")
    scenario: Optional[str] = Field(default=None, description="BDD Scenario 描述")
    background: Optional[str] = Field(default=None, description="BDD Background 描述")
    links: Optional[LinkInfo] = Field(default=None, description="相关资源链接")

    model_config = {"from_attributes": True}


class TestCaseMinifiedInfo(BaseModel):
    """
    测试用例精简信息模型（用于 minify=true 查询）
    """
    id: UUID = Field(..., description="测试用例 ID")
    identifier: str = Field(..., description="测试用例标识符")
    name: str = Field(..., description="测试用例名称")
    priority: Priority = Field(..., description="优先级")
    status: TestCaseState = Field(..., description="状态")
    case_type: TestCaseType = Field(..., description="测试类型")
    folder_id: Optional[UUID] = Field(default=None, description="所属文件夹 ID")
    owner: Optional[str] = Field(default=None, description="负责人邮箱")
    tags: list[str] = Field(default_factory=list, description="标签列表")

    model_config = {"from_attributes": True}


class TestCaseResponse(BaseResponse):
    """单个测试用例响应模型"""
    success: bool = Field(default=True)
    test_case: TestCaseInfo = Field(..., description="测试用例信息")


class TestCaseListResponse(BaseResponse):
    """测试用例列表响应模型"""
    success: bool = Field(default=True)
    test_cases: list[TestCaseInfo] = Field(default_factory=list)


class TestCaseDeleteResponse(BaseResponse):
    """删除测试用例响应模型"""
    success: bool = Field(default=True)
    message: str = Field(..., description="删除结果消息")


# ============ 批量操作相关模型 ============
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VW5GTmVBPT06NzM3MDVjODQ=

class BulkTestCaseRequest(BaseModel):
    """批量操作测试用例请求模型（简单批量更新）"""
    test_case_ids: list[str] = Field(
        ...,
        min_length=1,
        description="测试用例标识符列表，如 ['TC-1234', 'TC-1235']"
    )
    update_data: Optional[dict] = Field(
        default=None,
        description="要更新的字段"
    )


class FieldOperation(BaseModel):
    """字段操作模型"""
    operation: BulkEditOperation = Field(..., description="操作类型")
    value: Optional[Any] = Field(default=None, description="操作值")


class BulkEditWithOperationsRequest(BaseModel):
    """
    带操作符的批量编辑请求模型

    支持 ignore, replace, add, remove 操作
    """
    test_case_ids: list[str] = Field(
        ...,
        min_length=1,
        description="测试用例标识符列表"
    )
    automation_status: Optional[FieldOperation] = Field(default=None, description="自动化状态操作")
    case_type: Optional[FieldOperation] = Field(default=None, description="测试类型操作")
    priority: Optional[FieldOperation] = Field(default=None, description="优先级操作")
    state: Optional[FieldOperation] = Field(default=None, description="状态操作")
    owner: Optional[FieldOperation] = Field(default=None, description="负责人操作")
    preconditions: Optional[FieldOperation] = Field(default=None, description="前置条件操作")
    tags: Optional[FieldOperation] = Field(default=None, description="标签操作")
    issues: Optional[FieldOperation] = Field(default=None, description="关联 issues 操作")
    custom_fields: Optional[FieldOperation] = Field(default=None, description="自定义字段操作")


class BulkDeleteRequest(BaseModel):
    """批量删除请求模型"""
    test_case_ids: list[str] = Field(
        ...,
        min_length=1,
        description="测试用例标识符列表"
    )


class BulkOperationResponse(BaseResponse):
    """批量操作响应模型"""
    success: bool = Field(default=True)
    message: str = Field(..., description="操作结果消息")
    affected_count: int = Field(..., description="受影响的测试用例数量")


# ============ BDD 导出相关模型 ============

class ExportBDDRequest(BaseModel):
    """导出 BDD 测试用例请求模型"""
    test_case_ids: list[str] = Field(
        ...,
        min_length=1,
        description="要导出的测试用例标识符列表"
    )
    combine_into_one: bool = Field(
        default=False,
        description="是否合并为单个 .feature 文件"
    )
    combined_feature: Optional[str] = Field(
        default=None,
        description="合并后的 Feature 名称（combine_into_one=true 时必填）"
    )
    combined_background: Optional[str] = Field(
        default=None,
        description="合并后的 Background 内容"
    )

    @model_validator(mode='after')
    def validate_combined(self):
        """验证合并导出时必须提供 combined_feature"""
        if self.combine_into_one and not self.combined_feature:
            raise ValueError("合并导出时必须提供 combined_feature 字段")
        return self

# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VW5GTmVBPT06NzM3MDVjODQ=

class ExportBDDResponse(BaseResponse):
    """导出 BDD 测试用例响应模型"""
    success: bool = Field(default=True)
    export_id: str = Field(..., description="导出任务 ID")
    status: ExportStatus = Field(..., description="导出状态")
    status_url: str = Field(..., description="状态查询 URL")


class ExportStatusResponse(BaseResponse):
    """导出状态响应模型"""
    success: bool = Field(default=True)
    export_id: str = Field(..., description="导出任务 ID")
    status: ExportStatus = Field(..., description="导出状态")
    download_url: Optional[str] = Field(default=None, description="下载 URL（完成后可用）")
    error_message: Optional[str] = Field(default=None, description="错误信息（失败时）")


# ============ 测试用例历史相关模型 ============

class ModifiedFieldInfo(BaseModel):
    """修改字段信息"""
    old: Any = Field(..., description="旧值")
    new: Any = Field(..., description="新值")


class TestCaseHistoryItem(BaseModel):
    """测试用例历史记录项"""
    version_id: str = Field(..., description="版本 ID，如 v1, v2")
    version_name: str = Field(..., description="版本名称，如 V1, V2")
    source: str = Field(..., description="变更来源，如 update, create")
    modified_fields: list[str] = Field(default_factory=list, description="修改的字段列表")
    modified: dict[str, ModifiedFieldInfo] = Field(default_factory=dict, description="修改详情")
    user_id: Optional[int] = Field(default=None, description="操作用户 ID")
    updated_by: Optional[str] = Field(default=None, description="操作用户邮箱")
    testcase_id: str = Field(..., description="测试用例标识符")
    created_at: datetime = Field(..., description="变更时间")


class TestCaseHistoryResponse(BaseResponse):
    """测试用例历史响应模型"""
    success: bool = Field(default=True)
    info: dict = Field(..., description="分页信息")
    history: list[TestCaseHistoryItem] = Field(default_factory=list, description="历史记录列表")
