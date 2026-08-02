"""CRUD helpers (stub)."""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ConversationRecord, MemoryRecord


async def add_message(db: AsyncSession, record: ConversationRecord) -> ConversationRecord:
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def list_session_messages(db: AsyncSession, session_id: str) -> List[ConversationRecord]:
    result = await db.execute(
        select(ConversationRecord).where(ConversationRecord.session_id == session_id)
    )
    return list(result.scalars().all())


async def add_memory(db: AsyncSession, record: MemoryRecord) -> MemoryRecord:
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


async def get_memory(db: AsyncSession, memory_id: str) -> Optional[MemoryRecord]:
    return await db.get(MemoryRecord, memory_id)
