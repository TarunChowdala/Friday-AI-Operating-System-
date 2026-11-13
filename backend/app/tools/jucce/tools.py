"""LangChain-facing JUCCE tools — read-only observations + desktop actions.

computer-use-linux is a Node.js binary (npm: @agent-sh/computer-use-linux).
Jarvis does NOT import it as a Python package.  Instead it launches it as a
subprocess and speaks the MCP stdio JSON-RPC protocol with it directly:

    subprocess.Popen(["computer-use-linux", "mcp"], stdin=PIPE, stdout=PIPE)

The binary is the MCP *server*; MCPStdioClient in protocol.py is the *client*.
All tool calls go over stdin/stdout as JSON-RPC 2.0 messages.
"""
from __future__ import annotations

import base64
import json
import tempfile
from enum import Enum
from typing import Any, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logger import get_logger
from app.tools.jucce import get_computer_control_adapter
from app.tools.jucce.protocol import MCPStdioError

logger = get_logger(__name__)

_adapter = None
_discovered: set[str] = set()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_adapter():
    global _adapter, _discovered
    if _adapter is None:
        _adapter = get_computer_control_adapter()
        try:
            available = _adapter.discover_tools()
            _discovered = {str(item.get("name")) for item in available}
            logger.info("JUCCE discovered %d tools on %s", len(_discovered), _adapter.os_name)
        except Exception as exc:
            logger.warning("JUCCE MCP discovery failed: %s", exc)
            _discovered = set()
    return _adapter


def _enabled() -> bool:
    return get_settings().JUCCE_ENABLED


def _disabled_msg() -> str:
    return "JUCCE is disabled. Set JUCCE_ENABLED=true to use the MCP desktop adapter."


def _format_content(result: dict[str, Any], mcp_tool: str = "") -> str:
    """Return clean human-readable text from an MCP tool result, skipping raw binary blobs."""
    content = result.get("content") or []
    texts = [item.get("text", "") for item in content if item.get("type") == "text"]
    raw_str = "\n".join(texts) if texts else ""

    # Parse potential JSON payload inside raw_str or direct keys in result
    data: Any = None
    if raw_str:
        try:
            data = json.loads(raw_str)
        except Exception:
            pass
    if data is None and isinstance(result, dict):
        data = result

    if isinstance(data, dict):
        # Format list_windows / windows
        windows = data.get("windows")
        if windows is None and mcp_tool == "list_windows" and isinstance(data.get("result"), list):
            windows = data.get("result")
        if isinstance(windows, list):
            titles = []
            for w in windows:
                if isinstance(w, dict):
                    t = (w.get("title") or w.get("app_id") or w.get("wm_class") or "").strip()
                    if t and not w.get("hidden", False):
                        titles.append(t)
            if titles:
                return f"Open windows ({len(titles)}): " + "; ".join(titles)
            return "No open visible windows found."

        # Format focused_window
        if mcp_tool == "focused_window" or "focused_window" in data:
            w = data.get("focused_window") or data.get("window") or data
            if isinstance(w, dict):
                t = (w.get("title") or w.get("app_id") or w.get("wm_class") or "").strip()
                if t:
                    return f"Currently focused window: {t}"

        # Format list_apps
        if "apps" in data or mcp_tool == "list_apps":
            apps = data.get("apps") or []
            if isinstance(apps, list):
                names = [a.get("name") or a.get("app_id") or str(a) for a in apps if isinstance(a, dict)]
                if names:
                    return f"Running apps: {', '.join(names)}"

        # Format get_app_state / accessibility_tree
        if "accessibility_tree" in data or mcp_tool == "get_app_state":
            nodes = data.get("accessibility_tree") or []
            if isinstance(nodes, list):
                elements = []
                for n in nodes:
                    if isinstance(n, dict):
                        name = (n.get("name") or "").strip()
                        role = (n.get("role") or "").lower()
                        if name and name.lower() not in ("gnome-shell", "root", "desktop", "application"):
                            if role in ("heading", "link", "push button", "label", "text", "page tab", "entry"):
                                elements.append(name)
                            elif len(name) > 3 and name not in elements:
                                elements.append(name)
                unique_elements = list(dict.fromkeys(elements))[:6]
                if unique_elements:
                    return "Visible on screen: " + ", ".join(unique_elements)
                return "Screen state inspected; no prominent UI text found."

        # Clean failure messages from action tools
        if data.get("ok") is False:
            msg = data.get("message") or "Action failed."
            if "remote desktop portal" in msg.lower() or "denied" in msg.lower():
                return "Failed: Remote desktop permission was denied by the system."
            return f"Failed: {msg}"

        # Clean success messages from action tools
        if data.get("ok") is True:
            act = data.get("action") or "action"
            return f"OK:{act} completed"

        # Strip internal debug noise
        cleaned = {k: v for k, v in data.items() if k not in ("backend", "note", "content", "error") and v is not None}
        if cleaned:
            return json.dumps(cleaned)

    if raw_str:
        return raw_str

    return str({k: v for k, v in result.items() if k not in ("content", "backend", "note")})


