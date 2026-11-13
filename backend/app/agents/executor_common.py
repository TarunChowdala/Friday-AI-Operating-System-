"""Shared executor helpers for tool-bound agents."""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
import time
from typing import Any, AsyncIterator, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.llm import get_llm
from app.core.logger import get_logger

logger = get_logger(__name__)

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


def is_failure(result: str) -> bool:
    low = (result or "").lower()
    if low.startswith("ok:"):
        return False
    return any(m in low for m in _FAIL_MARKERS)


def parse_kv(result: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r"(\w+)=([^\s]+(?:\s(?!\w+=)[^\s]+)*)", result):
        out[m.group(1)] = m.group(2).strip()
    for key in ("url", "query", "app", "kind", "alias", "filename", "chars"):
        m = re.search(rf"\b{key}=(\S+)", result)
        if m:
            out[key] = m.group(1)
    return out


def parse_structured_result(result: str) -> dict[str, Any] | None:
    try:
        data = json.loads(result)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _sanitize_for_voice(text: str) -> str:
    """Strip raw JSON, markdown headers, and code fences from text intended for TTS."""
    if not text:
        return ""
    # Strip markdown code blocks
    s = re.sub(r"```[a-zA-Z0-9_-]*\n[\s\S]*?```", "", text)
    # Strip markdown inline code
    s = re.sub(r"`[^`]+`", "", s)
    # Strip markdown headers like ### Ran Playwright code
    s = re.sub(r"^#{1,6}\s+.*$", "", s, flags=re.MULTILINE)
    # Strip bullet lists
    s = re.sub(r"^\s*[-*]\s+.*$", "", s, flags=re.MULTILINE)
    # If string is raw JSON, never speak brackets and colons
    s = s.strip()
    if s.startswith("{") and s.endswith("}"):
        try:
            d = json.loads(s)
            if isinstance(d, dict):
                msg = d.get("message") or d.get("error") or ""
                if "remote desktop portal" in msg.lower() or "denied" in msg.lower():
                    return "Desktop remote input was denied by the system, Sir."
                if msg:
                    return f"Action notice: {msg[:120]}, Sir."
                if d.get("ok"):
                    return "Action completed successfully, Sir."
        except Exception:
            pass
        return "Action completed, Sir."
    return re.sub(r"\s+", " ", s).strip()


