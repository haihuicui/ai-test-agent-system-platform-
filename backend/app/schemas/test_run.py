"""
测试运行相关的 Pydantic 模型

字段集合严格对齐 BrowserStack Test Management API:
https://www.browserstack.com/docs/test-management/api-reference/test-runs
"""

from datetime import date, datetime
from typing import Optional, Any, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import (
    TestRunState,
    TestRunActiveState,
    TestResultStatus,
    Priority,
    TestCaseType,
    FilterScope,
    IssueTrackerName,
    ScriptType,
    ExecutionMode,
    TriggerType,
    JobStatus,
    ScheduleTriggerType,
    FailurePolicy,
)

# pylint: disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0hBeWFRPT06ODhjYzc5YzI=

# ============ 公共内嵌结构 ============

class IssueTracker(BaseModel):
    """问题跟踪器配置"""
    name: IssueTrackerName = Field(..., description="问题跟踪器类型 (jira/azure/asana)")
    host: str = Field(..., description="问题跟踪器地址")


class TestCaseFilter(BaseModel):
    """测试用例过滤条件（BS filter_test_cases）"""
    status: Optional[list[str]] = Field(default=None, description="状态过滤")
    priority: Optional[list[str]] = Field(default=None, description="优先级过滤")
    case_type: Optional[list[str]] = Field(default=None, description="测试类型过滤")
    owner: Optional[list[str]] = Field(default=None, description="负责人过滤")
    tags: Optional[list[str]] = Field(default=None, description="标签过滤")
    custom_fields: Optional[dict[str, list[Any]]] = Field(
        default=None, description="自定义字段过滤"
    )


class ConfigurationMapping(BaseModel):
    """测试用例-配置映射（BS configuration_map 条目）"""
    test_case_id: Union[str, list[str]] = Field(
        ..., description="测试用例标识符，支持字符串或字符串列表"
    )
    configuration_ids: list[int] = Field(..., description="配置 ID 列表")


# ============ 请求模型 ============

class ScriptSelection(BaseModel):
    """统一脚本选择 DTO"""
    script_type: ScriptType = Field(..., description="脚本类型")
    script_id: str = Field(..., description="脚本 ID（UUID 字符串）")
    script_identifier: Optional[str] = Field(default=None, description="脚本标识符")
    script_name: Optional[str] = Field(default=None, description="脚本名称")
    execution_order: int = Field(default=0, description="执行顺序")
    execution_mode: Optional[ExecutionMode] = Field(
        default=None, description="执行模式（默认继承 TestRun 配置）"
    )
    execution_config: Optional[dict] = Field(
        default=None, description="执行配置覆盖"
    )


