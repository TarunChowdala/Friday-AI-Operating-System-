"""Tracks active WebSocket connections."""
from typing import Dict

from fastapi import WebSocket

from app.core.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self.active: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active[client_id] = websocket
        logger.info("WS connected: %s (total=%d)", client_id, len(self.active))

    def disconnect(self, client_id: str) -> None:
        self.active.pop(client_id, None)
        logger.info("WS removed: %s (total=%d)", client_id, len(self.active))

    async def send(self, client_id: str, message: dict) -> None:
        ws = self.active.get(client_id)
        if ws:
            await ws.send_json(message)

    async def broadcast(self, message: dict) -> None:
        for client_id in list(self.active):
            await self.send(client_id, message)
