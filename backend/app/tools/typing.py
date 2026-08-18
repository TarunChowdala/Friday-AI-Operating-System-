"""Type text and save documents (Wayland ydotool + X11 xdotool support)."""
import os
import subprocess
from langchain_core.tools import tool
from app.core.logger import get_logger

logger = get_logger(__name__)


def _get_input_tool() -> str | None:
    """Returns 'ydotool' or 'xdotool' based on session type and availability."""
    import shutil
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland" and shutil.which("ydotool"):
        return "ydotool"
    if shutil.which("xdotool"):
        return "xdotool"
    if shutil.which("ydotool"):
        return "ydotool"
    return None


def _require_input_tool() -> tuple[str | None, str | None]:
    """Returns (tool_name, error_msg). If tool_name is set, error is None."""
    tool = _get_input_tool()
    if tool:
        return tool, None
    return None, (
        "Failed: no input automation tool available. "
        "Install ydotool for Wayland: sudo dnf install ydotool && "
        "sudo systemctl enable --now ydotoold"
    )


def _focus_window_by_hints(hints: list[str]) -> str | None:
    """Activate the first matching window via xdotool. Returns window id or None."""
    for hint in hints:
        if not hint:
            continue
        res = subprocess.run(
            ["xdotool", "search", "--name", hint],
            capture_output=True, text=True, timeout=5,
        )
        ids = [x.strip() for x in (res.stdout or "").splitlines() if x.strip()]
        if not ids:
            continue
        wid = ids[-1]
        subprocess.run(
            ["xdotool", "windowactivate", "--sync", wid],
            check=True, timeout=5, capture_output=True,
        )
        return wid
    return None


@tool
def type_text(text: str, target_hint: str = "") -> str:
    """Types text into the focused editor/app window (e.g. notepad JARVIS opened).
    Use after opening notepad/editor when the user asks to write or type something.
    target_hint: optional window name hint like 'gedit', 'Text Editor', 'kate'."""
    logger.info("type_text len=%d hint=%s", len(text or ""), target_hint)
    input_tool, err = _require_input_tool()
    if err:
        return err
    if not (text or "").strip():
        return "Failed: no text provided to type."

    import shutil
    import time

    if shutil.which("xdotool"):
        hints = []
        if target_hint:
            hints.append(target_hint)
        hints.extend(["Text Editor", "gnome-text-editor", "gedit", "Kate", "Mousepad", "Untitled", "notepad"])
        wid = _focus_window_by_hints(hints)
        if not wid:
            return "Failed: I couldn't find the editor window to type into. Open notepad first, then ask me to write."
        time.sleep(0.3)

    try:
        if input_tool == "ydotool":
            subprocess.run(["ydotool", "type", "--key-delay", "12", "--", text], check=True, timeout=120, capture_output=True)
        else:
            subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "12", "--", text], check=True, timeout=120, capture_output=True)
        return f"OK:typed chars={len(text)}"
    except Exception as e:
        logger.error("type_text failed: %s", e)
        return f"Failed to type text: {e}"


@tool
def save_document(filename: str = "") -> str:
    """Saves the focused document (Ctrl+S). If filename is provided, types it in the Save dialog and confirms."""
    logger.info("save_document filename=%r", filename)
    input_tool, err = _require_input_tool()
    if err:
        return err

    import shutil
    import time

    try:
        if shutil.which("xdotool"):
            hints = ["Text Editor", "gnome-text-editor", "gedit", "Kate", "Mousepad", "Untitled", "Save"]
            wid = _focus_window_by_hints(hints)
            if not wid:
                return "Failed: I couldn't find the editor window to save. Open notepad and write first."
            time.sleep(0.2)

        # Send Ctrl+S
        if input_tool == "ydotool":
            subprocess.run(["ydotool", "key", "29:1", "31:1", "31:0", "29:0"], check=True, timeout=5, capture_output=True)
        else:
            subprocess.run(["xdotool", "key", "--clearmodifiers", "ctrl+s"], check=True, timeout=5, capture_output=True)

        time.sleep(0.5)
        if filename.strip():
            if input_tool == "ydotool":
                subprocess.run(["ydotool", "type", "--key-delay", "12", "--", filename.strip()], check=True, timeout=30, capture_output=True)
                time.sleep(0.2)
                subprocess.run(["ydotool", "key", "28:1", "28:0"], check=True, timeout=5, capture_output=True)
            else:
                subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "12", "--", filename.strip()], check=True, timeout=30, capture_output=True)
                time.sleep(0.2)
                subprocess.run(["xdotool", "key", "Return"], check=True, timeout=5, capture_output=True)
            return f"OK:saved filename={filename.strip()}"
        return "OK:saved (Ctrl+S sent to focused editor)"
    except Exception as e:
        logger.error("save_document failed: %s", e)
        return f"Failed to save document: {e}"