class TestRunCreate(BaseModel):
    """
    创建测试运行请求模型（BS POST /test-runs）

    测试用例解析顺序（首个非空者生效）：
    1. include_all=True  → 项目下所有用例
    2. folder_ids + filter_test_cases + filter_scope=within_folders → 文件夹内+过滤
    3. folder_ids only  → 文件夹内全部
    4. filter_test_cases + filter_scope=global → 项目内按过滤
    5. test_cases → 显式列表
    6. scripts → 直接脚本选择（新方式，优先级最高）
    """
    name: str = Field(..., min_length=1, max_length=500, description="测试运行名称")
    description: Optional[str] = Field(default=None, description="测试运行描述")
    run_state: TestRunState = Field(
        default=TestRunState.NEW_RUN, description="运行状态"
    )
    assignee: Optional[str] = Field(default=None, description="负责人邮箱")
    test_case_assignee: Optional[str] = Field(
        default=None, description="测试用例默认负责人邮箱"
    )
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    issues: Optional[list[str]] = Field(default=None, description="关联的问题列表")
    issue_tracker: Optional[IssueTracker] = Field(
        default=None, description="问题跟踪器配置"
    )
    configurations: Optional[list[int]] = Field(
        default=None, description="配置 ID 列表（全局应用）"
    )
    configuration_map: Optional[list[ConfigurationMapping]] = Field(
        default=None, description="测试用例-配置映射，覆盖 configurations"
    )
    test_plan_id: Optional[str] = Field(
        default=None, description="关联的测试计划 ID（与 sub_test_plan_id 互斥）"
    )
    sub_test_plan_id: Optional[str] = Field(
        default=None, description="关联的子测试计划 ID，形如 STP-5"
    )
    test_cases: Optional[list[str]] = Field(
        default=None, description="测试用例标识符列表"
    )
    folder_ids: Optional[list[int]] = Field(
        default=None, description="文件夹 ID 列表（数据库内部使用 UUID，这里保留 int 兼容 BS schema）"
    )
    include_all: Optional[bool] = Field(
        default=False, description="是否包含项目下全部测试用例"
    )
    filter_scope: Optional[FilterScope] = Field(
        default=FilterScope.GLOBAL, description="过滤作用域 (global / within_folders)"
    )
    filter_test_cases: Optional[TestCaseFilter] = Field(
        default=None, description="测试用例过滤条件"
    )
    # 企业级测试调度：直接脚本选择
    scripts: Optional[list[ScriptSelection]] = Field(
        default=None, description="直接选择的脚本列表（API测试/场景测试/Web测试）"
    )
    execution_mode: Optional[ExecutionMode] = Field(
        default=ExecutionMode.SEQUENTIAL, description="执行模式: sequential / parallel"
    )
    max_concurrency: Optional[int] = Field(
        default=5, ge=1, le=50, description="最大并发数"
    )
    failure_policy: Optional[FailurePolicy] = Field(
        default=FailurePolicy.CONTINUE,
        description="失败策略: continue / stop_run / stop_job / mark_blocked",
    )
    environment_id: Optional[str] = Field(
        default=None, description="执行环境 ID，未指定时使用项目默认环境"
    )
    scheduled_by: Optional[str] = Field(
        default=None, description="来源定时调度 ID（trigger_type=scheduled 时使用）"
    )
    trigger_type: Optional[TriggerType] = Field(
        default=TriggerType.MANUAL, description="触发类型: manual / scheduled / api"
    )

    @model_validator(mode="after")
    def _check_mutual_exclusion(self) -> "TestRunCreate":
        if self.test_plan_id and self.sub_test_plan_id:
            raise ValueError(
                "test_plan_id 与 sub_test_plan_id 不能同时提供（BS 规范互斥）"
            )
        return self


class TestRunPatchUpdate(BaseModel):
    """
    PATCH /test-runs/{id}/update 请求体

    仅更新提供的字段；数组字段传 `[]` 可清空，未传字段保持不变。
    """
    name: Optional[str] = Field(
        default=None, min_length=1, max_length=500, description="测试运行名称"
    )
    description: Optional[str] = Field(default=None, description="测试运行描述")
    run_state: Optional[TestRunState] = Field(default=None, description="运行状态")
    active_state: Optional[TestRunActiveState] = Field(
        default=None, description="活跃状态 (active / closed)"
    )
    assignee: Optional[str] = Field(default=None, description="负责人邮箱")
    test_case_assignee: Optional[str] = Field(
        default=None, description="测试用例默认负责人邮箱"
    )
    tags: Optional[list[str]] = Field(default=None, description="标签列表")
    issues: Optional[list[str]] = Field(default=None, description="关联的问题列表")
    issue_tracker: Optional[IssueTracker] = Field(
        default=None, description="问题跟踪器配置"
    )
    test_plan_id: Optional[str] = Field(
        default=None, description="关联的测试计划 ID（与 sub_test_plan_id 互斥）"
    )
    sub_test_plan_id: Optional[str] = Field(default=None, description="子测试计划 ID")
    configurations: Optional[list[int]] = Field(
        default=None, description="配置 ID 列表"
    )
    configuration_map: Optional[list[ConfigurationMapping]] = Field(
        default=None, description="测试用例-配置映射"
    )
    folder_ids: Optional[list[int]] = Field(
        default=None, description="文件夹 ID 列表"
    )
    include_all: Optional[bool] = Field(
        default=None, description="是否包含项目下全部测试用例"
    )
    filter_scope: Optional[FilterScope] = Field(
        default=None, description="过滤作用域"
    )
    filter_test_cases: Optional[TestCaseFilter] = Field(
        default=None, description="测试用例过滤条件"
    )
    execution_mode: Optional[ExecutionMode] = Field(
        default=None, description="执行模式"
    )
    max_concurrency: Optional[int] = Field(
        default=None, ge=1, le=50, description="最大并发数"
    )
    failure_policy: Optional[FailurePolicy] = Field(
        default=None, description="失败策略: continue / stop_run / stop_job / mark_blocked"
    )
    environment_id: Optional[str] = Field(
        default=None, description="执行环境 ID"
    )
    scripts: Optional[list[ScriptSelection]] = Field(
        default=None, description="直接选择的脚本列表"
    )

    @model_validator(mode="after")
    def _check_mutual_exclusion(self) -> "TestRunPatchUpdate":
        if self.test_plan_id and self.sub_test_plan_id:
            raise ValueError("test_plan_id 与 sub_test_plan_id 不能同时提供")
        return self


