"""Shared pytest fixtures for DB-backed service tests.

Timeline (and future) integration tests need a real async Postgres session.
We reuse the same database the Node/Drizzle side provisions (`DATABASE_URL`,
plain `postgresql://` scheme) and adapt it to the `postgresql+asyncpg://`
scheme this service's SQLAlchemy engine expects — mirroring the conversion
documented in `.env.example` and `replit.md`.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

import pytest
import pytest_asyncio


def _to_asyncpg_url(raw: str) -> str:
    if raw.startswith("postgresql+asyncpg://"):
        return raw
    parts = urlsplit(raw)
    scheme = "postgresql+asyncpg"
    # asyncpg doesn't understand libpq query params like sslmode= — drop them.
    return urlunsplit((scheme, parts.netloc, parts.path, "", parts.fragment))


_raw_url = os.environ.get("DATABASE_URL", "")
if _raw_url:
    os.environ["DATABASE_URL"] = _to_asyncpg_url(_raw_url)


@pytest_asyncio.fixture
async def db_session():
    """Yields an AsyncSession inside a transaction that is always rolled back.

    Uses a dedicated per-test engine (NullPool, no connection reuse across
    event loops) instead of the app's process-wide singleton engine — each
    pytest-asyncio test function gets its own event loop, and asyncpg
    connections cannot be reused across loops.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import get_settings

    engine = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            async with session_factory(bind=conn) as session:  # type: ignore[call-arg]
                try:
                    yield session
                finally:
                    await session.close()
                    await trans.rollback()
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True, scope="session")
def _require_database_url():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured — skipping DB-backed tests")
