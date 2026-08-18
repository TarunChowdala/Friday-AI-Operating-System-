"""Launch or focus applications."""
import subprocess
from langchain_core.tools import tool
from app.core.logger import get_logger

logger = get_logger(__name__)


@tool
def open_application(app_name: str) -> str:
    """Opens a desktop application. Accepts friendly names like 'notepad', 'chrome', 'terminal', 'code', or a real binary name."""
    logger.info(f"Opening application: {app_name}")
    raw = (app_name or "").strip().lower()
    aliases: dict[str, list[str]] = {
        "notepad": ["gnome-text-editor", "gedit", "kate", "mousepad", "xed", "leafpad"],
        "text editor": ["gnome-text-editor", "gedit", "kate", "mousepad"],
        "editor": ["gnome-text-editor", "gedit", "kate"],
        "chrome": ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"],
        "browser": ["google-chrome", "firefox", "chromium"],
        "terminal": ["ptyxis", "gnome-terminal", "kgx", "konsole", "xterm"],
        "code": ["code", "codium"],
        "vscode": ["code", "codium"],
        "spotify": ["spotify"],
        "camera": ["snapshot", "cheese"],
        "webcam": ["snapshot", "cheese"],
    }
    candidates = aliases.get(raw, [raw.replace(" ", "-")])
    last_err = None
    for cmd in candidates:
        try:
            subprocess.Popen([cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            kind = "editor" if raw in ("notepad", "text editor", "editor") or cmd in (
                "gnome-text-editor", "gedit", "kate", "mousepad", "xed", "leafpad"
            ) else "app"
            return f"OK:opened app={cmd} kind={kind} alias={raw or cmd}"
        except FileNotFoundError as e:
            last_err = e
            continue
        except Exception as e:
            logger.error(f"Failed to open {cmd}: {e}")
            last_err = e
            continue
    logger.error(f"Application not found: {app_name} tried={candidates}")
    return f"Failed: I couldn't find an application named {app_name} on your system."
