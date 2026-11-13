from typing import Any, Dict

from app.core.logger import get_logger
from app.core.llm import get_llm
from app.managers.session_manager import session_manager
import time

logger = get_logger(__name__)


class PlannerAgent:
    name = "planner"

    def __init__(self) -> None:
        self.llm = get_llm(purpose="default", temperature=0.7)

    async def run(self, task: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context = context or {}
        client_id = context.get("client_id", "default")

        messages = await session_manager.get_langchain_messages(client_id)
        logger.info("PlannerAgent received task with %d context messages", len(messages))

        try:
            response = await self.llm.ainvoke(messages)
            ai_text = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.error("PlannerAgent LLM failed: %s", e)
            ai_text = "I'm having trouble connecting to my neural network right now."

        return {
            "agent": self.name,
            "task": task,
            "result": ai_text,
            "context_keys": list(context.keys()),
        }

    async def stream(self, task: str, context: Dict[str, Any] | None = None):
        """Streams the LLM response chunk by chunk."""
        context = context or {}
        client_id = context.get("client_id", "default")

        messages = await session_manager.get_langchain_messages(client_id)
        logger.info("PlannerAgent streaming with %d context messages", len(messages))
        t0 = time.time()
        first = True

        try:
            async for chunk in self.llm.astream(messages):
                piece = chunk.content if hasattr(chunk, "content") else str(chunk)
                if isinstance(piece, list):
                    piece = "".join(
                        p if isinstance(p, str) else p.get("text", "") 
                        for p in piece if isinstance(p, (str, dict))
                    )
                if first and piece:
                    first = False
                    logger.info("⏱️ [LATENCY] Planner first token: %.3fs", time.time() - t0)
                if piece:
                    yield piece
            logger.info("⏱️ [LATENCY] Planner stream total: %.3fs", time.time() - t0)
        except Exception as e:
            logger.error("PlannerAgent stream failed: %s", e)
            try:
                from app.llms.factory import _make_ollama
                backup = _make_ollama(temperature=0.7, purpose="default")
                async for chunk in backup.astream(messages):
                    piece = chunk.content if hasattr(chunk, "content") else str(chunk)
                    if isinstance(piece, list):
                        piece = "".join(
                            p if isinstance(p, str) else p.get("text", "") 
                            for p in piece if isinstance(p, (str, dict))
                        )
                    if piece:
                        yield piece
                return
            except Exception as e2:
                logger.error("Planner emergency fallback failed: %s", e2)
            yield "I'm having trouble with the connection right now, Sir."
