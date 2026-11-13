"""Playwright MCP browser automation integration for JARVIS.

Connects to the Playwright MCP server (via `npx -y @playwright/mcp@latest`)
to enable deep browser automation:
- DOM navigation
- Semantic accessibility snapshots (reading web pages without vision tokens)
- Robust element clicking and typing
- Web screenshots
"""
from __future__ import annotations

import base64
import json
import shlex
import tempfile
from typing import Any, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logger import get_logger
from app.tools.jucce.protocol import MCPStdioClient, MCPStdioError

logger = get_logger(__name__)

_client: Optional[MCPStdioClient] = None
_discovered_tools: dict[str, dict[str, Any]] = {}


def _get_client() -> MCPStdioClient:
    global _client, _discovered_tools
    if _client is None:
        cfg = get_settings()
        command = [cfg.PLAYWRIGHT_MCP_COMMAND, *shlex.split(cfg.PLAYWRIGHT_MCP_ARGS)]
        logger.info("Initializing Playwright MCP server with command: %s", command)
        _client = MCPStdioClient(command, timeout=cfg.PLAYWRIGHT_MCP_TIMEOUT_SECONDS)
        try:
            tools = _client.list_tools()
            _discovered_tools = {str(t.get("name")): t for t in tools if t.get("name")}
            logger.info("Playwright MCP discovered %d tools: %s", len(_discovered_tools), sorted(_discovered_tools.keys()))
        except Exception as exc:
            logger.warning("Playwright MCP discovery failed: %s", exc)
            _discovered_tools = {}
    return _client


def _enabled() -> bool:
    return get_settings().PLAYWRIGHT_MCP_ENABLED


def _disabled_msg() -> str:
    return "Playwright MCP is disabled. Set PLAYWRIGHT_MCP_ENABLED=true in .env to enable."


def _format_result(result: dict[str, Any]) -> str:
    content = result.get("content") or []
    texts = [item.get("text", "") for item in content if item.get("type") == "text"]
    raw_str = "\n".join(texts) if texts else ""

    # Check for image content
    for item in content:
        if item.get("type") == "image" and item.get("data"):
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(base64.b64decode(item["data"]))
                meta = {k: v for k, v in result.items() if k != "content"}
                return json.dumps({"image_path": f.name, **meta})

    if not raw_str:
        return str({k: v for k, v in result.items() if k != "content"})

    # Clean navigation / page info into a structured result
    if "Page Title:" in raw_str or "Page URL:" in raw_str:
        title = ""
        url = ""
        for line in raw_str.splitlines():
            line_s = line.strip()
            if line_s.startswith("- Page Title:"):
                title = line_s.split(":", 1)[1].strip()
            elif line_s.startswith("- Page URL:"):
                url = line_s.split(":", 1)[1].strip()
        if title or url:
            return f"OK:page_loaded title='{title}' url='{url}'"

    return raw_str


def _find_tool(*candidates: str) -> Optional[str]:
    for candidate in candidates:
        if candidate in _discovered_tools:
            return candidate
    return None


def _call_mcp(tool_name: str, args: dict[str, Any]) -> str:
    if not _enabled():
        return _disabled_msg()
    try:
        client = _get_client()
        if not _discovered_tools:
            # Attempt re-discovery
            tools = client.list_tools()
            for t in tools:
                if t.get("name"):
                    _discovered_tools[str(t["name"])] = t

        actual_tool = tool_name
        if actual_tool not in _discovered_tools:
            # Fallback search by substring
            match = next((k for k in _discovered_tools if tool_name in k or k in tool_name), None)
            if match:
                actual_tool = match
            else:
                return (
                    f"Tool '{tool_name}' not found on Playwright MCP server. "
                    f"Available tools: {sorted(_discovered_tools.keys())}"
                )

        result = client.call_tool(actual_tool, args)
        return _format_result(result)
    except (MCPStdioError, RuntimeError, ValueError, OSError) as exc:
        logger.warning("Playwright MCP %s failed: %s", tool_name, exc)
        return f"Playwright MCP '{tool_name}' failed: {exc}"


