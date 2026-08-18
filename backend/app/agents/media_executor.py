"""Media executor — play/pause/resume/skip/mute media."""
from app.agents.executor_common import ToolExecutorMixin
from app.tools.system_controls import media_control

_MEDIA_EXECUTOR_PROMPT = """You are JARVIS's media controller for Tarun (call him Sir only when natural).

Call exactly ONE tool via the API tool-calling interface.
Never put JSON inside the tool name.
Do NOT claim success in plain text — tools return the real outcome.

Use this agent for playback control only.

Tool picks:
- pause/play/resume/next/previous/mute/unmute → media_control
"""


class MediaExecutorAgent(ToolExecutorMixin):
    name = "media_executor"
    system_prompt = _MEDIA_EXECUTOR_PROMPT
    tools = [media_control]
