import hashlib
import random
import struct
from typing import Any

from config import settings


def _route_seed(route_origin: str, route_destination: str, salt: str) -> int:
    raw = f"{salt}|{route_origin.strip().lower()}|{route_destination.strip().lower()}".encode()
    return struct.unpack(">Q", hashlib.sha256(raw).digest()[:8])[0]


def get_geopolitics_mock(route_origin: str, route_destination: str) -> dict[str, Any]:
    rng = random.Random(_route_seed(route_origin, route_destination, "geo"))
    return {
        "risk_level": rng.choice(["low", "medium", "high"]),
        "impact_delay_hours": round(rng.uniform(0, 48), 1),
        "source": "mock",
    }


async def get_geopolitics_live(route_origin: str, route_destination: str) -> dict[str, Any] | None:
    """Заглушка для новостных/санкционных API (News API, кастомные источники)."""
    # TODO: подключить при наличии API
    return None


async def get_geopolitics(route_origin: str, route_destination: str) -> dict[str, Any]:
    if settings.use_live_geopolitics:
        out = await get_geopolitics_live(route_origin, route_destination)
        if out is not None:
            return out
    return get_geopolitics_mock(route_origin, route_destination)
