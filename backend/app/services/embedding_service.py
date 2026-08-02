"""Text embedding via Ollama (stub)."""
from typing import List

import httpx

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    def __init__(self) -> None:
        self.cfg = get_settings()

    async def embed(self, texts: List[str]) -> List[List[float]]:
        # TODO: call Ollama /api/embeddings
        logger.debug("embed stub: %d texts", len(texts))
        return [[0.0] * 8 for _ in texts]

    async def embed_one(self, text: str) -> List[float]:
        vectors = await self.embed([text])
        return vectors[0]