class TestRunFullReplace(TestRunCreate):
    """
    POST /test-runs/{id}/update 请求体（全量替换）

    与创建相同；服务层会按新参数重建关联用例。
    """
    pass
# fmt: off  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0hBeWFRPT06ODhjYzc5YzI=


class TestCaseAssignee(BaseModel):
    """单条测试用例分配条目（BS assign_to 元素）"""
    test_case_id: str = Field(..., description="测试用例标识符")
    configuration_id: Optional[int] = Field(default=None, description="配置 ID")
    assignee: str = Field(..., description="负责人邮箱")


class TestRunAssignRequest(BaseModel):
    """POST /test-runs/{id}/assign 请求体"""
    assign_to: list[TestCaseAssignee] = Field(..., description="分配列表")


class AddTestCasesRequest(BaseModel):
    """添加测试用例到测试运行（BS 之外的便利扩展）"""
    test_cases: list[str] = Field(..., description="测试用例标识符列表")
    configuration_ids: Optional[list[int]] = Field(
        default=None, description="配置 ID 列表"
    )
    assignee: Optional[str] = Field(default=None, description="负责人邮箱")


class RemoveTestCasesRequest(BaseModel):
    """从测试运行移除测试用例（BS 之外的便利扩展）"""
    test_cases: list[str] = Field(..., description="测试用例标识符列表")
    configuration_ids: Optional[list[int]] = Field(
        default=None, description="配置 ID 列表"
    )


class CloseTestRunRequest(BaseModel):
    """POST /test-runs/{id}/close 请求体（按 BS 实际无字段，留空对象）"""
    active_state: TestRunActiveState = Field(
        default=TestRunActiveState.CLOSED, description="活跃状态"
    )


class BatchRetryJobsRequest(BaseModel):
    """POST /test-runs/{id}/script-jobs/batch-retry 请求体"""
    job_ids: list[str] = Field(..., description="要重试的脚本作业 ID 列表")


# ============ 响应模型 ============

class TestRunLinks(BaseModel):
    """测试运行相关链接"""
    self_link: Optional[str] = Field(
        default=None, alias="self", description="自身链接"
    )
    test_cases: Optional[str] = Field(default=None, description="测试用例链接")

    model_config = ConfigDict(populate_by_name=True)


class OverallProgress(BaseModel):
    """
    整体进度统计（BS overall_progress）

    完整集合：untested / passed / retest / failed / blocked / skipped / in_progress
    """
    untested: int = Field(default=0, description="未执行数量")
    passed: int = Field(default=0, description="通过数量")
    retest: int = Field(default=0, description="重测数量")
    failed: int = Field(default=0, description="失败数量")
    blocked: int = Field(default=0, description="阻塞数量")
    skipped: int = Field(default=0, description="跳过数量")
    in_progress: int = Field(default=0, description="测试中数量")


class TestPlanRef(BaseModel):
    """关联的测试计划简要引用"""
    identifier: str = Field(..., description="测试计划标识符")
    name: str = Field(..., description="测试计划名称")

# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0hBeWFRPT06ODhjYzc5YzI=

class TestStepBrief(BaseModel):
    """测试运行内联返回的步骤摘要（BS test_cases[].steps）"""
    id: UUID = Field(..., description="步骤 ID")
    order: int = Field(..., description="步骤序号")
    description: str = Field(..., description="操作描述")
    result: Optional[str] = Field(default=None, description="预期结果")


