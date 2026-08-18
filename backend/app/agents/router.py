"""Routes tasks to the right agent — deterministic first, LLM only when ambiguous."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.core.logger import get_logger
from app.core.llm import get_llm

from app.agents.coder import CoderAgent
from app.agents.critic import CriticAgent
from app.agents.executor import ExecutorAgent
from app.agents.planner import PlannerAgent
from app.agents.researcher import ResearcherAgent

logger = get_logger(__name__)

_EXEC_RE = re.compile(
    r"\b("
    r"open|launch|start|close|quit|kill|"
    r"play|pause|resume|mute|unmute|volume|"
    r"type|write|save|click|focus|"
    r"screenshot|clipboard|terminal|run command|"
    r"youtube|notepad|chrome|browser|spotify"
    r")\b",
    re.I,
)
_SEARCH_IN_BROWSER_RE = re.compile(
    r"\b(search|google|look up|open)\b.*\b(chrome|browser|google)\b"
    r"|\b(chrome|browser)\b.*\b(search|google|look up)\b"
    r"|\bopen\b.*\b(same|that|this)\b.*\b(chrome|browser)\b"
    r"|\b(same|that)\b.*\b(news|link|page|result).*\b(chrome|browser|open)\b"
    r"|\bsearch\b.*\bin chrome\b",
    re.I,
)
_RESEARCH_RE = re.compile(
    r"\b("
    r"news|latest|today'?s|current|who won|stock price|weather|"
    r"what(?:'s| is) happening|look up|search for|find out|"
    r"recent (news|updates)|cricket|bcci"
    r")\b",
    re.I,
)
_GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|jarvis|good morning|good evening|good afternoon|"
    r"how are you|what'?s up|thanks|thank you|ok|okay|yeah|yes|no|alright)"
    r"(?:\s+\w+){0,3}\s*[.!]?\s*$",
    re.I,
)
_CODE_RE = re.compile(
    r"\b(code|refactor|debug|function|typescript|python|bug|compile)\b", re.I
)


def _deterministic_route(task: str) -> Optional[str]:
    """Fast path for obvious intents. None → fall back to LLM router."""
    t = (task or "").strip()
    if not t:
        return "planner"

    if _GREETING_RE.match(t):
        return "planner"

    # Desktop / browser *actions* beat pure research
    if _SEARCH_IN_BROWSER_RE.search(t):
        return "executor"
    if re.search(r"\b(write|type)\b.*\b(notepad|editor|document)\b", t, re.I):
        return "executor"
    if re.search(r"\b(notepad|editor)\b.*\b(write|type)\b", t, re.I):
        return "executor"
    if re.search(r"\b(save)\b.*\b(it|file|document|notepad)\b", t, re.I):
        return "executor"
    if re.search(
        r"\b(pause|resume|play|next|previous|mute|unmute)\b.*\b(youtube|video|song|music|track)?\b",
        t,
        re.I,
    ):
        return "executor"
    if re.search(r"\b(open|launch)\b.+\b(notepad|chrome|terminal|spotify|youtube|code)\b", t, re.I):
        return "executor"
    if re.search(r"\b(volume|screenshot|clipboard)\b", t, re.I):
        return "executor"

    # Pure info / news (no chrome/open action)
    if _RESEARCH_RE.search(t) and not _EXEC_RE.search(t):
        return "researcher"
    if re.search(r"\b(what is|who is|when did|how many)\b", t, re.I) and _RESEARCH_RE.search(t):
        return "researcher"

    if _CODE_RE.search(t) and not _EXEC_RE.search(t):
        return "coder"

    # Clear system verbs without browser-search ambiguity
    if re.match(
        r"^\s*(open|launch|play|pause|resume|mute|unmute|type|write|save)\b",
        t,
        re.I,
    ):
        return "executor"

    return None


class AgentRouter:
    def __init__(self) -> None:
        self.llm = get_llm(temperature=0.0)

        self.agents = {
            "planner": PlannerAgent(),
            "researcher": ResearcherAgent(),
            "coder": CoderAgent(),
            "executor": ExecutorAgent(),
            "critic": CriticAgent(),
        }

        prompt = PromptTemplate.from_template(
            "You are the central routing brain for JARVIS.\n"
            "Pick ONE agent for the user task.\n\n"
            "Rules:\n"
            "- planner: casual chat, greetings, opinions, clarification, 'what did you open?' without a new action.\n"
            "- executor: desktop/browser ACTIONS — open app/URL, search IN chrome, play/pause media, type/write/save in notepad, volume, screenshot, clipboard, terminal.\n"
            "  Follow-ups like 'open the same in chrome', 'search that in browser', 'write X in notepad' → executor.\n"
            "- researcher: factual/news questions answered by web search (NOT opening Chrome).\n"
            "- coder: writing/debugging code.\n"
            "- critic: code review only.\n\n"
            "Recent context (may be empty):\n{context}\n\n"
            "Task: {task}\n\n"
            "Respond with exactly ONE word: planner|executor|researcher|coder|critic"
        )
        self.router_chain = prompt | self.llm | StrOutputParser()

    async def route(
        self, task: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Deterministic route when obvious; otherwise one LLM classify call."""
        fast = _deterministic_route(task)
        if fast and fast in self.agents:
            logger.info("⏱️ [LATENCY] Router (deterministic → %s): 0.000s", fast)
            logger.info("Deterministic routed task to: %s", fast)
            return fast

        context_bits: list[str] = []
        if context:
            for m in (context.get("recent_messages") or [])[-6:]:
                role = m.get("role", "")
                content = (m.get("content") or "")[:120]
                if content:
                    context_bits.append(f"{role}: {content}")
            focused = context.get("focused") or {}
            if focused:
                context_bits.append(
                    f"focused: {focused.get('kind')}/{focused.get('name')} "
                    f"q={focused.get('query') or '-'}"
                )
        ctx = "\n".join(context_bits) if context_bits else "(none)"

        try:
            decision = await self.router_chain.ainvoke({"task": task, "context": ctx})
            decision = decision.strip().lower().split()[0].strip(".,")
            logger.info("LLM routed task to: %s", decision)
            if decision in self.agents:
                return decision
            logger.warning("LLM returned invalid agent '%s', falling back to planner", decision)
            return "planner"
        except Exception as e:
            logger.error("LLM routing failed: %s", e)
            return "planner"

    async def dispatch(self, agent_name: str, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        agent = self.agents.get(agent_name) or self.agents["planner"]
        return await agent.run(task, context)

    async def stream_dispatch(self, agent_name: str, task: str, context: Dict[str, Any]):
        agent = self.agents.get(agent_name) or self.agents["planner"]
        if not hasattr(agent, "stream"):
            result = await agent.run(task, context)
            yield result.get("result", "")
            return
        async for chunk in agent.stream(task, context):
            yield chunk
