"""Tool registration and dispatch."""
from typing import Awaitable, Callable, Dict, List

from app.models.tool import ToolCall, ToolDefinition, ToolResult
from app.tools import (
    applications,
    browser,
    clipboard,
    filesystem,
    notifications,
    screen,
    system,
    terminal,
    volume,
)

ToolFn = Callable[..., Awaitable[ToolResult]]


class ToolRegistry:
    def __init__(self) -> None:
        self._defs: Dict[str, ToolDefinition] = {}
        self._fns: Dict[str, ToolFn] = {}

    def register(self, definition: ToolDefinition, fn: ToolFn) -> None:
        self._defs[definition.name] = definition
        self._fns[definition.name] = fn

    def register_defaults(self) -> None:
        modules = [
            browser, filesystem, applications, terminal,
            clipboard, notifications, volume, screen, system,
        ]
        for mod in modules:
            self.register(mod.DEFINITION, mod.run)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._defs.values())

    async def run(self, call: ToolCall) -> ToolResult:
        fn = self._fns.get(call.name)
        if not fn:
            return ToolResult(call_id=call.id, name=call.name, success=False, error=f"unknown tool: {call.name}")
        try:
            return await fn(call)
        except Exception as exc:
            return ToolResult(call_id=call.id, name=call.name, success=False, error=str(exc))
