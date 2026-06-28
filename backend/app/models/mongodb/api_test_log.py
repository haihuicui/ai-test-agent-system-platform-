"""
API 测试详细日志模型

MongoDB 文档模型，用于存储完整的请求/响应数据
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID
# fmt: off  MC8zOmFIVnBZMlhsdEpUbXRiZm92b2s2Ym5Fd2JnPT06ZWQ0NWI5ZTA=

from pydantic import BaseModel, Field


class APITestDetailLog(BaseModel):
    """
    API 测试详细日志

    存储完整的请求/响应数据、断言结果等详细信息
    """
    log_id: str = Field(..., description="日志 ID")
    test_result_id: UUID = Field(..., description="测试结果 ID")
    test_run_id: UUID = Field(..., description="测试运行 ID")
    api_test_id: UUID = Field(..., description="API 测试 ID")

    # 场景信息
    scenario_name: str = Field(..., description="场景名称")
    endpoint: str = Field(..., description="API 端点")
    method: str = Field(..., description="HTTP 方法")
# pragma: no cover  MS8zOmFIVnBZMlhsdEpUbXRiZm92b2s2Ym5Fd2JnPT06ZWQ0NWI5ZTA=

    # 完整请求
    request: dict[str, Any] = Field(default_factory=dict, description="完整请求数据")
    # 完整响应
    response: dict[str, Any] = Field(default_factory=dict, description="完整响应数据")

    # 断言结果
    assertions: list[dict[str, Any]] = Field(default_factory=list, description="断言结果列表")

    # 时间线
    started_at: datetime = Field(default_factory=datetime.utcnow, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    duration_ms: Optional[int] = Field(None, description="执行时长(毫秒)")

    # 错误详情
    error: Optional[dict[str, Any]] = Field(None, description="错误详情")

    # 重试历史
    retry_history: list[dict[str, Any]] = Field(default_factory=list, description="重试历史")

    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")

    class Config:
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
        }

    @classmethod
    def collection_name(cls) -> str:
        """获取 MongoDB 集合名称"""
        return "api_test_logs"

    def to_document(self) -> dict:
        """转换为 MongoDB 文档"""
        return self.model_dump(mode='json')
# pylint: disable  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b2s2Ym5Fd2JnPT06ZWQ0NWI5ZTA=
