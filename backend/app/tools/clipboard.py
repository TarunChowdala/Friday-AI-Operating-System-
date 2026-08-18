"""Read or write clipboard (Wayland + X11 support)."""
import subprocess
from langchain_core.tools import tool
from app.core.logger import get_logger

logger = get_logger(__name__)


@tool
def clipboard_control(action: str, text: str = "") -> str:
    """Gets or sets the system clipboard content. action can be 'get' or 'set'."""
    logger.info(f"Clipboard action: {action}")
    try:
        if action.lower() == "get":
            for cmd in [["wl-paste"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "-b", "-o"]]:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and res.stdout.strip():
                    return f"Clipboard content: {res.stdout.strip()}"
            return "Clipboard is empty or no clipboard tool available."
        elif action.lower() == "set":
            if not text:
                return "No text provided to copy to clipboard."
            for cmd in [["wl-copy"], ["xclip", "-selection", "clipboard"]]:
                try:
                    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                    p.communicate(input=text.encode('utf-8'), timeout=5)
                    if p.returncode == 0:
                        return f"Copied text to clipboard: '{text[:50]}'"
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
            return "Failed: no clipboard tool (wl-copy/xclip) available."
        return "Invalid clipboard action. Use 'get' or 'set'."
    except Exception as e:
        logger.error(f"Clipboard error: {e}")
        return f"Clipboard error: {e}"
