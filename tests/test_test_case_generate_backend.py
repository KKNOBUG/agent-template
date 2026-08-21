from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import ModuleType, SimpleNamespace

from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient

from applications.test_case_generate.dependencies import get_current_user
from applications.test_case_generate.schemas.test_case_schema import TaskInfo
from applications.test_case_generate.views import test_case_generate_router as case_generate_router
from applications.test_case_generate.views import test_case_view
from configure import PROJECT_CONFIG
from services import AuthenticatedUserContext, CTX_CURRENT_USER


def _response_body(response) -> dict:
    return json.loads(response.body)


def test_source_and_compatibility_routes_are_registered() -> None:
    app = FastAPI()
    app.include_router(case_generate_router, prefix="/testCaseGen")
    app.include_router(case_generate_router, prefix="/test-case-gen")
    paths = {route.path for route in app.routes}

    expected_suffixes = {
        "/health",
        "/generateTestCases",
        "/tasks",
        "/testCasesContent",
        "/downloadMarkdown",
        "/downloadXlsx",
        "/streamGenerateTestCases",
        "/streamGenerateTestCasesThinking",
    }
    for suffix in expected_suffixes:
        assert f"/testCaseGen{suffix}" in paths
        assert f"/test-case-gen{suffix}" in paths


def test_health_uses_core_success_contract() -> None:
    app = FastAPI()
    app.include_router(case_generate_router, prefix="/testCaseGen")

    response = TestClient(app).get("/testCaseGen/health")

    assert response.status_code == 200
    assert response.json() == {
        "code": "000000",
        "message": "请求成功",
        "data": {"status": "ok"},
    }


def test_get_current_user_reads_unified_context() -> None:
    current_user = AuthenticatedUserContext(user_id=7, username="alice")
    token = CTX_CURRENT_USER.set(current_user)
    try:
        assert asyncio.run(get_current_user()) == current_user
    finally:
        CTX_CURRENT_USER.reset(token)


def test_generate_uses_authenticated_username_and_queues_celery(monkeypatch, tmp_path) -> None:
    captured: dict = {}

    class FakeTaskRecord:
        id = 42

    class FakeTestCaseTask:
        @classmethod
        async def create(cls, **kwargs):
            captured["record"] = kwargs
            return FakeTaskRecord()

    class FakeCelery:
        def send_task(self, name, kwargs):
            captured["task"] = {"name": name, "kwargs": kwargs}

    fake_worker_module = ModuleType("celery_scheduler.celery_worker")
    fake_worker_module.celery = FakeCelery()
    monkeypatch.setitem(sys.modules, "celery_scheduler.celery_worker", fake_worker_module)
    monkeypatch.setattr(test_case_view, "TestCaseTask", FakeTestCaseTask)
    monkeypatch.setattr(PROJECT_CONFIG, "TEST_CASE_OUTPUT_DIR", str(tmp_path))

    upload = UploadFile(filename="../requirement.docx", file=BytesIO(b"docx-content"))
    response = asyncio.run(
        test_case_view.generate_test_cases(
            files=[upload],
            app_system="core-banking",
            requirement_name="interest approval",
            current_user=AuthenticatedUserContext(user_id=7, username="alice"),
        )
    )

    assert _response_body(response) == {
        "code": "000000",
        "message": "请求成功",
        "data": {"status": "accepted", "task_id": 42},
    }
    assert captured["record"]["created_user"] == "alice"
    assert captured["record"]["updated_user"] == "alice"
    assert captured["record"]["status"] == "pending"
    assert captured["task"]["name"] == (
        "celery_scheduler.tasks.task_test_case_gen.generate_test_cases_task"
    )
    assert captured["task"]["kwargs"]["source_filenames"] == ["requirement.docx"]
    assert (Path(captured["task"]["kwargs"]["folder_path"]) / "requirement.docx").exists()


def test_task_schema_preserves_source_field_names() -> None:
    now = datetime(2026, 8, 14, 10, 30, 0)
    task = SimpleNamespace(
        id=1,
        folder_path="/tmp/task",
        app_system="core-banking",
        requirement_name="approval",
        status="success",
        error_reason=None,
        created_user="alice",
        updated_user="bob",
        created_time=now,
        updated_time=now,
    )

    data = TaskInfo.model_validate(task).model_dump(by_alias=True)

    assert data["createrUser"] == "alice"
    assert data["lastUpdateUser"] == "bob"
    assert data["createrTime"] == "2026-08-14 10:30:00"
    assert data["lastUpdateTime"] == "2026-08-14 10:30:00"
