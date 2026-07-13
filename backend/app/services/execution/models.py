"""
执行引擎内部数据模型

定义 runner 和 executor 之间传递的结果结构，与 ORM 模型解耦。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# pragma: no cover  MC8yOmFIVnBZMlhsdEpUbXRiZm92b2s2ZEVRME9BPT06NmVkNmVmNDQ=

@dataclass
class RunnerResult:
    """单次脚本运行的原始结果"""

    success: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    report_path: Optional[str] = None
    duration_ms: int = 0
    error_message: Optional[str] = None
    result_summary: Dict[str, Any] = field(default_factory=dict)

# pragma: no cover  MS8yOmFIVnBZMlhsdEpUbXRiZm92b2s2ZEVRME9BPT06NmVkNmVmNDQ=

@dataclass
class ExecutionResult:
    """作业级执行结果（写入 TestRunScriptJob）"""

    success: bool
    status: str  # JobStatus 枚举值
    failure_category: Optional[str] = None  # assertion / timeout / environment / infra
    passed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    duration_ms: int = 0
    error_message: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    report_path: Optional[str] = None
    result_summary: Dict[str, Any] = field(default_factory=dict)
    detail_run_id: Optional[str] = None  # API test run ID / scenario run ID
    has_missing_counts: bool = False  # 计数是否来自 NULL/缺失数据
