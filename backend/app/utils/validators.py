"""Input validators."""
import re

SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def is_valid_session_id(value: str) -> bool:
    return bool(SESSION_ID_RE.match(value or ""))


def non_empty(value: str, field: str = "value") -> str:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"{field} must not be empty")
    return text
