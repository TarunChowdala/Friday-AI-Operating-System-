"""Get or set system volume tool (stub)."""
from app.models.tool import ToolCall, ToolDefinition, ToolParameter, ToolResult

DEFINITION = ToolDefinition(
    name="volume",
    description="Get or set system volume",
    parameters=[
        ToolParameter(name="action", type="string", description="get|set|mute|unmute", required=True),
        ToolParameter(name="level", type="number", description="0-100", required=False),
    ],
)


async def run(call: ToolCall) -> ToolResult:
    # TODO: implement volume
    return ToolResult(
        call_id=call.id,
        name=call.name,
        success=True,
        output={"status": "stub", "args": call.arguments},
    )
