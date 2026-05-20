"""HTTP-клиент к микросервису телеметрии (эмуляция GPS)."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings

_timeout = 8.0


async def fetch_telemetry(
    route_origin: str,
    route_destination: str,
    transport_type: str,
    shipment_id: int,
    *,
    origin_lat: float | None = None,
    origin_lon: float | None = None,
    dest_lat: float | None = None,
    dest_lon: float | None = None,
    elapsed_hours: float | None = None,
    total_route_hours: float | None = None,
    shipment_status: str | None = None,
) -> dict[str, Any] | None:
    base = (settings.telemetry_service_url or "").rstrip("/")
    if not base:
        return None
    url = f"{base}/track"
    params: dict[str, Any] = {
        "route_origin": route_origin,
        "route_destination": route_destination,
        "transport_type": transport_type,
        "shipment_id": shipment_id,
    }
    if origin_lat is not None and origin_lon is not None:
        params["origin_lat"] = origin_lat
        params["origin_lon"] = origin_lon
    if dest_lat is not None and dest_lon is not None:
        params["dest_lat"] = dest_lat
        params["dest_lon"] = dest_lon
    if elapsed_hours is not None:
        params["elapsed_hours"] = round(elapsed_hours, 3)
    if total_route_hours is not None:
        params["total_route_hours"] = round(total_route_hours, 3)
    if shipment_status:
        params["shipment_status"] = shipment_status
    try:
        async with httpx.AsyncClient(timeout=_timeout) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


async def get_telemetry_progress(
    route_origin: str,
    route_destination: str,
    transport_type: str,
    shipment_id: int,
    *,
    total_route_hours: float | None = None,
    elapsed_hours: float | None = None,
    shipment_status: str | None = None,
) -> float | None:
    data = await fetch_telemetry(
        route_origin,
        route_destination,
        transport_type,
        shipment_id,
        elapsed_hours=elapsed_hours,
        total_route_hours=total_route_hours,
        shipment_status=shipment_status,
    )
    if not data or data.get("error"):
        return None
    p = data.get("progress")
    if p is None:
        return None
    try:
        return float(max(0.0, min(1.0, float(p))))
    except (TypeError, ValueError):
        return None


def remaining_route_hours(
    full_route_hours: float | None, progress: float | None
) -> float | None:
    """Часы от текущей позиции груза до назначения (для ML и ETA)."""
    if not full_route_hours or full_route_hours <= 0:
        return None
    p = 0.0 if progress is None else max(0.0, min(1.0, progress))
    return max(0.25, float(full_route_hours) * (1.0 - p))