# ---------------------------------------------------------------------------
# Input Schemas
# ---------------------------------------------------------------------------

class NavigateInput(BaseModel):
    url: str = Field(description="The complete web URL to navigate to (e.g. 'https://github.com')")


class ClickInput(BaseModel):
    selector: str = Field(
        description="Target selector, element description, or text to click (e.g. 'text=Login', '#submit-btn', 'button')"
    )


class TypeInput(BaseModel):
    selector: str = Field(description="Selector or element reference for the text field to fill")
    text: str = Field(description="Text to type into the input field")


class PressKeyInput(BaseModel):
    key: str = Field(description="Key to press (e.g. 'Enter', 'Tab', 'ArrowDown')")


class CustomActionInput(BaseModel):
    tool_name: str = Field(description="Name of the MCP tool to call on Playwright MCP server")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments dictionary for the tool")


# ---------------------------------------------------------------------------
# LangChain Tools
# ---------------------------------------------------------------------------

@tool("playwright_navigate", args_schema=NavigateInput)
def playwright_navigate(url: str) -> str:
    """Navigate to a URL using the automated Playwright browser."""
    tool_name = _find_tool("browser_navigate", "navigate", "page_navigate") or "browser_navigate"
    return _call_mcp(tool_name, {"url": url})


@tool("playwright_snapshot")
def playwright_snapshot() -> str:
    """Capture the accessibility snapshot / text content of the currently open webpage."""
    tool_name = _find_tool("browser_snapshot", "snapshot", "page_snapshot") or "browser_snapshot"
    return _call_mcp(tool_name, {})


@tool("playwright_click", args_schema=ClickInput)
def playwright_click(selector: str) -> str:
    """Click an element, link, or button on the webpage by selector or text."""
    tool_name = _find_tool("browser_click", "click", "page_click") or "browser_click"
    # Provide both common parameter names so the server gets what it expects
    return _call_mcp(tool_name, {"element": selector, "selector": selector})


@tool("playwright_type", args_schema=TypeInput)
def playwright_type(selector: str, text: str) -> str:
    """Fill or type text into an input field on the webpage."""
    tool_name = _find_tool("browser_type", "browser_fill", "type", "fill") or "browser_type"
    return _call_mcp(tool_name, {"element": selector, "selector": selector, "text": text, "value": text})


@tool("playwright_press_key", args_schema=PressKeyInput)
def playwright_press_key(key: str) -> str:
    """Press a key (e.g. 'Enter', 'Escape') on the current web page."""
    tool_name = _find_tool("browser_press_key", "press_key", "press") or "browser_press_key"
    return _call_mcp(tool_name, {"key": key})


@tool("playwright_screenshot")
def playwright_screenshot() -> str:
    """Take a screenshot of the current page in the Playwright browser."""
    tool_name = _find_tool("browser_screenshot", "screenshot", "page_screenshot") or "browser_screenshot"
    return _call_mcp(tool_name, {})


@tool("playwright_custom_action", args_schema=CustomActionInput)
def playwright_custom_action(tool_name: str, arguments: dict[str, Any] = {}) -> str:
    """Execute any native Playwright MCP tool by name with custom arguments."""
    return _call_mcp(tool_name, arguments)


ALL_PLAYWRIGHT_TOOLS = [
    playwright_navigate,
    playwright_snapshot,
    playwright_click,
    playwright_type,
    playwright_press_key,
    playwright_screenshot,
    playwright_custom_action,
]


def close_playwright_mcp() -> None:
    """Shutdown the Playwright MCP client process."""
    global _client, _discovered_tools
    if _client:
        try:
            _client.close()
        except Exception as exc:
            logger.debug("Error closing Playwright MCP client: %s", exc)
    _client = None
    _discovered_tools = {}

