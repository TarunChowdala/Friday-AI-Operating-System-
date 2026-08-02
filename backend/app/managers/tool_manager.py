"""Discovers and executes tools via registry."""
from typing import Any, Dict, List

from app.models.tool import ToolCall, ToolDefinition, ToolResult
from app.tools.registry import ToolRegistry


class ToolManager:
    def __init__(self) -> None:
        self.registry = ToolRegistry()
        self.registry.register_defaults()

    def list_tools(self) -> List[ToolDefinition]:
        return self.registry.list_tools()

    async def execute(self, call: ToolCall) -> ToolResult:
        return await self.registry.run(call)

    async def execute_many(self, calls: List[ToolCall]) -> List[ToolResult]:
        return [await self.execute(c) for c in calls]
