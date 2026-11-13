"""Small synchronous MCP stdio client used by JUCCE adapters.

The MCP process is started lazily, kept for the backend lifetime, and serialized
through a lock because stdio request/response streams are ordered.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import queue
from typing import Any


class MCPStdioError(RuntimeError):
    pass


class MCPStdioClient:
    def __init__(self, command: list[str], timeout: float = 15.0) -> None:
        self.command = command
        self.timeout = timeout
        self._process: subprocess.Popen[str] | None = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._initialized = False
        self._output: queue.Queue[str | None] = queue.Queue()

    def _start(self) -> None:
        if self._process and self._process.poll() is None:
            return
        try:
            self._process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=os.environ.copy(),
            )
        except OSError as exc:
            raise MCPStdioError(f"Could not start MCP server: {exc}") from exc
        self._initialized = False
        self._output = queue.Queue()
        process = self._process
        output = self._output
        assert process.stdout

        def read_output() -> None:
            assert process.stdout
            for line in process.stdout:
                output.put(line)
            output.put(None)

        threading.Thread(target=read_output, daemon=True, name="jucce-mcp-stdout").start()

    def _send(self, message: dict[str, Any]) -> None:
        assert self._process and self._process.stdin
        self._process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self._process.stdin.flush()

    def _receive(self, request_id: int) -> dict[str, Any]:
        # stdio MCP servers may emit notifications before the correlated reply.
        while True:
            try:
                line = self._output.get(timeout=self.timeout)
            except queue.Empty as exc:
                raise MCPStdioError(f"MCP request timed out after {self.timeout:g}s") from exc
            if line is None:
                code = self._process.poll()
                raise MCPStdioError(f"MCP server closed its output (exit={code})")
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise MCPStdioError(str(message["error"].get("message", message["error"])))
                return message.get("result") or {}

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._request_id += 1
        request_id = self._request_id
        self._send({
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        })
        return self._receive(request_id)

    def _initialize(self) -> None:
        self._start()
        if self._initialized:
            return
        self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "jarvis-jucce", "version": "1.0.0"},
            },
        )
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True

    def list_tools(self) -> list[dict[str, Any]]:
        with self._lock:
            self._initialize()
            return list(self._request("tools/list").get("tools") or [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._initialize()
            return self._request(
                "tools/call", {"name": name, "arguments": arguments}
            )

    def close(self) -> None:
        with self._lock:
            process, self._process = self._process, None
            self._initialized = False
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()

