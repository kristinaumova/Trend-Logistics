"""Завершение и отмена поставок с проверкой позиции груза."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import settings
from app.models.shipment import Shipment, ShipmentStatus
from app.services.geocode_address import geocode_place
from app.services.route_service import get_route
from app.services.telemetry_client import fetch_telemetry


@dataclass
class ProximityCheck:
    ok: bool
    distance_km: float | None
    max_distance_km: float
    progress: float | None
    message: str


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))
    return r * c


def _elapsed_hours(created_at: datetime | None, status: ShipmentStatus) -> float | None:
    if not created_at or status not in (ShipmentStatus.IN_TRANSIT, ShipmentStatus.DELAYED):
        return None
    created = created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds() / 3600.0)


async def check_cargo_near_destination(shipment: Shipment) -> ProximityCheck:
    max_km = float(settings.delivery_completion_max_km)
    min_progress = float(settings.delivery_completion_min_progress)

    dest = await geocode_place(shipment.route_destination)
    if not dest:
        return ProximityCheck(
            ok=False,
            distance_km=None,
            max_distance_km=max_km,
            progress=None,
            message="Не удалось определить координаты пункта назначения",
        )

    route_info = await get_route(
        shipment.route_origin,
        shipment.route_destination,
        shipment.transport_type or "truck",
    )
    total_h = (
        float(route_info["duration_hours"])
        if route_info and route_info.get("duration_hours")
        else None
    )
    elapsed = _elapsed_hours(shipment.transit_started_at or shipment.created_at, shipment.status)
    origin = await geocode_place(shipment.route_origin)

    tel = await fetch_telemetry(
        shipment.route_origin,
        shipment.route_destination,
        shipment.transport_type or "truck",
        shipment.id,
        origin_lat=origin[0] if origin else None,
        origin_lon=origin[1] if origin else None,
        dest_lat=dest[0],
        dest_lon=dest[1],
        elapsed_hours=elapsed,
        total_route_hours=total_h,
        shipment_status=shipment.status.value,
    )
    if not tel or tel.get("error"):
        return ProximityCheck(
            ok=False,
            distance_km=None,
            max_distance_km=max_km,
            progress=None,
            message="Телеметрия недоступна — нельзя проверить позицию груза",
        )

    pos = tel.get("position") or {}
    lat = pos.get("lat")
    lon = pos.get("lon")
    if lat is None or lon is None:
        return ProximityCheck(
            ok=False,
            distance_km=None,
            max_distance_km=max_km,
            progress=None,
            message="Нет координат груза",
        )

    dist = _haversine_km(float(lat), float(lon), dest[0], dest[1])
    progress = float(tel.get("progress") or 0.0)
    remaining_km = tel.get("remaining_km")

    near_by_distance = dist <= max_km
    near_by_progress = progress >= min_progress and (
        remaining_km is None or float(remaining_km) <= max_km * 1.5
    )

    if near_by_distance or near_by_progress:
        return ProximityCheck(
            ok=True,
            distance_km=round(dist, 1),
            max_distance_km=max_km,
            progress=round(progress, 3),
            message="Груз в зоне пункта назначения",
        )

    return ProximityCheck(
        ok=False,
        distance_km=round(dist, 1),
        max_distance_km=max_km,
        progress=round(progress, 3),
        message=(
            f"Груз ещё далеко от назначения: {dist:.1f} км "
            f"(нужно ≤ {max_km:.0f} км или прогресс ≥ {int(min_progress * 100)}%)"
        ),
    )
