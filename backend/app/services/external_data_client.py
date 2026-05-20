"""
Клиент к отдельному сервису внешних данных.
Если EXTERNAL_DATA_SERVICE_URL задан и сервис доступен — используем его (мок или живые API).
Иначе — fallback на локальный ExternalFactorsService (мок).
При включённом Redis кэшируем ответ (TTL из FACTORS_CACHE_TTL_SECONDS).
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings
from app.redis_client import get_redis
from app.services.external_factors_service import ExternalFactorsService

_fallback = ExternalFactorsService()
_timeout = 10.0


async def _cache_get(key: str) -> dict[str, dict[str, Any]] | None:
    r = await get_redis()
    if r is None:
        return None
    raw = await r.get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def _cache_set(key: str, value: dict[str, dict[str, Any]]) -> None:
    r = await get_redis()
    if r is None:
        return
    await r.setex(
        key,
        max(60, int(settings.factors_cache_ttl_seconds)),
        json.dumps(value, ensure_ascii=False),
    )


async def get_all_factors(route_origin: str, route_destination: str) -> dict[str, dict[str, Any]]:
    cache_key = f"factors:{route_origin}|{route_destination}"
    cached = await _cache_get(cache_key)
    if cached is not None:
        return cached

    base = (settings.external_data_service_url or "").rstrip("/")
    if not base:
        data = _fallback.get_all_factors(route_origin, route_destination)
        await _cache_set(cache_key, data)
        return data
    url = f"{base}/factors"
    params = {"route_origin": route_origin, "route_destination": route_destination}
    try:
        async with httpx.AsyncClient(timeout=_timeout) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception:
        data = _fallback.get_all_factors(route_origin, route_destination)
    await _cache_set(cache_key, data)
    return data
