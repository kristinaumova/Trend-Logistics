import hashlib
import random
import struct
from typing import Any

import httpx

from config import settings
from geocode import get_coords_for_city


def _route_seed(route_origin: str, route_destination: str, salt: str) -> int:
    raw = f"{salt}|{route_origin.strip().lower()}|{route_destination.strip().lower()}".encode()
    return struct.unpack(">Q", hashlib.sha256(raw).digest()[:8])[0]


def _mock_weather(route_origin: str, route_destination: str) -> dict[str, Any]:
    rng = random.Random(_route_seed(route_origin, route_destination, "weather"))
    conditions = ["clear", "moderate_rain", "snow", "fog", "cloudy"]
    return {
        "condition": rng.choice(conditions),
        "temp_min": round(rng.uniform(-10, 25), 1),
        "temp_max": round(rng.uniform(5, 35), 1),
        "wind_speed_kmh": round(rng.uniform(0, 50), 1),
        "impact_delay_hours": round(rng.uniform(0, 12), 1),
        "source": "mock",
    }


async def get_weather_live(route_origin: str, route_destination: str) -> dict[str, Any] | None:
    """Open-Meteo API (бесплатно, без ключа)."""
    coords = get_coords_for_city(route_origin) or get_coords_for_city(route_destination)
    if not coords:
        return None
    lat, lon = coords
    url = (
        f"{settings.open_meteo_base_url}/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,weather_code,wind_speed_10m"
        "&timezone=Europe/Moscow"
    )
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None
    current = data.get("current") or {}
    # weather_code: 0=clear, 1-3=clouds, 61-67=rain, 71-77=snow, etc.
    wmo = current.get("weather_code", 0)
    if wmo == 0:
        condition = "clear"
    elif wmo in (71, 73, 75, 77):
        condition = "snow"
    elif wmo in (61, 63, 65, 66, 67):
        condition = "moderate_rain"
    elif wmo in (45, 48):
        condition = "fog"
    else:
        condition = "cloudy"
    temp = current.get("temperature_2m")
    wind = current.get("wind_speed_10m") or 0
    # Упрощённая оценка влияния на доставку (часы задержки)
    impact = 0.0
    if condition == "snow":
        impact = 4.0 + (wind / 10)
    elif condition == "moderate_rain":
        impact = 1.0 + (wind / 20)
    elif condition == "fog":
        impact = 2.0
    return {
        "condition": condition,
        "temp_min": temp,
        "temp_max": temp,
        "wind_speed_kmh": round(wind, 1),
        "impact_delay_hours": round(impact, 1),
        "source": "open_meteo",
        "weather_code": wmo,
    }


async def get_weather(route_origin: str, route_destination: str) -> dict[str, Any]:
    if settings.use_live_weather:
        out = await get_weather_live(route_origin, route_destination)
        if out is not None:
            return out
    return _mock_weather(route_origin, route_destination)