class TestRunTestCaseInfo(BaseModel):
    """
    测试运行中的测试用例完整信息（默认/fetch_steps 响应使用）
    """
    id: UUID = Field(..., description="关联 ID")
    test_run_id: UUID = Field(..., description="测试运行 ID")
    test_case_id: UUID = Field(..., description="测试用例 ID")
    identifier: str = Field(..., description="测试用例标识符")
    name: str = Field(..., description="测试用例名称")
    description: Optional[str] = Field(default=None, description="测试用例描述")
    case_type: Optional[TestCaseType] = Field(default=None, description="测试类型")
    priority: Optional[Priority] = Field(default=None, description="优先级")
    status: Optional[str] = Field(default=None, description="测试用例自身状态")
    folder_id: Optional[UUID] = Field(default=None, description="文件夹 ID")
    folder_path: Optional[str] = Field(default=None, description="文件夹路径")
    configuration_id: Optional[int] = Field(default=None, description="配置 ID")
    assignee: Optional[str] = Field(default=None, description="负责人邮箱")
    latest_status: TestResultStatus = Field(
        default=TestResultStatus.UNTESTED, description="最新状态"
    )
    latest_result_id: Optional[UUID] = Field(
        default=None, description="最新测试结果 ID"
    )
    dataset: Optional[list[dict[str, Any]]] = Field(
        default=None, description="数据驱动数据集"
    )
    steps: Optional[list[TestStepBrief]] = Field(
        default=None, description="测试步骤（fetch_steps=true 时返回前 30 条）"
    )
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    last_updated_at: Optional[datetime] = Field(default=None, description="更新时间")
    created_by: Optional[UUID] = Field(default=None, description="创建者 ID")
    last_updated_by: Optional[UUID] = Field(default=None, description="更新者 ID")


class TestRunTestCaseMinifiedInfo(BaseModel):
    """测试运行中的测试用例精简信息（minify=true 响应使用）"""
    identifier: str = Field(..., description="测试用例标识符")
    name: str = Field(..., description="测试用例名称")
    description: Optional[str] = Field(default=None, description="测试用例描述")
    latest_status: TestResultStatus = Field(
        default=TestResultStatus.UNTESTED, description="最新状态"
    )


class TestRunScriptJobInfo(BaseModel):
    """测试运行脚本作业信息"""
    id: UUID = Field(..., description="作业 ID")
    test_run_id: UUID = Field(..., description="测试运行 ID")
    script_type: ScriptType = Field(..., description="脚本类型")
    script_id: UUID = Field(..., description="脚本 ID")
    script_identifier: Optional[str] = Field(default=None, description="脚本标识符")
    script_name: Optional[str] = Field(default=None, description="脚本名称")
    execution_order: int = Field(default=0, description="执行顺序")
    execution_mode: ExecutionMode = Field(..., description="执行模式")
    status: JobStatus = Field(..., description="作业状态")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    duration_ms: Optional[int] = Field(default=None, description="执行时长(毫秒)")
    result_summary: Optional[dict] = Field(default=None, description="结果摘要")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    stdout: Optional[str] = Field(default=None, description="标准输出日志")
    stderr: Optional[str] = Field(default=None, description="标准错误日志")
    report_path: Optional[str] = Field(default=None, description="报告路径")
    retry_count: int = Field(default=0, description="已重试次数")
    max_retries: int = Field(default=0, description="最大重试次数")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class TestRunScriptJobCreate(BaseModel):
    """创建测试运行脚本作业"""
    script_type: ScriptType = Field(..., description="脚本类型")
    script_id: str = Field(..., description="脚本 ID")
    script_identifier: Optional[str] = Field(default=None, description="脚本标识符")
    script_name: Optional[str] = Field(default=None, description="脚本名称")
    execution_order: int = Field(default=0, description="执行顺序")
    execution_mode: Optional[ExecutionMode] = Field(
        default=None, description="执行模式"
    )
    execution_config: Optional[dict] = Field(
        default=None, description="执行配置覆盖"
    )
    max_retries: int = Field(default=0, ge=0, le=10, description="最大重试次数")


class TestRunScriptJobUpdate(BaseModel):
    """更新测试运行脚本作业"""
    execution_order: Optional[int] = Field(default=None, description="执行顺序")
    execution_mode: Optional[ExecutionMode] = Field(default=None, description="执行模式")
    max_retries: Optional[int] = Field(default=None, ge=0, le=10, description="最大重试次数")
    execution_config: Optional[dict] = Field(default=None, description="执行配置覆盖")
