"""Launch or focus applications tool (stub)."""
from app.models.tool import ToolCall, ToolDefinition, ToolParameter, ToolResult

DEFINITION = ToolDefinition(
    name="applications",
    description="Launch or focus applications",
    parameters=[
        ToolParameter(name="name", type="string", description="application name", required=True),
    ],
)


async def run(call: ToolCall) -> ToolResult:
    # TODO: implement applications
    return ToolResult(
        call_id=call.id,
        name=call.name,
        success=True,
        output={"status": "stub", "args": call.arguments},
    )