def _call(mcp_tool: str, args: dict[str, Any] = {}) -> str:
    """Shared: check enabled, check discovered, call tool, return formatted text."""
    if not _enabled():
        return _disabled_msg()
    adapter = _get_adapter()
    if mcp_tool not in _discovered:
        return (
            f"JUCCE tool '{mcp_tool}' is unavailable on {adapter.os_name}; "
            f"discovered: {sorted(_discovered)}"
        )
    try:
        return _format_content(adapter.call_tool(mcp_tool, args), mcp_tool=mcp_tool)
    except (MCPStdioError, RuntimeError, ValueError) as exc:
        logger.warning("JUCCE %s failed: %s", mcp_tool, exc)
        return f"JUCCE {mcp_tool} failed: {exc}"


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------

class DesktopObservation(str, Enum):
    readiness      = "readiness"
    focused_window = "focused_window"
    list_windows   = "list_windows"
    list_apps      = "list_apps"


class JucceObserveInput(BaseModel):
    action: DesktopObservation = Field(description="Read-only desktop observation to perform")


_MCP_TOOL_BY_ACTION = {
    "readiness":      "doctor",
    "focused_window": "focused_window",
    "list_windows":   "list_windows",
    "list_apps":      "list_apps",
}


class JucceScreenshotInput(BaseModel):
    window_id: Optional[int] = Field(
        default=None,
        description="Compositor window ID from list_windows to capture a single window; omit for full screen.",
    )
    max_width: Optional[int] = Field(default=None, description="Max width in pixels.")
    max_height: Optional[int] = Field(default=None, description="Max height in pixels.")


class JucceClickInput(BaseModel):
    x: int = Field(description="Screen X coordinate to click.")
    y: int = Field(description="Screen Y coordinate to click.")
    button: str = Field(default="left", description="Mouse button: left | right | middle.")
    screenshot_after: bool = Field(default=False, description="Return a screenshot after clicking.")


class JucceTypeInput(BaseModel):
    text: str = Field(description="Text to type into the focused input field.")
    screenshot_after: bool = Field(default=False, description="Return a screenshot after typing.")


class JucceKeyInput(BaseModel):
    key: str = Field(
        description="Key or chord to press, e.g. 'Return', 'ctrl+c', 'alt+F4'."
    )
    screenshot_after: bool = Field(default=False, description="Return a screenshot after key press.")


class JucceScrollInput(BaseModel):
    x: int = Field(description="Screen X coordinate to scroll at.")
    y: int = Field(description="Screen Y coordinate to scroll at.")
    direction: str = Field(description="Scroll direction: up | down | left | right.")
    amount: int = Field(default=3, description="Number of scroll steps.")
    screenshot_after: bool = Field(default=False, description="Return a screenshot after scrolling.")


class JucceAppStateInput(BaseModel):
    app_name: str = Field(description="Name of the desktop application to inspect (e.g. 'Firefox').")


class JucceActivateWindowInput(BaseModel):
    window_id: int = Field(description="Compositor window ID from list_windows to bring into focus.")
    screenshot_after: bool = Field(default=False, description="Return a screenshot after activating.")


class JuccePerformActionInput(BaseModel):
    snapshot_id: str = Field(description="Snapshot ID returned by get_app_state.")
    element_index: int = Field(description="Element index from the accessibility tree snapshot.")
    action: str = Field(default="default", description="AT-SPI action name, e.g. 'default', 'press', 'toggle'.")
    screenshot_after: bool = Field(default=False, description="Return a screenshot after the action.")


# ---------------------------------------------------------------------------
# Tools — observations (read-only)
# ---------------------------------------------------------------------------

@tool("jucce_observe_desktop", args_schema=JucceObserveInput)
def jucce_observe_desktop(action: DesktopObservation) -> str:
    """Read desktop readiness, focused window, open windows, or running desktop apps through JUCCE."""
    mcp_tool = _MCP_TOOL_BY_ACTION[action.value]
    return _call(mcp_tool)


