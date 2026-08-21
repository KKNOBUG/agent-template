from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from configure import PROJECT_CONFIG

_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_database() -> None:
    """FastAPI lifespan 启动时调用，创建 engine 和 session factory 单例。"""
    global _engine, _async_session_factory
    _engine = create_async_engine(
        PROJECT_CONFIG.IDE_DATABASE_URL,
        echo=PROJECT_CONFIG.IDE_DATABASE_ECHO,
        pool_size=5,
        max_overflow=10,
    )
    _async_session_factory = async_sessionmaker(_engine, expire_on_commit=False)


def is_database_initialized() -> bool:
    return _engine is not None and _async_session_factory is not None


async def close_database() -> None:
    """FastAPI lifespan 关闭时调用，释放连接池。"""
    global _engine, _async_session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    global _async_session_factory
    if _async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    async with _async_session_factory() as session:
        yield session
