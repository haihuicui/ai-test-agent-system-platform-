"""
统一测试执行引擎（兼容层）

本模块保留原有的公共 API（TestExecutionService、ExecutionResult、ScriptExecutor），
内部实现已迁移到 app.services.execution 包中的 ScriptExecutionEngine。

如需扩展新的脚本执行器，请在 app.services.execution.executors 中注册。
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.schemas.enums import JobStatus
from app.services.execution.engine import ScriptExecutionEngine

logger = logging.getLogger(__name__)
# pylint: disable  MC8zOmFIVnBZMlhsdEpUbXRiZm92b2s2WXpKNFpnPT06ZGYzZTIxMDI=


@dataclass
class ExecutionResult:
    """单个脚本执行结果（保留以兼容既有导入）"""

    success: bool
    status: JobStatus
    duration_ms: int = 0
    error_message: Optional[str] = None
    report_path: Optional[str] = None
    result_summary: Dict[str, Any] = field(default_factory=dict)
    detail_run_id: Optional[str] = None

# pylint: disable  MS8zOmFIVnBZMlhsdEpUbXRiZm92b2s2WXpKNFpnPT06ZGYzZTIxMDI=

class ScriptExecutor(ABC):
    """脚本执行器抽象基类（保留以兼容既有导入）"""

    @abstractmethod
    async def execute(
        self,
        script_id: UUID,
        config: Dict[str, Any],
    ) -> ExecutionResult:
        """执行单个脚本"""
        ...

    @abstractmethod
    async def cancel(self) -> None:
        """取消当前执行"""
        ...


class TestExecutionService:
    """统一测试执行服务（委托给 ScriptExecutionEngine）"""

    def __init__(self, mongodb=None):
        self._engine = ScriptExecutionEngine(mongodb=mongodb)
# type: ignore  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b2s2WXpKNFpnPT06ZGYzZTIxMDI=

    async def execute_run(
        self,
        test_run_id: UUID,
        trigger: str = "manual",
    ) -> Dict[str, Any]:
        """
        执行整个测试运行。

        委托给 ScriptExecutionEngine.execute_run，保持 API 兼容。
        """
        return await self._engine.execute_run(test_run_id, trigger=trigger)

    async def execute_jobs(
        self,
        test_run_id: UUID,
        job_ids: List[UUID],
    ) -> Dict[str, Any]:
        """仅执行指定的脚本作业（重试场景），随后基于全部作业重新定案。

        委托给 ScriptExecutionEngine.execute_jobs。
        """
        return await self._engine.execute_jobs(test_run_id, job_ids)

    async def cancel_run(self, test_run_id: UUID) -> None:
        """取消测试运行"""
        await self._engine.cancel_run(test_run_id)
