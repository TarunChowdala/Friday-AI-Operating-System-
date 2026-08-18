"""Session Manager — single source of truth for the LIVE conversation.

Redis holds the active session. Postgres is written on session end (later).
Tools/agents should read/write through this manager, not Redis/DB directly.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.redis_client import get_redis
from app.database.crud import create_session, get_or_create_default_user
from app.database.database import SessionLocal
from app.prompts.system_prompt import get_system_prompt

logger = get_logger(__name__)

JARVIS_SYSTEM_PROMPT = get_system_prompt()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_key(client_id: str) -> str:
    return f"friday:client:{client_id}"


def _session_key(session_id: str) -> str:
    return f"friday:session:{session_id}"


class SessionManager:
    """Live session store (Redis) + Postgres session row on create."""

    def __init__(self) -> None:
        cfg = get_settings()
        self.ttl = cfg.SESSION_TTL_SECONDS
        self.max_messages = cfg.SESSION_MAX_MESSAGES

    def _empty_session(
        self,
        *,
        session_id: str,
        user_id: str,
        client_id: str,
    ) -> dict[str, Any]:
        return {
            "session_id": session_id,
            "user_id": user_id,
            "client_id": client_id,
            "status": "ACTIVE",
            "messages": [],
            "summary": "",
            "current_state": {},
            "pending_confirmation": None,
            "current_project": None,
            "browser_state": {},
            "desktop_state": {
                "active_window": None,
                "windows": [],
                "running_apps": [],
                "media": {},
                "captured_at": None,
            },
            "open_apps": [],
            "focused_target": None,
            "terminal_cwd": None,
            "tool_results": [],
            "episodic_memories": [],
            "wake_sent": False,
            "metrics": {},
            "temp_preferences": {},
            "started_at": _utcnow(),
            "updated_at": _utcnow(),
        }

    async def _fetch_episodic(self, user_id: str, *, limit: int = 5) -> list[dict[str, Any]]:
        import uuid as _uuid

        from app.database.crud import list_recent_episodic_memories

        try:
            async with SessionLocal() as db:
                rows = await list_recent_episodic_memories(
                    db, _uuid.UUID(user_id), limit=limit
                )
            out: list[dict[str, Any]] = []
            for r in rows:
                out.append(
                    {
                        "id": str(r.id),
                        "title": r.title,
                        "summary": r.summary,
                        "tags": list(r.tags or []),
                        "created_at": r.created_at.isoformat()
                        if r.created_at
                        else None,
                    }
                )
            return out
        except Exception as e:
            logger.warning("Failed to load episodic memories: %s", e)
            return []

    async def get_or_create(self, client_id: str) -> dict[str, Any]:
        """Resolve client_id → live Redis session; create Postgres+Redis if missing."""
        r = await get_redis()
        existing_id = await r.get(_client_key(client_id))
        if existing_id:
            raw = await r.get(_session_key(existing_id))
            if raw:
                await r.expire(_client_key(client_id), self.ttl)
                await r.expire(_session_key(existing_id), self.ttl)
                data = json.loads(raw)
                # Refresh episodic if empty (e.g. older sessions)
                if not data.get("episodic_memories") and data.get("user_id"):
                    data["episodic_memories"] = await self._fetch_episodic(
                        data["user_id"]
                    )
                    await self._save(data)
                return data

        # Create durable session row + live Redis doc
        async with SessionLocal() as db:
            user = await get_or_create_default_user(db)
            pg_session = await create_session(db, user.id)
            session_id = str(pg_session.id)
            user_id = str(user.id)

        data = self._empty_session(
            session_id=session_id, user_id=user_id, client_id=client_id
        )
        data["episodic_memories"] = await self._fetch_episodic(user_id)
        await self._save(data)
        await r.set(_client_key(client_id), session_id, ex=self.ttl)
        logger.info(
            "Live session created client=%s session=%s episodic=%d",
            client_id[:24],
            session_id,
            len(data["episodic_memories"]),
        )
        return data

    async def get(self, client_id: str) -> Optional[dict[str, Any]]:
        r = await get_redis()
        session_id = await r.get(_client_key(client_id))
        if not session_id:
            return None
        raw = await r.get(_session_key(session_id))
        return json.loads(raw) if raw else None

    async def _save(self, data: dict[str, Any]) -> None:
        r = await get_redis()
        data["updated_at"] = _utcnow()
        session_id = data["session_id"]
        await r.set(_session_key(session_id), json.dumps(data), ex=self.ttl)
        await r.set(_client_key(data["client_id"]), session_id, ex=self.ttl)

    async def append_message(
        self,
        client_id: str,
        role: str,
        content: str,
        *,
        intent: Optional[str] = None,
        actions: Optional[list[dict[str, Any]]] = None,
        hitl: bool = False,
    ) -> dict[str, Any]:
        data = await self.get_or_create(client_id)
        data["messages"].append(
            {
                "id": str(uuid.uuid4()),
                "role": role,
                "content": content,
                "intent": intent,
                "actions": actions,
                "hitl": hitl,
                "created_at": _utcnow(),
            }
        )
        # Keep Redis lean — drop oldest turns but leave room for system summary
        if len(data["messages"]) > self.max_messages:
            overflow = data["messages"][: -self.max_messages]
            # Stash a crude rolling note into summary until real summarizer is wired
            note = " | ".join(f"{m['role']}: {m['content'][:80]}" for m in overflow[-4:])
            prev = data.get("summary") or ""
            data["summary"] = (prev + " " + note).strip()[:2000]
            data["messages"] = data["messages"][-self.max_messages :]
        await self._save(data)
        return data

    async def set_state(self, client_id: str, key: str, value: Any) -> dict[str, Any]:
        data = await self.get_or_create(client_id)
        data["current_state"][key] = value
        await self._save(data)
        return data

    async def set_desktop_state(
        self, client_id: str, desktop_state: dict[str, Any]
    ) -> dict[str, Any]:
        data = await self.get_or_create(client_id)
        current = dict(data.get("desktop_state") or {})
        current.update(desktop_state or {})
        current["captured_at"] = _utcnow()
        data["desktop_state"] = current
        await self._save(data)
        return data

    async def add_tool_result(
        self, client_id: str, tool_name: str, result: Any, *, status: str = "success"
    ) -> dict[str, Any]:
        data = await self.get_or_create(client_id)
        data["tool_results"].append(
            {
                "tool": tool_name,
                "status": status,
                "result": result,
                "at": _utcnow(),
            }
        )
        # Cap tool result trail
        data["tool_results"] = data["tool_results"][-50:]
        await self._save(data)
        return data

    async def set_pending_confirmation(
        self, client_id: str, payload: Optional[dict[str, Any]]
    ) -> dict[str, Any]:
        data = await self.get_or_create(client_id)
        data["pending_confirmation"] = payload
        await self._save(data)
        return data

    async def remember_open(
        self,
        client_id: str,
        *,
        kind: str,
        name: str,
        title_hint: Optional[str] = None,
        url: Optional[str] = None,
        query: Optional[str] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Track something JARVIS opened so later actions can target it."""
        data = await self.get_or_create(client_id)
        entry = {
            "id": str(uuid.uuid4()),
            "kind": kind,  # app | browser | media | editor
            "name": name,
            "title_hint": title_hint or name,
            "url": url,
            "query": query,
            "meta": meta or {},
            "opened_at": _utcnow(),
        }
        apps = list(data.get("open_apps") or [])
        # Replace prior entry with same name+kind
        apps = [a for a in apps if not (a.get("name") == name and a.get("kind") == kind)]
        apps.append(entry)
        data["open_apps"] = apps[-20:]
        data["focused_target"] = entry

        if kind in ("media", "browser") and name == "youtube":
            browser = dict(data.get("browser_state") or {})
            browser["youtube"] = {
                "query": query,
                "url": url,
                "opened_at": entry["opened_at"],
                "id": entry["id"],
            }
            data["browser_state"] = browser
        elif kind == "browser" and url:
            browser = dict(data.get("browser_state") or {})
            browser["last_url"] = url
            data["browser_state"] = browser

        await self._save(data)
        logger.info(
            "Tracked open kind=%s name=%s client=%s", kind, name, client_id[:24]
        )
        return data

    def format_workspace_context(self, data: dict[str, Any]) -> str:
        """Compact workspace block for LLM prompts."""
        focused = data.get("focused_target") or {}
        apps = data.get("open_apps") or []
        browser = data.get("browser_state") or {}
        desktop = data.get("desktop_state") or {}
        tools = data.get("tool_results") or []
        lines = ["WORKSPACE STATE (what JARVIS already opened this session):"]
        if focused:
            lines.append(
                f"- FOCUSED: kind={focused.get('kind')} name={focused.get('name')} "
                f"title={focused.get('title_hint')} url={focused.get('url') or '-'} "
                f"query={focused.get('query') or '-'}"
            )
        else:
            lines.append("- FOCUSED: none")
        if apps:
            recent = apps[-5:]
            lines.append("- RECENTLY OPENED:")
            for a in recent:
                lines.append(
                    f"  • {a.get('kind')}/{a.get('name')} "
                    f"({a.get('title_hint')})"
                    + (f" url={a.get('url')}" if a.get("url") else "")
                )
        yt = browser.get("youtube") or {}
        if yt:
            lines.append(
                f"- YOUTUBE: query={yt.get('query') or '-'} url={yt.get('url') or '-'}"
            )
        active = desktop.get("active_window") or {}
        if active.get("title"):
            lines.append(
                f"- LIVE DESKTOP FOCUS: title={active.get('title')} "
                f"app={active.get('app') or '-'} pid={active.get('pid') or '-'}"
            )
        media = desktop.get("media") or {}
        if media.get("status"):
            lines.append(
                f"- LIVE MEDIA: status={media.get('status')} "
                f"title={media.get('title') or '-'} player={media.get('player') or '-'}"
            )
        if tools:
            lines.append("- RECENT TOOL RESULTS (newest last):")
            for t in tools[-5:]:
                res = str(t.get("result") or "")[:120].replace("\n", " ")
                lines.append(
                    f"  • {t.get('tool')} [{t.get('status')}]: {res}"
                )
        lines.append(
            "Use FOCUSED / YOUTUBE / RECENTLY OPENED for follow-ups "
            "(pause that video, type into notepad, save that file). "
            "Do not invent opens that are not listed."
        )
        return "\n".join(lines)

    def format_episodic_context(self, data: dict[str, Any]) -> str:
        episodes = data.get("episodic_memories") or []
        if not episodes:
            return (
                "EPISODIC MEMORY (past sessions): none yet.\n"
                "On wake with nothing useful, just: \"Morning, Sir. I'm online.\""
            )
        lines = [
            "EPISODIC MEMORY (past sessions with Tarun — use for wake suggestions):",
            "Only reference these. Never invent past work.",
        ]
        for i, ep in enumerate(episodes[:5], 1):
            tags = ", ".join(ep.get("tags") or []) or "-"
            lines.append(
                f"{i}. [{ep.get('created_at') or '?'}] {ep.get('title')}\n"
                f"   {ep.get('summary')}\n"
                f"   tags: {tags}"
            )
        lines.append(
            "On wake / greeting / 'Jarvis' / 'what's up': greet briefly, then ONE useful "
            "suggestion from the newest relevant episode (continue unfinished work, "
            "reopen what was left, etc.). If he declines, stop pitching."
        )
        return "\n".join(lines)

    def build_wake_greeting(self, data: dict[str, Any]) -> str:
        """Deterministic wake line from episodic + time. No LLM. Never invents."""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            hello = "Good morning, Sir."
        elif 12 <= hour < 17:
            hello = "Good afternoon, Sir."
        elif 17 <= hour < 22:
            hello = "Good evening, Sir."
        else:
            hello = "Welcome back, Sir."

        episodes = data.get("episodic_memories") or []
        if not episodes:
            return f"{hello} I'm online."

        latest = episodes[0]
        title = (latest.get("title") or "").strip()
        summary = (latest.get("summary") or "").strip()
        tags = [t.lower() for t in (latest.get("tags") or [])]

        suggestion = None
        if "youtube" in tags or "media" in tags:
            suggestion = "Want to pick up where we left off with that video?"
        elif "editor" in tags or "notepad" in tags:
            suggestion = "Want to continue in the editor we had open?"
        elif "unfinished" in tags:
            suggestion = "Want to continue from there?"
        elif title:
            suggestion = "Want to continue from there?"

        bit = title or summary[:120]
        if bit and suggestion:
            return f"{hello} Last time: {bit}. {suggestion}"
        if bit:
            return f"{hello} Last time we were on: {bit}."
        return f"{hello} I'm online."

    def to_langchain_messages(self, data: dict[str, Any]) -> list[BaseMessage]:
        """Build LLM context from live Redis session (chat + workspace + episodic)."""
        summary = (data.get("summary") or "").strip()
        system = JARVIS_SYSTEM_PROMPT
        if summary:
            system += f"\n\nHere is a summary of the earlier conversation:\n{summary}"

        system += f"\n\n{self.format_episodic_context(data)}"
        system += f"\n\n{self.format_workspace_context(data)}"

        messages: list[BaseMessage] = [SystemMessage(content=system)]
        for m in data.get("messages") or []:
            role = m.get("role")
            content = m.get("content") or ""
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
            elif role == "system":
                messages.append(SystemMessage(content=content))
        return messages

    async def get_langchain_messages(self, client_id: str) -> list[BaseMessage]:
        data = await self.get_or_create(client_id)
        return self.to_langchain_messages(data)

    async def get_workspace_block(self, client_id: str) -> str:
        data = await self.get_or_create(client_id)
        return self.format_workspace_context(data)

    def _build_episode_payload(
        self, data: dict[str, Any], *, session_summary: Optional[str]
    ) -> Optional[dict[str, Any]]:
        """Build episodic title/summary/tags from a finished session. None if empty."""
        messages = data.get("messages") or []
        tools = data.get("tool_results") or []
        focused = data.get("focused_target") or {}
        apps = data.get("open_apps") or []
        browser = data.get("browser_state") or {}

        user_msgs = [m for m in messages if m.get("role") == "user"]
        # Skip empty / wake-only sessions
        if not user_msgs and not tools and not focused and not apps:
            return None

        tags: list[str] = []
        title_parts: list[str] = []

        yt = browser.get("youtube") or {}
        if yt or (focused.get("name") == "youtube"):
            tags.append("youtube")
            tags.append("media")
            q = yt.get("query") or focused.get("query")
            title_parts.append(f"YouTube: {q}" if q else "YouTube session")

        for a in apps:
            kind = (a.get("kind") or "").lower()
            name = (a.get("name") or "").lower()
            if kind == "editor" or name in (
                "gedit",
                "gnome-text-editor",
                "kate",
                "mousepad",
                "notepad",
            ):
                if "editor" not in tags:
                    tags.append("editor")
                    tags.append("notepad")
                title_parts.append(f"Editor: {a.get('title_hint') or name}")
            elif kind == "app" and name not in title_parts:
                title_parts.append(f"App: {a.get('title_hint') or name}")

        tool_names = [t.get("tool") for t in tools if t.get("tool")]
        if tool_names:
            tags.append("tools")
            uniq = []
            for n in tool_names:
                if n not in uniq:
                    uniq.append(n)
            tags.extend(uniq[:5])

        if focused or any(
            t.get("status") == "failed" for t in tools
        ) or len(messages) >= 2:
            tags.append("unfinished")

        title = " · ".join(title_parts[:3]) if title_parts else "Session with Tarun"
        if len(title) > 120:
            title = title[:117] + "..."

        summary_bits: list[str] = []
        if session_summary:
            summary_bits.append(session_summary)
        if focused:
            summary_bits.append(
                f"Left focused on {focused.get('kind')}/{focused.get('name')}"
                + (f" ({focused.get('query')})" if focused.get("query") else "")
            )
        if apps:
            names = ", ".join(
                f"{a.get('kind')}/{a.get('name')}" for a in apps[-5:]
            )
            summary_bits.append(f"Opened: {names}")
        if tool_names:
            summary_bits.append(
                "Tools: " + ", ".join(dict.fromkeys(tool_names))
            )
        # last user intents
        user_bits = [
            (m.get("content") or "")[:80]
            for m in messages
            if m.get("role") == "user" and m.get("content")
        ][-3:]
        if user_bits:
            summary_bits.append("User asked: " + " | ".join(user_bits))

        summary = " — ".join(summary_bits)[:2000] if summary_bits else title
        # dedupe tags
        seen = set()
        clean_tags = []
        for t in tags:
            if t and t not in seen:
                seen.add(t)
                clean_tags.append(t)

        return {"title": title, "summary": summary, "tags": clean_tags}

    async def mark_wake_sent(self, client_id: str) -> dict[str, Any]:
        data = await self.get_or_create(client_id)
        data["wake_sent"] = True
        await self._save(data)
        return data

    async def end_session(
        self,
        client_id: str,
        *,
        status: str = "ENDED",
    ) -> Optional[dict[str, Any]]:
        """Flush live Redis chat → Postgres (+ episodic), mark closed, delete Redis."""
        import uuid as _uuid

        from app.database.crud import (
            add_episodic_memory,
            add_execution,
            add_message,
            end_session as pg_end_session,
        )

        r = await get_redis()
        data = await self.get(client_id)
        if not data:
            return None

        session_id = data["session_id"]
        user_id = data.get("user_id")
        messages = data.get("messages") or []
        tool_results = data.get("tool_results") or []

        summary_bits = []
        for m in messages[-6:]:
            role = m.get("role", "")
            content = (m.get("content") or "").strip().replace("\n", " ")
            if content:
                summary_bits.append(f"{role}: {content[:120]}")
        focused = data.get("focused_target") or {}
        if focused:
            summary_bits.append(
                f"focused:{focused.get('kind')}/{focused.get('name')}"
            )
        summary = " | ".join(summary_bits)[:2000] if summary_bits else None
        episode = self._build_episode_payload(data, session_summary=summary)

        try:
            sid = _uuid.UUID(session_id)
            uid = _uuid.UUID(user_id) if user_id else None
            async with SessionLocal() as db:
                for m in messages:
                    await add_message(
                        db,
                        sid,
                        role=m.get("role") or "user",
                        message=m.get("content") or "",
                        intent=m.get("intent"),
                        actions=m.get("actions"),
                        hitl=bool(m.get("hitl")),
                    )
                for tr in tool_results:
                    await add_execution(
                        db,
                        sid,
                        tool_name=tr.get("tool") or "unknown",
                        status=tr.get("status") or "success",
                        output_data={"result": tr.get("result")},
                    )
                if episode and uid:
                    await add_episodic_memory(
                        db,
                        uid,
                        episode["title"],
                        episode["summary"],
                        session_id=sid,
                        tags=episode["tags"],
                    )
                    logger.info(
                        "Episodic saved session=%s title=%s",
                        session_id,
                        episode["title"][:80],
                    )
                await pg_end_session(db, sid, summary=summary, status=status)
            logger.info(
                "Session persisted+closed session=%s status=%s msgs=%d tools=%d episodic=%s",
                session_id,
                status,
                len(messages),
                len(tool_results),
                bool(episode),
            )
        except Exception as e:
            logger.error("Failed to persist session %s: %s", session_id, e)

        await r.delete(_session_key(session_id))
        await r.delete(_client_key(client_id))
        return data


# Process-wide singleton
session_manager = SessionManager()
