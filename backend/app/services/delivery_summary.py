"""Фактические сроки доставки для завершённых поставок."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.shipment import Shipment, ShipmentStatus
from app.services.route_estimation import estimate_transit_hours


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_duration(hours: float) -> str:
    h = max(0.0, hours)
    if h < 1.0:
        return f"{int(round(h * 60))} мин"
    if h < 48.0:
        return f"{h:.1f} ч"
    days = h / 24.0
    if days < 14.0:
        return f"{days:.1f} дн."
    return f"{int(round(days))} дн."


def _status_value(status: ShipmentStatus | str) -> str:
    if isinstance(status, ShipmentStatus):
        return status.value
    return str(status)


def build_delivery_summary(shipment: Shipment) -> dict | None:
    if _status_value(shipment.status) != ShipmentStatus.DELIVERED.value:
        return None

    started = shipment.transit_started_at or shipment.created_at
    ended = shipment.actual_delivery_at

    if not started or not ended:
        return {
            "transit_started_at": _as_utc(started) if started else None,
            "delivered_at": _as_utc(ended) if ended else None,
            "duration_hours": None,
            "duration_label": None,
            "vs_plan_hours": None,
            "vs_plan_label": "Факт доставки не полностью зафиксирован в системе",
            "complete": False,
        }

    started_u = _as_utc(started)
    ended_u = _as_utc(ended)
    if ended_u < started_u:
        _, est_h = estimate_transit_hours(
            shipment.route_origin,
            shipment.route_destination,
            shipment.transport_type or "truck",
        )
        started_u = ended_u - timedelta(hours=max(24.0, est_h or 72.0))
    duration_h = max(0.0, (ended_u - started_u).total_seconds() / 3600.0)

    vs_plan_h = None
    vs_plan_label = None
    if shipment.planned_delivery_at:
        planned_u = _as_utc(shipment.planned_delivery_at)
        vs_plan_h = round((ended_u - planned_u).total_seconds() / 3600.0, 1)
        if abs(vs_plan_h) < 1:
            vs_plan_label = "В срок по плану"
        elif vs_plan_h > 0:
            vs_plan_label = f"Позже плана на {_format_duration(vs_plan_h)}"
        else:
            vs_plan_label = f"Раньше плана на {_format_duration(-vs_plan_h)}"

    return {
        "transit_started_at": started_u,
        "delivered_at": ended_u,
        "duration_hours": round(duration_h, 2),
        "duration_label": _format_duration(duration_h),
        "vs_plan_hours": vs_plan_h,
        "vs_plan_label": vs_plan_label,
        "complete": True,
    }
