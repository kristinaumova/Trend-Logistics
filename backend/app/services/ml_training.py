"""Дообучение ML на завершённых поставках (без отменённых)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shipment import Shipment, ShipmentStatus
from app.services.ml_forecast_service import MLForecastService


async def load_delivered_for_ml(db: AsyncSession, limit: int = 500) -> list[Shipment]:
    q = (
        select(Shipment)
        .where(
            Shipment.status == ShipmentStatus.DELIVERED,
            Shipment.planned_delivery_at.isnot(None),
            Shipment.actual_delivery_at.isnot(None),
        )
        .order_by(Shipment.actual_delivery_at.desc())
        .limit(limit)
    )
    result = await db.execute(q)
    return list(result.scalars().all())


async def retrain_ml_from_deliveries(
    db: AsyncSession,
    ml_service: MLForecastService,
    *,
    ensure_baseline: bool = True,
) -> dict:
    if ensure_baseline and not ml_service._is_fitted:
        ml_service.fit_synthetic_baseline()

    shipments = await load_delivered_for_ml(db)
    before = ml_service._is_fitted
    ml_service.fit_from_historical(shipments)
    return {
        "retrained": ml_service._is_fitted and len(shipments) >= 8,
        "samples_delivered": len(shipments),
        "min_samples_required": 8,
        "was_fitted_before": before,
    }
