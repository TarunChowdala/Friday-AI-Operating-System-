from typing import Any, Dict
import time

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
            "Answer ONLY from the search results. Do not invent facts.\n"
            "Speak like a human colleague, not a news reader.\n"
            "DEFAULT: 1–3 short sentences. Then one suggestion or offer more detail "
            "('Want the full picture?').\n"
            "FULL DETAIL only if the user asked for details, everything, a full explanation, "
            "or to go deeper. Then you may use more sentences, still no markdown lists.\n"
            "Address him as Sir sparingly. Never Boss. Never filler like 'I'd be happy to help'.\n"
            "If results are thin, say so briefly.\n\n"
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
        import random
        logger.info("ResearcherAgent streaming task: %s", task[:80])
        
        # Yield immediate filler audio to mask latency
        fillers = [
            "Let me look into that, Sir. ",
            "Searching for that right now. ",
            "Just a moment, let me check the web. ",
            "Working on it, Sir. ",
            "Let me pull that up. ",
            "I'll find out for you, Sir. ",
            "One moment, running a search. ",
            "Scanning the web for that information. ",
            "Let's see what I can find. "
        ]
        yield random.choice(fillers)
        
        try:
            search_t0 = time.time()
            results = await self._search(task, context)
            logger.info(
                "⏱️ [LATENCY] Researcher search: %.3fs | hits=%d chars",
                time.time() - search_t0,
                len(results or ""),
            )
            llm_t0 = time.time()
            first = True
            async for chunk in self.chain.astream(
                {"task": task, "search_results": results}
            ):
                piece = chunk.content if hasattr(chunk, "content") else str(chunk)
                if isinstance(piece, list):
                    piece = "".join(
                        p if isinstance(p, str) else p.get("text", "") 
                        for p in piece if isinstance(p, (str, dict))
                    )
                if first and piece:
                    first = False
                    logger.info(
                        "⏱️ [LATENCY] Researcher first token: %.3fs",
                        time.time() - llm_t0,
                    )
                if piece:
                    yield piece
            logger.info(
                "⏱️ [LATENCY] Researcher LLM stream: %.3fs", time.time() - llm_t0
            )
        except Exception as e:
            logger.error("ResearcherAgent stream failed: %s", e)
            yield "I encountered an error while searching, Sir."
