from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models.shipment import ShipmentStatus
from app.models.user import User
from app.schemas.shipment import (
    ProximityStatus,
    ShipmentActionResult,
    ShipmentCancelIn,
    ShipmentCreate,
    ShipmentListResponse,
    ShipmentResponse,
)
from app.services.metrics_registry import SHIPMENTS_CREATED
from app.services.ml_training import retrain_ml_from_deliveries
from app.services.shipment_service import ShipmentService

_COMPLETABLE = {ShipmentStatus.IN_TRANSIT, ShipmentStatus.DELAYED}

router = APIRouter(prefix="/shipments", tags=["shipments"])


@router.post("", response_model=ShipmentResponse)
async def create_shipment(
    data: ShipmentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    from app.services.geocode_address import geocode_place

    origin = await geocode_place(data.route_origin)
    if not origin:
        raise HTTPException(
            status_code=400,
            detail="Не удалось определить пункт отправления — выберите адрес из подсказок",
        )
    dest = await geocode_place(data.route_destination)
    if not dest:
        raise HTTPException(
            status_code=400,
            detail="Не удалось определить пункт назначения — выберите адрес из подсказок",
        )

    svc = ShipmentService(db)
    shipment = await svc.create(data)
    SHIPMENTS_CREATED.labels(shipment.transport_type or "unknown").inc()
    return ShipmentService.to_response(shipment)


@router.get("", response_model=ShipmentListResponse)
async def list_shipments(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: ShipmentStatus | None = Query(None),
    route_origin: str | None = Query(None),
    transport_type: str | None = Query(None),
):
    # Пустые строки из query трактуем как "без фильтра"
    status_val = status if status else None
    route_origin_val = (route_origin or "").strip() or None
    transport_type_val = (transport_type or "").strip() or None
    svc = ShipmentService(db)
    items, total = await svc.list_shipments(
        skip=skip,
        limit=limit,
        status=status_val,
        route_origin=route_origin_val or None,
        transport_type=transport_type_val or None,
    )
    return ShipmentListResponse(
        items=[ShipmentService.to_list_item(s) for s in items],
        total=total,
    )


@router.get("/stats")
async def shipment_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    period: str | None = Query(None, description="day|week|month для блока «Выполнение плана»"),
):
    """Сводка для дашборда: всего записей и (при period) выполнение плана за период."""
    from sqlalchemy import select, func
    from app.models.shipment import Shipment
    r = await db.execute(select(func.count()).select_from(Shipment))
    total = r.scalar() or 0
    out = {"total_shipments": total}
    if period in ("day", "week", "month"):
        svc = ShipmentService(db)
        out["plan_fulfillment"] = await svc.get_dashboard_plan_fulfillment(period)
    return out


@router.get("/active")
async def active_shipments(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(20, ge=1, le=100),
):
    """Поставки «в пути» для блока Real-time на дашборде."""
    from datetime import datetime, timezone

    from app.models.shipment import ShipmentStatus
    from app.services.geocode_address import geocode_place
    from app.services.route_service import get_route
    from app.services.telemetry_client import fetch_telemetry

    svc = ShipmentService(db)
    items = await svc.list_active_shipments(limit=limit)
    result = []
    for s in items:
        eta_hours = None
        route_info = await get_route(
            s.route_origin, s.route_destination, s.transport_type or "truck"
        )
        total_h = (
            float(route_info["duration_hours"])
            if route_info and route_info.get("duration_hours")
            else None
        )
        elapsed = None
        if s.created_at:
            created = s.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            elapsed = max(
                0.0,
                (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds()
                / 3600.0,
            )
        o = await geocode_place(s.route_origin)
        d = await geocode_place(s.route_destination)
        tel = await fetch_telemetry(
            s.route_origin,
            s.route_destination,
            s.transport_type or "truck",
            s.id,
            origin_lat=o[0] if o else None,
            origin_lon=o[1] if o else None,
            dest_lat=d[0] if d else None,
            dest_lon=d[1] if d else None,
            elapsed_hours=elapsed,
            total_route_hours=total_h,
            shipment_status=ShipmentStatus.IN_TRANSIT.value,
        )
        progress = tel.get("progress") if tel else None
        if tel and tel.get("eta_hours_remaining") is not None:
            eta_hours = tel["eta_hours_remaining"]
        position = tel.get("position") if tel else None

        result.append({
            "id": s.id,
            "route_origin": s.route_origin,
            "route_destination": s.route_destination,
            "transport_type": s.transport_type,
            "eta_hours": round(eta_hours, 1) if eta_hours is not None else None,
            "telemetry_progress": progress,
            "position": position,
        })
    return {"items": result}


@router.get("/{shipment_id}/completion-status", response_model=ProximityStatus)
async def completion_status(
    shipment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    """Проверка: можно ли завершить поставку (груз у пункта назначения)."""
    svc = ShipmentService(db)
    shipment = await svc.get_by_id(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if shipment.status not in _COMPLETABLE:
        return ProximityStatus(
            can_complete=False,
            max_distance_km=0,
            message="Завершение доступно только для рейсов «в пути» или «задержано»",
        )
    check = await svc.get_completion_proximity(shipment)
    return ProximityStatus(
        can_complete=check.ok,
        distance_km=check.distance_km,
        max_distance_km=check.max_distance_km,
        progress=check.progress,
        message=check.message,
    )


@router.post("/{shipment_id}/start", response_model=ShipmentActionResult)
async def start_shipment(
    shipment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    """Перевести запланированную поставку в статус «в пути» и зафиксировать время отправления."""
    svc = ShipmentService(db)
    shipment = await svc.get_by_id(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    try:
        await svc.start_transit(shipment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ShipmentActionResult(shipment=ShipmentService.to_response(shipment))


@router.post("/{shipment_id}/complete", response_model=ShipmentActionResult)
async def complete_shipment(
    shipment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    """Завершить доставку, если груз (GPS-эмуляция) у пункта назначения. Запускает дообучение ML."""
    from app.api import forecasts as forecasts_mod

    svc = ShipmentService(db)
    shipment = await svc.get_by_id(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    try:
        check = await svc.complete_shipment(shipment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not check.ok:
        raise HTTPException(
            status_code=409,
            detail={
                "message": check.message,
                "distance_km": check.distance_km,
                "max_distance_km": check.max_distance_km,
                "progress": check.progress,
            },
        )

    ml_info = await retrain_ml_from_deliveries(db, forecasts_mod._ml_service, ensure_baseline=True)

    prox = ProximityStatus(
        can_complete=True,
        distance_km=check.distance_km,
        max_distance_km=check.max_distance_km,
        progress=check.progress,
        message=check.message,
    )
    return ShipmentActionResult(
        shipment=ShipmentService.to_response(shipment),
        proximity=prox,
        ml_retrained=ml_info.get("retrained", False),
        ml_samples_used=ml_info.get("samples_delivered", 0),
    )


@router.post("/{shipment_id}/cancel", response_model=ShipmentActionResult)
async def cancel_shipment(
    shipment_id: int,
    body: ShipmentCancelIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    """Отменить поставку — в обучение ML не попадает."""
    svc = ShipmentService(db)
    shipment = await svc.get_by_id(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    try:
        await svc.cancel_shipment(shipment, body.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ShipmentActionResult(shipment=ShipmentService.to_response(shipment))


@router.get("/{shipment_id}", response_model=ShipmentResponse)
async def get_shipment(
    shipment_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    svc = ShipmentService(db)
    shipment = await svc.get_by_id(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    try:
        return ShipmentService.to_response(shipment)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка формирования ответа: {exc!s}",
        ) from exc
