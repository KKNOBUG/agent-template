from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiomysql

from applications.ticket_review.services.db2_pool import get_db2_connection


@dataclass
class ReviewResultRecord:
    """Latest Excel review record persisted with the shared DB2 pool."""

    table_name: str = "环境工单预审结果"
    source_file: str = ""
    source_file_data: bytes | None = None
    row_count: int = 0
    result_json: dict[str, Any] = field(default_factory=dict)
    id: int | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    async def save(self) -> None:
        """Persist the latest upload and remove all earlier Excel results atomically."""
        async with get_db2_connection() as connection:
            try:
                await connection.begin()
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO review_results (
                            table_name, source_file, source_file_data, row_count,
                            result_json, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            self.table_name,
                            self.source_file,
                            self.source_file_data,
                            self.row_count,
                            _dump_json(self.result_json),
                            self.created_at,
                            self.updated_at,
                        ),
                    )
                    self.id = int(cursor.lastrowid)
                    await cursor.execute(
                        "DELETE FROM review_results WHERE id <> %s",
                        (self.id,),
                    )
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise

    async def save_as_only_record(self) -> None:
        """Backward-compatible alias for saving the single latest Excel result."""
        await self.save()

    async def update_result(self, result_json: dict[str, Any], row_count: int) -> None:
        if self.id is None:
            raise RuntimeError("Cannot update an unsaved review result")

        updated_at = datetime.now()
        async with get_db2_connection() as connection:
            try:
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        """
                        UPDATE review_results
                        SET result_json = %s, row_count = %s, updated_at = %s
                        WHERE id = %s
                        """,
                        (_dump_json(result_json), row_count, updated_at, self.id),
                    )
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise

        self.result_json = result_json
        self.row_count = row_count
        self.updated_at = updated_at

    @classmethod
    async def count(cls) -> int:
        async with get_db2_connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT COUNT(*) FROM review_results")
                row = await cursor.fetchone()
        return int(row[0]) if row else 0

    @classmethod
    async def list_page(cls, limit: int, offset: int) -> list["ReviewResultRecord"]:
        rows = await cls._fetch_all(
            """
            SELECT id, table_name, source_file, row_count, result_json,
                   created_at, updated_at
            FROM review_results
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        return [cls._from_row(row) for row in rows]

    @classmethod
    async def get_latest(cls) -> "ReviewResultRecord | None":
        row = await cls._fetch_one(
            """
            SELECT id, table_name, source_file, row_count, result_json,
                   created_at, updated_at
            FROM review_results
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        )
        return cls._from_row(row) if row else None

    @classmethod
    async def get_by_id(cls, result_id: int) -> "ReviewResultRecord | None":
        row = await cls._fetch_one(
            """
            SELECT id, table_name, source_file, row_count, result_json,
                   created_at, updated_at
            FROM review_results
            WHERE id = %s
            """,
            (result_id,),
        )
        return cls._from_row(row) if row else None

    @classmethod
    async def get_with_file_by_id(cls, result_id: int) -> "ReviewResultRecord | None":
        row = await cls._fetch_one(
            """
            SELECT id, table_name, source_file, source_file_data, row_count,
                   result_json, created_at, updated_at
            FROM review_results
            WHERE id = %s
            """,
            (result_id,),
        )
        return cls._from_row(row) if row else None

    @classmethod
    async def _fetch_one(
        cls,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> dict[str, Any] | None:
        async with get_db2_connection() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, params)
                return await cursor.fetchone()

    @classmethod
    async def _fetch_all(
        cls,
        sql: str,
        params: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        async with get_db2_connection() as connection:
            async with connection.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, params)
                return list(await cursor.fetchall())

    @classmethod
    def _from_row(cls, row: dict[str, Any]) -> "ReviewResultRecord":
        return cls(
            id=int(row["id"]),
            table_name=str(row.get("table_name") or ""),
            source_file=str(row.get("source_file") or ""),
            source_file_data=row.get("source_file_data"),
            row_count=int(row.get("row_count") or 0),
            result_json=_load_json(row.get("result_json")),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def _dump_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, str):
        loaded = json.loads(value)
        if isinstance(loaded, dict):
            return loaded
    raise ValueError("review_results.result_json is not a JSON object")
