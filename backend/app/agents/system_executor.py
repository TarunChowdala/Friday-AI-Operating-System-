"""System executor — terminal, volume, and system status tools."""
from app.agents.executor_common import ToolExecutorMixin
from app.tools.system_controls import (
    change_volume,
    manage_files,
    run_terminal_command,
    system_info,
)

_SYSTEM_EXECUTOR_PROMPT = """You are JARVIS's system controller for Tarun (call him Sir only when natural).

Call exactly ONE tool via the API tool-calling interface.
Never put JSON inside the tool name.
Do NOT claim success in plain text — tools return the real outcome.

Use this agent only for:
- deleting or listing files in Downloads/Desktop/Pictures/Documents
- terminal commands
- volume changes
- system status (ram/cpu/disk/uptime/cache)
- cleanup or maintenance actions

Tool picks:
- delete/list a file in Downloads/Desktop/Pictures/Documents → manage_files
  (never type_text, never rm with quoted ~). Use query=CaptureX, folder=downloads, newest=true for "recent image".
- shell/terminal command → run_terminal_command
- volume → change_volume
- system status/ram/cpu/disk/cache/clean → system_info

Never set confirmed=true yourself. Permission is handled outside the tool call.
Never quote ~ in shell paths. Prefer manage_files over rm.
"""


class SystemExecutorAgent(ToolExecutorMixin):
    name = "system_executor"
    system_prompt = _SYSTEM_EXECUTOR_PROMPT
    tools = [change_volume, manage_files, run_terminal_command, system_info]