# type: ignore  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2T0hBeWFRPT06ODhjYzc5YzI=


class TestRunInfo(BaseModel):
    """
    测试运行完整信息（默认详情响应）
    """
    id: UUID = Field(..., description="测试运行 ID")
    identifier: str = Field(..., description="测试运行标识符，如 TR-123")
    name: str = Field(..., description="测试运行名称")
    description: Optional[str] = Field(default=None, description="测试运行描述")
    run_state: TestRunState = Field(..., description="运行状态")
    active_state: TestRunActiveState = Field(..., description="活跃状态")
    assignee: Optional[str] = Field(default=None, description="负责人邮箱")
    test_case_assignee: Optional[str] = Field(
        default=None, description="测试用例默认负责人邮箱"
    )
    project_id: UUID = Field(..., description="所属项目 ID")
    test_plan: Optional[TestPlanRef] = Field(
        default=None, description="关联的测试计划"
    )
    sub_test_plan: Optional[TestPlanRef] = Field(
        default=None, description="关联的子测试计划"
    )
    test_cases_count: int = Field(default=0, description="测试用例总数")
    passed_count: int = Field(default=0, description="通过数量")
    failed_count: int = Field(default=0, description="失败数量")
    customstatus_count: int = Field(default=0, description="自定义状态数量")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    issues: list[str] = Field(default_factory=list, description="关联的问题列表")
    issue_tracker: Optional[IssueTracker] = Field(
        default=None, description="问题跟踪器配置"
    )
    configurations: list[int] = Field(
        default_factory=list, description="配置 ID 列表"
    )
    configuration_map: Optional[list[ConfigurationMapping]] = Field(
        default=None, description="测试用例-配置映射"
    )
    folder_ids: Optional[list[int]] = Field(default=None, description="文件夹列表")
    include_all: bool = Field(default=False, description="是否含全部用例")
    filter_scope: FilterScope = Field(
        default=FilterScope.GLOBAL, description="过滤作用域"
    )
    filter_test_cases: Optional[TestCaseFilter] = Field(
        default=None, description="过滤条件"
    )
    overall_progress: OverallProgress = Field(
        default_factory=OverallProgress, description="整体进度"
    )
    test_cases: Optional[list[TestRunTestCaseInfo]] = Field(
        default=None, description="内联测试用例（详情接口默认返回）"
    )
    # 企业级扩展字段
    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.SEQUENTIAL, description="执行模式"
    )
    max_concurrency: int = Field(default=5, description="最大并发数")
    trigger_type: TriggerType = Field(
        default=TriggerType.MANUAL, description="触发方式"
    )
    script_jobs: Optional[list[TestRunScriptJobInfo]] = Field(
        default=None, description="脚本作业列表"
    )
    environment_id: Optional[str] = Field(
        default=None, description="执行环境 ID"
    )
    scheduled_by: Optional[UUID] = Field(
        default=None,
        alias="schedule_id",
        description="来源定时调度 ID",
    )
    schedule_name: Optional[str] = Field(
        default=None, description="来源定时调度名称"
    )
    failure_policy: FailurePolicy = Field(
        default=FailurePolicy.CONTINUE, description="失败策略"
    )
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")
    closed_at: Optional[datetime] = Field(default=None, description="关闭时间")
    links: Optional[TestRunLinks] = Field(default=None, description="相关资源链接")

    model_config = ConfigDict(populate_by_name=True)


class TestRunMinifiedInfo(BaseModel):
    """测试运行精简信息（detail?minify=true 响应）"""
    id: UUID = Field(..., description="测试运行 ID")
    identifier: str = Field(..., description="测试运行标识符")
    name: str = Field(..., description="测试运行名称")
    description: Optional[str] = Field(default=None, description="描述")
    run_state: TestRunState = Field(..., description="运行状态")
    active_state: TestRunActiveState = Field(..., description="活跃状态")
    assignee: Optional[str] = Field(default=None, description="负责人")
    project_id: UUID = Field(..., description="所属项目 ID")
    tags: list[str] = Field(default_factory=list, description="标签")
    configurations: list[int] = Field(default_factory=list, description="配置")
    overall_progress: OverallProgress = Field(
        default_factory=OverallProgress, description="整体进度"
    )
    failure_policy: FailurePolicy = Field(
        default=FailurePolicy.CONTINUE, description="失败策略"
    )
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")
    links: Optional[TestRunLinks] = Field(default=None, description="资源链接")


