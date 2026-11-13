import re
import time
from typing import Any, Dict

from langchain_core.prompts import PromptTemplate

from app.core.logger import get_logger
from app.core.llm import get_llm
from app.tools.search import perform_direct_search

logger = get_logger(__name__)


def _is_conversational_or_unclear(text: str) -> bool:
    t = (text or "").lower().strip()
    if not t or len(t.split()) <= 1:
        return True
    if _is_followup(t):
        return False
    greetings = (
        "good morning", "good evening", "good afternoon", "good night",
        "how are you", "who are you", "what are you", "what is your name",
        "where are you", "can you hear me", "can you keep up",
        "just greeting", "just greet", "hello", "hey", "hi",
        "thank you", "thanks",
    )
    if any(g in t for g in greetings):
        return True
    if "jarvis" in t or "avis" in t:
        if any(w in t for w in ("who", "where", "can you", "are you", "chat", "keep up", "tweet", "greet")):
            return True
    return False


def _is_followup(text: str) -> bool:
    t = (text or "").lower().strip()
    followup_patterns = (
        r"\b(tell me more|go on|continue|full picture|full story|details?|explain further|elaborate)\b",
        r"\b(what happened|what else|why did|how did|who was|who is|what did)\b.*\b(he|she|they|it|that|the company|the ceo|him|her|investigation|findings)\b",
        r"^(yeah|yes|sure|ok|okay|yep|yup)\b",
        r"\b(that company|that ceo|that scandal|that incident|that person|the investigation)\b",
        r"\bwhat happened exactly\b",
    )
    return any(re.search(p, t) for p in followup_patterns)


class ResearcherAgent:
    name = "researcher"

    def __init__(self) -> None:
        self.llm = get_llm(temperature=0.3, purpose="research")

        self.prompt = PromptTemplate.from_template(
            "You are JARVIS — personal assistant to Tarun Chowdala. Already in the room.\n"
            "Answer the user accurately using the search results and conversation history. Do not invent facts.\n"
            "Speak like a human colleague, not a news reader.\n"
            "Tone & Style:\n"
            "- If the user is following up or asking for the full story / more detail (e.g. 'what happened exactly', 'tell me more'), provide a thorough, complete explanation in 3–5 spoken sentences. Do not offer 'want the full picture?' again if they just asked for it!\n"
            "- If this is a fresh topic, provide 1–3 short sentences, then offer more detail if relevant.\n"
            "- Address him as Sir sparingly. Never say 'I'd be happy to help'. No markdown lists or bullets.\n\n"
            "Recent Conversation:\n{recent_context}\n\n"
            "Search Results & Background:\n{search_results}\n\n"
            "User: {task}\n"
            "JARVIS:"
        )
        self.chain = self.prompt | self.llm

    async def _get_context_data(self, client_id: str | None, task: str) -> tuple[str, str, str]:
        """Returns (effective_search_query, recent_context_str, prior_snippet)."""
        if not client_id:
            return task, "(none)", ""
        try:
            from app.managers.session_manager import session_manager
            data = await session_manager.get_or_create(client_id)
            msgs = data.get("messages") or []
            bits = []
            for m in msgs[-6:]:
                role = "User" if m.get("role") == "user" else "JARVIS"
                content = (m.get("content") or "").replace("\n", " ").strip()
                if content:
                    bits.append(f"{role}: {content[:200]}")
            recent_context = "\n".join(bits) if bits else "(none)"

            state = data.get("current_state") or {}
            last_query = state.get("last_research_query") or ""
            last_snippet = state.get("last_research_snippet") or ""

            if last_query and _is_followup(task):
                cleaned_task = re.sub(r"^(yeah|yes|sure|ok|okay|yep|yup)[\s,]*", "", task, flags=re.I).strip()
                effective_query = f"{last_query} {cleaned_task}".strip()
                return effective_query, recent_context, last_snippet

            return task, recent_context, ""
        except Exception as e:
            logger.debug("Could not fetch session research context: %s", e)
            return task, "(none)", ""

    async def run(self, task: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        context = context or {}
        logger.info("ResearcherAgent received task: %s", task[:80])
        if _is_conversational_or_unclear(task):
            return {
                "agent": self.name,
                "task": task,
                "result": "I'm right here, Sir. Could you clarify what you'd like me to search for?",
                "context_keys": list(context.keys()),
            }

        client_id = context.get("client_id")
        search_query, recent_context, prior_snippet = await self._get_context_data(client_id, task)

        try:
            results = await self._search(search_query, context, record_task=task)
            full_search = f"Prior findings:\n{prior_snippet}\n\nLatest findings:\n{results}" if prior_snippet else results
            response = await self.chain.ainvoke({
                "task": task,
                "recent_context": recent_context,
                "search_results": full_search,
            })
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

    async def _search(self, query: str, context: Dict[str, Any] | None, record_task: str = "") -> str:
        import asyncio

        results = await asyncio.to_thread(perform_direct_search, query)
        client_id = (context or {}).get("client_id")
        if client_id:
            try:
                from app.managers.session_manager import session_manager
                store_key = record_task or query
                await session_manager.set_state(client_id, "last_research_query", store_key)
                await session_manager.set_state(
                    client_id, "last_research_snippet", (results or "")[:800]
                )
            except Exception as e:
                logger.debug("Could not store research topic: %s", e)
        return results

    async def stream(self, task: str, context: Dict[str, Any] | None = None):
        import random
        logger.info("ResearcherAgent streaming task: %s", task[:80])

        if _is_conversational_or_unclear(task):
            yield "I'm right here, Sir. Could you clarify what you'd like me to look up?"
            return

        client_id = (context or {}).get("client_id")
        search_query, recent_context, prior_snippet = await self._get_context_data(client_id, task)

        # Yield immediate filler audio to mask latency
        fillers = [
            "Let me look into that, Sir. ",
            "Searching for that right now. ",
            "Just a moment, let me check the details. ",
            "Working on it, Sir. ",
            "Let me pull up the details on that. ",
            "I'll find out for you, Sir. ",
            "One moment, checking that out. ",
        ]
        yield random.choice(fillers)

        try:
            search_t0 = time.time()
            results = await self._search(search_query, context, record_task=task if not prior_snippet else "")
            logger.info(
                "⏱️ [LATENCY] Researcher search: %.3fs (query='%s') | hits=%d chars",
                time.time() - search_t0,
                search_query[:60],
                len(results or ""),
            )
            full_search = f"Prior findings:\n{prior_snippet}\n\nLatest findings:\n{results}" if prior_snippet else results

            llm_t0 = time.time()
            first = True
            async for chunk in self.chain.astream({
                "task": task,
                "recent_context": recent_context,
                "search_results": full_search,
            }):
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
            try:
                from app.llms.factory import _make_ollama
                backup = _make_ollama(temperature=0.3, purpose="research")
                backup_chain = self.prompt | backup
                async for chunk in backup_chain.astream({
                    "task": task,
                    "recent_context": recent_context,
                    "search_results": full_search,
                }):
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
                logger.error("Researcher emergency fallback failed: %s", e2)
            yield "I couldn't complete that search right now, Sir."
