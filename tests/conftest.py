"""Shared pytest fixtures.

Tests that exercise the database (repositories/services) require a running
PostgreSQL instance and opt in via the `db_session` fixture. If the database
is not reachable those tests are skipped. Pure unit tests (e.g. localization)
run without any database connection.
"""

import asyncio

import pytest

from app.database.base import Base

TEST_DATABASE_URL = "postgresql+asyncpg://apple_bot:test_password@localhost:5432/apple_store_test"


def _probe_database() -> bool:
    """Return True if PostgreSQL is reachable."""
    try:
        import asyncpg

        async def _probe():
            dsn = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
            conn = await asyncpg.connect(dsn, timeout=2)
            await conn.close()

        asyncio.run(_probe())
        return True
    except Exception:
        return False


@pytest.fixture
async def db_session():
    """Database session for tests that need one. Skips if PostgreSQL is unavailable."""
    if not _probe_database():
        pytest.skip("PostgreSQL database not available")
        return

    from sqlalchemy.ext.asyncio import (
        async_sessionmaker,
        create_async_engine,
        AsyncSession,
    )

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Prepare schema for this test run
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with maker() as s:
        yield s
        await s.rollback()

    # Tear down schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()