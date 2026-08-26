"""Celery entry point for asynchronously reviewing pushed tickets."""

from typing import Any

from celery_scheduler.celery_worker import celery
from configure import LOGGER


async def _ensure_ticket_review_pools() -> None:
    from applications.ticket_review.services.db1_pool import (
        init_db1_pool,
        is_db1_pool_initialized,
    )
    from applications.ticket_review.services.db2_pool import (
        init_db2_pool,
        is_db2_pool_initialized,
    )

    if not is_db1_pool_initialized():
        await init_db1_pool()
    if not is_db2_pool_initialized():
        await init_db2_pool()


@celery.task(
    name="celery_scheduler.tasks.task_ticket_review.process_push_ticket_review_task",
    soft_time_limit=3300,
    time_limit=3600,
)
async def process_push_ticket_review_task(request_id: str) -> dict[str, Any]:
    """Claim and process the persisted push task identified by ``request_id``."""
    try:
        await _ensure_ticket_review_pools()

        from applications.ticket_review.models.push_task import PushTaskRecord
        from applications.ticket_review.services.push_task_worker import PushTaskWorker

        execution_token = str(process_push_ticket_review_task.request.id or "")
        task = await PushTaskRecord.claim_by_request_id(
            request_id,
            lease_token=execution_token,
        )
        if task is None:
            existing = await PushTaskRecord.get_by_request_id(request_id)
            if existing is None:
                raise RuntimeError(f"Push task does not exist: request_id={request_id}")
            return {
                "success": existing.status in {"SUCCESS", "IGNORED"},
                "request_id": request_id,
                "status": existing.status,
                "skipped": True,
            }

        await PushTaskWorker().process(task)
        finished = await PushTaskRecord.get_by_request_id(request_id)
        status = finished.status if finished else task.status
        return {
            "success": status == "SUCCESS",
            "request_id": request_id,
            "status": status,
        }
    except Exception as exc:
        LOGGER.exception(
            "【Celery】工单预审任务失败: request_id=%s, error=%s",
            request_id,
            exc,
        )
        return {
            "success": False,
            "request_id": request_id,
            "error": str(exc),
        }
