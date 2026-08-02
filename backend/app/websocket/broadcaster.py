"""Broadcast helpers over ConnectionManager."""
from typing import Any, Dict

from app.websocket.connection_manager import ConnectionManager
from app.websocket.events import event


class Broadcaster:
    def __init__(self, manager: ConnectionManager) -> None:
        self.manager = manager

    async def emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        await self.manager.broadcast(event(event_type, payload))
