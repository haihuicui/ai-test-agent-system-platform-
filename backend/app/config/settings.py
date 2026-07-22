"""
应用配置管理

使用 Pydantic Settings 管理应用配置，支持环境变量和 .env 文件
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVU5d1lnPT06ZWNiZjc5OWY=

# 项目根目录（本文件位于 backend/app/config/，向上 4 级），与进程启动目录无关
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# 指向项目根目录的 .env（与 start_server_postgres.py 共用）
_ROOT_ENV = PROJECT_ROOT / ".env"

# 以项目根目录为基准的路径配置字段：
# 这些字段支持相对路径（相对项目根目录）或绝对路径，加载后统一解析为绝对路径
_PATH_FIELDS = (
    "perf_workspace_root", "perf_mcp_root", "perf_yaml_tests", "perf_skills_root",
    "api_workspace_root", "api_skills_root",
    "web_mcp_workspace_root", "web_mcp_root", "web_mcp_skills_root",
    "web_mcp_storage_state",
    "web_cli_workspace_root", "web_cli_skills_root",
    "web_chrome_workspace_root", "web_chrome_mcp_root", "web_chrome_skills_root",
    "testcase_workspace_root", "testcase_skills_root",
    "security_workspace_root", "security_skills_root",
    "android_workspace_root", "android_skills_root",
)


class Settings(BaseSettings):
    """应用配置类"""

    model_config = SettingsConfigDict(
        env_file=str(_ROOT_ENV),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # 应用基础配置
    app_name: str = "测试管理系统"
    app_version: str = "1.0.0"
    app_port: int = 8001
    debug: bool = False
    api_prefix: str = "/api/v2"
    
    # PostgreSQL 数据库配置
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "ai_test_management"
    
    @property
    def postgres_url(self) -> str:
        """获取 PostgreSQL 连接 URL"""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    @property
    def postgres_sync_url(self) -> str:
        """获取 PostgreSQL 同步连接 URL（用于 Alembic）"""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
    
    # MongoDB 配置
    mongodb_host: str = "121.40.159.60"
    mongodb_port: int = 27017
    mongodb_user: Optional[str] = None
    mongodb_password: Optional[str] = None
    mongodb_db: str = "ai_test_management"
    
    @property
    def mongodb_url(self) -> str:
        """获取 MongoDB 连接 URL"""
        if self.mongodb_user and self.mongodb_password:
            return (
                f"mongodb://{self.mongodb_user}:{self.mongodb_password}"
                f"@{self.mongodb_host}:{self.mongodb_port}"
            )
        return f"mongodb://{self.mongodb_host}:{self.mongodb_port}"
    
    # 速率限制配置
    rate_limit_requests: int = 300  # 每分钟最大请求数
    rate_limit_window: int = 60  # 时间窗口（秒）
    
    # 分页配置
    pagination_default_size: int = 30
    pagination_max_size: int = 300

    @property
    def default_page_size(self) -> int:
        """获取默认分页大小（别名）"""
        return self.pagination_default_size

    @property
    def max_page_size(self) -> int:
        """获取最大分页大小（别名）"""
        return self.pagination_max_size
    
    # CORS 配置
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVU5d1lnPT06ZWNiZjc5OWY=

    # JWT 配置（用于认证）
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # 敏感数据加密密钥（用于加密 ProjectEnvironment 中的 token/api_key 等）
    # 部署时必须设置为 32 字节以上字符串，建议使用 Fernet.generate_key() 生成
    testagent_secret_key: Optional[str] = None

    # 默认测试用户配置（开发环境使用）
    default_user_id: str = "00000000-0000-0000-0000-000000000001"
    default_user_email: str = "admin@test.com"
    default_user_name: str = "管理员"
# pylint: disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVU5d1lnPT06ZWNiZjc5OWY=

    # MinIO 对象存储配置
    minio_endpoint: str = "114.55.110.60:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "test-management"
    minio_secure: bool = False  # 是否使用 HTTPS
    minio_region: Optional[str] = None

    # 附件配置
    attachment_max_size: int = 50 * 1024 * 1024  # 50 MB
    attachment_allowed_types: list[str] = [
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "application/pdf", "application/zip", "application/x-rar-compressed",
        "text/plain", "text/csv",
        "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]

    # PDF 解析配置
    enable_pdf_multimodal: bool = False  # 是否启用 PDF 多模态图片解析（需要配置 DOUBAO_API_KEY）

    # 大模型配置
    # DeepSeek 文本模型（用于 ChatDeepSeek）
    llm_model: str = "deepseek-v4-flash"
    deepseek_api_key: Optional[str] = None

    # 图片解析模型（OpenAI 兼容接口，用于 ChatOpenAI）
    image_parser_api_base: Optional[str] = None
    image_parser_api_key: Optional[str] = None
    image_parser_model: Optional[str] = None

    # 性能测试工作目录配置
    # 路径字段说明：相对路径基于项目根目录（PROJECT_ROOT）解析，绝对路径原样使用，
    # 加载后统一转为绝对路径（见 _resolve_project_paths）
    perf_workspace_root: str = "backend/workspace/perf"
    perf_mcp_root: str = "backend/mcp/perf"
    perf_yaml_tests: str = "backend/app/agents/perf/yaml-tests"
    perf_skills_root: str = ".claude/skills"

    # 接口测试工作目录配置
    api_workspace_root: str = "backend/workspace/api"
    # api_mcp_root: str = "backend/mcp/api"
    api_skills_root: str = ".claude/skills"

    # 接口测试 trace 配置（同时被场景测试日志格式化复用）
    api_test_sensitive_headers: list[str] = [
        "authorization",
        "cookie",
        "x-api-key",
        "x-auth-token",
    ]
    api_test_sensitive_body_fields: list[str] = [
        "password",
        "token",
        "secret",
        "apikey",
        "api_key",
        "accesstoken",
        "refreshtoken",
        "auth_token",
    ]
    api_test_body_truncate_threshold: int = 50_000
    api_test_body_preview_length: int = 2_000

    # Web 测试工作目录配置
    web_mcp_workspace_root: str = "backend/workspace/web_mcp"
    web_mcp_root: str = "backend/workspace/web_mcp"
    web_mcp_skills_root: str = ".claude/skills"
    # Web MCP 是否使用无头浏览器（false=有头，true=无头）
    web_mcp_headless: bool = False
    # 全局登录态文件（Playwright storageState JSON）路径，相对项目根或绝对路径。
    # 配置后 ensure_playwright_mcp_project 生成的 playwright.config 会自动注入 storageState，
    # 使所有测试复用已登录会话，避免每条用例都走 UI 登录。默认 None（不启用）。
    web_mcp_storage_state: Optional[str] = None

    # Web 测试执行预算（超时/并发/重试，统一在此调整）。
    # 层级关系：单用例超时(web_exec_test_timeout_ms) < 整脚本执行超时(web_exec_timeout_seconds)。
    web_exec_test_timeout_ms: int = 60_000   # 单个测试用例超时（写入 playwright.config 的 timeout）
    web_exec_timeout_seconds: int = 300      # execute_web_script 整脚本 subprocess 总超时
    web_exec_static_check_timeout: int = 120  # 执行前静态校验(--list)超时
    web_exec_retries: int = 1                # playwright 自动重试次数；healer 会针对性修复重跑，此处不宜过高以免拉长失败反馈
    web_exec_max_concurrency: int = 2        # 全局并发执行上限（不同子功能间），防报告/资源互相覆盖

    # Web CLI 测试工作目录配置
    web_cli_workspace_root: str = "backend/workspace/web_cli"
    web_cli_skills_root: str = ".claude/skills"

    # Web Chrome 测试工作目录配置
    web_chrome_workspace_root: str = "backend/workspace/web_chrome"
    web_chrome_mcp_root: str = "backend/mcp/web_chrome"
    web_chrome_skills_root: str = ".claude/skills"

    # 测试用例工作目录配置
    testcase_workspace_root: str = "backend/workspace/testcase"
    testcase_skills_root: str = ".claude/skills/testcase"

    # 渗透测试工作目录配置
    security_workspace_root: str = "backend/workspace/security"
    security_skills_root: str = ".claude/skills/security"

    # Android 测试工作目录配置
    android_workspace_root: str = "backend/workspace/android"
    android_skills_root: str = ".claude/skills/android"
    adb_path: Optional[str] = None  # adb 可执行文件绝对路径（如 C:/Users/xxx/AppData/Local/Android/Sdk/platform-tools/adb.exe）
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVU5d1lnPT06ZWNiZjc5OWY=

    @model_validator(mode="after")
    def _resolve_project_paths(self) -> "Settings":
        """将 _PATH_FIELDS 中的路径统一解析为绝对路径。

        - 相对路径：基于项目根目录 PROJECT_ROOT 解析，与进程启动目录（CWD）无关；
        - 绝对路径：原样保留（.env 中可覆盖到项目外任意位置）。
        """
        for field in _PATH_FIELDS:
            value = getattr(self, field)
            if not value:
                continue
            path = Path(value)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            setattr(self, field, str(path.resolve()))
        return self


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()

