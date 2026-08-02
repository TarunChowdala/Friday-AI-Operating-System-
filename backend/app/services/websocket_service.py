"""High-level WS publish helpers."""
from typing import Any, Dict, Optional

from app.websocket.broadcaster import Broadcaster
from app.websocket.connection_manager import ConnectionManager


class WebSocketService:
    def __init__(self, manager: Optional[ConnectionManager] = None) -> None:
        self.manager = manager or ConnectionManager()
        self.broadcaster = Broadcaster(self.manager)

    async def push(self, client_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        await self.manager.send(client_id, {"type": event_type, "payload": payload})

    async def broadcast(self, event_type: str, payload: Dict[str, Any]) -> None:
        await self.broadcaster.emit(event_type, payload)
