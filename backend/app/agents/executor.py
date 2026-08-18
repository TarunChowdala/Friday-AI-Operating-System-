"""Executor agent — runs system tools and speaks only verified outcomes."""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, AsyncIterator, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.logger import get_logger
from app.core.llm import get_llm
from app.tools.system_controls import (
    change_volume,
    open_application,
    open_url,
    search_google,
    play_youtube,
    run_terminal_command,
    media_control,
    clipboard_control,
    capture_screen_and_analyze,
    type_text,
    save_document,
)

logger = get_logger(__name__)

_EXECUTOR_SYSTEM = """You are JARVIS's system controller for Tarun (call him Sir only when natural).

Call exactly ONE tool via the API tool-calling interface.
Never put JSON inside the tool name.
Do NOT claim success in plain text — tools return the real outcome.

Workspace awareness:
- Use WORKSPACE STATE and RECENT CHAT below.
- "pause/resume/skip" after YouTube → media_control.
- "write/type …" with notepad focused → type_text (put the actual words in `text`).
- "save" → save_document.
- "open/search … in chrome" or "open the same/that news" → search_google (preferred) or open_url.
  For "same/that", use LAST RESEARCH TOPIC / recent chat — NEVER bare news.google.com unless he asked for the Google News home page.
- Prefer search_google with a concrete query over a generic portal.
- Do not open a second notepad if one is already focused — type into it.
- You cannot click arbitrary UI; if he asks only to "click another window", say so briefly.

Tool picks:
- play YouTube → play_youtube
- pause/play/resume/next/previous/mute → media_control
- open app → open_application
- open link → open_url
- google/chrome search → search_google
- type into open editor → type_text
- save open document → save_document
"""

_FAIL_MARKERS = (
    "failed",
    "couldn't find",
    "could not",
    "couldn't",
    "error:",
    "not installed",
    "timed out",
    "unavailable",
    "no media player",
    "nothing is playing",
    "not confirmed",
    "could not confirm",
    "can't confirm",
    "cannot confirm",
)


def _is_failure(result: str) -> bool:
    low = (result or "").lower()
    if low.startswith("ok:"):
        return False
    return any(m in low for m in _FAIL_MARKERS)


def _parse_kv(result: str) -> dict[str, str]:
    """Parse 'OK:youtube query=foo url=https://...' style strings."""
    out: dict[str, str] = {}
    for m in re.finditer(r"(\w+)=([^\s]+(?:\s(?!\w+=)[^\s]+)*)", result):
        out[m.group(1)] = m.group(2).strip()
    # simpler split for url=/query=
    for key in ("url", "query", "app", "kind", "alias", "filename", "chars"):
        m = re.search(rf"\b{key}=(\S+)", result)
        if m:
            out[key] = m.group(1)
    return out


def _voice_line(tool_name: str, tool_args: dict, result: str) -> str:
    """Natural spoken line from verified tool result. Never invent success."""
    text = (result or "").strip()
    if not text:
        return "That returned nothing, Sir. I can't confirm it worked."

    if _is_failure(text):
        cleaned = re.sub(r"\s+", " ", text)
        cleaned = re.sub(
            r"^(Failed:\s*|OK:\w+:\s*|UNCONFIRMED:\w+:\s*)",
            "",
            cleaned,
            flags=re.I,
        ).strip()
        action = (tool_args.get("action") or "").lower()
        if tool_name == "media_control" and "pause" in action:
            return (
                f"I couldn't pause it, Sir. {cleaned}"
                if cleaned
                else "I couldn't pause it, Sir."
            )
        if tool_name == "type_text":
            return f"I couldn't type that, Sir. {cleaned}" if cleaned else "I couldn't type that, Sir."
        if tool_name == "save_document":
            return f"I couldn't save it, Sir. {cleaned}" if cleaned else "I couldn't save it, Sir."
        return cleaned[:280] if cleaned else "That didn't work, Sir."

    if tool_name == "media_control":
        action = (tool_args.get("action") or "").lower()
        if "pause" in action or text.startswith("OK:pause"):
            return "Alright, Sir. I've paused the video we opened."
        if action in ("play", "resume") or text.startswith("OK:play"):
            return "Alright, Sir. Resuming playback."
        if action == "next":
            return "Skipped ahead, Sir."
        if action == "previous":
            return "Went back, Sir."
        if action == "mute":
            return "Muted, Sir."
        if action == "unmute":
            return "Unmuted, Sir."
        return "Done, Sir."

    if tool_name == "play_youtube":
        q = tool_args.get("query") or _parse_kv(text).get("query") or "that"
        return f"Playing {q} on YouTube, Sir. I'll keep track of that tab."

    if tool_name == "open_application":
        alias = tool_args.get("app_name") or _parse_kv(text).get("alias") or "it"
        return f"Opened {alias} for you, Sir. I'm focused on that window now."

    if tool_name == "open_url":
        return "Opened that link, Sir."

    if tool_name == "search_google":
        return f"Searching Google for {tool_args.get('query', 'that')}, Sir."

    if tool_name == "type_text":
        return "I've typed that into the editor, Sir."

    if tool_name == "save_document":
        fn = (tool_args.get("filename") or "").strip()
        if fn:
            return f"Saved as {fn}, Sir."
        return "Saved, Sir."

    if tool_name == "change_volume":
        return f"Volume is at {tool_args.get('level')} percent, Sir."

    if tool_name in ("run_terminal_command", "clipboard_control", "capture_screen_and_analyze"):
        return text[:400]

    return text[:200]


