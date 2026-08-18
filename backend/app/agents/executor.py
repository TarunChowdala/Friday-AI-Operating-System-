"""Legacy monolithic executor kept for compatibility.

Normal action routing should use the specialized executors instead.
"""
from app.agents.executor_common import ToolExecutorMixin
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
    system_info,
)
_LEGACY_EXECUTOR_SYSTEM = """You are JARVIS's legacy all-tools controller for Tarun.

This compatibility executor should only be used as a fallback path.
Prefer the specialized executors in normal routing.
Call exactly ONE tool via the API tool-calling interface.
Do NOT claim success in plain text — tools return the real outcome.
"""


class ExecutorAgent(ToolExecutorMixin):
    name = "executor"
    system_prompt = _LEGACY_EXECUTOR_SYSTEM
    tools = [
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
        system_info,
    ]
