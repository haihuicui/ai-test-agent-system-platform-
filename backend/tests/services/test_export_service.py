"""导出服务单元测试"""

from datetime import datetime
from uuid import uuid4, UUID

import pytest

from app.schemas.enums import ExportFormat, ExportStatus, Priority, TestCaseState, TestCaseType
from app.schemas.test_case import TestCaseInfo, ExportTestCasesRequest, ExportExcelRequest
from app.services.export_service import ExportService


class _FakeMongoCollection:
    """内存中的假 MongoDB 集合，仅用于服务测试。"""

    def __init__(self):
        self.docs: dict[str, dict] = {}

    async def insert_one(self, doc: dict) -> None:
        self.docs[doc["_id"]] = doc

    async def update_one(self, filter_: dict, update: dict) -> None:
        doc_id = filter_.get("_id")
        doc = self.docs.get(doc_id)
        if doc is None:
            return
        set_values = update.get("$set", {})
        doc.update(set_values)

    async def find_one(self, filter_: dict) -> dict | None:
        return self.docs.get(filter_.get("_id"))


class _FakeTestCaseService:
    """返回固定测试用例的假服务。"""

    def __init__(self, cases: list[TestCaseInfo]):
        self.cases = cases

    async def get_test_cases_for_export(
        self,
        project_identifier: str,
        test_case_ids: list[str] | None = None,
        folder_ids: list[str] | None = None,
    ) -> list[TestCaseInfo]:
        return self.cases


def _make_test_case(identifier: str = "TC-001", name: str = "登录") -> TestCaseInfo:
    return TestCaseInfo(
        id=uuid4(),
        identifier=identifier,
        name=name,
        priority=Priority.HIGH,
        status=TestCaseState.NEW,
        case_type=TestCaseType.FUNCTIONAL,
        project_id=uuid4(),
        created_by="tester@example.com",
        created_at=datetime.utcnow(),
        module="用户模块",
        test_data={"username": "admin"},
        test_case_steps=[],
    )


@pytest.fixture
def fake_collection():
    return _FakeMongoCollection()


@pytest.fixture
def export_service(fake_collection):
    return ExportService(db=None, mongodb={ExportService.COLLECTION_NAME: fake_collection})


@pytest.fixture
def fake_service():
    return _FakeTestCaseService([_make_test_case()])


async def test_start_export_creates_job(export_service, fake_service, fake_collection):
    data = ExportTestCasesRequest(format=ExportFormat.JSON, test_case_ids=["TC-001"])
    response = await export_service.start_export("proj-1", data, fake_service)

    assert response.success is True
    assert response.format == ExportFormat.JSON
    assert response.status == ExportStatus.PENDING
    assert response.export_id

    job = fake_collection.docs[response.export_id]
    assert job["format"] == "json"
    assert job["project_identifier"] == "proj-1"
    assert job["test_case_ids"] == ["TC-001"]


async def test_process_test_cases_export_generates_json(export_service, fake_service, fake_collection):
    data = ExportTestCasesRequest(format=ExportFormat.JSON, test_case_ids=["TC-001"])
    response = await export_service.start_export("proj-1", data, fake_service)

    job = fake_collection.docs[response.export_id]
    assert job["status"] == ExportStatus.COMPLETED.value
    assert job["filename"].endswith(".json")
    assert job["content_type"] == "application/json; charset=utf-8"
    assert b"TC-001" in job["file_content"]


async def test_process_test_cases_export_generates_csv(export_service, fake_service, fake_collection):
    data = ExportTestCasesRequest(format=ExportFormat.CSV, test_case_ids=["TC-001"])
    response = await export_service.start_export("proj-1", data, fake_service)

    job = fake_collection.docs[response.export_id]
    assert job["status"] == ExportStatus.COMPLETED.value
    assert job["filename"].endswith(".csv")
    assert job["content_type"] == "text/csv; charset=utf-8"
    assert job["file_content"].startswith(b"\xef\xbb\xbf")


async def test_process_test_cases_export_generates_markdown(export_service, fake_service, fake_collection):
    data = ExportTestCasesRequest(format=ExportFormat.MARKDOWN, test_case_ids=["TC-001"])
    response = await export_service.start_export("proj-1", data, fake_service)

    job = fake_collection.docs[response.export_id]
    assert job["status"] == ExportStatus.COMPLETED.value
    assert job["filename"].endswith(".md")
    assert job["content_type"] == "text/markdown; charset=utf-8"
    assert b"# \xe6\xb5\x8b\xe8\xaf\x95\xe7\x94\xa8\xe4\xbe\x8b\xe5\xaf\xbc\xe5\x87\xba" in job["file_content"]


async def test_process_test_cases_export_generates_excel(export_service, fake_service, fake_collection):
    data = ExportTestCasesRequest(format=ExportFormat.EXCEL, test_case_ids=["TC-001"])
    response = await export_service.start_export("proj-1", data, fake_service)

    job = fake_collection.docs[response.export_id]
    assert job["status"] == ExportStatus.COMPLETED.value
    assert job["filename"].endswith(".xlsx")
    assert "spreadsheetml" in job["content_type"]


async def test_start_excel_export_backward_compatible(export_service, fake_service, fake_collection):
    data = ExportExcelRequest(test_case_ids=["TC-001"])
    response = await export_service.start_excel_export("proj-1", data, fake_service)

    assert response.success is True
    assert response.export_id
    assert response.status_url

    job = fake_collection.docs[response.export_id]
    assert job["format"] == "excel"


async def test_download_export_returns_file(export_service, fake_service, fake_collection):
    data = ExportTestCasesRequest(format=ExportFormat.CSV, test_case_ids=["TC-001"])
    response = await export_service.start_export("proj-1", data, fake_service)

    content, filename, content_type = await export_service.download_export(response.export_id)
    assert filename.endswith(".csv")
    assert content_type == "text/csv; charset=utf-8"
    assert content.startswith(b"\xef\xbb\xbf")
