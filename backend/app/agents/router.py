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
from app.agents.browser_executor import BrowserExecutorAgent
from app.agents.desktop_context_executor import DesktopContextExecutorAgent
from app.agents.desktop_executor import DesktopExecutorAgent
from app.agents.media_executor import MediaExecutorAgent
from app.agents.planner import PlannerAgent
from app.agents.researcher import ResearcherAgent
from app.agents.system_executor import SystemExecutorAgent

logger = get_logger(__name__)

_EXEC_RE = re.compile(
    r"\b("
    r"open|launch|start|close|quit|kill|"
    r"play|pause|resume|mute|unmute|volume|"
    r"type|write|save|click|focus|"
    r"screenshot|clipboard|terminal|run command|"
    r"system status|ram|storage|disk|cache|cpu|uptime|battery|clean cache|"
    r"youtube|notepad|chrome|browser|spotify|camera|webcam|photo|"
    r"delete|remove"
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

_SYSTEM_RE = re.compile(
    r"\b("
    r"terminal|run command|shell|volume|system status|ram|storage|disk|cache|cpu|uptime|battery|clean cache|clean tmp"
    r")\b",
    re.I,
)
_FILE_RE = re.compile(r"\b(delete|remove)\b", re.I)
_MEDIA_RE = re.compile(
    r"\b(pause|resume|play|next|previous|mute|unmute)\b.*\b(youtube|video|song|music|track)?\b",
    re.I,
)
_DESKTOP_RE = re.compile(
    r"\b(write|type|save|screenshot|clipboard|notepad|editor|document|focus|switch|close this|close app|close window|kill process)\b",
    re.I,
)
_APP_LAUNCH_RE = re.compile(
    r"\b(open|launch)\b.+\b(notepad|terminal|spotify|code|editor|camera|webcam)\b",
    re.I,
)
_CAMERA_RE = re.compile(
    r"\b("
    r"open camera|close camera|launch camera|"
    r"take (a )?photo|click (a )?photo|capture (a )?(photo|picture)|"
    r"take (a )?picture|click (a )?picture|"
    r"webcam"
    r")\b",
    re.I,
)
_DESKTOP_CONTEXT_RE = re.compile(
    r"\b("
    r"what app am i in|which app am i in|current window|focused window|focused app|"
    r"what('?s| is) open|open windows|list windows|what('?s| is) running|running apps|running processes|"
    r"what.{0,40}(apps?|processes) .{0,20}running|apps? .{0,20}running|"
    r"is \w[\w-]* running|\w[\w-]* is running|"
    r"what('?s| is) playing|is .+ open|is .+ running"
    r")\b",
    re.I,
)


def _deterministic_route(task: str) -> Optional[str]:
    """Fast path for obvious intents. None → fall back to LLM router."""
    t = (task or "").strip()
    if not t:
        return "planner"

    if _GREETING_RE.match(t):
        return "planner"

    # Desktop / browser *actions* beat pure research
    if _DESKTOP_CONTEXT_RE.search(t):
        return "desktop_context_executor"
    if _CAMERA_RE.search(t):
        return "desktop_executor"
    if _FILE_RE.search(t):
        return "system_executor"
    if _SEARCH_IN_BROWSER_RE.search(t):
        return "browser_executor"
    if re.search(r"\b(write|type)\b.*\b(notepad|editor|document)\b", t, re.I):
        return "desktop_executor"
    if re.search(r"\b(notepad|editor)\b.*\b(write|type)\b", t, re.I):
        return "desktop_executor"
    if re.search(r"\b(save)\b.*\b(it|file|document|notepad)\b", t, re.I):
        return "desktop_executor"
    if _MEDIA_RE.search(t):
        return "media_executor"
    if re.search(r"\b(focus|switch to|close|quit|kill process)\b", t, re.I):
        return "desktop_executor"
    if re.search(r"\b(open|launch)\b.+\b(chrome|youtube|browser)\b", t, re.I):
        return "browser_executor"
    if _APP_LAUNCH_RE.search(t) or _DESKTOP_RE.search(t):
        return "desktop_executor"
    if _SYSTEM_RE.search(t):
        return "system_executor"

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
        if re.match(r"^\s*(play|pause|resume|mute|unmute)\b", t, re.I):
            return "media_executor"
        if re.match(r"^\s*(type|write|save)\b", t, re.I):
            return "desktop_executor"
        return "desktop_executor"

    return None


class AgentRouter:
    def __init__(self) -> None:
        self.llm = get_llm(temperature=0.0)

        self.agents = {
            "planner": PlannerAgent(),
            "researcher": ResearcherAgent(),
            "coder": CoderAgent(),
            "system_executor": SystemExecutorAgent(),
            "browser_executor": BrowserExecutorAgent(),
            "media_executor": MediaExecutorAgent(),
            "desktop_executor": DesktopExecutorAgent(),
            "desktop_context_executor": DesktopContextExecutorAgent(),
            "critic": CriticAgent(),
        }

        prompt = PromptTemplate.from_template(
            "You are the central routing brain for JARVIS.\n"
            "Pick ONE agent for the user task.\n\n"
            "Rules:\n"
            "- planner: casual chat, greetings, opinions, clarification, 'what did you open?' without a new action.\n"
            "- system_executor: terminal commands, delete/list files in Downloads/Desktop, system status, ram/cpu/disk/cache, volume, maintenance/cleanup.\n"
            "- browser_executor: open URLs, search in chrome/browser/google, play YouTube, browser follow-ups like 'open the same in chrome'.\n"
            "- media_executor: pause/play/resume/next/previous/mute/unmute active media.\n"
            "- desktop_executor: open desktop apps, write/type/save in notepad/editor, clipboard, screenshot/screen analysis, focus windows, close apps/windows, kill a process, open/close camera, take a photo.\n"
            "- desktop_context_executor: read-only desktop awareness like current window, open windows, running apps, and what's playing.\n"
            "- researcher: factual/news questions answered by web search (NOT opening Chrome).\n"
            "- coder: writing/debugging code.\n"
            "- critic: code review only.\n\n"
            "Recent context (may be empty):\n{context}\n\n"
            "Task: {task}\n\n"
            "Respond with exactly ONE word: planner|system_executor|browser_executor|media_executor|desktop_executor|desktop_context_executor|researcher|coder|critic"
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
