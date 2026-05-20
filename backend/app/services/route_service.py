"""
Расчёт маршрута между городами: OSRM + валидация + fallback по оценке (Хаверсин).
"""
from typing import Any

import httpx

from app.services.geocode_address import geocode_place
from app.services.route_estimation import (
    build_route_fallback_response,
    estimate_transit_hours,
    reasonable_max_drive_hours,
)

OSRM_BASE = "https://router.project-osrm.org"


async def get_route(
    route_origin: str,
    route_destination: str,
    transport_type: str = "truck",
) -> dict[str, Any] | None:
    """
    distance_km, duration_hours, coordinates ([lat, lon]), origin, destination.
    Для всех типов пытаемся получить геометрию через OSRM (чтобы рисовать путь на карте).
    Для truck используем время OSRM, для прочих типов — оценку по профилю транспорта.
    """
    p1 = await geocode_place(route_origin)
    p2 = await geocode_place(route_destination)
    if not p1 or not p2:
        return None
    lat1, lon1 = p1
    lat2, lon2 = p2

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
        if transport_type == "truck":
            # Публичный OSRM иногда отдаёт некорректное время; сверяем с разумной границей
            max_h = reasonable_max_drive_hours(distance_km)
            if duration_h > max_h or duration_h < 0.05:
                fb = build_route_fallback_response(route_origin, route_destination, transport_type)
                if fb:
                    fb["source"] = "estimated_osrm_corrected"
                    return fb
            final_duration_hours = round(duration_h, 1)
        else:
            _, estimated_h = estimate_transit_hours(route_origin, route_destination, transport_type)
            final_duration_hours = estimated_h if estimated_h is not None else round(duration_h, 1)
        coordinates = [[c[1], c[0]] for c in coords]
        return {
            "distance_km": distance_km,
            "duration_hours": final_duration_hours,
            "coordinates": coordinates,
            "origin": [lat1, lon1],
            "destination": [lat2, lon2],
            "source": "osrm",
        }

    return build_route_fallback_response(route_origin, route_destination, transport_type)
