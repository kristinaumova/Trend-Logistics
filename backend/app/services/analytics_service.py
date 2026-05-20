"""Сводная аналитика для страницы Analytics (PostgreSQL + опционально ClickHouse)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.forecast import Forecast
from app.models.shipment import Shipment, ShipmentStatus
from app.services.clickhouse_analytics import _get_client
from app.services.shipment_service import ShipmentService

_FACTOR_LABELS = {
    "weather": "Погода",
    "traffic": "Трафик",
    "geopolitics": "Геополитика",
    "route": "Маршрут",
    "telemetry": "Телеметрия",
}


async def build_analytics_summary(db: AsyncSession, period: str = "month") -> dict[str, Any]:
    total = (await db.execute(select(func.count()).select_from(Shipment))).scalar() or 0
    fc_total = (await db.execute(select(func.count()).select_from(Forecast))).scalar() or 0

    by_status: dict[str, int] = {}
    for st in ShipmentStatus:
        c = (await db.execute(select(func.count()).where(Shipment.status == st))).scalar() or 0
        by_status[st.value] = c

    transport_rows = await db.execute(
        select(Shipment.transport_type, func.count()).group_by(Shipment.transport_type)
    )
    by_transport = {r[0] or "unknown": r[1] for r in transport_rows.all()}

    priority_rows = await db.execute(
        select(Shipment.priority, func.count()).group_by(Shipment.priority)
    )
    by_priority = {r[0] or "normal": r[1] for r in priority_rows.all()}

    with_forecast = (
        await db.execute(select(func.count(func.distinct(Forecast.shipment_id))))
    ).scalar() or 0

    fc_stats = await db.execute(
        select(
            func.avg(Forecast.predicted_days_median),
            func.avg(Forecast.risk_score),
            func.min(Forecast.predicted_days_median),
            func.max(Forecast.predicted_days_median),
        )
    )
    avg_median, avg_risk, min_days, max_days = fc_stats.one()
    high_risk = (
        await db.execute(select(func.count()).where(Forecast.risk_score >= 0.5))
    ).scalar() or 0

    fc_by_transport_rows = await db.execute(
        select(Shipment.transport_type, func.count())
        .select_from(Forecast)
        .join(Shipment, Shipment.id == Forecast.shipment_id)
        .group_by(Shipment.transport_type)
    )
    forecasts_by_transport = {r[0] or "unknown": r[1] for r in fc_by_transport_rows.all()}

    route_rows = await db.execute(
        select(Shipment.route_origin, Shipment.route_destination, func.count())
        .group_by(Shipment.route_origin, Shipment.route_destination)
        .order_by(func.count().desc())
        .limit(8)
    )
    top_routes = [
        {"origin": r[0], "destination": r[1], "count": r[2]}
        for r in route_rows.all()
    ]

    since = datetime.utcnow() - timedelta(days=90)
    timeline_rows = await db.execute(
        select(
            func.date_trunc("week", Forecast.created_at).label("bucket"),
            func.count(),
        )
        .where(Forecast.created_at >= since)
        .group_by("bucket")
        .order_by("bucket")
    )
    forecasts_timeline = [
        {
            "period": r[0].strftime("%d.%m") if r[0] else "",
            "count": r[1],
        }
        for r in timeline_rows.all()
    ]

    risk_low = (await db.execute(select(func.count()).where(Forecast.risk_score < 0.3))).scalar() or 0
    risk_mid = (
        await db.execute(
            select(func.count()).where(Forecast.risk_score >= 0.3, Forecast.risk_score < 0.6)
        )
    ).scalar() or 0
    risk_high = (await db.execute(select(func.count()).where(Forecast.risk_score >= 0.6))).scalar() or 0
    risk_distribution = [
        {"bucket": "Низкий (<30%)", "count": risk_low},
        {"bucket": "Средний (30–60%)", "count": risk_mid},
        {"bucket": "Высокий (≥60%)", "count": risk_high},
    ]

    factor_impact_avg = await _aggregate_factor_impacts(db)
    delivery_performance = await _delivery_performance(db)

    svc = ShipmentService(db)
    plan_fulfillment = await svc.get_dashboard_plan_fulfillment(period)

    ch_forecasts_30d = _clickhouse_forecasts_last_days(30)

    active = by_status.get("in_transit", 0) + by_status.get("delayed", 0)
    coverage = round(with_forecast / total * 100, 1) if total else 0.0

    weight_rows = await db.execute(
        select(
            func.avg(Shipment.weight_kg),
            func.sum(Shipment.weight_kg),
        ).where(Shipment.weight_kg.isnot(None))
    )
    avg_weight, sum_weight = weight_rows.one()

    return {
        "total_shipments": total,
        "forecasts_total": fc_total,
        "shipments_with_forecast": with_forecast,
        "forecast_coverage_percent": coverage,
        "active_shipments": active,
        "delivered_shipments": by_status.get("delivered", 0),
        "delayed_shipments": by_status.get("delayed", 0),
        "by_status": by_status,
        "by_transport": by_transport,
        "by_priority": by_priority,
        "forecasts_by_transport": forecasts_by_transport,
        "plan_fulfillment": plan_fulfillment,
        "forecast_stats": {
            "avg_median_days": round(float(avg_median or 0), 2),
            "avg_risk_score": round(float(avg_risk or 0), 2),
            "min_median_days": round(float(min_days or 0), 2),
            "max_median_days": round(float(max_days or 0), 2),
            "high_risk_count": high_risk,
        },
        "cargo_stats": {
            "avg_weight_kg": round(float(avg_weight or 0), 0),
            "total_weight_kg": round(float(sum_weight or 0), 0),
        },
        "factor_impact_avg": factor_impact_avg,
        "top_routes": top_routes,
        "forecasts_timeline": forecasts_timeline,
        "risk_distribution": risk_distribution,
        "delivery_performance": delivery_performance,
        "clickhouse_forecasts_30d": ch_forecasts_30d,
        "period": period,
    }


async def _aggregate_factor_impacts(db: AsyncSession) -> list[dict[str, Any]]:
    rows = await db.execute(
        select(Forecast.factors_impact_json)
        .where(Forecast.factors_impact_json.isnot(None))
        .order_by(Forecast.created_at.desc())
        .limit(400)
    )
    totals: dict[str, list[float]] = {}
    for (payload,) in rows.all():
        if not payload:
            continue
        for item in payload:
            name = item.get("factor_name") or item.get("factor") or "unknown"
            hours = float(item.get("impact_hours") or 0)
            totals.setdefault(name, []).append(hours)
    result = []
    for name, values in totals.items():
        label = _FACTOR_LABELS.get(name, name)
        result.append({
            "factor": name,
            "label": label,
            "avg_hours": round(sum(values) / len(values), 2),
            "samples": len(values),
        })
    result.sort(key=lambda x: x["avg_hours"], reverse=True)
    return result[:8]


async def _delivery_performance(db: AsyncSession) -> dict[str, Any]:
    rows = await db.execute(
        select(Shipment.planned_delivery_at, Shipment.actual_delivery_at)
        .where(
            Shipment.status == ShipmentStatus.DELIVERED,
            Shipment.planned_delivery_at.isnot(None),
            Shipment.actual_delivery_at.isnot(None),
        )
        .limit(2000)
    )
    on_time = 0
    delays: list[float] = []
    n = 0
    for planned, actual in rows.all():
        if not planned or not actual:
            continue
        n += 1
        delta_days = (actual - planned).total_seconds() / 86400
        if delta_days <= 0:
            on_time += 1
        else:
            delays.append(delta_days)
    return {
        "sample_size": n,
        "on_time_percent": round(on_time / n * 100, 1) if n else None,
        "avg_delay_days": round(sum(delays) / len(delays), 2) if delays else 0.0,
        "late_count": len(delays),
    }


def _clickhouse_forecasts_last_days(days: int) -> int | None:
    c = _get_client()
    if c is None:
        return None
    try:
        r = c.query(
            f"SELECT count() FROM forecast_events WHERE created_at >= now() - INTERVAL {int(days)} DAY"
        )
        return int(r.result_rows[0][0]) if r.result_rows else 0
    except Exception:
        return None
