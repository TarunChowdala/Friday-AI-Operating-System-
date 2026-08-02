"""In-session working memory."""
from collections import deque
from typing import Deque, List

from app.core.constants import SHORT_TERM_MAX_MESSAGES
from app.models.chat import ChatMessage


class ShortTermMemory:
    def __init__(self, max_messages: int = SHORT_TERM_MAX_MESSAGES) -> None:
        self.max_messages = max_messages
        self._buffer: Deque[ChatMessage] = deque(maxlen=max_messages)

    def add(self, message: ChatMessage) -> None:
        self._buffer.append(message)

    def get(self) -> List[ChatMessage]:
        return list(self._buffer)

    def clear(self) -> None:
        self._buffer.clear()