def _recover_tool_from_error(err: str) -> tuple[str, dict] | None:
    m = re.search(r"tool '([a-zA-Z0-9_]+)(\{.*\})'", err)
    if not m:
        m = re.search(
            r"<function=([a-zA-Z0-9_]+)(\{.*?\})></function>", err, re.DOTALL
        )
    if not m:
        return None
    tool_name, raw_args = m.group(1), m.group(2)
    try:
        return tool_name, json.loads(raw_args)
    except Exception:
        return None


async def _track_open_from_tool(
    client_id: str, tool_name: str, tool_args: dict, result: str
) -> None:
    if _is_failure(result):
        return
    from app.managers.session_manager import session_manager

    kv = _parse_kv(result)
    if tool_name == "play_youtube":
        await session_manager.remember_open(
            client_id,
            kind="media",
            name="youtube",
            title_hint="YouTube",
            url=kv.get("url"),
            query=tool_args.get("query") or kv.get("query"),
        )
    elif tool_name == "open_url":
        url = tool_args.get("url") or kv.get("url")
        name = "youtube" if url and "youtube" in url.lower() else "browser"
        await session_manager.remember_open(
            client_id,
            kind="media" if name == "youtube" else "browser",
            name=name,
            title_hint="YouTube" if name == "youtube" else "Browser",
            url=url,
        )
    elif tool_name == "search_google":
        await session_manager.remember_open(
            client_id,
            kind="browser",
            name="google",
            title_hint="Google",
            url=kv.get("url"),
            query=tool_args.get("query"),
        )
    elif tool_name == "open_application":
        app = kv.get("app") or tool_args.get("app_name") or "app"
        kind = kv.get("kind") or "app"
        await session_manager.remember_open(
            client_id,
            kind=kind,
            name=app,
            title_hint=tool_args.get("app_name") or app,
            meta={"alias": kv.get("alias") or tool_args.get("app_name")},
        )
    elif tool_name == "type_text":
        # Keep focus on current editor; stash last typed snippet length
        await session_manager.set_state(
            client_id, "last_typed_chars", len(tool_args.get("text") or "")
        )
    elif tool_name == "save_document":
        await session_manager.set_state(
            client_id, "last_saved", tool_args.get("filename") or "saved"
        )


