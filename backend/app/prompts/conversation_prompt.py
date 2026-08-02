"""Conversation framing prompts."""

CONVERSATION_PROMPT = """Continue the conversation naturally.
Use retrieved memory when relevant. Keep answers tight unless asked for depth.
"""


def build_conversation_prompt(user_message: str, memory_context: str = "") -> str:
    parts = [CONVERSATION_PROMPT]
    if memory_context:
        parts.append(f"Relevant memory:\n{memory_context}")
    parts.append(f"User: {user_message}")
    return "\n\n".join(parts)
