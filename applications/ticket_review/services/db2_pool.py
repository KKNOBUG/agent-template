from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiomysql

from applications.ticket_review.config import settings

_db2_pool: aiomysql.Pool | None = None


async def init_db2_pool() -> None:
    """Initialize the shared pool used for DB2 persistence and agent queries."""
    global _db2_pool
    if _db2_pool is not None:
        return
    _db2_pool = await aiomysql.create_pool(
        host=settings.db2_host,
        port=settings.db2_port,
        user=settings.db2_user,
        password=settings.db2_password,
        db=settings.db2_name,
        charset="utf8mb4",
        autocommit=False,
        minsize=settings.db2_pool_min_size,
        maxsize=settings.db2_pool_max_size,
        connect_timeout=settings.db2_connect_timeout,
        pool_recycle=1800,
    )


async def close_db2_pool() -> None:
    """Close the shared DB2 pool and all of its connections."""
    global _db2_pool
    if _db2_pool is None:
        return
    _db2_pool.close()
    await _db2_pool.wait_closed()
    _db2_pool = None


def get_db2_pool() -> aiomysql.Pool:
    if _db2_pool is None:
        raise RuntimeError("DB2 pool is not initialized. Call init_db2_pool() first.")
    return _db2_pool


def is_db2_pool_initialized() -> bool:
    return _db2_pool is not None


@asynccontextmanager
async def get_db2_connection() -> AsyncGenerator[aiomysql.Connection, None]:
    """Acquire and automatically release one DB2 connection."""
    pool = get_db2_pool()
    async with pool.acquire() as connection:
        try:
            yield connection
        finally:
            # DB2 uses autocommit=False. Never return a connection carrying an
            # unfinished read or write transaction back to the shared pool.
            await connection.rollback()


@asynccontextmanager
async def get_db2_cursor() -> AsyncGenerator[aiomysql.DictCursor, None]:
    """Acquire a dictionary cursor from the shared DB2 pool."""
    async with get_db2_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            yield cursor
