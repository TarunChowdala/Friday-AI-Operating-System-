"""Persisted conversation transcripts."""
import json
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import get_settings


class ConversationHistory:
    def __init__(self) -> None:
        self.base = Path(get_settings().CONVERSATIONS_PATH)
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self.base / f"{session_id}.json"

    async def save(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        self._path(session_id).write_text(json.dumps(messages, default=str, indent=2))

    async def load(self, session_id: str) -> List[Dict[str, Any]]:
        path = self._path(session_id)
        if not path.exists():
            return []
        return json.loads(path.read_text())
