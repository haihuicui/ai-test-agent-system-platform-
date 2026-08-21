"""
ProbeExecutor 单元测试

覆盖环境安全过滤、请求构造、响应解析、标注沉淀逻辑。
使用 mocked AsyncSession 与 pytest-httpx mock。
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest

from app.models.api_annotation import APIAnnotation
from app.models.api_endpoint import APIEndpoint
from app.models.environment import ProjectEnvironment
from app.repositories.api_annotation_repo import APIAnnotationRepository
from app.services.probe_executor import ProbeExecutor


class TestProbeExecutor:
    @pytest.fixture
    def session(self):
        session = MagicMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.add = MagicMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def executor(self, session):
        return ProbeExecutor(session)

    def _make_endpoint(
        self,
        path="/api/users",
        method="POST",
        parameters=None,
        request_body=None,
    ):
        ep = MagicMock(spec=APIEndpoint)
        ep.id = uuid4()
        ep.project_id = uuid4()
        ep.path = path
        ep.method = method
        ep.parameters = parameters or []
        ep.request_body = request_body or None
        return ep

    def _make_env(self, name="test-env"):
        env = MagicMock(spec=ProjectEnvironment)
        env.id = uuid4()
        env.project_id = uuid4()
        env.name = name
        env.base_url = "http://localhost:8080"
        env.auth_type = "none"
        env.auth_secret = None
        env.auth_config = {}
        return env

    def test_is_safe_environment_allows_test(self):
        assert ProbeExecutor.is_safe_environment("local-dev") is True
        assert ProbeExecutor.is_safe_environment("SIT") is True
        assert ProbeExecutor.is_safe_environment("uat-env") is True

    def test_is_safe_environment_rejects_prod(self):
        assert ProbeExecutor.is_safe_environment("prod") is False
        assert ProbeExecutor.is_safe_environment("production") is False
        assert ProbeExecutor.is_safe_environment("my-live-env") is False

    def test_is_safe_environment_rejects_unknown(self):
        assert ProbeExecutor.is_safe_environment("custom") is False

    def test_fill_path_params(self):
        url = "http://api.example.com/api/users/{id}"
        result = ProbeExecutor._fill_path_params(url, {"id": "123"})
        assert result == "http://api.example.com/api/users/123"

    def test_extract_business_code(self):
        assert ProbeExecutor._extract_business_code({"code": "4009"}) == "4009"
        assert ProbeExecutor._extract_business_code({"errorCode": 1001}) == "1001"
        assert ProbeExecutor._extract_business_code("not dict") is None

    def test_extract_message(self):
        assert ProbeExecutor._extract_message({"message": "bad request"}) == "bad request"
        assert ProbeExecutor._extract_message({"msg": "error"}) == "error"

    def test_is_interesting_result(self):
        assert ProbeExecutor._is_interesting_result(400, None) is True
        assert ProbeExecutor._is_interesting_result(200, "4009") is True
        assert ProbeExecutor._is_interesting_result(200, "0") is False
        assert ProbeExecutor._is_interesting_result(200, 0) is False

    @pytest.mark.asyncio
    async def test_probe_endpoint_dry_run(self, executor, session):
        ep = self._make_endpoint(
            path="/api/users",
            method="POST",
            request_body={
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["email"],
                            "properties": {
                                "email": {"type": "string", "format": "email"},
                            },
                        }
                    }
                }
            },
        )
        session.get = AsyncMock(return_value=ep)

        env = self._make_env()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.probe_executor.ProbeExecutor._get_environment",
                AsyncMock(return_value=env),
            )
            mp.setattr(
                "app.services.probe_executor.EnvironmentService.get_execution_env_vars",
                AsyncMock(return_value={"API_BASE_URL": "http://localhost:8080"}),
            )
            result = await executor.probe_endpoint(
                project_identifier="PR-1",
                endpoint_id=str(ep.id),
                dry_run=True,
            )

        assert result["success"] is True
        assert result["dry_run"] is True
        assert result["probe_count"] > 0

    @pytest.mark.asyncio
    async def test_probe_endpoint_rejects_unsafe_environment(self, executor, session):
        ep = self._make_endpoint()
        session.get = AsyncMock(return_value=ep)

        env = self._make_env(name="production")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.probe_executor.ProbeExecutor._get_environment",
                AsyncMock(return_value=env),
            )
            with pytest.raises(Exception) as exc_info:
                await executor.probe_endpoint(
                    project_identifier="PR-1",
                    endpoint_id=str(ep.id),
                )
            assert "不在主动探测允许列表" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_probe_endpoint_executes_and_harvests(self, executor, session):
        ep = self._make_endpoint(
            path="/api/users",
            method="POST",
            request_body={
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["email"],
                            "properties": {
                                "email": {"type": "string", "format": "email"},
                            },
                        }
                    }
                }
            },
        )
        session.get = AsyncMock(return_value=ep)

        env = self._make_env()

        # Mock httpx.AsyncClient to avoid real network
        class FakeResponse:
            status_code = 400
            headers = {"content-type": "application/json"}
            elapsed = None

            def json(self):
                return {"code": "4001", "message": "邮箱格式不正确"}

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                pass

            async def request(self, **kwargs):
                return FakeResponse()

            async def aclose(self):
                pass

        # Mock repo.create to return a new annotation; mock find to return no existing
        created_ann = None
        async def fake_create(*, project_id, endpoint_id, **kwargs):
            nonlocal created_ann
            created_ann = APIAnnotation(
                id=uuid4(),
                project_id=project_id,
                endpoint_id=endpoint_id,
                **kwargs,
            )
            return created_ann

        executor.repo.create = AsyncMock(side_effect=fake_create)
        executor._find_existing_annotation = AsyncMock(return_value=None)
        executor.repo.session = session

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "app.services.probe_executor.ProbeExecutor._get_environment",
                AsyncMock(return_value=env),
            )
            mp.setattr(
                "app.services.probe_executor.EnvironmentService.get_execution_env_vars",
                AsyncMock(return_value={"API_BASE_URL": "http://localhost:8080"}),
            )
            mp.setattr(
                "app.services.probe_executor.httpx.AsyncClient",
                lambda **kwargs: FakeClient(),
            )
            result = await executor.probe_endpoint(
                project_identifier="PR-1",
                endpoint_id=str(ep.id),
                probe_budget=10,
            )

        assert result["success"] is True
        assert result["dry_run"] is False
        assert result["executed"] > 0
        # 至少有一个探测命中了 400 响应并被沉淀
        assert result["harvested"] >= 1
        assert any(r["business_code"] == "4001" for r in result["results"])

    @pytest.mark.asyncio
    async def test_persist_probe_results_creates_annotation(self, executor, session):
        ep_id = uuid4()
        project_id = uuid4()

        created = []
        async def fake_create(*, project_id, endpoint_id, **kwargs):
            ann = APIAnnotation(id=uuid4(), project_id=project_id, endpoint_id=endpoint_id, **kwargs)
            created.append(ann)
            return ann

        executor.repo.create = AsyncMock(side_effect=fake_create)
        executor._find_existing_annotation = AsyncMock(return_value=None)

        results = [
            {
                "probe": {
                    "name": "缺少必填字段 body.email",
                    "field_path": "body.email",
                    "condition": "required_missing",
                },
                "status": 400,
                "body": {"code": "4001", "message": "邮箱必填"},
                "business_code": "4001",
                "message": "邮箱必填",
            }
        ]

        harvested = await executor._persist_probe_results(project_id, ep_id, results)

        assert len(harvested) == 1
        assert harvested[0].annotation_type == "field_validation"
        assert harvested[0].business_code == "4001"
        assert harvested[0].source == "probe"
