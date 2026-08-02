"""WebSocket event payload helpers."""
from typing import Any, Dict

from app.core.constants import (
    WS_EVENT_ERROR,
    WS_EVENT_RESPONSE,
    WS_EVENT_STATUS,
    WS_EVENT_SYSTEM,
    WS_EVENT_TOOL,
    WS_EVENT_TRANSCRIPT,
)


def event(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": event_type, "payload": payload}


def status_event(state: str, detail: str = "") -> Dict[str, Any]:
    return event(WS_EVENT_STATUS, {"state": state, "detail": detail})


def transcript_event(text: str, final: bool = False) -> Dict[str, Any]:
    return event(WS_EVENT_TRANSCRIPT, {"text": text, "final": final})


def response_event(text: str) -> Dict[str, Any]:
    return event(WS_EVENT_RESPONSE, {"text": text})


def tool_event(name: str, status: str, output: Any = None) -> Dict[str, Any]:
    return event(WS_EVENT_TOOL, {"name": name, "status": status, "output": output})


def error_event(message: str) -> Dict[str, Any]:
    return event(WS_EVENT_ERROR, {"message": message})


def system_event(message: str) -> Dict[str, Any]:
    return event(WS_EVENT_SYSTEM, {"message": message})
