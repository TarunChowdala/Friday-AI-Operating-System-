"""Orchestrates chat turns: memory → agents → tools → reply."""
import uuid
from typing import Any, Dict, List

from app.core.logger import get_logger
from app.models.chat import ChatMessage, ChatRequest, ChatResponse

logger = get_logger(__name__)


class ConversationManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, List[ChatMessage]] = {}

    async def handle_message(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or str(uuid.uuid4())
        history = self._sessions.setdefault(session_id, [])
        history.append(ChatMessage(role="user", content=request.message))

        # TODO: MemoryManager → AgentManager → ToolManager → OllamaService
        reply = f"[stub] Received: {request.message}"
        history.append(ChatMessage(role="assistant", content=reply))
        logger.info("session=%s messages=%d", session_id, len(history))

        return ChatResponse(reply=reply, session_id=session_id)

    async def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        return [m.model_dump() for m in self._sessions.get(session_id, [])]
