"""
Оценка расстояния и времени в пути без внешнего OSRM (fallback и ML).
Формула Хаверсина + коэффициент «не по прямой» + средняя скорость по виду транспорта.
"""
from __future__ import annotations

import math
from typing import Any

from app.services.city_geocode import geocode

ROAD_FACTOR = 1.18

_SPEED_KMH: dict[str, float] = {
    "truck": 62.0,
    "rail": 48.0,
    "sea": 22.0,
    "air": 650.0,
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))
    return r * c


def estimate_road_distance_km(origin: str, destination: str) -> float | None:
    p1 = geocode(origin)
    p2 = geocode(destination)
    if not p1 or not p2:
        return None
    lat1, lon1 = p1
    lat2, lon2 = p2
    crow = haversine_km(lat1, lon1, lat2, lon2)
    return round(crow * ROAD_FACTOR, 1)


def estimate_transit_hours(
    origin: str,
    destination: str,
    transport_type: str = "truck",
) -> tuple[float | None, float | None]:
    dist = estimate_road_distance_km(origin, destination)
    if dist is None:
        return None, None
    speed = _SPEED_KMH.get(transport_type, _SPEED_KMH["truck"])
    if speed <= 0:
        return dist, None
    hours = dist / speed
    hours = max(hours, 1.5 if transport_type == "truck" else 0.5)
    return dist, round(hours, 1)


def build_route_fallback_response(
    route_origin: str,
    route_destination: str,
    transport_type: str = "truck",
) -> dict[str, Any] | None:
    p1 = geocode(route_origin)
    p2 = geocode(route_destination)
    if not p1 or not p2:
        return None
    lat1, lon1 = p1
    lat2, lon2 = p2
    dist_km, hours = estimate_transit_hours(route_origin, route_destination, transport_type)
    if dist_km is None or hours is None:
        return None
    coordinates = [[lat1, lon1], [lat2, lon2]]
    return {
        "distance_km": dist_km,
        "duration_hours": hours,
        "coordinates": coordinates,
        "origin": [lat1, lon1],
        "destination": [lat2, lon2],
        "source": "estimated",
    }


def reasonable_max_drive_hours(distance_km: float) -> float:
    """Верхняя граница «нормального» времени на автодороге (медленный режим + остановки)."""
    return max(6.0, distance_km / 28.0 + 4.0)