def voice_line(tool_name: str, tool_args: dict, result: str) -> str:
    text = (result or "").strip()
    structured = parse_structured_result(text)
    if tool_name in ("desktop_context", "desktop_action") and structured:
        return str(structured.get("summary") or "I read the desktop state, Sir.")
    if not text:
        return "That returned nothing, Sir. I can't confirm it worked."

    # Failure handling
    if is_failure(text):
        cleaned = re.sub(r"\s+", " ", text)
        cleaned = re.sub(
            r"^(Failed:\s*|OK:\w+:\s*|UNCONFIRMED:\w+:\s*)",
            "",
            cleaned,
            flags=re.I,
        ).strip()

        # JUCCE failure handling
        if tool_name.startswith("jucce_"):
            if tool_name == "jucce_get_app_state":
                if text.startswith("Visible on screen:"):
                    return text[:280] + ", Sir."
                return "I inspected the screen, Sir."
            if "remote desktop portal" in text.lower() or "denied" in text.lower():
                key = tool_args.get("key", "input")
                return f"The system denied remote desktop permission for {key}, Sir."
            if tool_name == "jucce_press_key":
                return f"I couldn't press {tool_args.get('key', 'that key')}, Sir."
            if tool_name == "jucce_click":
                return "I couldn't click on that part of the screen, Sir."
            if tool_name == "jucce_type_text":
                return "I couldn't type that text on the desktop, Sir."
            if tool_name == "jucce_activate_window":
                return "I couldn't switch to that window, Sir."
            return "That desktop action couldn't be completed, Sir."

        # Playwright failure handling
        if tool_name.startswith("playwright_"):
            if tool_name == "playwright_navigate":
                return "I couldn't load that webpage, Sir."
            if tool_name == "playwright_click":
                return "I couldn't click that element on the webpage, Sir."
            if tool_name == "playwright_type":
                return "I couldn't type into that web field, Sir."
            return "That browser automation action failed, Sir."

        action = (tool_args.get("action") or "").lower()
        if tool_name == "media_control" and "pause" in action:
            return (
                f"I couldn't pause it, Sir. {cleaned}"
                if cleaned and not cleaned.startswith("{")
                else "I couldn't pause it, Sir."
            )
        if tool_name == "type_text":
            return (
                f"I couldn't type that, Sir. {cleaned}"
                if cleaned and not cleaned.startswith("{")
                else "I couldn't type that, Sir."
            )
        if tool_name == "save_document":
            return (
                f"I couldn't save it, Sir. {cleaned}"
                if cleaned and not cleaned.startswith("{")
                else "I couldn't save it, Sir."
            )
        sanitized = _sanitize_for_voice(cleaned)
        return sanitized[:180] if sanitized else "That didn't work, Sir."

    # Playwright MCP Tools (Success)
    if tool_name.startswith("playwright_"):
        if tool_name == "playwright_navigate":
            url = tool_args.get("url") or parse_kv(text).get("url") or ""
            title = parse_kv(text).get("title") or ""
            if "youtube" in url.lower() or "youtube" in title.lower():
                return "Opened YouTube in the browser, Sir."
            if title:
                return f"Opened {title}, Sir."
            return "Opened that webpage for you, Sir."
        if tool_name == "playwright_click":
            return "Clicked that on the page, Sir."
        if tool_name == "playwright_type":
            return "Typed that into the web page, Sir."
        if tool_name == "playwright_press_key":
            return "Sent key to the browser, Sir."
        if tool_name == "playwright_screenshot":
            return "Captured a screenshot of the webpage, Sir."
        if tool_name == "playwright_snapshot":
            items = []
            for line in text.splitlines():
                line_s = line.strip()
                m = re.search(r'[-*]\s+(?:\[[^\]]+\]\s+)?["\']?([^"\']{2,40})["\']?', line_s)
                if m and not any(skip in line_s.lower() for skip in ("page url", "console", "snapshot", "button", "link", "heading")):
                    candidate = m.group(1).strip()
                    if len(candidate) > 2 and candidate not in items:
                        items.append(candidate)
            unique_items = items[:5]
            if unique_items:
                return "Visible on the page: " + ", ".join(unique_items) + ", Sir."
            title_m = re.search(r"Page Title:\s*([^\n\r]+)", text)
            if title_m:
                return f"Inspected page: {title_m.group(1).strip()}, Sir."
            return "I've inspected the webpage content, Sir."
        if tool_name == "playwright_custom_action":
            return "Browser action completed, Sir."

    # JUCCE Tools (Success)
    if tool_name.startswith("jucce_"):
        if tool_name == "jucce_press_key":
            return f"Pressed {tool_args.get('key', 'key')}, Sir."
        if tool_name == "jucce_click":
            return "Clicked on the screen, Sir."
        if tool_name == "jucce_type_text":
            return "Typed that out for you, Sir."
        if tool_name == "jucce_activate_window":
            return "Switched to that window, Sir."
        if tool_name == "jucce_scroll":
            return "Scrolled the view, Sir."
        if tool_name == "jucce_screenshot":
            return "Captured desktop screenshot, Sir."
        if tool_name == "jucce_get_app_state":
            if text.startswith("Visible on screen:"):
                return text[:280] + ", Sir."
            return "Inspected the application state, Sir."
        if tool_name == "jucce_perform_action":
            return "Desktop action completed, Sir."
        if tool_name == "jucce_observe_desktop":
            if text.startswith("{"):
                try:
                    d = json.loads(text)
                    if "windows" in d:
                        wins = [w.get("title") or w.get("app_id") for w in d["windows"] if isinstance(w, dict)]
                        return f"Open windows: {', '.join(wins[:4])}, Sir."
                except Exception:
                    pass
            sanitized = _sanitize_for_voice(text)
            return sanitized[:250] if sanitized else "Desktop observation completed, Sir."

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
        q = tool_args.get("query") or parse_kv(text).get("query") or "that"
        return f"Playing {q} on YouTube, Sir. I'll keep track of that tab."

    if tool_name == "open_application":
        alias = tool_args.get("app_name") or parse_kv(text).get("alias") or "it"
        return f"Opened {alias} for you, Sir. I'm focused on that window now."

    if tool_name == "camera_control":
        action = (tool_args.get("action") or "").lower()
        if action in ("open", "launch", "start") or text.startswith("OK:opened"):
            return "Opened the camera, Sir."
        if action in ("close", "quit") or text.startswith("OK:closed"):
            return "Closed the camera, Sir."
        if action in ("photo", "click", "capture", "take_photo", "take photo") or text.startswith("OK:photo"):
            path = parse_kv(text).get("path") or "Pictures"
            return f"Photo saved to {path}, Sir."
        return text[:200]

    if tool_name == "open_url":
        url = tool_args.get("url") or ""
        if "newtab" in url or "about:blank" in url:
            return "Opened a new tab, Sir."
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

    if tool_name in (
        "desktop_context",
        "system_info",
        "run_terminal_command",
        "manage_files",
        "clipboard_control",
        "capture_screen_and_analyze",
    ):
        return _sanitize_for_voice(text)[:400]

    return _sanitize_for_voice(text)[:200]


