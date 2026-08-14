from __future__ import annotations

import json
import logging
import os
import tempfile
import asyncio
from datetime import datetime
from typing import Any

import aiomysql

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from applications.ticket_review.models.push_task import PushTaskRecord
from applications.ticket_review.models.review_result import ReviewResultRecord
from applications.ticket_review.schemas.push_ticket import PushTicketAck, PushTicketAckData, PushTicketRequest
from core.responses import BaseResponse, FailureResponse, SuccessResponse
from applications.ticket_review.services.db2_pool import get_db2_connection
from applications.ticket_review.services.excel_skill_json_formatter import ExcelSkillJsonFormatter
from applications.ticket_review.services.push_task_events import push_task_events
from configure import PROJECT_CONFIG
from applications.ticket_review.utils.ticket_review_xlsx_writer import append_review_to_source_xlsx, ticket_review_to_xlsx

router = APIRouter(tags=["环境工单预审"])
logger = logging.getLogger(__name__)
_excel_review_tasks: set[asyncio.Task[None]] = set()


async def _detached_sse(source):
    """Keep Excel review running if the browser disconnects from its SSE response."""
    events: asyncio.Queue[str | None] = asyncio.Queue()

    async def pump() -> None:
        try:
            async for message in source:
                await events.put(message)
        finally:
            await events.put(None)

    task = asyncio.create_task(pump(), name="excel-review-stream")
    _excel_review_tasks.add(task)
    task.add_done_callback(_excel_review_tasks.discard)
    # while True:
    #     message = await events.get()
    #     if message is None:
    #         break
    #     yield message
    while True:
        try:
            message = await asyncio.wait_for(
                events.get(),
                timeout=15,
            )
        except asyncio.TimeoutError:
            yield _sse("heartbeat", {
                "timestamp": datetime.now().isoformat()
            })
            continue

        if message is None:
            break

        yield message


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _result_detail(record: ReviewResultRecord) -> dict[str, Any]:
    return {
        "resultId": record.id,
        "tableName": record.table_name,
        "sourceFile": record.source_file,
        "rowCount": record.row_count,
        "createdAt": record.created_at.isoformat(),
        "json": record.result_json,
    }


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/pushTickets", response_model=PushTicketAck)
async def push_tickets(body: PushTicketRequest) -> PushTicketAck:
    """Persist an external push and acknowledge it before LLM processing."""
    payload = body.raw_payload()
    try:
        task, created = await PushTaskRecord.create_or_get(
            message_id=body.message_id,
            push_time=body.push_time,
            raw_payload=payload,
            total_records=body.review_record_count(),
        )
    except Exception as exc:
        logger.exception("Failed to persist pushed tickets: %s", exc)
        raise HTTPException(status_code=500, detail="工单报文保存失败") from exc

    if created:
        event = "ignored" if task.status == "IGNORED" else "task_created"
        await push_task_events.publish(event, task.summary())

    received_records = body.received_record_count()
    accepted_records = body.review_record_count()
    return PushTicketAck(
        message=(
            "接收成功，无需处理的数据"
            if created and accepted_records == 0
            else "接收成功"
            if created
            else "报文已接收，请勿重复提交"
        ),
        data=PushTicketAckData(
            messageId=body.message_id,
            requestId=task.request_id,
            status=task.status,
            receivedRecords=received_records,
            acceptedRecords=accepted_records,
            ignoredRecords=received_records - accepted_records,
        ),
    )
@router.get("/pushTasks/events", response_model=None)
async def push_task_event_stream() -> StreamingResponse:
    async def event_stream():
        async with push_task_events.subscribe() as queue:
            recent = await PushTaskRecord.list_page(limit=50, offset=0)
            yield _sse("snapshot", {"items": [item.summary() for item in recent]})
            while True:
                try:
                    message = await asyncio.wait_for(
                        queue.get(), timeout=PROJECT_CONFIG.TICKET_PUSH_TASK_SSE_HEARTBEAT_SECONDS
                    )
                    yield _sse(message["event"], message["data"])
                except asyncio.TimeoutError:
                    yield _sse("heartbeat", {"timestamp": datetime.now().isoformat()})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/pushTasks")
