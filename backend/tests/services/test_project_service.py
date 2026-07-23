"""
ProjectService 单元测试

覆盖项目列表与详情中的计数逻辑：
- get_projects 返回正确的测试用例/文件夹数量
- get_project 返回请求项目的数量，而不是仅最新项目的数量
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.services.project_service import ProjectService
from app.schemas.project import ProjectUpdate


class DummyUser:
    email = "user@example.com"


class DummyProject:
    def __init__(self, identifier: str, name: str):
        self.id = uuid4()
        self.identifier = identifier
        self.name = name
        self.description = None
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = None
        self.creator = DummyUser()
        self.teams = []


class FakeSession:
    async def flush(self):
        pass

    async def refresh(self, instance):
        pass


class FakeProjectRepo:
    def __init__(self, projects_data: list[dict], total: int):
        self._projects_data = projects_data
        self._total = total

    async def get_all_with_counts(self, offset: int, limit: int) -> list[dict]:
        return self._projects_data[offset : offset + limit]

    async def count(self) -> int:
        return self._total

    async def get_by_identifier_with_counts(self, identifier: str) -> dict | None:
        for data in self._projects_data:
            if data["project"].identifier == identifier:
                return data
        return None

    async def get_by_identifier(self, identifier: str):
        for data in self._projects_data:
            if data["project"].identifier == identifier:
                return data["project"]
        return None


class TestProjectService:
    @pytest.mark.asyncio
    async def test_get_projects_returns_counts(self):
        data = [
            {
                "project": DummyProject("P-1", "Project A"),
                "test_cases_count": 5,
                "folders_count": 2,
            }
        ]
        service = ProjectService.__new__(ProjectService)
        service.repo = FakeProjectRepo(data, 1)

        projects, total = await service.get_projects(0, 10)

        assert total == 1
        assert len(projects) == 1
        assert projects[0].identifier == "P-1"
        assert projects[0].test_cases_count == 5
        assert projects[0].folders_count == 2

    @pytest.mark.asyncio
    async def test_get_project_returns_counts_for_requested_project(self):
        data = [
            {
                "project": DummyProject("P-1", "Older project"),
                "test_cases_count": 1,
                "folders_count": 1,
            },
            {
                "project": DummyProject("P-2", "Newer project"),
                "test_cases_count": 10,
                "folders_count": 3,
            },
        ]
        service = ProjectService.__new__(ProjectService)
        service.repo = FakeProjectRepo(data, 2)

        info = await service.get_project("P-1")

        assert info.identifier == "P-1"
        assert info.test_cases_count == 1
        assert info.folders_count == 1

    @pytest.mark.asyncio
    async def test_get_project_not_found_raises(self):
        service = ProjectService.__new__(ProjectService)
        service.repo = FakeProjectRepo([], 0)
        service.session = FakeSession()

        with pytest.raises(Exception):  # NotFoundException
            await service.get_project("P-999")

    @pytest.mark.asyncio
    async def test_update_project_returns_info_with_creator_email(self):
        project = DummyProject("P-1", "Project A")
        data = [
            {
                "project": project,
                "test_cases_count": 5,
                "folders_count": 2,
            }
        ]
        service = ProjectService.__new__(ProjectService)
        service.repo = FakeProjectRepo(data, 1)
        service.session = FakeSession()

        info = await service.update_project("P-1", ProjectUpdate(name="Updated"))

        assert info.identifier == "P-1"
        assert info.name == "Updated"
        assert info.created_by == "user@example.com"
