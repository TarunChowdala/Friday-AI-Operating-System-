"""Facade over short-term, long-term, and vector memory."""
from typing import List, Optional

from app.memory.conversation_history import ConversationHistory
from app.memory.long_term import LongTermMemory
from app.memory.short_term import ShortTermMemory
from app.memory.vector_store import VectorStore
from app.models.memory import MemoryItem


class MemoryManager:
    def __init__(self) -> None:
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        self.vector = VectorStore()
        self.history = ConversationHistory()

    async def remember(self, item: MemoryItem) -> MemoryItem:
        await self.long_term.add(item)
        await self.vector.upsert(item)
        return item

    async def recall(self, query: str, top_k: int = 5, session_id: Optional[str] = None) -> List[MemoryItem]:
        _ = session_id
        return await self.vector.search(query, top_k=top_k)
