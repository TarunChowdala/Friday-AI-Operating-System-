"""Memory schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MemoryItem(BaseModel):
    id: str
    content: str
    kind: str = "fact"  # fact | preference | event | summary
    importance: float = 0.5
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = 5
    session_id: Optional[str] = None


class MemorySearchResponse(BaseModel):
    results: List[MemoryItem] = Field(default_factory=list)
