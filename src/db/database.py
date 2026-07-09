# Created by Metrum AI for Solidigm

"""Database connection management for Sports Analytics Platform."""

import os
import logging
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from src.db.models import Base

logger = logging.getLogger(__name__)

DEFAULT_DB_HOST = os.getenv("DB_HOST", "localhost")
DEFAULT_DB_PORT = os.getenv("DB_PORT", "5432")
DEFAULT_DB_NAME = os.getenv("DB_NAME", "sports_analytics")
DEFAULT_DB_USER = os.getenv("DB_USER", "postgres")
DEFAULT_DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+asyncpg://{DEFAULT_DB_USER}:{DEFAULT_DB_PASSWORD}" f"@{DEFAULT_DB_HOST}:{DEFAULT_DB_PORT}/{DEFAULT_DB_NAME}",
)

DB_STATE = SimpleNamespace(engine=None, session_factory=None)


async def init_db():
    """Initialize database connection and create tables if needed."""
    logger.info("Connecting to database...")

    DB_STATE.engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    DB_STATE.session_factory = async_sessionmaker(
        DB_STATE.engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with DB_STATE.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized")


async def close_db():
    """Close database connection."""
    if DB_STATE.engine:
        await DB_STATE.engine.dispose()
        logger.info("Database connection closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    if DB_STATE.session_factory is None:
        await init_db()

    async with DB_STATE.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database session."""
    if DB_STATE.session_factory is None:
        await init_db()

    async with DB_STATE.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
