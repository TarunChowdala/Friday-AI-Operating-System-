"""Read or write clipboard tool (stub)."""
from app.models.tool import ToolCall, ToolDefinition, ToolParameter, ToolResult

DEFINITION = ToolDefinition(
    name="clipboard",
    description="Read or write clipboard",
    parameters=[
        ToolParameter(name="action", type="string", description="get|set", required=True),
        ToolParameter(name="text", type="string", description="text to set", required=False),
    ],
)


async def run(call: ToolCall) -> ToolResult:
    # TODO: implement clipboard
    return ToolResult(
        call_id=call.id,
        name=call.name,
        success=True,
        output={"status": "stub", "args": call.arguments},
    )
