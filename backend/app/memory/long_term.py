"""Persistent long-term memory store (stub)."""
from typing import Dict, List

from app.models.memory import MemoryItem


class LongTermMemory:
    def __init__(self) -> None:
        self._items: Dict[str, MemoryItem] = {}

    async def add(self, item: MemoryItem) -> None:
        self._items[item.id] = item

    async def get(self, item_id: str) -> MemoryItem | None:
        return self._items.get(item_id)

    async def list_all(self) -> List[MemoryItem]:
        return list(self._items.values())

    async def delete(self, item_id: str) -> bool:
        return self._items.pop(item_id, None) is not None
