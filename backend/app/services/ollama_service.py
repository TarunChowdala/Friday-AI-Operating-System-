"""Ollama LLM client wrapper."""
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class OllamaService:
    def __init__(self) -> None:
        self.cfg = get_settings()
        self.base_url = self.cfg.OLLAMA_BASE_URL.rstrip("/")

    async def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> str:
        model = model or self.cfg.OLLAMA_MODEL
        payload = {"model": model, "messages": messages, "stream": False}
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "")
        except Exception as exc:
            logger.warning("ollama unavailable: %s", exc)
            return f"[ollama stub] echo: {messages[-1].get('content', '') if messages else ''}"

    async def stream(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> AsyncIterator[str]:
        # TODO: implement streaming
        text = await self.chat(messages, model=model)
        yield text