def recover_tool_from_error(err: str) -> tuple[str, dict] | None:
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


async def track_open_from_tool(
    client_id: str, tool_name: str, tool_args: dict, result: str
) -> None:
    if is_failure(result):
        return
    from app.managers.session_manager import session_manager
    if tool_name in ("desktop_context", "desktop_action"):
        structured = parse_structured_result(result)
        if structured and structured.get("desktop_state") is not None:
            await session_manager.set_desktop_state(
                client_id, structured.get("desktop_state") or {}
            )
        return

    kv = parse_kv(result)
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
        await session_manager.set_state(
            client_id, "last_typed_chars", len(tool_args.get("text") or "")
        )
    elif tool_name == "save_document":
        await session_manager.set_state(
            client_id, "last_saved", tool_args.get("filename") or "saved"
        )


class ToolExecutorMixin:
    """Reusable executor behavior for specialized agents."""

    name = "executor"
    system_prompt = ""
    tools: list[Any]

    def __init__(self) -> None:
        self.llm = get_llm(temperature=0.0)
        self.llm_with_tools = self.llm.bind_tools(self.tools)

    async def run(
        self, task: str, context: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
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

        # Model cannot self-approve dangerous actions.
        tool_args = dict(tool_args)
        tool_args.pop("confirmed", None)

        logger.info("Executing tool=%s args=%s", tool_name, tool_args)
        tool_t0 = time.time()
        try:
            result = await asyncio.to_thread(tool.invoke, tool_args)
            result_str = result if isinstance(result, str) else str(result)
        except Exception as e:
            logger.error("Tool %s raised: %s", tool_name, e)
            result_str = f"Failed to run {tool_name}: {e}"
        logger.info(
            "⏱️ [LATENCY] Tool %s: %.3fs | result=%s",
            tool_name,
            time.time() - tool_t0,
            (result_str or "")[:180].replace("\n", " "),
        )

        if result_str.startswith("NEEDS_PERMISSION:") and client_id:
            from app.core.permissions import request_permission
            from app.websocket.connection_manager import ConnectionManager

            desc = result_str.replace("NEEDS_PERMISSION:", "").strip()
            manager = (
                ConnectionManager._instance
                if hasattr(ConnectionManager, "_instance")
                else None
            )
            if manager:
                approved = await request_permission(
                    client_id, desc, manager.send, timeout=30.0
                )
                if approved:
                    rerun_args = {**tool_args, "confirmed": True}
                    try:
                        result = await asyncio.to_thread(tool.invoke, rerun_args)
                        result_str = result if isinstance(result, str) else str(result)
                    except Exception:
                        # Backward-compatible fallback for plain shell commands.
                        from app.tools.terminal import expand_command_homes

                        cmd = expand_command_homes(tool_args.get("command", ""))
                        try:
                            res = subprocess.run(
                                cmd,
                                shell=True,
                                capture_output=True,
                                text=True,
                                timeout=15,
                            )
                            out = (res.stdout or "").strip()
                            err = (res.stderr or "").strip()
                            if res.returncode != 0:
                                result_str = (
                                    f"Failed: command exited {res.returncode}: "
                                    f"{(err or out or 'no output')[:1000]}"
                                )
                            elif out:
                                result_str = f"Command output:\n{out[:1000]}"
                            elif err:
                                result_str = f"Command error:\n{err[:1000]}"
                            else:
                                result_str = "Command executed successfully."
                        except Exception as e:
                            result_str = f"Execution error: {e}"
                else:
                    result_str = "Action cancelled by user — command was not executed."
            else:
                result_str = "Failed: permission system unavailable (no WS connection)."

        if client_id:
            try:
                from app.managers.session_manager import session_manager

                status = "failed" if is_failure(result_str) else "success"
                await session_manager.add_tool_result(
                    client_id, tool_name, result_str, status=status
                )
                await track_open_from_tool(client_id, tool_name, tool_args, result_str)
            except Exception as e:
                logger.warning("Could not persist tool/workspace state: %s", e)

        return result_str

    async def stream(
        self, task: str, context: Dict[str, Any] | None = None
    ) -> AsyncIterator[str]:
        context = context or {}
        client_id = context.get("client_id")
        logger.info("%s analyzing task: %s", self.__class__.__name__, task[:80])
        llm_t0 = time.time()

        workspace = ""
        recent_chat = ""
        last_research = ""
        if client_id:
            try:
                from app.managers.session_manager import session_manager

                ctx_t0 = time.time()
                data = await session_manager.get_or_create(client_id)
                logger.info(
                    "⏱️ [LATENCY] %s session hydrate: %.3fs",
                    self.__class__.__name__,
                    time.time() - ctx_t0,
                )
                workspace = session_manager.format_workspace_context(data)
                msgs = data.get("messages") or []
                bits = []
                for m in msgs[-3:]:
                    role = m.get("role", "")
                    content = (m.get("content") or "").strip().replace("\n", " ")
                    if content:
                        bits.append(f"{role}: {content[:100]}")
                recent_chat = "\n".join(bits)
                state = data.get("current_state") or {}
                last_research = state.get("last_research_query") or ""
            except Exception as e:
                logger.warning("Executor context unavailable: %s", e)

        system = self.system_prompt
        if workspace:
            system += f"\n\n{workspace}"
        if last_research:
            system += (
                "\n\nLAST RESEARCH TOPIC (for 'same/that' chrome search): "
                f"{last_research}"
            )
        if recent_chat:
            system += f"\n\nRECENT CHAT:\n{recent_chat}"

        messages = [
            SystemMessage(content=system),
            HumanMessage(content=f"User request: {task}"),
        ]

        try:
            response = await self.llm_with_tools.ainvoke(messages)
            logger.info(
                "⏱️ [LATENCY] %s LLM tool-select: %.3fs",
                self.__class__.__name__,
                time.time() - llm_t0,
            )
        except Exception as e:
            logger.error("%s LLM failed: %s", self.__class__.__name__, e)
            recovered = recover_tool_from_error(str(e))
            if recovered:
                tool_name, tool_args = recovered
                result = await self._invoke_tool(tool_name, tool_args, client_id)
                yield voice_line(tool_name, tool_args, result)
                return
            yield "I hit an error before I could run that command, Sir."
            return

        if hasattr(response, "tool_calls") and response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = dict(tool_call.get("args") or {})
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
                yield voice_line(tool_name, tool_args, result)
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
