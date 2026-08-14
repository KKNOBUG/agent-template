from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI

from core.initializations import module_initialization


@pytest.mark.asyncio
async def test_application_lifespan_starts_and_stops_modules_in_order(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(
        module_initialization,
        "register_database",
        AsyncMock(side_effect=lambda app: calls.append("main-db-start")),
    )
    monkeypatch.setattr(
        module_initialization,
        "init_database_table",
        AsyncMock(side_effect=lambda app: calls.append("main-db-init")),
    )
    monkeypatch.setattr(
        module_initialization,
        "start_ticket_review",
        AsyncMock(side_effect=lambda app: calls.append("ticket-start")),
    )
    monkeypatch.setattr(
        module_initialization,
        "start_code_server_ide",
        AsyncMock(side_effect=lambda app: calls.append("ide-start")),
    )
    monkeypatch.setattr(
        module_initialization,
        "stop_code_server_ide",
        AsyncMock(side_effect=lambda app: calls.append("ide-stop")),
    )
    monkeypatch.setattr(
        module_initialization,
        "stop_ticket_review",
        AsyncMock(side_effect=lambda app: calls.append("ticket-stop")),
    )
    monkeypatch.setattr(
        module_initialization.Tortoise,
        "close_connections",
        AsyncMock(side_effect=lambda: calls.append("main-db-stop")),
    )

    app = FastAPI()
    async with module_initialization.application_lifespan(app):
        app.state.ticket_review_started = True
        app.state.code_server_ide_started = True
        calls.append("running")

    assert calls == [
        "main-db-start",
        "main-db-init",
        "ticket-start",
        "ide-start",
        "running",
        "ide-stop",
        "ticket-stop",
        "main-db-stop",
    ]


@pytest.mark.asyncio
async def test_partial_startup_still_stops_started_ticket_module(monkeypatch):
    app = FastAPI()

    async def start_ticket(target):
        target.state.ticket_review_started = True

    monkeypatch.setattr(module_initialization, "register_database", AsyncMock())
    monkeypatch.setattr(module_initialization, "init_database_table", AsyncMock())
    monkeypatch.setattr(module_initialization, "start_ticket_review", AsyncMock(side_effect=start_ticket))
    monkeypatch.setattr(
        module_initialization,
        "start_code_server_ide",
        AsyncMock(side_effect=RuntimeError("IDE startup failed")),
    )
    stop_ticket = AsyncMock()
    monkeypatch.setattr(module_initialization, "stop_ticket_review", stop_ticket)
    monkeypatch.setattr(module_initialization, "stop_code_server_ide", AsyncMock())
    monkeypatch.setattr(module_initialization.Tortoise, "close_connections", AsyncMock())

    with pytest.raises(RuntimeError, match="IDE startup failed"):
        async with module_initialization.application_lifespan(app):
            pass

    stop_ticket.assert_awaited_once_with(app)
