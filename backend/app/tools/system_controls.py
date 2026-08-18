"""System controls — re-exports all tool functions from split modules.

The executor imports from here, so this file keeps backward compatibility.
Actual implementations live in their own files under app/tools/.
"""
from app.tools.volume import change_volume
from app.tools.applications import open_application
from app.tools.browser import open_url, search_google, play_youtube
from app.tools.terminal import run_terminal_command
from app.tools.media import media_control
from app.tools.clipboard import clipboard_control
from app.tools.screen import capture_screen_and_analyze
from app.tools.typing import type_text, save_document
from app.tools.system import system_info
from app.tools.desktop import desktop_context, desktop_action
from app.tools.camera import camera_control
from app.tools.filesystem import manage_files

__all__ = [
    "change_volume",
    "open_application",
    "open_url",
    "search_google",
    "play_youtube",
    "run_terminal_command",
    "media_control",
    "clipboard_control",
    "capture_screen_and_analyze",
    "type_text",
    "save_document",
    "system_info",
    "desktop_context",
    "desktop_action",
    "camera_control",
    "manage_files",
]
