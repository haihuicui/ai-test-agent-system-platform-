"""
系统枚举值定义

基于 BrowserStack Test Management API 的枚举值定义
参考: https://www.browserstack.com/docs/test-management/api-reference/enums
"""

from enum import Enum


class Priority(str, Enum):
    """
    测试用例优先级
    
    用于标识测试用例的重要程度和执行优先顺序
    """
    LOW = "low"           # 低优先级
    MEDIUM = "medium"     # 中优先级
    HIGH = "high"         # 高优先级
    CRITICAL = "critical" # 关键优先级


class TestCaseState(str, Enum):
    """
    测试用例状态

    基于测试用例生命周期的完整状态定义

    设计阶段状态：
    - new: 新建 - 用例刚创建，尚未评审
    - review_pending: 待评审 - 等待团队评审
    - reviewed: 已评审 - 评审完成，可准备执行

    执行阶段状态：
    - not_run: 未执行 - 尚未执行过
    - passed: 通过 - 执行结果符合预期
    - failed: 失败 - 执行结果与预期不符
    - blocked: 阻塞 - 因依赖问题无法执行
    - skipped: 跳过 - 因特定原因跳过执行
    """
    # 设计阶段
    NEW = "new"                           # 新建
    REVIEW_PENDING = "review_pending"     # 待评审
    REVIEWED = "reviewed"                 # 已评审

    # 执行阶段
    NOT_RUN = "not_run"                   # 未执行
    PASSED = "passed"                     # 通过
    FAILED = "failed"                     # 失败
    BLOCKED = "blocked"                   # 阻塞
    SKIPPED = "skipped"                   # 跳过


class TestCaseType(str, Enum):
    """
    测试用例类型
    
    用于分类测试用例的测试类型
    """
    ACCEPTANCE = "acceptance"       # 验收测试
    ACCESSIBILITY = "accessibility" # 可访问性测试
    COMPATIBILITY = "compatibility" # 兼容性测试
    DESTRUCTIVE = "destructive"     # 破坏性测试
    FUNCTIONAL = "functional"       # 功能测试
    OTHER = "other"                 # 其他类型
    PERFORMANCE = "performance"     # 性能测试
    REGRESSION = "regression"       # 回归测试
    SECURITY = "security"           # 安全测试
    SMOKE_SANITY = "smoke_sanity"   # 冒烟和健全性测试
    USABILITY = "usability"         # 可用性测试
# fmt: off  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2VGpjMlVRPT06NTgzODlkZGE=


class HTTPStatusCode(int, Enum):
    """
    HTTP 状态码
    
    API 响应使用的标准 HTTP 状态码
    参考: https://www.browserstack.com/docs/test-management/api-reference/status-code
    """
    OK = 200                    # 请求成功
    CREATED = 201               # 资源创建成功
    NO_CONTENT = 204            # 无内容（删除成功）
    BAD_REQUEST = 400           # 请求格式错误
    UNAUTHORIZED = 401          # 未授权 - 无效的访问凭证
    FORBIDDEN = 403             # 禁止访问
    NOT_FOUND = 404             # 资源未找到
    UNPROCESSABLE_ENTITY = 422  # 请求格式正确但语义错误
    TOO_MANY_REQUESTS = 429     # 请求过多 - 超出速率限制
    INTERNAL_SERVER_ERROR = 500 # 服务器内部错误


class SortOrder(str, Enum):
    """排序顺序"""
    ASC = "asc"   # 升序
    DESC = "desc" # 降序

# pragma: no cover  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2VGpjMlVRPT06NTgzODlkZGE=

class IssueType(str, Enum):
    """
    关联问题类型

    用于标识测试用例关联的外部问题类型
    """
    JIRA = "jira"           # Jira 问题
    GITHUB = "github"       # GitHub Issue
    GITLAB = "gitlab"       # GitLab Issue
    AZURE = "azure"         # Azure DevOps
    OTHER = "other"         # 其他类型


class TestCaseTemplate(str, Enum):
    """
    测试用例模板类型

    用于区分普通测试用例和 BDD 测试用例
    """
    TEST_CASE = "test_case"       # 普通测试用例
    TEST_CASE_BDD = "test_case_bdd"  # BDD 测试用例


class AutomationStatus(str, Enum):
    """
    自动化状态

    用于标识测试用例的自动化程度
    """
    NOT_AUTOMATED = "not_automated"   # 未自动化
    AUTOMATED = "automated"           # 已自动化
    IN_PROGRESS = "in_progress"       # 自动化进行中
    OBSOLETE = "obsolete"             # 自动化已过时


class BulkEditOperation(str, Enum):
    """
    批量编辑操作符

    用于批量编辑测试用例时指定字段的处理方式
    """
    IGNORE = "ignore"     # 保持现有值不变
    REPLACE = "replace"   # 用提供的值覆盖当前值
    ADD = "add"           # 将提供的值追加到现有列表（多值字段）
    REMOVE = "remove"     # 从现有列表中移除指定的值（多值字段）


class ExportStatus(str, Enum):
    """
    导出任务状态

    用于标识 BDD 测试用例导出任务的状态
    """
    PENDING = "pending"       # 等待处理
    PROCESSING = "processing" # 处理中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败


class ExportFormat(str, Enum):
    """
    测试用例导出格式

    用于标识测试用例导出的目标文件格式
    """
    EXCEL = "excel"       # Microsoft Excel (.xlsx)
    JSON = "json"         # JSON (.json)
    CSV = "csv"           # CSV (.csv)
    MARKDOWN = "markdown" # Markdown (.md)
    BDD = "bdd"           # BDD Gherkin (.feature)


