"""Async Redis: JWT-сессии и кэш (опционально, если задан REDIS_URL)."""
from __future__ import annotations

import redis.asyncio as redis

from app.config import settings

_client: redis.Redis | None = None


async def get_redis() -> redis.Redis | None:
    global _client
    url = (settings.redis_url or "").strip()
    if not url:
        return None
    if _client is None:
        _client = redis.from_url(url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
