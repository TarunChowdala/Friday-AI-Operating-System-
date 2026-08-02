"""Open URLs or search the web tool (stub)."""
from app.models.tool import ToolCall, ToolDefinition, ToolParameter, ToolResult

DEFINITION = ToolDefinition(
    name="browser",
    description="Open URLs or search the web",
    parameters=[
        ToolParameter(name="action", type="string", description="open|search", required=True),
        ToolParameter(name="query", type="string", description="URL or search query", required=True),
    ],
)


async def run(call: ToolCall) -> ToolResult:
    # TODO: implement browser
    return ToolResult(
        call_id=call.id,
        name=call.name,
        success=True,
        output={"status": "stub", "args": call.arguments},
    )
