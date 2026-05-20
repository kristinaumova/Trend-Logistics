"""
Геокодирование: справочник городов → Nominatim для полных адресов.
"""
from __future__ import annotations

import httpx

from app.services.city_geocode import CITY_COORDS, geocode, normalize_city_name

_cache: dict[str, tuple[float, float] | None] = {}
_suggest_cache: dict[str, list[dict[str, str]]] = {}
_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_USER_AGENT = "TrendLogistics/1.0 (educational logistics demo)"


def _looks_like_full_address(query: str) -> bool:
    q = query.lower()
    if "," in query or len(query) > 28:
        return True
    markers = ("ул", "улиц", "просп", "пр-т", "пер.", "дом", "д.", "строен", "шоссе", "наб.")
    return any(m in q for m in markers) or any(ch.isdigit() for ch in query)


def _short_label(row: dict) -> str:
    display = (row.get("display_name") or "").strip()
    addr = row.get("address") or {}
    if not isinstance(addr, dict):
        return display
    road = addr.get("road") or addr.get("pedestrian") or addr.get("footway")
    house = addr.get("house_number")
    city = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("municipality")
        or addr.get("state")
    )
    parts = []
    if road:
        parts.append(f"{road}{f', {house}' if house else ''}")
    elif house:
        parts.append(str(house))
    if city:
        parts.append(str(city))
    if parts:
        return ", ".join(parts)
    return display


async def _nominatim_search(
    q: str,
    limit: int = 8,
    *,
    addressdetails: bool = True,
) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.get(
                _NOMINATIM,
                params={
                    "q": q,
                    "format": "json",
                    "limit": limit,
                    "countrycodes": "ru",
                    "addressdetails": 1 if addressdetails else 0,
                    "accept-language": "ru",
                },
                headers={"User-Agent": _USER_AGENT},
            )
            r.raise_for_status()
            return r.json() or []
    except Exception:
        return []


async def geocode_place(query: str) -> tuple[float, float] | None:
    q = (query or "").strip()
    if not q:
        return None
    key = q.lower()
    if key in _cache:
        return _cache[key]

    local = geocode(q)
    if local:
        _cache[key] = local
        return local

    for part in [p.strip() for p in q.replace(";", ",").split(",") if p.strip()]:
        hit = geocode(part)
        if hit:
            _cache[key] = hit
            return hit

    rows = await _nominatim_search(q, limit=1)
    if rows:
        lat = float(rows[0]["lat"])
        lon = float(rows[0]["lon"])
        _cache[key] = (lat, lon)
        return (lat, lon)

    _cache[key] = None
    return None


def _city_display_name(key: str) -> str:
    special = {
        "москва": "Москва",
        "санкт-петербург": "Санкт-Петербург",
        "спб": "Санкт-Петербург",
        "нижний новгород": "Нижний Новгород",
        "ростов-на-дону": "Ростов-на-Дону",
    }
    if key in special:
        return special[key]
    return key.replace("-", " ").title()


def _local_city_suggestions(query: str, limit: int) -> list[dict[str, str]]:
    if _looks_like_full_address(query):
        return []
    needle = query.strip().lower()
    if len(needle) < 2:
        return []
    items: list[dict[str, str]] = []
    for city_key in sorted(CITY_COORDS.keys()):
        display = _city_display_name(city_key)
        if needle in city_key or needle in display.lower():
            items.append({"label": display, "value": display, "type": "city"})
        if len(items) >= limit:
            break
    return items


async def suggest_addresses(query: str, limit: int = 10) -> list[dict[str, str]]:
    q = (query or "").strip()
    if len(q) < 2:
        return []

    cache_key = f"{q.lower()}|{limit}"
    if cache_key in _suggest_cache:
        return _suggest_cache[cache_key]

    seen: set[str] = set()
    items: list[dict[str, str]] = []

    rows = await _nominatim_search(q, limit=limit)
    for row in rows:
        display = (row.get("display_name") or "").strip()
        label = _short_label(row)
        if not display or display in seen:
            continue
        seen.add(display)
        try:
            _cache[display.lower()] = (float(row["lat"]), float(row["lon"]))
        except (KeyError, TypeError, ValueError):
            pass
        items.append({"label": label or display, "value": display, "type": "address"})

    if len(items) < limit and not _looks_like_full_address(q):
        for city in _local_city_suggestions(q, limit - len(items)):
            if city["value"] not in seen:
                seen.add(city["value"])
                items.append(city)

    _suggest_cache[cache_key] = items[:limit]
    return _suggest_cache[cache_key]
