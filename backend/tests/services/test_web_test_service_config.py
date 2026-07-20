"""
WebTestService 配置生成单元测试
"""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

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
        """应返回项目最近一次 completed 且 output_path 非空的记录"""
        project_id = uuid4()
        expected_path = "/tmp/latest-state.json"

        fake_job = MagicMock(spec=StorageStateJob)
        fake_job.output_path = expected_path

        fake_result = MagicMock()
        fake_result.scalar_one_or_none = MagicMock(return_value=fake_job)

        fake_session = MagicMock()
        fake_session.execute = AsyncMock(return_value=fake_result)

        service = WebTestService(session=fake_session)
        path = await service._resolve_storage_state_path(project_id)

        assert path == expected_path
        fake_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_completed_job(self):
        """没有 completed 记录时应返回 None"""
        project_id = uuid4()

        fake_result = MagicMock()
        fake_result.scalar_one_or_none = MagicMock(return_value=None)

        fake_session = MagicMock()
        fake_session.execute = AsyncMock(return_value=fake_result)

        service = WebTestService(session=fake_session)
        path = await service._resolve_storage_state_path(project_id)

        assert path is None
