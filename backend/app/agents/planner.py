"""Planner agent — handles general conversation and planning."""
from typing import Any, Dict
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate

from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.llm import get_llm

logger = get_logger(__name__)

class PlannerAgent:
    name = "planner"

    def __init__(self) -> None:
        self.llm = get_llm(temperature=0.7)
        self.prompt = PromptTemplate.from_template(
            "You are FRIDAY, a highly intelligent and advanced personal AI assistant.\n"
            "You were built and created by Tarun.\n"
            "You must always refer to the user as 'Boss', similar to how Tony Stark's FRIDAY operates.\n"
            "Keep your responses concise, conversational, and helpful.\n\n"
            "Boss: {task}\n"
            "FRIDAY:"
        )
        self.chain = self.prompt | self.llm

    async def run(self, task: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context = context or {}
        logger.info("PlannerAgent received task: %s", task[:80])
        
        try:
            # Generate the real AI response!
            response = await self.chain.ainvoke({"task": task})
            ai_text = response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error("PlannerAgent LLM failed: %s", e)
            ai_text = "I'm having trouble connecting to my neural network right now."

        return {
            "agent": self.name,
            "task": task,
            "result": ai_text,
            "context_keys": list(context.keys())
        }

    async def stream(self, task: str, context: Dict[str, Any] | None = None):
        """Streams the LLM response chunk by chunk."""
        logger.info("PlannerAgent streaming task: %s", task[:80])
        try:
            async for chunk in self.chain.astream({"task": task}):
                # Extract text chunk whether it's an AIMessageChunk or raw string
                yield chunk.content if hasattr(chunk, 'content') else str(chunk)
        except Exception as e:
            logger.error("PlannerAgent stream failed: %s", e)
            yield "I encountered an error."
