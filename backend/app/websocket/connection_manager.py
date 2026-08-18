"""Tracks active WebSocket connections and per-client interrupt flags."""
from __future__ import annotations

import asyncio
from typing import Dict

from fastapi import WebSocket

from app.core.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    _instance: "ConnectionManager | None" = None

    def __init__(self) -> None:
        self.active: Dict[str, WebSocket] = {}
        self._interrupt: Dict[str, asyncio.Event] = {}
        self._turn_tasks: Dict[str, asyncio.Task] = {}
        ConnectionManager._instance = self

    async def connect(self, client_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active[client_id] = websocket
        self._interrupt[client_id] = asyncio.Event()
        logger.info("WS connected: %s (total=%d)", client_id, len(self.active))

    def disconnect(self, client_id: str) -> None:
        self.request_interrupt(client_id)
        task = self._turn_tasks.pop(client_id, None)
        if task and not task.done():
            task.cancel()
        self.active.pop(client_id, None)
        self._interrupt.pop(client_id, None)
        logger.info("WS removed: %s (total=%d)", client_id, len(self.active))

    def interrupt_event(self, client_id: str) -> asyncio.Event:
        if client_id not in self._interrupt:
            self._interrupt[client_id] = asyncio.Event()
        return self._interrupt[client_id]

    def request_interrupt(self, client_id: str) -> None:
        ev = self._interrupt.get(client_id)
        if ev:
            ev.set()
        task = self._turn_tasks.get(client_id)
        if task and not task.done():
            task.cancel()
            logger.info("Interrupted active turn for %s", client_id)

    def clear_interrupt(self, client_id: str) -> None:
        ev = self._interrupt.get(client_id)
        if ev:
            ev.clear()

    def set_turn_task(self, client_id: str, task: asyncio.Task) -> None:
        old = self._turn_tasks.get(client_id)
        if old and not old.done():
            old.cancel()
        self._turn_tasks[client_id] = task

    def is_interrupted(self, client_id: str) -> bool:
        ev = self._interrupt.get(client_id)
        return bool(ev and ev.is_set())

    async def send(self, client_id: str, message: dict) -> None:
        ws = self.active.get(client_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning("Failed to send WS message to %s: %s", client_id, e)
                self.disconnect(client_id)

    async def broadcast(self, message: dict) -> None:
        for client_id in list(self.active):
            await self.send(client_id, message)
