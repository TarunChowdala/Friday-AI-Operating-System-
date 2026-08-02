"""System info and power actions tool (stub)."""
from app.models.tool import ToolCall, ToolDefinition, ToolParameter, ToolResult

DEFINITION = ToolDefinition(
    name="system",
    description="System info and power actions",
    parameters=[
        ToolParameter(name="action", type="string", description="info|lock|sleep", required=True),
    ],
)


async def run(call: ToolCall) -> ToolResult:
    # TODO: implement system
    return ToolResult(
        call_id=call.id,
        name=call.name,
        success=True,
        output={"status": "stub", "args": call.arguments},
    )
