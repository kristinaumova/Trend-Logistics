import asyncio
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models.forecast import Forecast
from app.models.user import User
from app.schemas.forecast import ForecastRequestIn, ForecastResponse, FactorImpact
from app.services.clickhouse_analytics import insert_forecast_event_sync
from app.services.external_data_client import get_all_factors
from app.services.metrics_registry import FORECASTS_CREATED
from app.services.ml_forecast_service import MLForecastService
from app.services.route_service import get_route
from app.services.shipment_service import ShipmentService
from app.models.shipment import ShipmentStatus
from app.services.telemetry_client import get_telemetry_progress, remaining_route_hours

router = APIRouter(prefix="/forecasts", tags=["forecasts"])

_ml_service = MLForecastService()


def _parse_factors_impact(raw: list | None) -> list[FactorImpact] | None:
    if not raw:
        return None
    out: list[FactorImpact] = []
    for x in raw:
        if not isinstance(x, dict):
            continue
        try:
            out.append(FactorImpact.model_validate(x))
        except Exception:
            continue
    return out or None


@router.post("", response_model=ForecastResponse)
async def create_forecast(
    body: ForecastRequestIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    """Запрос прогноза срока поставки по ID поставки. Возвращает интервальный прогноз и факторы влияния."""
    svc = ShipmentService(db)
    shipment = await svc.get_by_id(body.shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    external = await get_all_factors(shipment.route_origin, shipment.route_destination)
    route_info = await get_route(
        shipment.route_origin,
        shipment.route_destination,
        shipment.transport_type or "truck",
    )
    route_hours_full = (
        float(route_info["duration_hours"]) if route_info and route_info.get("duration_hours") else None
    )
    elapsed = None
    if shipment.created_at and shipment.status in (
        ShipmentStatus.IN_TRANSIT,
        ShipmentStatus.DELAYED,
    ):
        created = shipment.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        elapsed = max(
            0.0,
            (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds() / 3600.0,
        )
    tel_progress = await get_telemetry_progress(
        shipment.route_origin,
        shipment.route_destination,
        shipment.transport_type or "truck",
        shipment.id,
        total_route_hours=route_hours_full,
        elapsed_hours=elapsed,
        shipment_status=shipment.status.value,
    )
    route_hours_remaining = remaining_route_hours(route_hours_full, tel_progress)
    days_min, days_max, days_median, risk_score, factors_impact = _ml_service.predict_interval(
        shipment,
        external,
        route_base_hours=route_hours_remaining or route_hours_full,
        telemetry_progress=tel_progress,
    )
    forecast = Forecast(
        shipment_id=shipment.id,
        predicted_days_min=round(days_min, 2),
        predicted_days_max=round(days_max, 2),
        predicted_days_median=round(days_median, 2),
        confidence_level=0.9,
        risk_score=round(risk_score, 2),
        factors_impact_json=[f.model_dump() for f in factors_impact] if factors_impact else None,
    )
    db.add(forecast)
    await db.flush()
    await db.refresh(forecast)
    try:
        FORECASTS_CREATED.labels(shipment.transport_type or "unknown").inc()
        await asyncio.to_thread(
            insert_forecast_event_sync,
            forecast.id,
            shipment.id,
            shipment.transport_type or "",
            float(forecast.predicted_days_min),
            float(forecast.predicted_days_max),
            float(forecast.predicted_days_median),
            float(forecast.risk_score or 0.0),
            forecast.created_at,
        )
    except Exception:
        pass
    return ForecastResponse(
        id=forecast.id,
        shipment_id=forecast.shipment_id,
        predicted_days_min=forecast.predicted_days_min,
        predicted_days_max=forecast.predicted_days_max,
        predicted_days_median=forecast.predicted_days_median,
        confidence_level=forecast.confidence_level,
        risk_score=forecast.risk_score,
        factors_impact=_parse_factors_impact(forecast.factors_impact_json),
        created_at=forecast.created_at,
    )


@router.get("/by-shipment/{shipment_id}", response_model=ForecastResponse | None)
async def get_latest_forecast_for_shipment(
    shipment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    from sqlalchemy import select
    result = await db.execute(
        select(Forecast).where(Forecast.shipment_id == shipment_id).order_by(Forecast.created_at.desc()).limit(1)
    )
    forecast = result.scalar_one_or_none()
    if not forecast:
        return None
    return ForecastResponse(
        id=forecast.id,
        shipment_id=forecast.shipment_id,
        predicted_days_min=forecast.predicted_days_min,
        predicted_days_max=forecast.predicted_days_max,
        predicted_days_median=forecast.predicted_days_median,
        confidence_level=forecast.confidence_level,
        risk_score=forecast.risk_score,
        factors_impact=_parse_factors_impact(forecast.factors_impact_json),
        created_at=forecast.created_at,
    )
