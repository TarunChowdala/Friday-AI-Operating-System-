"""Vector similarity store (stub — swap for Chroma/FAISS)."""
from typing import List

from app.models.memory import MemoryItem


class VectorStore:
    def __init__(self) -> None:
        self._docs: List[MemoryItem] = []

    async def upsert(self, item: MemoryItem) -> None:
        self._docs = [d for d in self._docs if d.id != item.id]
        self._docs.append(item)

    async def search(self, query: str, top_k: int = 5) -> List[MemoryItem]:
        # TODO: real embeddings + similarity
        q = query.lower()
        scored = [d for d in self._docs if q in d.content.lower()]
        return scored[:top_k] or self._docs[:top_k]
