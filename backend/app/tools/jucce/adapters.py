"""OS-specific computer-control adapters."""
from __future__ import annotations

import shlex
from typing import Any, Protocol

from app.core.config import get_settings
from app.tools.jucce.protocol import MCPStdioClient


class ComputerControlAdapter(Protocol):
    os_name: str

    def discover_tools(self) -> list[dict[str, Any]]: ...

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...

    def close(self) -> None: ...


class LinuxComputerUseAdapter:
    os_name = "linux"

    def __init__(self) -> None:
        cfg = get_settings()
        command = [cfg.JUCCE_LINUX_COMMAND, *shlex.split(cfg.JUCCE_LINUX_ARGS)]
        self.client = MCPStdioClient(command, timeout=cfg.JUCCE_MCP_TIMEOUT_SECONDS)
        self._tools: dict[str, dict[str, Any]] = {}

    def discover_tools(self) -> list[dict[str, Any]]:
        tools = self.client.list_tools()
        self._tools = {tool["name"]: tool for tool in tools if tool.get("name")}
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self._tools:
            self.discover_tools()
        if name not in self._tools:
            raise ValueError(f"MCP tool is not available: {name}")
        return self.client.call_tool(name, arguments)

    def close(self) -> None:
        self.client.close()


class UnsupportedComputerControlAdapter:
    """Explicit placeholder for platforms without a configured MCP adapter."""

    def __init__(self, os_name: str) -> None:
        self.os_name = os_name

    def discover_tools(self) -> list[dict[str, Any]]:
        return []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError(f"JUCCE has no configured computer-control adapter for {self.os_name}")

    def close(self) -> None:
        pass
