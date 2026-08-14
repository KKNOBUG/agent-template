from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI

from configure import PROJECT_CONFIG

from .services.db1_pool import close_db1_pool, init_db1_pool
from .services.db2_pool import close_db2_pool, init_db2_pool
from .services.push_task_worker import PushTaskWorker

logger = logging.getLogger(__name__)


def _worker_finished(app: FastAPI, task: asyncio.Task[None]) -> None:
    if getattr(app.state, "shutting_down", False) or task.cancelled():
        return
    error = task.exception()
    app.state.ticket_review_worker_error = repr(error) if error else "worker exited unexpectedly"
    logger.critical("Ticket review worker stopped unexpectedly: %s", app.state.ticket_review_worker_error)


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
    if not PROJECT_CONFIG.TICKET_PUSH_TASK_WORKER_ENABLED:
        return
    worker = PushTaskWorker()
    task = asyncio.create_task(worker.run(), name="ticket-review-push-task-worker")
    task.add_done_callback(lambda finished: _worker_finished(app, finished))
    app.state.ticket_review_worker = worker
    app.state.ticket_review_worker_task = task


async def stop_ticket_review(app: FastAPI) -> None:
    worker = getattr(app.state, "ticket_review_worker", None)
    task = getattr(app.state, "ticket_review_worker_task", None)
    if worker is not None:
        worker.stop()
    try:
        if task is not None:
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            except Exception:
                logger.exception("Ticket review worker failed while shutting down")
    finally:
        try:
            try:
                await close_db2_pool()
            finally:
                await close_db1_pool()
        finally:
            app.state.ticket_review_started = False
