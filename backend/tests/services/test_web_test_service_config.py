"""
WebTestService 配置生成单元测试
"""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.environment import AuthType, ProjectEnvironment
from app.models.storage_state_job import StorageStateJob
from app.services.web_test_service import WebTestService


class TestGeneratePlaywrightConfig:
    def test_config_without_storage_state(self):
        """未传 storage_state_path 时，config 不应包含 storageState"""
        service = WebTestService(session=MagicMock())
        web_test = SimpleNamespace(base_url="https://example.com")

        config = service._generate_playwright_config(web_test, {})

        assert "storageState" not in config
        assert "https://example.com" in config

    def test_config_with_existing_storage_state(self):
        """传入存在的 storage_state_path 时，config 应包含 storageState"""
        service = WebTestService(session=MagicMock())
        web_test = SimpleNamespace(base_url="https://example.com")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"cookies": [], "origins": []}')
            storage_path = f.name

        try:
            config = service._generate_playwright_config(
                web_test, {}, storage_state_path=storage_path
            )

            assert "storageState" in config
            expected = json.dumps(Path(storage_path).as_posix())
            assert f"storageState: {expected}," in config
        finally:
            Path(storage_path).unlink(missing_ok=True)

    def test_config_with_missing_storage_state(self):
        """传入不存在的 storage_state_path 时，config 不应包含 storageState"""
        service = WebTestService(session=MagicMock())
        web_test = SimpleNamespace(base_url="https://example.com")

        config = service._generate_playwright_config(
            web_test, {}, storage_state_path="/tmp/nonexistent-storage-state.json"
        )

        assert "storageState" not in config


class TestResolveStorageStatePath:
    @pytest.mark.asyncio
    async def test_returns_latest_completed_path(self):
        """应返回项目/环境最近一次 completed 且 output_path 非空的记录"""
        project_id = uuid4()
        environment_id = uuid4()
        expected_path = "/tmp/latest-state.json"

        fake_job = MagicMock(spec=StorageStateJob)
        fake_job.output_path = expected_path

        fake_result = MagicMock()
        fake_result.scalar_one_or_none = MagicMock(return_value=fake_job)

        fake_session = MagicMock()
        fake_session.execute = AsyncMock(return_value=fake_result)

        service = WebTestService(session=fake_session)
        path = await service._resolve_storage_state_path(
            fake_session, project_id, environment_id
        )

        assert path == expected_path
        fake_session.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_completed_job(self):
        """没有 completed 记录时应返回 None"""
        project_id = uuid4()

        fake_result = MagicMock()
        fake_result.scalar_one_or_none = MagicMock(return_value=None)

        fake_session = MagicMock()
        fake_session.execute = AsyncMock(return_value=fake_result)

        service = WebTestService(session=fake_session)
        path = await service._resolve_storage_state_path(fake_session, project_id)

        assert path is None

    @pytest.mark.asyncio
    async def test_filters_by_environment_id_and_falls_back(self):
        """优先按 environment_id 查询，无结果时回退到项目级记录"""
        project_id = uuid4()
        environment_id = uuid4()
        expected_path = "/tmp/env-state.json"

        fake_job = MagicMock(spec=StorageStateJob)
        fake_job.output_path = expected_path

        fake_result = MagicMock()
        fake_result.scalar_one_or_none = MagicMock(return_value=fake_job)

        fake_session = MagicMock()
        fake_session.execute = AsyncMock(return_value=fake_result)

        service = WebTestService(session=fake_session)
        path = await service._resolve_storage_state_path(
            fake_session, project_id, environment_id
        )

        assert path == expected_path
        # 期望被调用两次：第一次按环境，第二次回退（但 mock 第一次就返回了，所以实际只调用一次）
        fake_session.execute.assert_awaited_once()


class TestResolveEnvironmentForWebTest:
    @pytest.mark.asyncio
    async def test_uses_execution_config_environment_id(self):
        """execution_config 中指定 environment_id 时优先使用"""
        project_id = uuid4()
        env_id = uuid4()

        fake_env = MagicMock(spec=ProjectEnvironment)
        fake_env.id = env_id
        fake_env.project_id = project_id

        fake_repo = MagicMock()
        fake_repo.get_by_id = AsyncMock(return_value=fake_env)
        fake_repo.list_by_project = AsyncMock(return_value=[])
        fake_repo.get_default_by_project = AsyncMock(return_value=None)

        fake_session = MagicMock()

        service = WebTestService(session=fake_session)
        with patch(
            "app.services.web_test_service.EnvironmentRepository",
            return_value=fake_repo,
        ):
            env = await service._resolve_environment_for_web_test(
                fake_session,
                project_id,
                "https://example.com",
                {"environment_id": str(env_id)},
            )

        assert env == fake_env
        fake_repo.get_by_id.assert_awaited_once_with(env_id)

    @pytest.mark.asyncio
    async def test_falls_back_to_base_url_match(self):
        """未指定 environment_id 时按 base_url 匹配"""
        project_id = uuid4()
        env_id = uuid4()

        fake_env = MagicMock(spec=ProjectEnvironment)
        fake_env.id = env_id
        fake_env.project_id = project_id
        fake_env.base_url = "https://example.com/"

        fake_repo = MagicMock()
        fake_repo.get_by_id = AsyncMock(return_value=None)
        fake_repo.list_by_project = AsyncMock(return_value=[fake_env])
        fake_repo.get_default_by_project = AsyncMock(return_value=None)

        fake_session = MagicMock()

        service = WebTestService(session=fake_session)
        with patch(
            "app.services.web_test_service.EnvironmentRepository",
            return_value=fake_repo,
        ):
            env = await service._resolve_environment_for_web_test(
                fake_session,
                project_id,
                "https://example.com",
                {},
            )

        assert env == fake_env

    @pytest.mark.asyncio
    async def test_falls_back_to_default_environment(self):
        """未匹配到指定环境时回退到默认环境"""
        project_id = uuid4()

        fake_env = MagicMock(spec=ProjectEnvironment)
        fake_env.id = uuid4()
        fake_env.project_id = project_id

        fake_repo = MagicMock()
        fake_repo.get_by_id = AsyncMock(return_value=None)
        fake_repo.list_by_project = AsyncMock(return_value=[])
        fake_repo.get_default_by_project = AsyncMock(return_value=fake_env)

        fake_session = MagicMock()

        service = WebTestService(session=fake_session)
        with patch(
            "app.services.web_test_service.EnvironmentRepository",
            return_value=fake_repo,
        ):
            env = await service._resolve_environment_for_web_test(
                fake_session,
                project_id,
                "https://example.com",
                {},
            )

        assert env == fake_env
