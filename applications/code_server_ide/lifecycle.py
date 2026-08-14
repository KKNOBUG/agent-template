from __future__ import annotations

from fastapi import FastAPI

from .database import close_database, init_database
from .services.ide_service import ide_service


async def start_code_server_ide(app: FastAPI) -> None:
    init_database()
    try:
        ide_service.start_background_tasks()
    except Exception:
        await close_database()
        raise
    app.state.code_server_ide_started = True


async def stop_code_server_ide(app: FastAPI) -> None:
    try:
        await ide_service.stop_background_tasks()
    finally:
        try:
            await close_database()
        finally:
            app.state.code_server_ide_started = False
