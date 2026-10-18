"""
Database session management.
Provides async engine and session factory for SQLAlchemy 2.0.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from config import get_settings

settings = get_settings()

# Create async engine.
# StaticPool is used for SQLite to allow shared in-memory DB in tests.
_engine_kwargs = {}
if settings.database_url.startswith("sqlite"):
    _engine_kwargs = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    **_engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


from typing import AsyncGenerator
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_session_context():
    """
    Async context manager for background services / coordinators outside FastAPI request cycle.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session.
    Automatically closes the session after the request.

    Usage:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Create all tables on startup if they don't exist and migrate missing columns.
    """
    from db.models import Base
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Non-destructive schema synchronization for SQLite
        if settings.database_url.startswith("sqlite"):
            try:
                cursor_res = await conn.execute(text("PRAGMA table_info(tasks)"))
                cols = [row[1] for row in cursor_res.fetchall()]
                if "approval_reason" not in cols:
                    await conn.execute(text("ALTER TABLE tasks ADD COLUMN approval_reason TEXT"))
                if "rejection_reason" not in cols:
                    await conn.execute(text("ALTER TABLE tasks ADD COLUMN rejection_reason TEXT"))
                if "approved_at" not in cols:
                    await conn.execute(text("ALTER TABLE tasks ADD COLUMN approved_at TIMESTAMP"))
                if "approved_by" not in cols:
                    await conn.execute(text("ALTER TABLE tasks ADD COLUMN approved_by VARCHAR(100)"))
            except Exception as exc:
                pass