class TestRunListInfo(BaseModel):
    """
    测试运行列表项信息

    对应 BS list 响应中 test_runs[] 元素
    """
    id: UUID = Field(..., description="测试运行 ID")
    identifier: str = Field(..., description="测试运行标识符")
    name: str = Field(..., description="测试运行名称")
    description: Optional[str] = Field(default=None, description="测试运行描述")
    run_state: TestRunState = Field(..., description="运行状态")
    active_state: TestRunActiveState = Field(..., description="活跃状态")
    assignee: Optional[str] = Field(default=None, description="负责人邮箱")
    test_case_assignee: Optional[str] = Field(default=None, description="测试用例默认负责人邮箱")
    project_id: UUID = Field(..., description="所属项目 ID")
    test_cases_count: int = Field(default=0, description="测试用例总数")
    configurations: list[int] = Field(
        default_factory=list, description="配置 ID 列表"
    )
    overall_progress: OverallProgress = Field(
        default_factory=OverallProgress, description="整体进度"
    )
    created_at: datetime = Field(..., description="创建时间")
    closed_at: Optional[datetime] = Field(default=None, description="关闭时间")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    issues: list[str] = Field(default_factory=list, description="关联的问题列表")
    # 企业级扩展字段
    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.SEQUENTIAL, description="执行模式"
    )
    max_concurrency: int = Field(default=5, description="最大并发数")
    failure_policy: FailurePolicy = Field(
        default=FailurePolicy.CONTINUE, description="失败策略"
    )
    trigger_type: TriggerType = Field(
        default=TriggerType.MANUAL, description="触发方式"
    )
    environment_id: Optional[str] = Field(
        default=None, description="执行环境 ID"
    )
    scheduled_by: Optional[UUID] = Field(
        default=None,
        alias="schedule_id",
        description="来源定时调度 ID",
    )
    schedule_name: Optional[str] = Field(
        default=None, description="来源定时调度名称"
    )

    model_config = ConfigDict(populate_by_name=True)


# ============ 调度 Schema ============

class TestRunScheduleInfo(BaseModel):
    """测试运行定时调度信息"""
    id: UUID = Field(..., description="调度 ID")
    project_id: UUID = Field(..., description="所属项目 ID")
    name: str = Field(..., description="调度名称")
    description: Optional[str] = Field(default=None, description="调度描述")
    trigger_type: ScheduleTriggerType = Field(..., description="触发器类型")
    trigger_config: dict = Field(..., description="触发器配置")
    is_enabled: bool = Field(..., description="是否启用")
    next_run_at: Optional[datetime] = Field(default=None, description="下次执行时间")
    last_run_at: Optional[datetime] = Field(default=None, description="上次执行时间")
    test_run_template: Optional[dict] = Field(default=None, description="测试运行创建模板")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class TestRunScheduleCreate(BaseModel):
    """创建测试运行定时调度"""
    name: str = Field(..., min_length=1, max_length=500, description="调度名称")
    description: Optional[str] = Field(default=None, description="调度描述")
    test_run_template: dict = Field(..., description="测试运行创建模板")
    trigger_type: ScheduleTriggerType = Field(..., description="触发器类型")
    trigger_config: dict = Field(..., description="触发器配置")
    is_enabled: bool = Field(default=True, description="是否启用")


class TestRunScheduleUpdate(BaseModel):
    """更新测试运行定时调度"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=500, description="调度名称")
    description: Optional[str] = Field(default=None, description="调度描述")
    test_run_template: Optional[dict] = Field(default=None, description="测试运行创建模板")
    trigger_type: Optional[ScheduleTriggerType] = Field(default=None, description="触发器类型")
    trigger_config: Optional[dict] = Field(default=None, description="触发器配置")
    is_enabled: Optional[bool] = Field(default=None, description="是否启用")


# 兼容旧名（部分调用方可能引用）
TestRunUpdate = TestRunPatchUpdate
TestRunFullUpdate = TestRunFullReplace
TestRunAssigneeUpdate = TestRunAssignRequest
