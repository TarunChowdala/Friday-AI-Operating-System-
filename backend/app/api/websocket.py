"""WebSocket API routes."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logger import get_logger
from app.websocket.connection_manager import ConnectionManager

router = APIRouter()
logger = get_logger(__name__)
manager = ConnectionManager()


@router.websocket("/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            logger.debug("WS received: %s/%s %r", client_id, data.get("type", "unknown"), data)
            # TODO: route to voice/chat managers
            await manager.send(client_id, {"type": "ack", "payload": data})
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logger.info("WS disconnected: %s", client_id)
