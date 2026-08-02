"""Generic helpers."""
import uuid
from datetime import datetime, timezone


def new_id(prefix: str = "") -> str:
    uid = uuid.uuid4().hex[:12]
    return f"{prefix}_{uid}" if prefix else uid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