class TestRunState(str, Enum):
    """
    测试运行状态

    用于标识测试运行的执行状态
    参考: https://www.browserstack.com/docs/test-management/api-reference/test-runs
    """
    NEW_RUN = "new_run"                  # 新建运行
    IN_PROGRESS = "in_progress"          # 进行中
    UNDER_REVIEW = "under_review"        # 审核中
    REJECTED = "rejected"                # 已拒绝
    DONE = "done"                        # 已完成
    DONE_WITH_FAILURES = "done_with_failures"  # 已完成但存在失败
    CLOSED = "closed"                    # 已关闭


class TestRunActiveState(str, Enum):
    """
    测试运行活跃状态

    用于标识测试运行是否处于活跃状态
    """
    ACTIVE = "active"   # 活跃状态
    CLOSED = "closed"   # 已关闭


class TestResultStatus(str, Enum):
    """
    测试结果状态

    用于标识单个测试用例在测试运行中的执行结果
    参考: https://www.browserstack.com/docs/test-management/api-reference/test-results

    BrowserStack overall_progress 字段集合：
    - untested: 未执行（新建用例的默认状态）
    - passed: 通过
    - retest: 需重新测试
    - failed: 失败
    - blocked: 被阻塞
    - skipped: 跳过
    - in_progress: 测试中

    NOT_EXECUTED 保留是为了向后兼容老数据。新代码应使用 UNTESTED。
    """
    UNTESTED = "untested"           # 未执行（BS 标准）
    PASSED = "passed"               # 通过
    RETEST = "retest"               # 重测
    FAILED = "failed"               # 失败
    BLOCKED = "blocked"             # 阻塞
    SKIPPED = "skipped"             # 跳过
    IN_PROGRESS = "in_progress"     # 测试中
    NOT_EXECUTED = "not_executed"   # 历史兼容（等价 UNTESTED，不要在新代码里使用）


class FilterScope(str, Enum):
    """
    测试用例过滤作用域

    与 BrowserStack TestRun 创建/更新接口的 filter_scope 字段对齐
    """
    GLOBAL = "global"                   # 项目全局过滤
    WITHIN_FOLDERS = "within_folders"   # 仅在指定文件夹内过滤


class IssueTrackerName(str, Enum):
    """
    问题跟踪器名称

    BrowserStack TestRun.issue_tracker.name 支持的枚举
    """
    JIRA = "jira"
    AZURE = "azure"
    ASANA = "asana"


class TestPlanStatus(str, Enum):
    """
    测试计划状态

    用于标识测试计划的当前状态
    参考: https://www.browserstack.com/docs/test-management/api-reference/test-plans
    """
    DRAFT = "draft"           # 草稿
    ACTIVE = "active"         # 活跃
    COMPLETED = "completed"   # 已完成
    ARCHIVED = "archived"     # 已归档
# type: ignore  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2VGpjMlVRPT06NTgzODlkZGE=


class TestPlanActiveState(str, Enum):
    """
    测试计划活跃状态

    用于标识测试计划是否处于活跃状态
    """
    ACTIVE = "active"   # 活跃状态
    CLOSED = "closed"   # 已关闭


class ScriptType(str, Enum):
    """
    脚本类型

    用于标识测试运行中包含的脚本来源类型
    """
    API_TEST = "api_test"       # API 测试脚本
    SCENARIO = "scenario"       # 场景测试脚本
    WEB_TEST = "web_test"       # Web 测试脚本
    TEST_CASE = "test_case"     # 测试用例（兼容旧模式）


class ExecutionMode(str, Enum):
    """
    执行模式

    用于配置脚本作业的执行方式
    """
    SEQUENTIAL = "sequential"   # 顺序执行
    PARALLEL = "parallel"       # 并行执行


class TriggerType(str, Enum):
    """
    触发方式

    用于标识测试运行的触发来源
    """
    MANUAL = "manual"       # 手动触发
    SCHEDULED = "scheduled" # 定时调度触发
    API = "api"             # API 调用触发


class FailurePolicy(str, Enum):
    """
    测试运行失败策略

    用于配置脚本作业失败后的后续行为
    """
    CONTINUE = "continue"           # 继续执行后续脚本
    STOP_RUN = "stop_run"           # 失败即停止整个运行
    STOP_JOB = "stop_job"           # 仅当前脚本失败，后续继续执行
    MARK_BLOCKED = "mark_blocked"   # 后续脚本标记为阻塞


class ScheduleTriggerType(str, Enum):
    """
    调度触发器类型

    用于配置定时调度的触发规则
    """
    CRON = "cron"       # Cron 表达式
    INTERVAL = "interval"   # 间隔触发
    DATE = "date"       # 一次性日期触发

# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2VGpjMlVRPT06NTgzODlkZGE=

class JobStatus(str, Enum):
    """
    脚本作业状态

    用于标识 TestRunScriptJob 的执行状态
    """
    PENDING = "pending"         # 等待执行
    RUNNING = "running"         # 执行中
    COMPLETED = "completed"     # 执行完成
    FAILED = "failed"           # 执行失败
    SKIPPED = "skipped"         # 已跳过
    BLOCKED = "blocked"         # 已阻塞
    CANCELLED = "cancelled"     # 已取消
