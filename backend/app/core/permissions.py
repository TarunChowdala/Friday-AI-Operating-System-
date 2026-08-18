"""Permission system for dangerous commands.

Dangerous actions require the user to speak a secret confirmation code
stored in .env (CONFIRM_CODE). Jarvis reads out the code and asks the user
to repeat it. If user speaks it back correctly, action is approved.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from app.core.logger import get_logger

logger = get_logger(__name__)

# Actions that require confirmation
DANGEROUS_PATTERNS = [
    "rm ",
    "rm -",
    "rmdir",
    "delete",
    "shred",
    "mkfs",
    "dd if=",
    "format",
    "> /dev/",
    "kill",
    "killall",
    "pkill",
    "shutdown",
    "reboot",
    "poweroff",
    "systemctl stop",
    "systemctl disable",
    "chmod 777",
    "chown",
    "sudo rm",
    "mv / ",
    "unlink",
]

# Pending permission requests: {client_id: {future, description}}
_pending: dict[str, dict] = {}


def _get_confirm_code() -> str:
    from app.core.config import get_settings
    return get_settings().CONFIRM_CODE


def is_dangerous(command: str) -> bool:
    """Check if a command/action requires permission."""
    low = command.lower().strip()
    return any(pat in low for pat in DANGEROUS_PATTERNS)


async def request_permission(
    client_id: str,
    action_description: str,
    send_fn,
    timeout: float = 30.0,
) -> bool:
    """Request permission from user. Jarvis speaks the code, user repeats it.

    send_fn: async callable(client_id, message_dict) to send WS message.
    Returns True if approved, False if denied/timeout.
    """
    code = _get_confirm_code()
    future: asyncio.Future = asyncio.get_event_loop().create_future()

    _pending[client_id] = {
        "future": future,
        "description": action_description,
    }

    # Jarvis asks for the code without revealing it
    await send_fn(client_id, {
        "type": "permission_request",
        "description": action_description,
        "speak": "Sir, this action requires your approval. Please say the confirmation code.",
        "message": f"⚠️ {action_description} — Say your secret code to confirm or 'cancel' to abort.",
    })

    logger.info("Permission requested for '%s' — waiting for code", action_description)

    try:
        result = await asyncio.wait_for(future, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        logger.info("Permission timed out for '%s'", action_description)
        await send_fn(client_id, {
            "type": "permission_expired",
            "speak": "No confirmation received, Sir. Action cancelled.",
            "message": "Permission request timed out. Action cancelled.",
        })
        return False
    finally:
        _pending.pop(client_id, None)


def verify_permission(client_id: str, user_input: str) -> Optional[bool]:
    """Called when user responds. Returns True/False if this was a permission response, None if not.

    Returns:
        True  — code matched, action approved
        False — user said cancel
        None  — not a permission response (normal message)
    """
    pending = _pending.get(client_id)
    if not pending:
        return None

    cleaned = user_input.strip().lower().replace(" ", "")
    code = _get_confirm_code()

    # Cancel keywords
    if cleaned in ("cancel", "no", "stop", "abort", "deny", "don't", "nope"):
        pending["future"].set_result(False)
        return False

    # Check code match — handle spoken "7 9 8 9" or "7989" or with filler words
    if code in cleaned or cleaned == code:
        pending["future"].set_result(True)
        return True

    # Fuzzy: extract digits from speech and check
    digits_only = "".join(c for c in cleaned if c.isdigit())
    if digits_only == code:
        pending["future"].set_result(True)
        return True

    # Not a permission response — could be unrelated speech
    return None


def has_pending(client_id: str) -> bool:
    """Check if there's a pending permission request for this client."""
    return client_id in _pending
