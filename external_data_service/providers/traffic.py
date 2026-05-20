import hashlib
import random
import struct
from typing import Any

from config import settings


def _route_seed(route_origin: str, route_destination: str, salt: str) -> int:
    raw = f"{salt}|{route_origin.strip().lower()}|{route_destination.strip().lower()}".encode()
    return struct.unpack(">Q", hashlib.sha256(raw).digest()[:8])[0]


def get_traffic_mock(route_origin: str, route_destination: str) -> dict[str, Any]:
    rng = random.Random(_route_seed(route_origin, route_destination, "traffic"))
    return {
        "congestion_level": rng.choice(["low", "medium", "high"]),
        "road_works_km": round(rng.uniform(0, 30), 1),
        "impact_delay_hours": round(rng.uniform(0, 8), 1),
        "source": "mock",
    }


async def get_traffic_live(route_origin: str, route_destination: str) -> dict[str, Any] | None:
    """Заглушка для подключения реального API (Яндекс.Пробки, OpenRouteService и т.д.)."""
    # TODO: подключить при наличии API-ключа
    return None


async def get_traffic(route_origin: str, route_destination: str) -> dict[str, Any]:
    if settings.use_live_traffic:
        out = await get_traffic_live(route_origin, route_destination)
        if out is not None:
            return out
    return get_traffic_mock(route_origin, route_destination)
