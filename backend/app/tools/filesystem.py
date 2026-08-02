"""Read/write/list files tool (stub)."""
from app.models.tool import ToolCall, ToolDefinition, ToolParameter, ToolResult

DEFINITION = ToolDefinition(
    name="filesystem",
    description="Read/write/list files",
    parameters=[
        ToolParameter(name="action", type="string", description="read|write|list|delete", required=True),
        ToolParameter(name="path", type="string", description="filesystem path", required=True),
        ToolParameter(name="content", type="string", description="write content", required=False),
    ],
)


async def run(call: ToolCall) -> ToolResult:
    # TODO: implement filesystem
    return ToolResult(
        call_id=call.id,
        name=call.name,
        success=True,
        output={"status": "stub", "args": call.arguments},
    )
