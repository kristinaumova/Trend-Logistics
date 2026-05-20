"""
Расчёт маршрута между городами: OSRM + валидация + fallback по оценке (Хаверсин).
"""
from typing import Any

import httpx

from app.services.geocode_address import geocode_place
from app.services.route_estimation import build_route_fallback_response, reasonable_max_drive_hours

OSRM_BASE = "https://router.project-osrm.org"


async def get_route(
    route_origin: str,
    route_destination: str,
    transport_type: str = "truck",
) -> dict[str, Any] | None:
    """
    distance_km, duration_hours, coordinates ([lat, lon]), origin, destination.
    Для truck — OSRM (автодорога) + проверка; для rail/sea/air — оценка по расстоянию и скорости.
    """
    p1 = await geocode_place(route_origin)
    p2 = await geocode_place(route_destination)
    if not p1 or not p2:
        return None
    lat1, lon1 = p1
    lat2, lon2 = p2

    if transport_type in ("rail", "sea", "air"):
        fb = build_route_fallback_response(route_origin, route_destination, transport_type)
        if fb:
            fb["source"] = "estimated"
        return fb

    url = f"{OSRM_BASE}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    data = None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
    except Exception:
        data = None

    if data and data.get("code") == "Ok" and data.get("routes"):
        route = data["routes"][0]
        distance_m = float(route.get("distance") or 0)
        duration_s = float(route.get("duration") or 0)
        coords = route.get("geometry", {}).get("coordinates") or []
        distance_km = round(distance_m / 1000, 1)
        duration_h = round(duration_s / 3600, 2)
        # Публичный OSRM иногда отдаёт некорректное время; сверяем с разумной границей
        max_h = reasonable_max_drive_hours(distance_km)
        if duration_h > max_h or duration_h < 0.05:
            fb = build_route_fallback_response(route_origin, route_destination, transport_type)
            if fb:
                fb["source"] = "estimated_osrm_corrected"
                return fb
        coordinates = [[c[1], c[0]] for c in coords]
        return {
            "distance_km": distance_km,
            "duration_hours": round(duration_h, 1),
            "coordinates": coordinates,
            "origin": [lat1, lon1],
            "destination": [lat2, lon2],
            "source": "osrm",
        }

    return build_route_fallback_response(route_origin, route_destination, transport_type)
