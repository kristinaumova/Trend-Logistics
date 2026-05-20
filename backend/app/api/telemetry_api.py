import math
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models.shipment import ShipmentStatus
from app.models.user import User
from app.services.geocode_address import geocode_place
from app.services.route_service import get_route
from app.services.shipment_service import ShipmentService
from app.services.telemetry_client import fetch_telemetry

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

_LIVE_STATUSES = {ShipmentStatus.IN_TRANSIT, ShipmentStatus.DELAYED}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))
    return r * c


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _elapsed_hours(
    transit_started_at: datetime | None,
    created_at: datetime | None,
    status: ShipmentStatus,
) -> float | None:
    if status not in _LIVE_STATUSES:
        return None
    base = transit_started_at or created_at
    if not base:
        return None
    return max(0.0, (_utc_now() - _as_utc(base)).total_seconds() / 3600.0)


def _apply_shipment_status(
    data: dict[str, Any],
    status: ShipmentStatus,
    dest_coords: tuple[float, float] | None,
) -> dict[str, Any]:
    out = dict(data)
    if status == ShipmentStatus.DELIVERED and dest_coords:
        out["position"] = {"lat": round(dest_coords[0], 5), "lon": round(dest_coords[1], 5)}
        out["progress"] = 1.0
        out["remaining_km"] = 0.0
        out["eta_hours_remaining"] = 0.0
        out["speed_kmh"] = 0.0
        out["note"] = "Поставка доставлена"
    elif status == ShipmentStatus.CANCELLED:
        out["eta_hours_remaining"] = None
        out["remaining_km"] = None
        out["note"] = "Поставка отменена"
    elif status in _LIVE_STATUSES:
        out["note"] = "ETA от текущей позиции груза до пункта назначения (обновляется по времени рейса)"
    return out


@router.get("/shipment/{shipment_id}")
async def telemetry_for_shipment(
    shipment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    """Эмулированная телеметрия: координаты груза и остаток маршрута."""
    svc = ShipmentService(db)
    s = await svc.get_by_id(shipment_id)
    if not s:
        raise HTTPException(status_code=404, detail="Shipment not found")

    origin = await geocode_place(s.route_origin)
    dest = await geocode_place(s.route_destination)
    route_info = await get_route(
        s.route_origin, s.route_destination, s.transport_type or "truck"
    )
    total_h = float(route_info["duration_hours"]) if route_info and route_info.get("duration_hours") else None
    elapsed = _elapsed_hours(s.transit_started_at, s.created_at, s.status)

    data = await fetch_telemetry(
        s.route_origin,
        s.route_destination,
        s.transport_type or "truck",
        s.id,
        origin_lat=origin[0] if origin else None,
        origin_lon=origin[1] if origin else None,
        dest_lat=dest[0] if dest else None,
        dest_lon=dest[1] if dest else None,
        elapsed_hours=elapsed,
        total_route_hours=total_h,
        shipment_status=s.status.value,
    )
    if not data or data.get("error"):
        return {
            "available": False,
            "message": "Телеметрия недоступна: проверьте адреса и TELEMETRY_SERVICE_URL",
            "shipment_id": s.id,
            "shipment_status": s.status.value,
        }
    data = _apply_shipment_status(data, s.status, dest)
    return {
        "available": True,
        "live": s.status in _LIVE_STATUSES,
        "shipment_id": s.id,
        "shipment_status": s.status.value,
        "data": data,
    }
