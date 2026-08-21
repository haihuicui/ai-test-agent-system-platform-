"""
APIAnnotationRepository 单元测试

使用 mocked AsyncSession 验证查询条件、自然键去重、过期失效逻辑。
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.api_annotation import APIAnnotation
from app.repositories.api_annotation_repo import APIAnnotationRepository


class TestAPIAnnotationRepository:
    @pytest.fixture
    def repo(self):
        session = MagicMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return APIAnnotationRepository(session)

    def _mock_result(self, repo, return_value):
        """构造 execute → scalars → all 的 mock 链"""
        result_mock = MagicMock()
        scalars_mock = MagicMock()
        all_mock = MagicMock()
        all_mock.return_value = return_value
        scalars_mock.all = all_mock
        result_mock.scalars.return_value = scalars_mock
        repo.session.execute.return_value = result_mock
        return result_mock

    def _mock_scalar_one(self, repo, return_value):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=return_value)
        result_mock.scalar_one = MagicMock(return_value=return_value)
        repo.session.execute.return_value = result_mock
        return result_mock

    @pytest.mark.asyncio
    async def test_list_for_endpoint_filters_by_project_and_endpoint(self, repo):
        project_id = uuid4()
        endpoint_id = uuid4()
        self._mock_result(repo, [])

        await repo.list_for_endpoint(project_id, endpoint_id)

        call_args = repo.session.execute.call_args[0][0]
        compiled = str(call_args.compile(compile_kwargs={"literal_binds": True}))
        assert "api_annotations.project_id" in compiled
        assert "api_annotations.endpoint_id" in compiled

    @pytest.mark.asyncio
    async def test_list_for_endpoint_includes_only_enabled_by_default(self, repo):
        project_id = uuid4()
        endpoint_id = uuid4()
        self._mock_result(repo, [])

        await repo.list_for_endpoint(project_id, endpoint_id)

        call_args = repo.session.execute.call_args[0][0]
        compiled = str(call_args.compile(compile_kwargs={"literal_binds": True}))
        assert "enabled" in compiled

    @pytest.mark.asyncio
    async def test_upsert_by_natural_key_creates_new_annotation(self, repo):
        project_id = uuid4()
        self._mock_scalar_one(repo, None)

        ann = await repo.upsert_by_natural_key(
            project_id=project_id,
            annotation_type="business_error_code",
            source="trace",
            http_status=400,
            business_code="4009",
        )

        assert isinstance(ann, APIAnnotation)
        assert ann.project_id == project_id
        assert ann.annotation_type == "business_error_code"
        assert ann.confidence == 0.5
        assert ann.hit_count == 1
        repo.session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_by_natural_key_updates_existing_annotation(self, repo):
        project_id = uuid4()
        existing = APIAnnotation(
            id=uuid4(),
            project_id=project_id,
            annotation_type="business_error_code",
            source="trace",
            http_status=400,
            business_code="4009",
            confidence=0.6,
            hit_count=2,
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        self._mock_scalar_one(repo, existing)

        ann = await repo.upsert_by_natural_key(
            project_id=project_id,
            annotation_type="business_error_code",
            source="trace",
            http_status=400,
            business_code="4009",
        )

        assert ann.hit_count == 3
        assert ann.confidence == 0.7
        assert ann.enabled is True

    @pytest.mark.asyncio
    async def test_upsert_by_natural_key_rejects_manual_source(self, repo):
        with pytest.raises(ValueError):
            await repo.upsert_by_natural_key(
                project_id=uuid4(),
                annotation_type="business_error_code",
                source="manual",
            )

    @pytest.mark.asyncio
    async def test_disable_stale_marks_older_items_disabled(self, repo):
        project_id = uuid4()
        stale = APIAnnotation(
            id=uuid4(),
            project_id=project_id,
            annotation_type="business_error_code",
            source="trace",
            confidence=0.5,
            hit_count=1,
            enabled=True,
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        self._mock_result(repo, [stale])

        count = await repo.disable_stale(project_id, older_than_days=30, max_confidence=0.8)

        assert count == 1
        assert stale.enabled is False

    @pytest.mark.asyncio
    async def test_count_by_project_returns_scalar(self, repo):
        project_id = uuid4()
        result_mock = MagicMock()
        result_mock.scalar_one.return_value = 5
        repo.session.execute.return_value = result_mock

        result = await repo.count_by_project(project_id)

        assert result == 5
        call_args = repo.session.execute.call_args[0][0]
        compiled = str(call_args.compile(compile_kwargs={"literal_binds": True}))
        assert "count" in compiled
        assert "enabled" in compiled
