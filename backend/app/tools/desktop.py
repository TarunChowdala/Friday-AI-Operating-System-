"""Live desktop awareness and control — windows, apps, media state."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any

import psutil
from langchain_core.tools import tool

from app.core.logger import get_logger

logger = get_logger(__name__)


def _run_text(cmd: list[str], timeout: int = 5) -> str:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if res.returncode == 0:
            return (res.stdout or "").strip()
    except Exception:
        pass
    return ""


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _find_window(target: str) -> dict[str, Any] | None:
    target = (target or "").strip()
    if not target or not shutil.which("xdotool"):
        return None

    windows = _list_windows(limit=50)
    needle = _norm_name(target)
    for win in windows:
        title = _norm_name(win.get("title") or "")
        app = _norm_name(win.get("app") or "")
        if needle and (needle in title or needle in app):
            return win
    return None


def _find_process(target: str) -> dict[str, Any] | None:
    needle = _norm_name(target)
    if not needle or len(needle) < 3:
        return None
    helper: dict[str, Any] | None = None
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = proc.info.get("name") or ""
            cmdline = proc.info.get("cmdline") or []
            blob = _norm_name(name + " " + " ".join(cmdline[:4]))
            if needle not in blob:
                continue
            is_helper = any(str(a).startswith("--type=") for a in cmdline)
            cand = {"pid": proc.pid, "name": name}
            if not is_helper:
                return cand
            if helper is None:
                helper = cand
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return helper


def _active_window() -> dict[str, Any]:
    if shutil.which("xdotool"):
        try:
            win_id = _run_text(["xdotool", "getactivewindow"])
            if win_id:
                title = _run_text(["xdotool", "getwindowname", win_id])
                pid = _run_text(["xdotool", "getwindowpid", win_id])
                app = ""
                if pid and pid.isdigit():
                    try:
                        app = psutil.Process(int(pid)).name()
                    except Exception:
                        app = ""
                return {
                    "source": "xdotool",
                    "window_id": win_id,
                    "title": title or "",
                    "pid": int(pid) if pid.isdigit() else None,
                    "app": app or "",
                }
        except Exception as e:
            logger.debug("active window via xdotool failed: %s", e)
    return {
        "source": "unavailable",
        "window_id": None,
        "title": "",
        "pid": None,
        "app": "",
    }


def _list_windows(limit: int = 12) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    if shutil.which("xdotool"):
        out = _run_text(["xdotool", "search", "--onlyvisible", "--name", "."])
        seen: set[str] = set()
        for win_id in out.splitlines():
            win_id = win_id.strip()
            if not win_id or win_id in seen:
                continue
            seen.add(win_id)
            title = _run_text(["xdotool", "getwindowname", win_id])
            pid = _run_text(["xdotool", "getwindowpid", win_id])
            app = ""
            if pid.isdigit():
                try:
                    app = psutil.Process(int(pid)).name()
                except Exception:
                    app = ""
            if title:
                windows.append(
                    {
                        "window_id": win_id,
                        "title": title,
                        "pid": int(pid) if pid.isdigit() else None,
                        "app": app or "",
                    }
                )
            if len(windows) >= limit:
                break
    return windows


def _running_apps(limit: int = 12) -> list[dict[str, Any]]:
    apps: dict[str, dict[str, Any]] = {}
    for proc in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
        try:
            name = (proc.info.get("name") or "").strip()
            if not name:
                continue
            mem = int((proc.info.get("memory_info").rss) if proc.info.get("memory_info") else 0)
            cpu = float(proc.info.get("cpu_percent") or 0.0)
            entry = apps.get(name)
            if not entry:
                apps[name] = {
                    "name": name,
                    "count": 1,
                    "rss": mem,
                    "cpu": cpu,
                }
            else:
                entry["count"] += 1
                entry["rss"] += mem
                entry["cpu"] += cpu
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    ranked = sorted(apps.values(), key=lambda x: (x["rss"], x["cpu"]), reverse=True)
    return ranked[:limit]


def _media_state() -> dict[str, Any]:
    if not shutil.which("playerctl"):
        return {"available": False, "status": "unavailable", "player": "", "title": ""}
    status = _run_text(["playerctl", "status"])
    player = _run_text(["playerctl", "-l"]).splitlines()
    title = _run_text(["playerctl", "metadata", "title"])
    artist = _run_text(["playerctl", "metadata", "artist"])
    return {
        "available": True,
        "status": (status or "unknown").lower(),
        "player": player[0].strip() if player else "",
        "title": title,
        "artist": artist,
    }


def _summary_for_state(action: str, state: dict[str, Any]) -> str:
    if action == "active_window":
        aw = state["active_window"]
        if aw.get("title"):
            app = aw.get("app") or "unknown app"
            return f"Focused window: {aw['title']} ({app})."
        return "I couldn't detect the focused window in this desktop session."
    if action == "list_windows":
        windows = state["windows"]
        if not windows:
            return "I couldn't list visible windows in this desktop session."
        shown = ", ".join(w["title"] for w in windows[:5])
        more = len(windows) - min(len(windows), 5)
        return f"{len(windows)} visible windows. Top ones: {shown}" + (f", and {more} more." if more > 0 else ".")
    if action == "running_apps":
        apps = state["running_apps"]
        if not apps:
            return "I couldn't read running apps right now."
        shown = ", ".join(f"{a['name']} ({a['count']})" for a in apps[:5])
        return f"Top running apps: {shown}."
    if action == "media_state":
        media = state["media"]
        if not media.get("available"):
            return "Media state is unavailable because playerctl is not installed."
        if media.get("title"):
            artist = media.get("artist") or "unknown artist"
            return f"Media is {media.get('status')}. {media.get('title')} by {artist}."
        return f"Media state: {media.get('status')}."

    aw = state["active_window"]
    media = state["media"]
    parts: list[str] = []
    if aw.get("title"):
        parts.append(f"Focused: {aw['title']}")
    if state["windows"]:
        parts.append(f"{len(state['windows'])} windows visible")
    if state["running_apps"]:
        parts.append(f"top app: {state['running_apps'][0]['name']}")
    if media.get("available"):
        parts.append(f"media: {media.get('status')}")
    return ". ".join(parts) + "." if parts else "I couldn't read desktop state right now."


def _summary_for_action(action: str, target: str, state: dict[str, Any]) -> str:
    if action == "focus_app":
        match = state.get("matched_window") or {}
        if match.get("title"):
            return f"Focused {match['title']}."
        return f"I couldn't find an open app or window matching {target}."
    if action in ("close_app", "close_window"):
        match = state.get("matched_window") or {}
        if match.get("title"):
            return f"Closed {match['title']}."
        return f"I couldn't find an open app or window matching {target}."
    if action == "kill_process":
        proc = state.get("matched_process") or {}
        if proc.get("name"):
            return f"Stopped process {proc['name']}."
        return f"I couldn't find a running process matching {target}."
    return "Desktop action completed."


@tool
def desktop_context(action: str) -> str:
    """Read live desktop state.
    action: 'active_window', 'list_windows', 'running_apps', 'media_state', 'full_state'."""
    action = action.lower().strip()
    logger.info("desktop_context action=%s", action)

    state = {
        "active_window": None,
        "windows": [],
        "running_apps": [],
        "media": {},
    }

    if action == "active_window":
        state["active_window"] = _active_window()
    elif action == "list_windows":
        state["windows"] = _list_windows()
    elif action == "running_apps":
        state["running_apps"] = _running_apps()
    elif action == "media_state":
        state["media"] = _media_state()
    elif action == "full_state":
        state["active_window"] = _active_window()
        state["windows"] = _list_windows()
        state["running_apps"] = _running_apps()
        state["media"] = _media_state()
    else:
        return json.dumps(
            {
                "summary": "Unknown desktop action. Use: active_window, list_windows, running_apps, media_state, full_state.",
                "desktop_state": state,
            }
        )

    return json.dumps(
        {
            "summary": _summary_for_state(action, state),
            "desktop_state": state,
        }
    )


@tool
def desktop_action(action: str, target: str = "", confirmed: bool = False) -> str:
    """Control desktop windows/apps.
    action: 'focus_app', 'close_app', 'close_window', 'kill_process'."""
    action = action.lower().strip()
    target = (target or "").strip()
    logger.info("desktop_action action=%s target=%s", action, target)

    state: dict[str, Any] = {
        "matched_window": None,
        "matched_process": None,
        "active_window": _active_window(),
        "windows": _list_windows(),
        "running_apps": _running_apps(),
        "media": _media_state(),
    }

    if action == "focus_app":
        match = _find_window(target)
        if not match:
            return json.dumps(
                {
                    "summary": f"I couldn't find an open app or window matching {target}.",
                    "desktop_state": state,
                }
            )
        state["matched_window"] = match
        try:
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", str(match["window_id"])],
                check=True,
                capture_output=True,
                timeout=5,
            )
        except Exception as e:
            return json.dumps(
                {
                    "summary": f"I found {match.get('title')}, but couldn't focus it: {e}",
                    "desktop_state": state,
                }
            )
        state["active_window"] = _active_window()
        return json.dumps(
            {
                "summary": _summary_for_action(action, target, state),
                "desktop_state": state,
            }
        )

    if action in ("close_app", "close_window"):
        match = _find_window(target)
        if match:
            state["matched_window"] = match
            if not confirmed:
                return f"NEEDS_PERMISSION:Close {match.get('title') or target}"
            try:
                subprocess.run(
                    ["xdotool", "windowclose", str(match["window_id"])],
                    check=True,
                    capture_output=True,
                    timeout=5,
                )
            except Exception as e:
                return json.dumps(
                    {
                        "summary": f"I found {match.get('title')}, but couldn't close it: {e}",
                        "desktop_state": state,
                    }
                )
            state["windows"] = _list_windows()
            state["active_window"] = _active_window()
            return json.dumps(
                {
                    "summary": _summary_for_action(action, target, state),
                    "desktop_state": state,
                }
            )

        proc_match = _find_process(target)
        if not proc_match:
            return json.dumps(
                {
                    "summary": f"I couldn't find an open app or window matching {target}.",
                    "desktop_state": state,
                }
            )
        state["matched_process"] = proc_match
        if not confirmed:
            return f"NEEDS_PERMISSION:Close {proc_match['name']}"
        try:
            psutil.Process(proc_match["pid"]).terminate()
        except Exception as e:
            return json.dumps(
                {
                    "summary": f"I found process {proc_match['name']}, but couldn't stop it: {e}",
                    "desktop_state": state,
                }
            )
        state["running_apps"] = _running_apps()
        return json.dumps(
            {
                "summary": f"Closed {proc_match['name']} via process (no window match on this desktop).",
                "desktop_state": state,
            }
        )

    if action == "kill_process":
        proc_match = _find_process(target)
        if not proc_match:
            return json.dumps(
                {
                    "summary": f"I couldn't find a running process matching {target}.",
                    "desktop_state": state,
                }
            )
        state["matched_process"] = proc_match
        if not confirmed:
            return f"NEEDS_PERMISSION:Kill process {proc_match['name']} ({proc_match['pid']})"
        try:
            psutil.Process(proc_match["pid"]).terminate()
        except Exception as e:
            return json.dumps(
                {
                    "summary": f"I found process {proc_match['name']}, but couldn't stop it: {e}",
                    "desktop_state": state,
                }
            )
        state["running_apps"] = _running_apps()
        return json.dumps(
            {
                "summary": _summary_for_action(action, target, state),
                "desktop_state": state,
            }
        )

    return json.dumps(
        {
            "summary": "Unknown desktop action. Use: focus_app, close_app, close_window, kill_process.",
            "desktop_state": state,
        }
    )
