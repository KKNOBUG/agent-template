from __future__ import annotations

import asyncio
import logging
import time
# from typing import Any
from datetime import datetime
from applications.ticket_review.config import settings
from applications.ticket_review.models.push_task import PushTaskRecord
from applications.ticket_review.services.push_ticket_review import (
    PushTicketReviewRecord,
)
from applications.ticket_review.services.excel_skill_json_formatter import ExcelSkillJsonFormatter
from applications.ticket_review.services.push_task_events import push_task_events

logger = logging.getLogger(__name__)


class PushTaskWorker:
    def __init__(self) -> None:
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        logger.info("Push task worker started")
        last_cleanup = 0.0
        last_stale_reset = 0.0
        last_failed_retry = 0.0
        stale_reset_interval = _stale_reset_interval(
            settings.push_task_stale_processing_seconds,
            settings.push_task_poll_interval,
        )
        try:
            while not self._stop.is_set():
                try:
                    now = time.monotonic()
                    if now - last_stale_reset >= stale_reset_interval:
                        await PushTaskRecord.reset_stale(
                            settings.push_task_stale_processing_seconds
                        )
                        last_stale_reset = now
                    if now - last_failed_retry >= 60.0:
                        retried = await PushTaskRecord.retry_failed(
                            settings.push_task_failed_retry_delay_seconds
                        )
                        if retried:
                            logger.info(
                                "Scheduled %s failed push task(s) for retry",
                                retried,
                            )
                        last_failed_retry = now
                    if now - last_cleanup >= settings.push_task_cleanup_interval:
                        await PushTaskRecord.cleanup(settings.push_task_retention_days)
                        last_cleanup = now

                    task = await PushTaskRecord.claim_next()
                    if task is not None:
                        await self._process(task)
                        continue
                except Exception:
                    logger.exception("Push task worker iteration failed; retrying")
                if not self._stop.is_set():
                    await self._wait_for_stop(settings.push_task_poll_interval)
        except asyncio.CancelledError:
            raise
        finally:
            logger.info("Push task worker stopped")

    async def _wait_for_stop(self, seconds: int) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=max(0.1, seconds))
        except asyncio.TimeoutError:
            pass
    #         await task.mark_failed(str(exc))
    #         await push_task_events.publish("error", task.summary())
    async def _heartbeat_loop(
        self,
        task: PushTaskRecord,
        heartbeat_stop: asyncio.Event,
        lease_lost: asyncio.Event,
    ) -> None:
        interval = settings.push_task_heartbeat_interval_seconds
        try:
            while not heartbeat_stop.is_set():
                try:
                    ok = await task.heartbeat()
                    if not ok:
                        logger.warning(
                            "Lease lost for push task %s",
                            task.request_id,
                        )
                        lease_lost.set()
                        break
                except Exception:
                    logger.exception(
                        "Heartbeat failed for push task %s",
                        task.request_id,
                    )
                try:
                    await asyncio.wait_for(
                        heartbeat_stop.wait(),
                        timeout=interval,
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass

    async def _process(self, task: PushTaskRecord) -> None:
        await push_task_events.publish(
            "start",
            task.summary(),
        )

        heartbeat_stop = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(
                task,
                heartbeat_stop,
                lease_lost,
            ),
            name=f"heartbeat-{task.request_id}",
        )

        # 不再从result_json.tickets判断恢复位置。
        resume_processed = min(
            task.total_records,
            task.processed_records,
        )

        formatter = ExcelSkillJsonFormatter()

        try:
            async for event in formatter.stream_push_payload(
                task.raw_payload,
                batch_size=settings.push_task_batch_size,
                start_after=resume_processed,
            ):
                if event["type"] == "start":
                    continue

                if lease_lost.is_set():
                    logger.warning(
                        "Aborting push task %s due to lease lost",
                        task.request_id,
                    )
                    break

                batch_tickets = event.get("tickets", [])
                if not isinstance(batch_tickets, list):
                    raise ValueError(
                        "LLM batch tickets must be a list"
                    )

                processed = int(event["processedRows"])
                # 1. 写FW038/FW039子表；
                # 2. 更新push_tasks处理进度。
                await PushTicketReviewRecord.save_batch_and_progress(
                    request_id=task.request_id,
                    message_id=task.message_id,
                    lease_token=task.lease_token,
                    tickets=batch_tickets,
                    processed_records=processed,
                )

                task.processed_records = max(
                    task.processed_records,
                    processed,
                )
                task.updated_at = datetime.now()

                await push_task_events.publish(
                    "batch",
                    {
                        **task.summary(),
                        "processedRecords": processed,
                        "batchIndex": event["batchIndex"],
                        "totalBatches": event["totalBatches"],
                        "tickets": batch_tickets,
                    },
                )

            if not lease_lost.is_set():
                await task.mark_success()
                await push_task_events.publish(
                    "complete",
                    task.summary(),
                )

        except asyncio.CancelledError:
            try:
                await asyncio.shield(
                    task.release_to_pending()
                )
            except Exception:
                logger.exception(
                    "Failed to release cancelled push task %s",
                    task.request_id,
                )
            raise

        except Exception as exc:
            logger.exception(
                "Push task %s failed",
                task.request_id,
            )

            if not lease_lost.is_set():
                await task.mark_failed(str(exc))
            await push_task_events.publish(
                "error",
                task.summary(),
            )
        finally:
            heartbeat_stop.set()
            try:
                await asyncio.wait_for(
                    heartbeat_task,
                    timeout=5,
                )
            except asyncio.TimeoutError:
                heartbeat_task.cancel()
            except asyncio.CancelledError:
                pass

def _stale_reset_interval(stale_seconds: int, poll_interval: int) -> float:
    """Recheck abandoned PROCESSING tasks without querying MySQL every poll."""
    return max(1.0, min(60.0, max(float(poll_interval), float(stale_seconds) / 2)))
