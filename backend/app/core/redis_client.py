"""Async Redis client singleton for live session state."""
from __future__ import annotations

from typing import Optional

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        cfg = get_settings()
        _client = redis.from_url(
            cfg.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _client


async def ping_redis() -> bool:
    client = await get_redis()
    return bool(await client.ping())


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("Redis connection closed")
