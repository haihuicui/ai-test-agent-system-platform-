"""
场景测试相关的 Pydantic 模型
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

# pragma: no cover  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkhCa2FBPT06N2ZjYWUyNTI=

# ==================== 场景模型 ====================

class ScenarioBase(BaseModel):
    """场景基础模型"""
    name: str = Field(..., min_length=1, max_length=500, description="场景名称")
    description: Optional[str] = Field(None, description="场景描述")
    folder_id: Optional[UUID] = Field(None, description="所属文件夹 ID")
    global_variables: Dict[str, Any] = Field(default_factory=dict, description="全局变量")
    retry_count: int = Field(0, ge=0, description="重试次数")
    timeout_seconds: int = Field(300, ge=1, description="超时时间（秒）")
    parallel_execution: bool = Field(False, description="是否并行执行")


class ScenarioCreate(ScenarioBase):
    """创建场景请求"""
    pass


class ScenarioUpdate(BaseModel):
    """更新场景请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    global_variables: Optional[Dict[str, Any]] = None
    retry_count: Optional[int] = Field(None, ge=0)
    timeout_seconds: Optional[int] = Field(None, ge=1)
    status: Optional[str] = Field(None, pattern="^(draft|active|archived)$")


class ScenarioResponse(ScenarioBase):
    """场景响应"""
    id: UUID
    project_id: UUID
    identifier: str
    status: str
    total_steps: int
    last_run_status: Optional[str]
    last_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID]

    class Config:
        from_attributes = True


class ScenarioListResponse(BaseModel):
    """场景列表响应"""
    total: int
    items: List[ScenarioResponse]


# ==================== 步骤模型 ====================

class DataMappingCreate(BaseModel):
    """创建数据映射请求"""
    source_type: str = Field(..., pattern="^(previous_response|variable|static)$")
    source_step_id: Optional[UUID] = None
    source_path: Optional[str] = None
    target_path: str = Field(..., description="目标路径，如 headers.Authorization")
    transform_expression: Optional[str] = None
    description: Optional[str] = None


class DataMappingResponse(BaseModel):
    """数据映射响应"""
    id: UUID
    source_type: str
    source_step_id: Optional[UUID]
    source_path: Optional[str]
    target_path: str
    transform_expression: Optional[str]
    description: Optional[str]

    class Config:
        from_attributes = True
# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkhCa2FBPT06N2ZjYWUyNTI=


class StepExtractor(BaseModel):
    """数据提取器"""
    name: str = Field(..., description="变量名")
    path: str = Field(..., description="JSONPath 路径")
    type: str = Field("jsonpath", description="提取器类型")


class StepAssertion(BaseModel):
    """断言"""
    type: str = Field(..., pattern="^(status|jsonpath|header)$")
    expected: Any
    path: Optional[str] = None
    operator: str = Field("eq", description="比较运算符")


class ScenarioStepCreate(BaseModel):
    """创建步骤请求"""
    endpoint_id: Optional[UUID] = None
    name: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    step_order: Optional[int] = None
    request_override: Dict[str, Any] = Field(default_factory=dict)
    headers_override: Dict[str, Any] = Field(default_factory=dict)
    extractors: List[StepExtractor] = Field(default_factory=list)
    assertions: List[StepAssertion] = Field(default_factory=list)
    condition_expression: Optional[str] = None
    continue_on_failure: bool = False
    delay_ms: int = Field(0, ge=0)
    retry_count: int = Field(0, ge=0)


class ScenarioStepUpdate(BaseModel):
    """更新步骤请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    request_override: Optional[Dict[str, Any]] = None
    headers_override: Optional[Dict[str, Any]] = None
    extractors: Optional[List[StepExtractor]] = None
    assertions: Optional[List[StepAssertion]] = None
    condition_expression: Optional[str] = None
    continue_on_failure: Optional[bool] = None
    delay_ms: Optional[int] = Field(None, ge=0)
    retry_count: Optional[int] = Field(None, ge=0)


class ScenarioStepResponse(ScenarioStepCreate):
    """步骤响应"""
    id: UUID
    scenario_id: UUID
    endpoint_id: Optional[UUID]
    step_order: int
    data_mappings: List[DataMappingResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== 执行模型 ====================

class ScenarioExecuteRequest(BaseModel):
    """执行场景请求"""
    variables: Dict[str, Any] = Field(default_factory=dict, description="运行时变量")
    base_url: str = Field("", description="API 基础 URL")
    env_id: Optional[UUID] = Field(None, description="执行环境 ID")
    async_mode: bool = Field(False, description="是否异步执行")
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkhCa2FBPT06N2ZjYWUyNTI=


class ScenarioExecuteResponse(BaseModel):
    """执行场景响应"""
    run_id: UUID
    status: str
    message: str
    result: Optional["ScenarioRunResponse"] = None


class ScenarioRunResponse(BaseModel):
    """执行记录响应"""
    id: UUID
    scenario_id: UUID
    identifier: str
    status: str
    total_steps: int
    passed_steps: int
    failed_steps: int
    skipped_steps: int
    duration_ms: Optional[int]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

# fmt: off  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VkhCa2FBPT06N2ZjYWUyNTI=

class ScenarioRunListResponse(BaseModel):
    """执行记录列表响应"""
    total: int
    items: List[ScenarioRunResponse]


class ScenarioStepResultResponse(BaseModel):
    """步骤执行结果响应"""
    id: UUID
    run_id: UUID
    step_id: UUID
    endpoint_id: Optional[UUID]
    step_order: int
    step_name: Optional[str]
    full_url: Optional[str]
    status: str
    duration_ms: Optional[int]
    error_message: Optional[str]
    error_stack: Optional[str]
    created_at: datetime
    request_data: Optional[Dict[str, Any]]
    response_data: Optional[Dict[str, Any]]
    extracted_data: Dict[str, Any]
    assertion_results: List[Dict[str, Any]]

    class Config:
        from_attributes = True


# 更新前向引用
ScenarioExecuteResponse.model_rebuild()
