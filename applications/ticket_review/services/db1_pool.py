from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiomysql

from configure import PROJECT_CONFIG

_db1_pool: aiomysql.Pool | None = None


async def init_db1_pool() -> None:
    """Initialize the shared pool for the department directory database."""
    global _db1_pool
    if _db1_pool is not None:
        return
    _db1_pool = await aiomysql.create_pool(
        host=PROJECT_CONFIG.TICKET_DB1_HOST,
        port=PROJECT_CONFIG.TICKET_DB1_PORT,
        user=PROJECT_CONFIG.TICKET_DB1_USER,
        password=PROJECT_CONFIG.TICKET_DB1_PASSWORD,
        db=PROJECT_CONFIG.TICKET_DB1_NAME,
        charset="utf8mb4",
        autocommit=False,
        minsize=PROJECT_CONFIG.TICKET_DB1_POOL_MIN_SIZE,
        maxsize=PROJECT_CONFIG.TICKET_DB1_POOL_MAX_SIZE,
        connect_timeout=PROJECT_CONFIG.TICKET_DB1_CONNECT_TIMEOUT,
        pool_recycle=1800,
    )


async def close_db1_pool() -> None:
    """Close the department database pool and all of its connections."""
    global _db1_pool
    if _db1_pool is None:
        return
    _db1_pool.close()
    await _db1_pool.wait_closed()
    _db1_pool = None


def get_db1_pool() -> aiomysql.Pool:
    if _db1_pool is None:
        raise RuntimeError("DB1 pool is not initialized. Call init_db1_pool() first.")
    return _db1_pool


def is_db1_pool_initialized() -> bool:
    return _db1_pool is not None


@asynccontextmanager
async def get_db1_connection() -> AsyncGenerator[aiomysql.Connection, None]:
    """Acquire DB1 connection inside a read-only transaction and release it safely."""
    pool = get_db1_pool()
    async with pool.acquire() as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("START TRANSACTION READ ONLY")
        try:
            yield connection
        finally:
            # Never return an active transaction to the shared pool.
            await connection.rollback()


@asynccontextmanager
async def get_db1_cursor() -> AsyncGenerator[aiomysql.DictCursor, None]:
    """Acquire a dictionary cursor for parameterized read-only queries."""
    async with get_db1_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            yield cursor