@tool("jucce_screenshot", args_schema=JucceScreenshotInput)
def jucce_screenshot(
    window_id: Optional[int] = None,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
) -> str:
    """Capture a screenshot of the full desktop or a specific window via JUCCE.

    Returns the path to the saved PNG file and metadata.
    Pass window_id (from jucce_observe_desktop list_windows) to capture a single window.
    """
    args: dict[str, Any] = {}
    if window_id is not None:
        args["window_id"] = window_id
    if max_width is not None:
        args["max_width"] = max_width
    if max_height is not None:
        args["max_height"] = max_height

    if not _enabled():
        return _disabled_msg()
    adapter = _get_adapter()
    if "screenshot" not in _discovered:
        return f"JUCCE 'screenshot' tool not available; discovered: {sorted(_discovered)}"
    try:
        result = adapter.call_tool("screenshot", args)
    except (MCPStdioError, RuntimeError, ValueError) as exc:
        logger.warning("JUCCE screenshot failed: %s", exc)
        return f"JUCCE screenshot failed: {exc}"

    # Save any embedded base64 image to a temp file; return path + metadata.
    content = result.get("content") or []
    for item in content:
        if item.get("type") == "image" and item.get("data"):
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(base64.b64decode(item["data"]))
                logger.info("JUCCE screenshot saved to %s", f.name)
                meta = {k: v for k, v in result.items() if k != "content"}
                return json.dumps({"path": f.name, **meta})
    return _format_content(result)


@tool("jucce_get_app_state", args_schema=JucceAppStateInput)
def jucce_get_app_state(app_name: str) -> str:
    """Return the accessibility tree (AT-SPI) of a running desktop app as JSON.

    Use the returned snapshot_id and element_index values with jucce_perform_action or jucce_click.
    """
    return _call("get_app_state", {"app_name": app_name})


# ---------------------------------------------------------------------------
# Tools — actions (mutating)
# ---------------------------------------------------------------------------

@tool("jucce_click", args_schema=JucceClickInput)
def jucce_click(
    x: int,
    y: int,
    button: str = "left",
    screenshot_after: bool = False,
) -> str:
    """Click a screen coordinate via JUCCE (uses xdotool/XTEST or portal input).

    Always verify the result with screenshot_after=True or jucce_screenshot afterwards.
    """
    args: dict[str, Any] = {"x": x, "y": y, "button": button}
    if screenshot_after:
        args["screenshot_after"] = True
    return _call("click", args)


@tool("jucce_type_text", args_schema=JucceTypeInput)
def jucce_type_text(text: str, screenshot_after: bool = False) -> str:
    """Type text into the currently focused input field via JUCCE.

    Inspect the field content afterwards (screenshot_after=True recommended).
    """
    args: dict[str, Any] = {"text": text}
    if screenshot_after:
        args["screenshot_after"] = True
    return _call("type_text", args)


@tool("jucce_press_key", args_schema=JucceKeyInput)
def jucce_press_key(key: str, screenshot_after: bool = False) -> str:
    """Press a key or key chord via JUCCE (e.g. 'Return', 'ctrl+c', 'alt+F4').

    Use XKB key names. Verify results with screenshot_after=True when in doubt.
    """
    args: dict[str, Any] = {"key": key}
    if screenshot_after:
        args["screenshot_after"] = True
    return _call("press_key", args)


@tool("jucce_scroll", args_schema=JucceScrollInput)
def jucce_scroll(
    x: int,
    y: int,
    direction: str,
    amount: int = 3,
    screenshot_after: bool = False,
) -> str:
    """Scroll at a screen coordinate in the given direction via JUCCE."""
    args: dict[str, Any] = {"x": x, "y": y, "direction": direction, "amount": amount}
    if screenshot_after:
        args["screenshot_after"] = True
    return _call("scroll", args)


@tool("jucce_activate_window", args_schema=JucceActivateWindowInput)
def jucce_activate_window(window_id: int, screenshot_after: bool = False) -> str:
    """Bring a compositor window to the foreground via JUCCE.

    Get window_id from jucce_observe_desktop(action='list_windows').
    """
    args: dict[str, Any] = {"window_id": window_id}
    if screenshot_after:
        args["screenshot_after"] = True
    return _call("activate_window", args)


@tool("jucce_perform_action", args_schema=JuccePerformActionInput)
def jucce_perform_action(
    snapshot_id: str,
    element_index: int,
    action: str = "default",
    screenshot_after: bool = False,
) -> str:
    """Trigger an AT-SPI action on an accessibility-tree element via JUCCE.

    snapshot_id and element_index come from jucce_get_app_state.
    action is typically 'default', 'press', or 'toggle'.
    """
    args: dict[str, Any] = {
        "snapshot_id": snapshot_id,
        "element_index": element_index,
        "action": action,
    }
    if screenshot_after:
        args["screenshot_after"] = True
    return _call("perform_action", args)


# ---------------------------------------------------------------------------
# All JUCCE tools — import this list to register with an agent
# ---------------------------------------------------------------------------

ALL_JUCCE_TOOLS = [
    # read-only
    jucce_observe_desktop,
    jucce_screenshot,
    jucce_get_app_state,
    # mutating
    jucce_click,
    jucce_type_text,
    jucce_press_key,
    jucce_scroll,
    jucce_activate_window,
    jucce_perform_action,
]


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def close_jucce() -> None:
    global _adapter, _discovered
    if _adapter:
        _adapter.close()
    _adapter = None
    _discovered = set()
