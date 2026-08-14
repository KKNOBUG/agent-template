from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiomysql

from applications.ticket_review.services.db2_pool import get_db2_connection


@dataclass
class PushTaskRecord:
    request_id: str
    message_id: str
    push_time: datetime
    status: str
    total_records: int
    processed_records: int = 0
    passed_records: int = 0
    returned_records: int = 0
    manual_records: int = 0
    raw_payload: dict[str, Any] = field(default_factory=dict)
    result_json: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    lease_token: str | None = None
    heartbeat_at: datetime | None = None

    @classmethod
    async def create_or_get(
        cls,
        *,
        message_id: str,
        push_time: datetime,
        raw_payload: dict[str, Any],
        total_records: int,
    ) -> tuple["PushTaskRecord", bool]:
        existing = await cls.get_by_message_id(message_id)
        if existing:
            return existing, False

        request_id = uuid.uuid4().hex
        status = "PENDING" if total_records else "IGNORED"
        result_json = {}
        async with get_db2_connection() as connection:
            try:
                await connection.begin()
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO push_tasks (
                            request_id, message_id, push_time, status,
                            total_records, processed_records, raw_payload,
                            result_json, error_message, created_at, updated_at,
                            started_at, finished_at
                        ) VALUES (%s, %s, %s, %s, %s, 0, %s, %s, NULL,
                                  NOW(6), NOW(6), NULL, %s)
                        """,
                        (
                            request_id,
                            message_id,
                            push_time,
                            status,
                            total_records,
                            _dump_json(raw_payload),
                            _dump_json(result_json),
                            datetime.now() if status == "IGNORED" else None,
                        ),
                    )
                await connection.commit()
            except aiomysql.IntegrityError:
                await connection.rollback()
                existing = await cls.get_by_message_id(message_id)
                if existing:
                    return existing, False
                raise
            except Exception:
                await connection.rollback()
                raise

        created = await cls.get_by_request_id(request_id)
        if created is None:
            raise RuntimeError("push_tasks insert succeeded but the task cannot be reloaded")
        return created, True
    @classmethod
    async def claim_next(cls) -> "PushTaskRecord | None":
        lease_token = uuid.uuid4().hex
        async with get_db2_connection() as connection:
            try:
                await connection.begin()
                async with connection.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(
                        """
                        SELECT * FROM push_tasks
                        WHERE status = 'PENDING'
                        ORDER BY created_at, id
                        LIMIT 1 FOR UPDATE
                        """
                    )
                    row = await cursor.fetchone()
                    if not row:
                        await connection.commit()
                        return None
                    await cursor.execute(
                        """
                        UPDATE push_tasks
                        SET status = 'PROCESSING',
                            lease_token = %s,
                            heartbeat_at = NOW(6),
                            started_at = COALESCE(started_at, NOW(6)),
                            error_message = NULL,
                            updated_at = NOW(6)
                        WHERE id = %s AND status = 'PENDING'
                        """,
                        (lease_token, row["id"]),
                    )
                    if cursor.rowcount != 1:
                        await connection.rollback()
                        return None
                    row["lease_token"] = lease_token
                    row["heartbeat_at"] = datetime.now()
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise
        claimed = cls._from_row(row)
        claimed.status = "PROCESSING"
        claimed.lease_token = lease_token
        claimed.heartbeat_at = datetime.now()
        return claimed

    async def heartbeat(self) -> bool:
        changed = await self._execute(
            """
            UPDATE push_tasks
            SET heartbeat_at = NOW(6),
                updated_at = NOW(6)
            WHERE request_id = %s
              AND status = 'PROCESSING'
              AND lease_token = %s
            """,
            (self.request_id, self.lease_token),
        )
        return changed == 1

    async def save_progress(self, result_json: dict[str, Any], processed_records: int) -> None:
        updated_at = datetime.now()
        await self._update(
            """
            UPDATE push_tasks
            SET result_json = %s,
                processed_records = GREATEST(processed_records, %s),
                updated_at = NOW(6)
            WHERE request_id = %s AND status = 'PROCESSING' AND lease_token = %s
            """,
            (_dump_json(result_json), processed_records, self.request_id, self.lease_token),
        )
        self.result_json = result_json
        self.processed_records = max(self.processed_records, processed_records)
        self.updated_at = updated_at

    async def mark_success(self) -> None:
        finished_at = datetime.now()
        await self._update(
            """
            UPDATE push_tasks
            SET status = 'SUCCESS', processed_records = total_records,
                heartbeat_at = NULL, lease_token = NULL,
                finished_at = NOW(6), updated_at = NOW(6)
            WHERE request_id = %s AND status = 'PROCESSING' AND lease_token = %s
            """,
            (self.request_id, self.lease_token),
        )
        self.status = "SUCCESS"
        self.processed_records = self.total_records
        self.lease_token = None
        self.heartbeat_at = None
        self.finished_at = finished_at
        self.updated_at = finished_at

    async def mark_failed(self, message: str) -> None:
        finished_at = datetime.now()
        await self._update(
            """
            UPDATE push_tasks
            SET status = 'FAILED', error_message = %s,
                heartbeat_at = NULL, lease_token = NULL,
                finished_at = NOW(6), updated_at = NOW(6)
            WHERE request_id = %s AND status = 'PROCESSING' AND lease_token = %s
            """,
            (message[:65535], self.request_id, self.lease_token),
        )
        self.status = "FAILED"
        self.error_message = message
        self.lease_token = None
        self.heartbeat_at = None
        self.finished_at = finished_at
        self.updated_at = finished_at
    async def release_to_pending(self) -> None:
        await self._update(
            """
            UPDATE push_tasks
            SET status = 'PENDING', started_at = NULL,
                heartbeat_at = NULL, lease_token = NULL,
                updated_at = NOW(6)
            WHERE request_id = %s AND status = 'PROCESSING' AND lease_token = %s
            """,
            (self.request_id, self.lease_token),
        )
        self.status = "PENDING"
        self.started_at = None
        self.lease_token = None
        self.heartbeat_at = None

    @classmethod
    async def reset_stale(cls, stale_seconds: int) -> int:
        return await cls._execute(
            """
            UPDATE push_tasks
            SET status = 'PENDING',
                started_at = NULL,
                heartbeat_at = NULL,
                lease_token = NULL,
                updated_at = NOW(6)
            WHERE status = 'PROCESSING'
              AND COALESCE(heartbeat_at, updated_at) < TIMESTAMPADD(SECOND, -%s, NOW(6))
            """,
            (stale_seconds,),
        )

    @classmethod
    async def retry_failed_once(cls, delay_seconds: int) -> int:
        """失败任务等待指定时间后仅重新进入待处理状态一次。"""
        return await cls._execute(
            """
            UPDATE push_tasks
            SET status = 'PENDING',
                started_at = NULL,
                finished_at = NULL,
                heartbeat_at = NULL,
                lease_token = NULL,
                error_message = NULL,
                result_json = JSON_SET(
                    COALESCE(result_json, JSON_OBJECT()),
                    '$._system.retry_count',
                    COALESCE(
                        CAST(
                            JSON_UNQUOTE(
                                JSON_EXTRACT(
                                    result_json,
                                    '$._system.retry_count'
                                )
                            ) AS UNSIGNED
                        ),
                        0
                    ) + 1,
                    '$._system.retry_scheduled_at',
                    DATE_FORMAT(NOW(6), '%%Y-%%m-%%dT%%H:%%i:%%s.%%f')
                ),
                updated_at = NOW(6)
            WHERE status = 'FAILED'
              AND JSON_EXTRACT(result_json, '$._system.retry_count') IS NULL
              AND finished_at IS NOT NULL
              AND finished_at <= TIMESTAMPADD(
                    SECOND,
                    -%s,
                    NOW(6)
                  )
            """,
            (max(0, delay_seconds),),
        )

    retry_failed = retry_failed_once

    @classmethod
    async def cleanup(cls, retention_days: int) -> int:
        return await cls._execute(
            """
            DELETE FROM push_tasks
            WHERE created_at < TIMESTAMPADD(DAY, -%s, NOW(6))
            """,
            (retention_days,),
        )

    @classmethod
    async def count(cls) -> int:
        row = await cls._fetch_one("SELECT COUNT(*) AS total FROM push_tasks")
        return int(row["total"]) if row else 0

    @classmethod
    async def list_page(cls, limit: int, offset: int) -> list["PushTaskRecord"]:
        rows = await cls._fetch_all(
            """
            SELECT * FROM push_tasks
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        return [cls._from_row(row) for row in rows]

    @classmethod
    async def get_by_message_id(cls, message_id: str) -> "PushTaskRecord | None":
        row = await cls._fetch_one(
            "SELECT * FROM push_tasks WHERE message_id = %s LIMIT 1", (message_id,)
        )
        return cls._from_row(row) if row else None

    @classmethod
    async def get_by_request_id(cls, request_id: str) -> "PushTaskRecord | None":
        row = await cls._fetch_one(
            "SELECT * FROM push_tasks WHERE request_id = %s LIMIT 1", (request_id,)
        )
        return cls._from_row(row) if row else None
    #         data["rawPayload"] = self.raw_payload
    #         data["resultJson"] = self.result_json
    #     return data
    def summary(self, include_payload: bool = False) -> dict[str, Any]:
        data = {
            "requestId": self.request_id,
            "messageId": self.message_id,
            "pushTime": _iso(self.push_time),
            "status": self.status,
            "totalRecords": self.total_records,
            "processedRecords": self.processed_records,
            "passedRecords": self.passed_records,
            "returnedRecords": self.returned_records,
            "manualRecords": self.manual_records,
            "errorMessage": self.error_message,
            "createdAt": _iso(self.created_at),
            "updatedAt": _iso(self.updated_at),
            "startedAt": _iso(self.started_at),
            "finishedAt": _iso(self.finished_at),
            "heartbeatAt": _iso(self.heartbeat_at),
        }

        if include_payload:
            data["rawPayload"] = self.raw_payload
        return data

    async def _update(self, sql: str, params: tuple[Any, ...]) -> None:
        changed = await self._execute(sql, params)
        if changed != 1:
            raise RuntimeError(f"push task {self.request_id} was not updated")

    @classmethod
    async def _execute(cls, sql: str, params: tuple[Any, ...]) -> int:
        async with get_db2_connection() as connection:
            try:
                async with connection.cursor() as cursor:
                    await cursor.execute(sql, params)
                    changed = int(cursor.rowcount)
                await connection.commit()
                return changed
            except Exception:
                await connection.rollback()
                raise

    @classmethod
    async def _fetch_one(
        cls, sql: str, params: tuple[Any, ...] = ()
    ) -> dict[str, Any] | None:
        async with get_db2_connection() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, params)
                return await cursor.fetchone()

    @classmethod
    async def _fetch_all(
        cls, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        async with get_db2_connection() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, params)
                return list(await cursor.fetchall())

    @classmethod
    def _from_row(cls, row: dict[str, Any]) -> "PushTaskRecord":
        return cls(
            id=int(row["id"]),
            request_id=str(row["request_id"]),
            message_id=str(row["message_id"]),
            push_time=row["push_time"],
            status=str(row["status"]),
            total_records=int(row.get("total_records") or 0),
            processed_records=int(row.get("processed_records") or 0),
            passed_records=int(row.get("passed_records") or 0),
            returned_records=int(row.get("returned_records") or 0),
            manual_records=int(row.get("manual_records") or 0),
            raw_payload=_load_json(row.get("raw_payload")),
            result_json=_load_json(row.get("result_json")),
            error_message=row.get("error_message"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            started_at=row.get("started_at"),
            finished_at=row.get("finished_at"),
            lease_token=row.get("lease_token"),
            heartbeat_at=row.get("heartbeat_at"),
        )


def _dump_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load_json(value: Any) -> dict[str, Any]:
    if value in (None, "", b""):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    loaded = json.loads(value)
    return loaded if isinstance(loaded, dict) else {}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