async def list_push_tasks(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> BaseResponse:
    try:
        total = await PushTaskRecord.count()
        records = await PushTaskRecord.list_page(limit, (page - 1) * limit)
    except Exception as exc:
        logger.exception("Failed to list push tasks: %s", exc)
        return FailureResponse(message=f"查询推送任务失败: {exc}")
    return SuccessResponse(
        data={
            "total": total,
            "page": page,
            "limit": limit,
            "items": [record.summary() for record in records],
        }
    )


@router.get("/pushTasks/{request_id}")
async def get_push_task(request_id: str) -> BaseResponse:
    try:
        record = await PushTaskRecord.get_by_request_id(request_id)
    except Exception as exc:
        logger.exception("Failed to load push task %s: %s", request_id, exc)
        return FailureResponse(message=f"查询推送任务失败: {exc}")
    if record is None:
        return FailureResponse(message="推送任务不存在")
    return SuccessResponse(data=record.summary(include_payload=True))


@router.get("/pushTasks/{request_id}/results")
async def get_push_task_results(
    request_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
) -> BaseResponse:
    try:
        total = await _count_results(request_id)
        results = await _list_results(request_id, limit, (page - 1) * limit)
    except Exception as exc:
        logger.exception("Failed to load push task results %s: %s", request_id, exc)
        return FailureResponse(message=f"查询工单明细失败: {exc}")
    return SuccessResponse(data={
        "total": total,
        "page": page,
        "limit": limit,
        "items": results,
    })


async def _count_results(request_id: str) -> int:
    async with get_db2_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(
                """
                SELECT COUNT(*) AS total FROM (
                    SELECT 1 FROM fw038_review_results
                    WHERE request_id = %s
                    UNION ALL
                    SELECT 1 FROM fw039_review_results
                    WHERE request_id = %s
                ) AS combined
                """,
                (request_id, request_id),
            )
            row = await cursor.fetchone()
            return int(row["total"]) if row else 0
async def _list_results(
    request_id: str,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    columns = [
        "request_id", "message_id", "row_number", "ticket_id",
        "instance_id", "ticket_no", "ticket_type", "ticket_center",
        "title", "work_type", "app_system", "matched_keyword",
        "primary_category", "secondary_category", "screening_condition",
        "required_fields", "missing_fields", "information_complete",
        "operation_party", "assignee", "review_result", "reason",
        "source_sheet", "created_at", "updated_at",
    ]
    col_str = ", ".join(columns)
    async with get_db2_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(
                f"""
                SELECT {col_str}, table_code
                FROM (
                    SELECT 'FW038' AS table_code, {col_str}
                    FROM fw038_review_results
                    WHERE request_id = %s
                    UNION ALL
                    SELECT 'FW039' AS table_code, {col_str}
                    FROM fw039_review_results
                    WHERE request_id = %s
                ) AS combined
                ORDER BY row_number
                LIMIT %s OFFSET %s
                """,
                (request_id, request_id, limit, offset),
            )
            rows = await cursor.fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        for key in ("required_fields", "missing_fields"):
            try:
                item[key] = json.loads(item.get(key) or "[]")
            except json.JSONDecodeError:
                item[key] = []
        item["information_complete"] = bool(item.get("information_complete"))
        item["createdAt"] = _iso(item.pop("created_at", None))
        item["updatedAt"] = _iso(item.pop("updated_at", None))
        results.append(item)
    return results


@router.post("/formatExcelJson", response_model=None)
async def format_excel_json(file: UploadFile = File(...)):
    if not file.filename:
        return FailureResponse(message="请上传 Excel 文件")

    safe_filename = os.path.basename(file.filename)
    if not safe_filename.lower().endswith((".xlsx", ".xlsm")):
        return FailureResponse(message=f"文件《{safe_filename}》不是 .xlsx/.xlsm 格式")

    excel_bytes = await file.read()
    if not excel_bytes:
        return FailureResponse(message=f"文件《{safe_filename}》为空")

    async def event_stream():
        record: ReviewResultRecord | None = None
        combined: dict[str, Any] = {"metadata": {}, "tickets": []}
        try:
            formatter = ExcelSkillJsonFormatter()
            async for event in formatter.stream_excel_batches(excel_bytes, safe_filename, batch_size=5):
                if event["type"] == "start":
                    combined["metadata"] = event["metadata"]
                    record = ReviewResultRecord(
                        table_name="环境工单预审结果",
                        source_file=safe_filename,
                        source_file_data=excel_bytes,
                        row_count=0,
                        result_json=combined,
                    )
                    await record.save()
                    yield _sse("start", {**event, "resultId": record.id})
                    continue

                batch_tickets = event["tickets"]
                combined["metadata"] = event["metadata"]
                combined["tickets"].extend(batch_tickets)
                if record is None:
                    raise RuntimeError("预审结果记录尚未创建")

                # Commit first, then notify the browser: every received batch is durable.
                await record.update_result(combined, len(combined["tickets"]))
                yield _sse("batch", {
                    **event,
                    "resultId": record.id,
                    "savedRows": len(combined["tickets"]),
                })

            if record is None:
                raise RuntimeError("Excel 解析未产生结果")
            yield _sse("complete", {
                "resultId": record.id,
                "tableName": record.table_name,
                "sourceFile": record.source_file,
                "rowCount": len(combined["tickets"]),
                "createdAt": record.created_at.isoformat(),
                "metadata": combined["metadata"],
            })
        except Exception as exc:
            logger.exception("Excel 流式预审失败: %s", exc)
            yield _sse("error", {"message": f"Excel 预审失败: {exc}", "resultId": record.id if record else None})

    return StreamingResponse(
        _detached_sse(event_stream()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
@router.get("/reviewResults/latest")
async def get_latest_review_result() -> BaseResponse:
    try:
        record = await ReviewResultRecord.get_latest()
    except Exception as exc:
        logger.exception("查询最新预审结果失败: %s", exc)
        return FailureResponse(message=f"查询最新预审结果失败: {exc}")
    return SuccessResponse(data=_result_detail(record) if record else None)


@router.get("/reviewResults")
async def list_review_results(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
) -> BaseResponse:
    try:
        total = await ReviewResultRecord.count()
        records = await ReviewResultRecord.list_page(limit=limit, offset=(page - 1) * limit)
    except Exception as exc:
        logger.exception("查询预审历史失败: %s", exc)
        return FailureResponse(message=f"查询预审历史失败: {exc}")

    return SuccessResponse(data={
        "total": total,
        "page": page,
        "limit": limit,
        "items": [
            {
                "resultId": record.id,
                "tableName": record.table_name,
                "sourceFile": record.source_file,
                "rowCount": record.row_count,
                "createdAt": record.created_at.isoformat(),
            }
            for record in records
        ],
    })


@router.get("/reviewResults/{result_id}")
async def get_review_result(result_id: int) -> BaseResponse:
    try:
        record = await ReviewResultRecord.get_by_id(result_id)
    except Exception as exc:
        logger.exception("查询预审结果失败: %s", exc)
        return FailureResponse(message=f"查询预审结果失败: {exc}")
    if not record:
        return FailureResponse(message="预审结果不存在")
    return SuccessResponse(data=_result_detail(record))


@router.get("/reviewResults/{result_id}/download", response_model=None)
async def download_review_result(result_id: int, background_tasks: BackgroundTasks):
    record = await ReviewResultRecord.get_with_file_by_id(result_id)
    if not record:
        return FailureResponse(message="预审结果不存在")

    original_suffix = ".xlsm" if record.source_file.lower().endswith(".xlsm") else ".xlsx"
    fd, tmp_path = tempfile.mkstemp(suffix=original_suffix, prefix="ticket_review_history_")
    os.close(fd)
    try:
        if record.source_file_data:
            append_review_to_source_xlsx(
                record.source_file_data,
                record.result_json,
                tmp_path,
                keep_vba=original_suffix == ".xlsm",
            )
        else:
            # Old records created before source-file persistence remain downloadable.
            ticket_review_to_xlsx(record.result_json, output_path=tmp_path)
        base_name = os.path.splitext(os.path.basename(record.source_file))[0] or "环境工单"
        filename = f"{base_name}_预审结果{original_suffix}"
        background_tasks.add_task(os.unlink, tmp_path)
        media_type = (
            "application/vnd.ms-excel.sheet.macroEnabled.12"
            if original_suffix == ".xlsm"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        return FileResponse(path=tmp_path, filename=filename, media_type=media_type)
    except Exception as exc:
        logger.exception("历史预审结果导出失败: %s", exc)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return FailureResponse(message=f"历史预审结果导出失败: {exc}")


@router.post("/exportReviewExcel", response_model=None)
async def export_review_excel(background_tasks: BackgroundTasks, body: dict) -> FileResponse:
    review_data = body.get("json", {})
    if isinstance(review_data, str):
        try:
            review_data = json.loads(review_data)
        except json.JSONDecodeError as exc:
            return FailureResponse(message=f"json 字段不是合法 JSON: {exc}")
    if not isinstance(review_data, dict) or "tickets" not in review_data:
        return FailureResponse(message="json 内容缺少 tickets 字段")

    fd, tmp_path = tempfile.mkstemp(suffix=".xlsx", prefix="ticket_review_")
    os.close(fd)
    try:
        ticket_review_to_xlsx(review_data, output_path=tmp_path)
        source_file = review_data.get("metadata", {}).get("source_file", "")
        filename = f"{os.path.splitext(os.path.basename(source_file))[0]}_预审结果.xlsx" if source_file else "预审结果.xlsx"
        background_tasks.add_task(os.unlink, tmp_path)
        return FileResponse(
            path=tmp_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as exc:
        logger.exception("预审结果导出 Excel 失败: %s", exc)
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return FailureResponse(message=f"导出 Excel 失败: {exc}")
