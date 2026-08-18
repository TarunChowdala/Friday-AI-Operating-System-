"""SQLAlchemy async engine / session (stub)."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

cfg = get_settings()
engine = create_async_engine(cfg.DATABASE_URL, echo=cfg.DEBUG)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    # Import models so their tables register on Base.metadata before create_all
    from app.database import models  # noqa: F401
    from sqlalchemy import text

    async with engine.begin() as conn:
        # Drop legacy stub tables from the earlier sqlite-era schema
        await conn.execute(text("DROP TABLE IF EXISTS conversations CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS memories CASCADE"))
        await conn.run_sync(Base.metadata.create_all)

    # Seed a default single-user row for local Friday
    async with SessionLocal() as session:
        from app.database.crud import get_or_create_default_user

        await get_or_create_default_user(session)