class ExecutorAgent:
    name = "executor"

    def __init__(self) -> None:
        self.llm = get_llm(temperature=0.0)
        self.tools = [
            change_volume,
            open_application,
            open_url,
            search_google,
            play_youtube,
            run_terminal_command,
            media_control,
            clipboard_control,
            capture_screen_and_analyze,
            type_text,
            save_document,
        ]
        self.llm_with_tools = self.llm.bind_tools(self.tools)

    async def run(self, task: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        chunks: list[str] = []
        async for piece in self.stream(task, context):
            chunks.append(piece)
        return {
            "agent": self.name,
            "task": task,
            "result": "".join(chunks),
            "context_keys": list((context or {}).keys()),
        }

    async def _invoke_tool(
        self, tool_name: str, tool_args: dict, client_id: Optional[str]
    ) -> str:
        tool_map = {t.name: t for t in self.tools}
        tool = tool_map.get(tool_name)
        if not tool:
            return f"I don't have a working tool named {tool_name}."

        if "{" in tool_name and tool_name not in tool_map:
            base, _, rest = tool_name.partition("{")
            base = base.strip()
            try:
                tool_args = json.loads("{" + rest)
                tool_name = base
                tool = tool_map.get(tool_name)
            except Exception:
                pass
            if not tool:
                return f"I don't have a working tool named {tool_name}."

        # Enrich type_text with focused editor hint from session
        if client_id and tool_name == "type_text" and not tool_args.get("target_hint"):
            try:
                from app.managers.session_manager import session_manager

                data = await session_manager.get_or_create(client_id)
                focused = data.get("focused_target") or {}
                if focused.get("kind") == "editor" or focused.get("name") in (
                    "gedit",
                    "gnome-text-editor",
                    "kate",
                    "mousepad",
                ):
                    tool_args = {
                        **tool_args,
                        "target_hint": focused.get("title_hint")
                        or focused.get("name")
                        or "",
                    }
            except Exception as e:
                logger.debug("Could not enrich type_text hint: %s", e)

        logger.info("Executing tool=%s args=%s", tool_name, tool_args)
        try:
            result = await asyncio.to_thread(tool.invoke, tool_args)
            result_str = result if isinstance(result, str) else str(result)
        except Exception as e:
            logger.error("Tool %s raised: %s", tool_name, e)
            result_str = f"Failed to run {tool_name}: {e}"

        if client_id:
            try:
                from app.managers.session_manager import session_manager

                status = "failed" if _is_failure(result_str) else "success"
                await session_manager.add_tool_result(
                    client_id, tool_name, result_str, status=status
                )
                await _track_open_from_tool(
                    client_id, tool_name, tool_args, result_str
                )
            except Exception as e:
                logger.warning("Could not persist tool/workspace state: %s", e)

        return result_str

    async def stream(
        self, task: str, context: Dict[str, Any] | None = None
    ) -> AsyncIterator[str]:
        """Run one tool, await it, speak only the verified outcome."""
        context = context or {}
        client_id = context.get("client_id")
        logger.info("ExecutorAgent analyzing task: %s", task[:80])

        workspace = ""
        recent_chat = ""
        last_research = ""
        if client_id:
            try:
                from app.managers.session_manager import session_manager

                data = await session_manager.get_or_create(client_id)
                workspace = session_manager.format_workspace_context(data)
                msgs = data.get("messages") or []
                bits = []
                for m in msgs[-8:]:
                    role = m.get("role", "")
                    content = (m.get("content") or "").strip().replace("\n", " ")
                    if content:
                        bits.append(f"{role}: {content[:160]}")
                recent_chat = "\n".join(bits)
                state = data.get("current_state") or {}
                last_research = (
                    state.get("last_research_query")
                    or (data.get("browser_state") or {}).get("youtube", {}).get("query")
                    or ""
                )
            except Exception as e:
                logger.warning("Executor context unavailable: %s", e)

        system = _EXECUTOR_SYSTEM
        if workspace:
            system += f"\n\n{workspace}"
        if last_research:
            system += f"\n\nLAST RESEARCH TOPIC (for 'same/that' chrome search): {last_research}"
        if recent_chat:
            system += f"\n\nRECENT CHAT:\n{recent_chat}"

        messages = [
            SystemMessage(content=system),
            HumanMessage(content=f"User request: {task}"),
        ]

        try:
            response = await self.llm_with_tools.ainvoke(messages)
        except Exception as e:
            logger.error("ExecutorAgent LLM failed: %s", e)
            recovered = _recover_tool_from_error(str(e))
            if recovered:
                tool_name, tool_args = recovered
                result = await self._invoke_tool(tool_name, tool_args, client_id)
                yield _voice_line(tool_name, tool_args, result)
                return
            yield "I hit an error before I could run that command, Sir."
            return

        if hasattr(response, "tool_calls") and response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = dict(tool_call.get("args") or {})
                # Enrich vague chrome searches with last research topic
                if tool_name in ("search_google", "open_url") and last_research:
                    q = (tool_args.get("query") or tool_args.get("url") or "").lower()
                    if (
                        not q
                        or q in ("https://news.google.com", "news.google.com")
                        or "news.google.com" in q
                        or q.strip() in ("news", "same", "that")
                    ):
                        if tool_name == "search_google":
                            tool_args["query"] = last_research
                        else:
                            tool_args["url"] = (
                                "https://www.google.com/search?q="
                                + last_research.replace(" ", "+")
                            )
                result = await self._invoke_tool(tool_name, tool_args, client_id)
                yield _voice_line(tool_name, tool_args, result)
            return

        if hasattr(response, "content") and response.content:
            text = str(response.content).strip()
            low = text.lower()
            if any(
                w in low
                for w in (
                    "paused",
                    "playing",
                    "opened",
                    "done",
                    "i've",
                    "i have",
                    "successfully",
                    "typed",
                    "saved",
                )
            ):
                yield "I couldn't map that to a system action, so I didn't change anything, Sir."
                return
            yield text
            return

        yield "I couldn't figure out which system command to run, so I didn't change anything, Sir."
