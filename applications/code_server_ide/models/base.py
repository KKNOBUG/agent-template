from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import inspect, update
from sqlmodel import SQLModel

from applications.code_server_ide.database import get_db_session


class AsyncSQLModelRecord(SQLModel):
    """Small async persistence helper shared by IDE SQLModel records."""

    def __init__(self, **data: Any) -> None:
        object.__setattr__(self, "_dirty_fields", set())
        super().__init__(**data)
        self._dirty_fields.update(data)

    def _ensure_dirty_fields(self) -> set[str]:
        dirty_fields = getattr(self, "_dirty_fields", None)
        if dirty_fields is None:
            dirty_fields = set()
            object.__setattr__(self, "_dirty_fields", dirty_fields)
        return dirty_fields

    async def save(self) -> None:
        async with get_db_session() as session:
            dirty_fields = self._ensure_dirty_fields()
            mapper = inspect(type(self))
            pk_values = {column.key: getattr(self, column.key) for column in mapper.primary_key}
            has_pk = bool(pk_values) and all(value is not None for value in pk_values.values())

            if has_pk:
                values = {
                    column.key: getattr(self, column.key)
                    for column in mapper.columns
                    if column.key in dirty_fields and column.key not in pk_values
                }
                if values:
                    where_clause = [column == pk_values[column.key] for column in mapper.primary_key]
                    await session.execute(update(type(self)).where(*where_clause).values(**values))
            else:
                session.add(self)
                await session.flush()

            await session.commit()
            dirty_fields.clear()

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        mapper = inspect(type(self), raiseerr=False)
        if mapper is not None and name in mapper.columns:
            dirty_fields = self._ensure_dirty_fields()
            dirty_fields.add(name)
            if name != "updated_at" and "updated_at" in mapper.columns:
                object.__setattr__(self, "updated_at", datetime.now())
                dirty_fields.add("updated_at")
