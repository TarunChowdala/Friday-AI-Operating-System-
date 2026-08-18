"""CRUD helpers for Friday persistent tables."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    ConversationMessage,
    EpisodicMemory,
    ExecutionHistory,
    SemanticMemory,
    Session,
    TaskQueueItem,
    User,
    UserPreference,
)


# ── Users ────────────────────────────────────────────────────────────────────

async def get_or_create_default_user(
    db: AsyncSession, display_name: str = "Tarun"
) -> User:
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(display_name=display_name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    return await db.get(User, user_id)


# ── Sessions ─────────────────────────────────────────────────────────────────

async def create_session(db: AsyncSession, user_id: uuid.UUID) -> Session:
    session = Session(user_id=user_id, status="ACTIVE")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> Optional[Session]:
    return await db.get(Session, session_id)


async def end_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    summary: Optional[str] = None,
    status: str = "ENDED",
) -> Optional[Session]:
    session = await db.get(Session, session_id)
    if not session:
        return None
    now = datetime.now(timezone.utc)
    session.status = status
    session.ended_at = now
    session.summary = summary
    started = session.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    session.duration_seconds = int((now - started).total_seconds())
    await db.commit()
    await db.refresh(session)
    return session


# ── Messages ─────────────────────────────────────────────────────────────────

async def add_message(
    db: AsyncSession,
    session_id: uuid.UUID,
    role: str,
    message: str,
    *,
    intent: Optional[str] = None,
    actions: Optional[list[dict[str, Any]]] = None,
    hitl: bool = False,
) -> ConversationMessage:
    row = ConversationMessage(
        session_id=session_id,
        role=role,
        message=message,
        intent=intent,
        actions=actions,
        hitl=hitl,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_session_messages(
    db: AsyncSession, session_id: uuid.UUID
) -> list[ConversationMessage]:
    result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.session_id == session_id)
        .order_by(ConversationMessage.created_at)
    )
    return list(result.scalars().all())


# ── Execution history ────────────────────────────────────────────────────────

async def add_execution(
    db: AsyncSession,
    session_id: uuid.UUID,
    tool_name: str,
    *,
    status: str = "success",
    intent: Optional[str] = None,
    decision: Optional[str] = None,
    reason: Optional[str] = None,
    execution_time_ms: Optional[int] = None,
    input_data: Optional[dict[str, Any]] = None,
    output_data: Optional[dict[str, Any]] = None,
    task_id: Optional[uuid.UUID] = None,
) -> ExecutionHistory:
    row = ExecutionHistory(
        session_id=session_id,
        task_id=task_id,
        tool_name=tool_name,
        intent=intent,
        decision=decision,
        reason=reason,
        status=status,
        execution_time_ms=execution_time_ms,
        input=input_data,
        output=output_data,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ── Preferences ──────────────────────────────────────────────────────────────

async def upsert_preference(
    db: AsyncSession, user_id: uuid.UUID, key: str, value: str
) -> UserPreference:
    result = await db.execute(
        select(UserPreference).where(
            UserPreference.user_id == user_id, UserPreference.key == key
        )
    )
    pref = result.scalar_one_or_none()
    if pref:
        pref.value = value
    else:
        pref = UserPreference(user_id=user_id, key=key, value=value)
        db.add(pref)
    await db.commit()
    await db.refresh(pref)
    return pref


async def get_preferences(db: AsyncSession, user_id: uuid.UUID) -> list[UserPreference]:
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    return list(result.scalars().all())


# ── Episodic memory ──────────────────────────────────────────────────────────

async def add_episodic_memory(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    summary: str,
    *,
    session_id: Optional[uuid.UUID] = None,
    tags: Optional[list[Any]] = None,
) -> EpisodicMemory:
    row = EpisodicMemory(
        user_id=user_id,
        session_id=session_id,
        title=title,
        summary=summary,
        tags=tags or [],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_recent_episodic_memories(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 5,
) -> list[EpisodicMemory]:
    """Newest-first episodic memories for wake suggestions / context."""
    result = await db.execute(
        select(EpisodicMemory)
        .where(EpisodicMemory.user_id == user_id)
        .order_by(EpisodicMemory.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ── Semantic memory ──────────────────────────────────────────────────────────

async def upsert_semantic_memory(
    db: AsyncSession,
    user_id: uuid.UUID,
    category: str,
    key: str,
    value: str,
    *,
    confidence: float = 0.5,
) -> SemanticMemory:
    result = await db.execute(
        select(SemanticMemory).where(
            SemanticMemory.user_id == user_id,
            SemanticMemory.category == category,
            SemanticMemory.key == key,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        row.value = value
        row.confidence = confidence
    else:
        row = SemanticMemory(
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            confidence=confidence,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_semantic_memories(
    db: AsyncSession, user_id: uuid.UUID, category: Optional[str] = None
) -> list[SemanticMemory]:
    stmt = select(SemanticMemory).where(SemanticMemory.user_id == user_id)
    if category:
        stmt = stmt.where(SemanticMemory.category == category)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── Task queue ───────────────────────────────────────────────────────────────

async def create_task(
    db: AsyncSession,
    user_id: uuid.UUID,
    task_name: str,
    *,
    session_id: Optional[uuid.UUID] = None,
) -> TaskQueueItem:
    row = TaskQueueItem(
        user_id=user_id,
        session_id=session_id,
        task_name=task_name,
        status="pending",
        progress=0.0,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_task(
    db: AsyncSession,
    task_id: uuid.UUID,
    *,
    status: Optional[str] = None,
    progress: Optional[float] = None,
    result: Optional[dict[str, Any]] = None,
    error: Optional[str] = None,
) -> Optional[TaskQueueItem]:
    row = await db.get(TaskQueueItem, task_id)
    if not row:
        return None
    if status is not None:
        row.status = status
    if progress is not None:
        row.progress = progress
    if result is not None:
        row.result = result
    if error is not None:
        row.error = error
    await db.commit()
    await db.refresh(row)
    return row


async def list_tasks(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: Optional[str] = None,
) -> list[TaskQueueItem]:
    stmt = select(TaskQueueItem).where(TaskQueueItem.user_id == user_id)
    if status:
        stmt = stmt.where(TaskQueueItem.status == status)
    stmt = stmt.order_by(TaskQueueItem.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
