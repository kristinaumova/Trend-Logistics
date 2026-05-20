"""
Эмуляция телеметрии: позиция груза движется по маршруту во времени (для рейсов «в пути»).
"""
from __future__ import annotations

import hashlib
import math
import struct
from typing import Any

CITY: dict[str, tuple[float, float]] = {
    "москва": (55.7558, 37.6173),
    "санкт-петербург": (59.9343, 30.3351),
    "спб": (59.9343, 30.3351),
    "казань": (55.8304, 49.0661),
    "нижний новгород": (56.2965, 43.9361),
    "новосибирск": (55.0084, 82.9357),
    "екатеринбург": (56.8389, 60.6057),
    "самара": (53.1959, 50.1002),
    "омск": (54.9885, 73.3242),
    "челябинск": (55.1644, 61.4368),
    "уфа": (54.7388, 55.9721),
    "красноярск": (56.0153, 92.8932),
    "иркутск": (52.2897, 104.2806),
    "владивосток": (43.1198, 131.8869),
    "хабаровск": (48.4827, 135.0838),
    "ростов-на-дону": (47.2357, 39.7015),
    "краснодар": (45.0355, 38.9753),
    "воронеж": (51.6720, 39.1843),
    "пермь": (58.0105, 56.2502),
    "волгоград": (48.7194, 44.5018),
}

TRANSPORT = {
    "truck": {"label": "Автоперевозка", "kmh_base": 62, "icon": "truck"},
    "rail": {"label": "Железнодорожная перевозка", "kmh_base": 48, "icon": "rail"},
    "sea": {"label": "Морской/речной лег", "kmh_base": 22, "icon": "sea"},
    "air": {"label": "Авиаперевозка", "kmh_base": 650, "icon": "air"},
}


def _norm(s: str) -> str:
    return s.strip().lower().replace("ё", "е")


def _seed(*parts: str | int | float) -> int:
    raw = "|".join(str(p) for p in parts).encode()
    return struct.unpack(">Q", hashlib.sha256(raw).digest()[:8])[0]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))
    return r * c


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _resolve_points(
    route_origin: str,
    route_destination: str,
    origin_lat: float | None,
    origin_lon: float | None,
    dest_lat: float | None,
    dest_lon: float | None,
) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
    if origin_lat is not None and origin_lon is not None:
        o = (float(origin_lat), float(origin_lon))
    else:
        o = CITY.get(_norm(route_origin))
    if dest_lat is not None and dest_lon is not None:
        d = (float(dest_lat), float(dest_lon))
    else:
        d = CITY.get(_norm(route_destination))
    return o, d


def compute_track(
    route_origin: str,
    route_destination: str,
    transport_type: str = "truck",
    shipment_id: int = 0,
    origin_lat: float | None = None,
    origin_lon: float | None = None,
    dest_lat: float | None = None,
    dest_lon: float | None = None,
    elapsed_hours: float | None = None,
    total_route_hours: float | None = None,
    shipment_status: str | None = None,
) -> dict[str, Any] | None:
    o, d = _resolve_points(
        route_origin, route_destination, origin_lat, origin_lon, dest_lat, dest_lon
    )
    if not o or not d:
        return None
    lat1, lon1 = o
    lat2, lon2 = d
    dist_km = _haversine_km(lat1, lon1, lat2, lon2) * 1.18
    meta = TRANSPORT.get(transport_type, TRANSPORT["truck"])
    seed = _seed(route_origin, route_destination, transport_type, shipment_id)
    rng = (seed % 10000) / 10000.0
    speed = meta["kmh_base"] * (0.85 + 0.3 * rng)

    status = (shipment_status or "in_transit").lower()
    if status == "pending":
        progress = 0.0
    elif status == "delivered":
        progress = 1.0
    elif (
        status in ("in_transit", "delayed")
        and total_route_hours is not None
        and total_route_hours > 0
        and elapsed_hours is not None
    ):
        # Движение по времени: чем дольше рейс, тем дальше груз по линии маршрута
        progress = min(0.97, max(0.04, float(elapsed_hours) / float(total_route_hours)))
    else:
        progress = (seed % 997) / 997.0 * 0.85 + 0.05

    cur_lat = _lerp(lat1, lat2, progress)
    cur_lon = _lerp(lon1, lon2, progress)
    remaining_km = _haversine_km(cur_lat, cur_lon, lat2, lon2) * 1.12
    eta_hours = remaining_km / max(speed, 1.0)

    n = 12
    coords = []
    for i in range(n + 1):
        t = i / n
        coords.append([_lerp(lat1, lat2, t), _lerp(lon1, lon2, t)])

    return {
        "transport_type": transport_type,
        "transport_label": meta["label"],
        "distance_km_total": round(dist_km, 1),
        "progress": round(progress, 4),
        "speed_kmh": round(speed, 1),
        "remaining_km": round(remaining_km, 1),
        "eta_hours_remaining": round(eta_hours, 2),
        "position": {"lat": round(cur_lat, 5), "lon": round(cur_lon, 5)},
        "coordinates": coords,
        "source": "telemetry_emulation",
        "progress_mode": "time" if elapsed_hours is not None and total_route_hours else "seed",
        "note": "Эмуляция GPS: позиция обновляется по времени рейса (не бортовой трекер)",
    }
