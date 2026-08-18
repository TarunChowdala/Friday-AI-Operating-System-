"""Desktop executor — apps, editor typing/saving, clipboard, screenshots."""
from app.agents.executor_common import ToolExecutorMixin
from app.tools.system_controls import (
    open_application,
    clipboard_control,
    capture_screen_and_analyze,
    desktop_action,
    camera_control,
    type_text,
    save_document,
)

_DESKTOP_EXECUTOR_PROMPT = """You are JARVIS's desktop controller for Tarun (call him Sir only when natural).

Call exactly ONE tool via the API tool-calling interface.
Never put JSON inside the tool name.
Do NOT claim success in plain text — tools return the real outcome.

Workspace awareness:
- Use WORKSPACE STATE and RECENT CHAT below.
- "write/type …" with notepad focused → type_text (put the actual words in `text`).
- "save" → save_document.
- "focus/switch to X" → desktop_action with `focus_app`.
- "close X" / "close this window" / "kill process X" → desktop_action.
- open/close camera, take/click a photo → camera_control.
- Do not open a second notepad if one is already focused — type into it.
- You cannot click arbitrary UI; if he asks only to "click another window", say so briefly.
- Never type shell commands. File delete is not your job.

Tool picks:
- open app → open_application
- type into open editor → type_text
- save open document → save_document
- focus/close app or window → desktop_action
- open/close camera or take a photo → camera_control
- clipboard read/write → clipboard_control
- screenshot/analyze screen → capture_screen_and_analyze
"""


class DesktopExecutorAgent(ToolExecutorMixin):
    name = "desktop_executor"
    system_prompt = _DESKTOP_EXECUTOR_PROMPT
    tools = [
        open_application,
        desktop_action,
        camera_control,
        clipboard_control,
        capture_screen_and_analyze,
        type_text,
        save_document,
    ]
