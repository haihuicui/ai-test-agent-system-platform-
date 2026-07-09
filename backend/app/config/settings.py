"""
应用配置管理

使用 Pydantic Settings 管理应用配置，支持环境变量和 .env 文件
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
# type: ignore  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVU5d1lnPT06ZWNiZjc5OWY=

# 指向项目根目录的 .env（与 start_server_postgres.py 共用）
_ROOT_ENV = Path(__file__).resolve().parent.parent.parent.parent / ".env"


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
    llm_model: str = "deepseek-chat"
    deepseek_api_key: Optional[str] = None

    # 图片解析模型（OpenAI 兼容接口，用于 ChatOpenAI）
    image_parser_api_base: Optional[str] = None
    image_parser_api_key: Optional[str] = None
    image_parser_model: Optional[str] = None

    # 性能测试工作目录配置
    perf_workspace_root: str = "backend/app/agents/perf/workspace"
    perf_mcp_root: str = "backend/mcp/perf"
    perf_yaml_tests: str = "backend/app/agents/perf/yaml-tests"
    perf_skills_root: str = "backend/app/agents/perf/agent_skills"

    # 接口测试工作目录配置
    api_workspace_root: str
    # api_mcp_root: str = "backend/mcp/api"
    api_skills_root: str

    # Web 测试工作目录配置
    web_mcp_workspace_root: str
    web_mcp_root: str
    web_mcp_skills_root: str

    # Web CLI 测试工作目录配置
    web_cli_workspace_root: str = "backend/workspace/web_cli"
    web_cli_skills_root: str = ".claude/skills/web_cli"

    # Web Chrome 测试工作目录配置
    web_chrome_workspace_root: str = "C:/Users/65132/Desktop/workspace/testing/ai-test-management/backend/workspace/web_chrome"
    web_chrome_mcp_root: str = "backend/mcp/web_chrome"
    web_chrome_skills_root: str = "C:/Users/65132/Desktop/workspace/testing/ai-test-management/backend/workspace/web_chrome"

    # 测试用例工作目录配置
    testcase_workspace_root: str = r"D:\project\ai-test-agent\backend\workspace\testcase"
    testcase_skills_root: str = ".claude/skills/testcase"

    # 渗透测试工作目录配置
    security_workspace_root: str = "backend/workspace/security"
    security_skills_root: str = ".claude/skills/security"

    # Android 测试工作目录配置
    android_workspace_root: str = "backend/workspace/android"
    android_skills_root: str = ".claude/skills/android"
    adb_path: Optional[str] = None  # adb 可执行文件绝对路径（如 C:/Users/xxx/AppData/Local/Android/Sdk/platform-tools/adb.exe）
# pragma: no cover  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2WVU5d1lnPT06ZWNiZjc5OWY=


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()

