from __future__ import annotations

import json
from typing import Any

import aiomysql

from applications.ticket_review.services.db2_pool import get_db2_connection


_TABLE_NAMES = {
    "FW038": "fw038_review_results",
    "FW039": "fw039_review_results",
}


class PushTicketReviewRecord:
    """Persist reviewed push records in their table-code-specific tables."""

    @classmethod
    async def save_batch_and_progress(
        cls,
        *,
        request_id: str,
        message_id: str,
        lease_token: str,
        tickets: list[dict[str, Any]],
        processed_records: int,
    ) -> None:
        if not lease_token:
            raise RuntimeError(f"Push task {request_id} has no lease token")

        grouped: dict[str, list[tuple[Any, ...]]] = {"FW038": [], "FW039": []}
        for ticket in tickets:
            if not isinstance(ticket, dict):
                raise ValueError("LLM ticket result must be an object")

            table_code = str(ticket.get("table_code") or "").strip().upper()
            if table_code not in grouped:
                raise ValueError(f"Unsupported result table_code: {table_code!r}")

            row_number = int(ticket.get("row_number") or 0)
            if row_number <= 0:
                raise ValueError("Ticket result is missing a valid row_number")

            grouped[table_code].append(
                (
                    request_id,
                    message_id,
                    row_number,
                    _text(ticket.get("ticket_id")),
                    _text(ticket.get("instance_id")),
                    _text(ticket.get("ticket_no")),
                    _text(ticket.get("ticket_type")),
                    _text(ticket.get("ticket_center")),
                    _text(ticket.get("title")),
                    _text(ticket.get("work_type")),
                    _text(ticket.get("app_system")),
                    _text(ticket.get("matched_keyword")),
                    _text(ticket.get("primary_category")),
                    _text(ticket.get("secondary_category")),
                    _text(ticket.get("screening_condition")),
                    _json_array(ticket.get("required_fields")),
                    _json_array(ticket.get("missing_fields")),
                    1 if ticket.get("information_complete") else 0,
                    _text(ticket.get("operation_party")),
                    _text(ticket.get("assignee")),
                    _text(ticket.get("review_result")),
                    _text(ticket.get("reason")),
                    _text(ticket.get("source_sheet")),
                )
            )

        async with get_db2_connection() as connection:
            try:
                await connection.begin()
                async with connection.cursor() as cursor:
                    for table_code, rows in grouped.items():
                        if not rows:
                            continue
                        await cursor.executemany(_upsert_sql(_TABLE_NAMES[table_code]), rows)

                    await cursor.execute(
                        """
                        UPDATE push_tasks
                        SET processed_records = GREATEST(processed_records, %s),
                            updated_at = NOW(6)
                        WHERE request_id = %s
                          AND status = 'PROCESSING'
                          AND lease_token = %s
                        """,
                        (processed_records, request_id, lease_token),
                    )
                    if cursor.rowcount != 1:
                        raise RuntimeError(
                            f"Push task {request_id} is no longer owned by this worker"
                        )
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise

    @classmethod
    async def count_by_request_id(cls, request_id: str) -> int:
        async with get_db2_connection() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT (
                        SELECT COUNT(*) FROM fw038_review_results
                        WHERE request_id = %s
                    ) + (
                        SELECT COUNT(*) FROM fw039_review_results
                        WHERE request_id = %s
                    ) AS total
                    """,
                    (request_id, request_id),
                )
                row = await cursor.fetchone()
                return int(row["total"] or 0) if row else 0

    @classmethod
    async def list_by_request_id(
        cls, request_id: str, limit: int, offset: int
    ) -> list[dict[str, Any]]:
        async with get_db2_connection() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    """
                    SELECT *
                    FROM (
                        SELECT 'FW038' AS table_code, r.*
                        FROM fw038_review_results r
                        WHERE r.request_id = %s
                        UNION ALL
                        SELECT 'FW039' AS table_code, r.*
                        FROM fw039_review_results r
                        WHERE r.request_id = %s
                    ) AS reviewed
                    ORDER BY row_number
                    LIMIT %s OFFSET %s
                    """,
                    (request_id, request_id, limit, offset),
                )
                rows = list(await cursor.fetchall())
        for row in rows:
            row["required_fields"] = _load_json_array(row.get("required_fields"))
            row["missing_fields"] = _load_json_array(row.get("missing_fields"))
            row["information_complete"] = bool(row.get("information_complete"))
        return rows


def _upsert_sql(table_name: str) -> str:
    return f"""
        INSERT INTO `{table_name}` (
            request_id, message_id, row_number, ticket_id, instance_id,
            ticket_no, ticket_type, ticket_center, title, work_type,
            app_system, matched_keyword, primary_category, secondary_category,
            screening_condition, required_fields, missing_fields,
            information_complete, operation_party, assignee, review_result,
            reason, source_sheet
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON DUPLICATE KEY UPDATE
            message_id = VALUES(message_id),
            ticket_id = VALUES(ticket_id),
            instance_id = VALUES(instance_id),
            ticket_no = VALUES(ticket_no),
            ticket_type = VALUES(ticket_type),
            ticket_center = VALUES(ticket_center),
            title = VALUES(title),
            work_type = VALUES(work_type),
            app_system = VALUES(app_system),
            matched_keyword = VALUES(matched_keyword),
            primary_category = VALUES(primary_category),
            secondary_category = VALUES(secondary_category),
            screening_condition = VALUES(screening_condition),
            required_fields = VALUES(required_fields),
            missing_fields = VALUES(missing_fields),
            information_complete = VALUES(information_complete),
            operation_party = VALUES(operation_party),
            assignee = VALUES(assignee),
            review_result = VALUES(review_result),
            reason = VALUES(reason),
            source_sheet = VALUES(source_sheet),
            updated_at = NOW(6)
    """


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _json_array(value: Any) -> str:
    return json.dumps(
        value if isinstance(value, list) else [],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _load_json_array(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, "", b""):
        return []
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    loaded = json.loads(value)
    return loaded if isinstance(loaded, list) else []
