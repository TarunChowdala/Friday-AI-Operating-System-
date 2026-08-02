"""Tool-calling prompt helpers."""
from typing import List

from app.models.tool import ToolDefinition


TOOL_PROMPT = """You may call tools to accomplish the task.
Only call a tool when necessary. Prefer the smallest tool set.
"""


def build_tool_prompt(tools: List[ToolDefinition]) -> str:
    catalog = "\n".join(f"- {t.name}: {t.description}" for t in tools)
    return f"{TOOL_PROMPT}\n\nAvailable tools:\n{catalog}"
