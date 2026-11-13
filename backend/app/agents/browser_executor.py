"""Browser executor — general web browsing and in-page automation."""
from app.agents.executor_common import ToolExecutorMixin
from app.tools.system_controls import open_url, search_google, play_youtube

_BROWSER_PROMPT = """You are JARVIS's browser controller for Tarun (Sir).
Understand the user's intent and pick the appropriate tool:

Tools:
- open_url(url="..."): Open a requested website or URL.
- search_google(query="..."): Search Google on the web.
- play_youtube(query="..."): Play a video or music.

In-page tools (for interacting with the currently open webpage):
- playwright_snapshot(): Read or inspect what elements/text are on the active page.
- playwright_click(selector="..."): Click an element, button, or link.
- playwright_type(selector="...", text="..."): Type text into an input or textbox.
- playwright_press_key(key="Enter"): Press a keyboard key.

RULES:
1. Understand the user's request and open the site or URL they want.
2. NEVER guess a random site or open a site unprompted. If the user's request is ambiguous or you do not know what site they want, DO NOT call open_url — reply in plain text asking for clarification.
3. For general conversation or meta-questions, do NOT call any tool — reply in plain text.
Call at most ONE tool per turn.
"""


class BrowserExecutorAgent(ToolExecutorMixin):
    name = "browser_executor"
    system_prompt = _BROWSER_PROMPT
    tools = [open_url, search_google, play_youtube]

    def __init__(self) -> None:
        from app.core.config import get_settings

        if get_settings().PLAYWRIGHT_MCP_ENABLED:
            from app.tools.playwright_mcp import ALL_PLAYWRIGHT_TOOLS

            self.tools = [
                open_url,
                search_google,
                play_youtube,
                *ALL_PLAYWRIGHT_TOOLS,
            ]

        super().__init__()
