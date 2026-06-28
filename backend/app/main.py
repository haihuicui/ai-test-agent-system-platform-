"""
测试管理系统主入口

FastAPI 应用程序入口点
"""

from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import api_router
from app.config.settings import settings
from app.config.database import engine, MongoDB, async_session_factory
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.error_handler import setup_exception_handlers
from app.models.base import Base
from app.models.user import User
from app.services.scheduler_service import get_scheduler_service

# Import all models DIRECTLY from their modules (not through __init__.py)
# This ensures correct initialization order for SQLAlchemy foreign key resolution
# IMPORTANT: Models referenced by foreign keys must be imported FIRST

from app.models.project import Project
from app.models.folder import Folder
from app.models.team import Team
from app.models.test_case import TestCase, TestStep, Tag, TestCaseTag
from app.models.test_run import TestRun, TestRunTestCase
from app.models.test_result import TestResult, TestStepResult
from app.models.attachment import Attachment
from app.models.configuration import Configuration
from app.models.test_plan import TestPlan
from app.models.api_test import APITest, APITestRun, APITestResult
from app.models.api_endpoint import APIEndpoint

# Import scenario models LAST (they depend on projects, folders, users, api_endpoints)
from app.models.test_scenario import (
    TestScenario,
    ScenarioStep,
    StepDataMapping,
    ScenarioVariable,
    ScenarioRun,
    ScenarioStepResult,
)
from app.models.pentest import Pentest, PentestReport, PentestVulnerability
from app.models.web_test import WebTest, WebTestRun, WebTestResult
from app.models.web_function import WebFunction, WebSubFunction
from app.models.android_test import AndroidTest, AndroidTestRun, AndroidTestResult

# deepagents 消息 reducer 的 None-state 崩溃修复见 deepagents 源文件
# _messages_reducer.py（无法用 monkeypatch，因 graph 在导入时即按值绑定 reducer）。

async def ensure_default_user():
    """
    确保默认测试用户存在

    在应用启动时检查并创建默认用户（开发环境使用）
    """
    async with async_session_factory() as session:
        # 检查默认用户是否存在
        user_id = UUID(settings.default_user_id)
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            # 创建默认用户
            user = User(
                id=user_id,
                email=settings.default_user_email,
                username=settings.default_user_name,
                password_hash="not_used_for_dev",  # 开发环境不需要真实密码
                is_active=True,
            )
            session.add(user)
            await session.commit()
            print(f"[OK] Created default test user: {settings.default_user_email}")
        else:
            print(f"[OK] Default test user exists: {settings.default_user_email}")
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TUc1RmJRPT06MGM2MDM2MGM=


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时初始化数据库连接，关闭时清理资源
    """
    # 启动时
    # 连接 MongoDB
    # await MongoDB.connect()

    # 创建数据库表（开发环境）
    if settings.debug:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # 确保默认用户存在
    await ensure_default_user()

    # 启动定时调度器
    scheduler = get_scheduler_service()
    scheduler.start()
    await scheduler.load_schedules_from_db()
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TUc1RmJRPT06MGM2MDM2MGM=

    yield

    # 关闭时
    # 断开 MongoDB 连接
    # await MongoDB.disconnect()

    # 关闭定时调度器
    scheduler.shutdown()

    # 关闭 PostgreSQL 连接池
    await engine.dispose()


def create_app() -> FastAPI:
    """
    创建 FastAPI 应用实例
    
    Returns:
        FastAPI: 应用实例
    """
    app = FastAPI(
        title=settings.app_name,
        description="""
# 测试管理系统 API

专业的软件测试管理系统，提供完整的测试用例管理功能。

## 功能特性

- **项目管理**: 创建、查看、删除项目
- **文件夹管理**: 层级文件夹结构，支持移动操作
- **测试用例管理**: 完整的测试用例 CRUD，支持步骤、标签、版本管理
- **分页支持**: 所有列表接口支持分页
- **速率限制**: 每分钟最多 300 个请求

## API 版本

当前版本: v2

## 认证

所有 API 需要认证（待实现）
        """,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # 添加 CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 添加速率限制中间件
    app.add_middleware(RateLimiterMiddleware)
# pylint: disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2TUc1RmJRPT06MGM2MDM2MGM=
    
    # 设置异常处理器
    setup_exception_handlers(app)
    
    # 注册 API 路由
    app.include_router(api_router)
    
    # 健康检查端点
    @app.get("/health", tags=["系统"])
    async def health_check():
        """健康检查"""
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
        }
    
    # 根路径
    @app.get("/", tags=["系统"])
    async def root():
        """API 根路径"""
        return {
            "message": "欢迎使用测试管理系统 API",
            "docs": "/docs",
            "version": settings.app_version,
        }
    
    return app


# 创建应用实例
app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.app_port)