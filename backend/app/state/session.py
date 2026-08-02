"""Per-client session state."""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SessionState:
    session_id: str
    user_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)
