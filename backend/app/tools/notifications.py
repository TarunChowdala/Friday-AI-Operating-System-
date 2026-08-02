"""Send desktop notifications tool (stub)."""
from app.models.tool import ToolCall, ToolDefinition, ToolParameter, ToolResult

DEFINITION = ToolDefinition(
    name="notifications",
    description="Send desktop notifications",
    parameters=[
        ToolParameter(name="title", type="string", description="notification title", required=True),
        ToolParameter(name="body", type="string", description="notification body", required=True),
    ],
)


async def run(call: ToolCall) -> ToolResult:
    # TODO: implement notifications
    return ToolResult(
        call_id=call.id,
        name=call.name,
        success=True,
        output={"status": "stub", "args": call.arguments},
    )
