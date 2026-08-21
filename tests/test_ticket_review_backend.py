from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from applications.ticket_review.schemas.push_ticket import TARGET_APPROVAL_GROUP
from applications.ticket_review.views import routes


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_push_tickets_filters_records_and_publishes_event(monkeypatch):
    task = SimpleNamespace(
        request_id="request-1",
        status="PENDING",
        summary=lambda: {"requestId": "request-1", "status": "PENDING"},
    )
    create_or_get = AsyncMock(return_value=(task, True))
    publish = AsyncMock()
    monkeypatch.setattr(routes.PushTaskRecord, "create_or_get", create_or_get)
    monkeypatch.setattr(routes.push_task_events, "publish", publish)

    response = _client().post(
        "/pushTickets",
        json={
            "messageId": "message-1",
            "pushTime": "2026-08-14 10:00:00",
            "items": [
                {
                    "tableCode": "FW038",
                    "tableName": "FW038",
                    "records": [
                        {"ticketNo": "accepted", "extra5": TARGET_APPROVAL_GROUP},
                        {"ticketNo": "ignored", "extra5": "another-group"},
                    ],
                },
                {
                    "tableCode": "OTHER",
                    "tableName": "OTHER",
                    "records": [{"ticketNo": "unsupported", "extra5": TARGET_APPROVAL_GROUP}],
                },
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "code": "000000",
        "message": response.json()["message"],
        "data": {
            "messageId": "message-1",
            "requestId": "request-1",
            "status": "PENDING",
            "receivedRecords": 3,
            "acceptedRecords": 1,
            "ignoredRecords": 2,
        },
    }
    create_or_get.assert_awaited_once()
    assert create_or_get.await_args.kwargs["total_records"] == 1
    publish.assert_awaited_once_with("task_created", task.summary())


def test_push_tickets_rejects_invalid_payload():
    response = _client().post(
        "/pushTickets",
        json={"messageId": "", "pushTime": "not-a-date", "items": []},
    )
    assert response.status_code == 422


def test_list_push_tasks_returns_paginated_data(monkeypatch):
    record = SimpleNamespace(summary=lambda: {"requestId": "request-2", "status": "DONE"})
    monkeypatch.setattr(routes.PushTaskRecord, "count", AsyncMock(return_value=1))
    list_page = AsyncMock(return_value=[record])
    monkeypatch.setattr(routes.PushTaskRecord, "list_page", list_page)

    response = _client().get("/pushTasks?page=2&limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == "000000"
    assert payload["data"] == {
        "total": 1,
        "page": 2,
        "limit": 10,
        "items": [{"requestId": "request-2", "status": "DONE"}],
    }
    list_page.assert_awaited_once_with(10, 10)


def test_export_review_excel_validates_and_generates_xlsx():
    with _client() as client:
        invalid = client.post("/exportReviewExcel", json={"json": {}})
        assert invalid.status_code == 200
        assert invalid.json()["code"] == "999999"

        exported = client.post(
            "/exportReviewExcel",
            json={"json": {"metadata": {"source_file": "tickets.xlsx"}, "tickets": []}},
        )
        assert exported.status_code == 200
        assert exported.content.startswith(b"PK")
        assert "spreadsheetml.sheet" in exported.headers["content-type"]
