"""Run shell commands tool (stub)."""
from app.models.tool import ToolCall, ToolDefinition, ToolParameter, ToolResult

DEFINITION = ToolDefinition(
    name="terminal",
    description="Run shell commands",
    parameters=[
        ToolParameter(name="command", type="string", description="shell command", required=True),
    ],
)


async def run(call: ToolCall) -> ToolResult:
    # TODO: implement terminal
    return ToolResult(
        call_id=call.id,
        name=call.name,
        success=True,
        output={"status": "stub", "args": call.arguments},
    )
