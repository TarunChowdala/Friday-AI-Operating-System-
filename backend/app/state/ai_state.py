"""Current AI runtime state."""
from dataclasses import dataclass, field
from typing import Optional

from app.core.constants import AI_STATES


@dataclass
class AIState:
    state: str = "idle"
    detail: str = ""
    current_tool: Optional[str] = None
    session_id: Optional[str] = None
    meta: dict = field(default_factory=dict)

    def set_state(self, state: str, detail: str = "") -> None:
        if state not in AI_STATES:
            raise ValueError(f"invalid AI state: {state}")
        self.state = state
        self.detail = detail
