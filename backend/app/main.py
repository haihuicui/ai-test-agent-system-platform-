"""
测试管理系统主入口

FastAPI 应用程序入口点
"""

from contextlib import asynccontextmanager
from uuid import UUID
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import api_router
from app.config.settings import settings
from app.config.database import engine, MongoDB, async_session_factory, run_migrations
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.error_handler import setup_exception_handlers
from app.models.user import User
from app.services.scheduler_service import get_scheduler_service

logger = logging.getLogger(__name__)

# Import all models DIRECTLY from their modules (not through __init__.py)
# This ensures correct initialization order for SQLAlchemy foreign key resolution
# IMPORTANT: Models referenced by foreign keys must be imported FIRST

from app.models.project import Project
from app.models.folder import Folder
from app.models.team import Team
from app.models.test_case import TestCase, TestStep, Tag, TestCaseTag
from app.models.test_run import TestRun, TestRunTestCase, TestRunScriptJob
from app.models.test_result import TestResult, TestStepResult
from app.models.attachment import Attachment
from app.schemas.enums import TestRunState, JobStatus
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


async def cleanup_stale_execution_state():
    """
    启动自洁：重置上次运行遗留的 IN_PROGRESS 测试运行和 RUNNING 脚本作业。

    后端进程异常退出或重启后，后台执行协程会消失，但数据库里的状态可能仍停留在
    '进行中'。这会导致用户再次点击执行时，后端直接返回'已在执行中'而什么都不做。
    启动时把这些脏状态统一标记为失败/拒绝，避免重启后卡死。
    """
    try:
        from app.repositories.test_run_repo import (
            TestRunRepository,
            TestRunScriptJobRepository,
        )
        from datetime import datetime, timezone

        async with async_session_factory() as session:
            run_repo = TestRunRepository(session)
            job_repo = TestRunScriptJobRepository(session)

            # 1. 找出所有遗留的 IN_PROGRESS 测试运行
            result = await session.execute(
                select(TestRun).where(TestRun.run_state == TestRunState.IN_PROGRESS)
            )
            stale_runs = list(result.scalars().all())
            if not stale_runs:
                logger.info("[Startup Cleanup] 未发现遗留的进行中测试运行")
                return

            logger.info(
                "[Startup Cleanup] 发现 %s 个上次遗留的进行中测试运行，正在重置状态...",
                len(stale_runs),
            )

            reset_count = 0
            for test_run in stale_runs:
                # 重置该运行下所有 RUNNING 的脚本作业
                jobs_result = await session.execute(
                    select(TestRunScriptJob).where(
                        TestRunScriptJob.test_run_id == test_run.id,
                        TestRunScriptJob.status == JobStatus.RUNNING,
                    )
                )
                stale_jobs = list(jobs_result.scalars().all())
                now = datetime.now(timezone.utc)
                for job in stale_jobs:
                    await job_repo.update_status(
                        job.id,
                        JobStatus.FAILED,
                        completed_at=now,
                        error_message="后端重启，遗留的执行状态已重置",
                    )

                # 测试运行本身标记为 rejected
                test_run.run_state = TestRunState.REJECTED
                await run_repo.update(test_run)

                # 基于 script_jobs 重新统计计数
                await run_repo.update_counts_from_jobs(test_run.id)
                reset_count += 1

            await session.commit()
            logger.info(
                "[Startup Cleanup] 已重置 %s 个测试运行及其脚本作业状态",
                reset_count,
            )
    except Exception as e:
        # 自洁失败不应阻塞应用启动
        logger.exception("[Startup Cleanup] 重置遗留执行状态时出错: %s", e)
# type: ignore  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2TUc1RmJRPT06MGM2MDM2MGM=


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时初始化数据库连接，关闭时清理资源
    """
    # 启动时
    # 1. 自动应用 Alembic 迁移（生产/开发统一走迁移，保证 schema 与模型一致）
    await run_migrations()
    logger.info("[Startup] Alembic 迁移已应用到 head")

    # 2. 连接 MongoDB
    await MongoDB.connect()

    # 3. 确保默认用户存在
    await ensure_default_user()

    # 4. 启动自洁：重置上次遗留的进行中状态
    await cleanup_stale_execution_state()

    # 5. 启动定时调度器
    scheduler = get_scheduler_service()
    scheduler.start()
    await scheduler.load_schedules_from_db()
# pragma: no cover  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2TUc1RmJRPT06MGM2MDM2MGM=

    yield

    # 关闭时
    # 断开 MongoDB 连接
    await MongoDB.disconnect()

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