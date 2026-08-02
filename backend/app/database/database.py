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
    # TODO: create tables / run migrations
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
