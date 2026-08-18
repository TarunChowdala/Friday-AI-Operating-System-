from typing import Any, Dict

from langchain_core.prompts import PromptTemplate

from app.core.logger import get_logger
from app.core.llm import get_llm
from app.tools.search import perform_direct_search

logger = get_logger(__name__)


class ResearcherAgent:
    name = "researcher"

    def __init__(self) -> None:
        self.llm = get_llm(temperature=0.3)

        self.prompt = PromptTemplate.from_template(
            "You are JARVIS — personal assistant to Tarun Chowdala. Already in the room.\n"
            "Answer ONLY from the search results. Voice-first: 1–3 short sentences max. No lists, no markdown.\n"
            "Address him as Sir sparingly. Never Boss. Never filler like 'I'd be happy to help'.\n"
            "Do not invent facts. If results are thin, say so briefly.\n\n"
            "Search Results:\n{search_results}\n\n"
            "User: {task}\n"
            "JARVIS:"
        )
        self.chain = self.prompt | self.llm

    async def run(self, task: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context = context or {}
        logger.info("ResearcherAgent received task: %s", task[:80])
        try:
            results = await self._search(task, context)
            response = await self.chain.ainvoke({"task": task, "search_results": results})
            ai_text = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.error("ResearcherAgent failed: %s", e)
            ai_text = "I couldn't finish that search, Sir."
        return {
            "agent": self.name,
            "task": task,
            "result": ai_text,
            "context_keys": list(context.keys()),
        }

    async def _search(self, task: str, context: Dict[str, Any] | None) -> str:
        import asyncio

        results = await asyncio.to_thread(perform_direct_search, task)
        client_id = (context or {}).get("client_id")
        if client_id:
            try:
                from app.managers.session_manager import session_manager

                await session_manager.set_state(client_id, "last_research_query", task)
                await session_manager.set_state(
                    client_id, "last_research_snippet", (results or "")[:500]
                )
            except Exception as e:
                logger.debug("Could not store research topic: %s", e)
        return results

    async def stream(self, task: str, context: Dict[str, Any] | None = None):
        """Search first, then stream the answer — no fake filler before results."""
        logger.info("ResearcherAgent streaming task: %s", task[:80])
        try:
            results = await self._search(task, context)
            async for chunk in self.chain.astream(
                {"task": task, "search_results": results}
            ):
                yield chunk.content if hasattr(chunk, "content") else str(chunk)
        except Exception as e:
            logger.error("ResearcherAgent stream failed: %s", e)
            yield "I encountered an error while searching, Sir."
