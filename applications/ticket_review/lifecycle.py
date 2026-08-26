from __future__ import annotations

from fastapi import FastAPI

from .services.db1_pool import close_db1_pool, init_db1_pool
from .services.db2_pool import close_db2_pool, init_db2_pool

async def start_ticket_review(app: FastAPI) -> None:
    try:
        await init_db1_pool()
        await init_db2_pool()
    except Exception:
        try:
            await close_db2_pool()
        finally:
            await close_db1_pool()
        raise
    app.state.ticket_review_started = True
    app.state.ticket_review_worker_error = None


async def stop_ticket_review(app: FastAPI) -> None:
    try:
        await close_db2_pool()
    finally:
        try:
            await close_db1_pool()
        finally:
            app.state.ticket_review_started = False
