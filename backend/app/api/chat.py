"""Chat endpoints."""
from fastapi import APIRouter, HTTPException

from app.core.dependencies import ConversationManagerDep
from app.core.logger import get_logger
from app.models.chat import ChatRequest, ChatResponse

router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=ChatResponse)
async def chat(payload: ChatRequest, manager: ConversationManagerDep):
    try:
        return await manager.handle_message(payload)
    except Exception as exc:
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/history/{session_id}")
async def history(session_id: str, manager: ConversationManagerDep):
    return await manager.get_history(session_id)
