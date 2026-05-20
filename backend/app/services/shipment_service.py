from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shipment import Shipment, ShipmentStatus
from app.schemas.shipment import DeliverySummary, ShipmentCreate, ShipmentListItem, ShipmentResponse
from app.services.delivery_summary import build_delivery_summary
from app.services.route_estimation import estimate_transit_hours
from app.services.shipment_completion import ProximityCheck, check_cargo_near_destination

_COMPLETABLE = {ShipmentStatus.IN_TRANSIT, ShipmentStatus.DELAYED}
_CANCELLABLE = {ShipmentStatus.PENDING, ShipmentStatus.IN_TRANSIT, ShipmentStatus.DELAYED}


class ShipmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: ShipmentCreate) -> Shipment:
        now = datetime.now(timezone.utc)
        transit_start = None
        actual = None
        if data.status in (ShipmentStatus.IN_TRANSIT, ShipmentStatus.DELAYED):
            transit_start = now
        elif data.status == ShipmentStatus.DELIVERED:
            transit_start = now
            actual = data.planned_delivery_at or now

        shipment = Shipment(
            route_origin=data.route_origin,
            route_destination=data.route_destination,
            transport_type=data.transport_type,
            product_type=data.product_type,
            weight_kg=data.weight_kg,
            volume_m3=data.volume_m3,
            priority=data.priority,
            planned_delivery_at=data.planned_delivery_at,
            status=data.status,
            notes=data.notes,
            transit_started_at=transit_start,
            actual_delivery_at=actual,
            created_at=now,
        )
        self.db.add(shipment)
        await self.db.flush()
        if not shipment.planned_delivery_at and data.status in (
            ShipmentStatus.IN_TRANSIT,
            ShipmentStatus.DELAYED,
        ):
            await self._ensure_planned_delivery(shipment)
        await self.db.refresh(shipment)
        return shipment

    async def get_by_id(self, shipment_id: int) -> Shipment | None:
        result = await self.db.execute(select(Shipment).where(Shipment.id == shipment_id))
        return result.scalar_one_or_none()

    @staticmethod
    def to_list_item(shipment: Shipment) -> ShipmentListItem:
        return ShipmentListItem.model_validate(shipment)

    @staticmethod
    def to_response(shipment: Shipment) -> ShipmentResponse:
        base = ShipmentListItem.model_validate(shipment)
        summary = None
        try:
            raw = build_delivery_summary(shipment)
            if raw:
                summary = DeliverySummary.model_validate(raw)
        except Exception:
            summary = None
        return ShipmentResponse(**base.model_dump(), delivery_summary=summary)

    async def list_shipments(
        self,
        skip: int = 0,
        limit: int = 20,
        status: ShipmentStatus | None = None,
        route_origin: str | None = None,
        transport_type: str | None = None,
    ):
        q = select(Shipment).order_by(Shipment.id.desc())
        count_q = select(func.count()).select_from(Shipment)
        if status is not None:
            q = q.where(Shipment.status == status)
            count_q = count_q.where(Shipment.status == status)
        if route_origin:
            q = q.where(Shipment.route_origin.ilike(f"%{route_origin}%"))
            count_q = count_q.where(Shipment.route_origin.ilike(f"%{route_origin}%"))
        if transport_type:
            q = q.where(Shipment.transport_type == transport_type)
            count_q = count_q.where(Shipment.transport_type == transport_type)
        total = (await self.db.execute(count_q)).scalar() or 0
        q = q.offset(skip).limit(limit)
        result = await self.db.execute(q)
        items = list(result.scalars().all())
        return items, total

    async def get_history_for_route(
        self, route_origin: str, route_destination: str, transport_type: str, limit: int = 100
    ):
        """Исторические поставки по маршруту для ML-признаков."""
        q = (
            select(Shipment)
            .where(
                Shipment.route_origin.ilike(f"%{route_origin}%"),
                Shipment.route_destination.ilike(f"%{route_destination}%"),
                Shipment.transport_type == transport_type,
                Shipment.status == ShipmentStatus.DELIVERED,
                Shipment.actual_delivery_at.isnot(None),
            )
            .order_by(Shipment.actual_delivery_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_dashboard_plan_fulfillment(self, period: str = "month"):
        """Статистика выполнения плана за период: план, факт, в работе, задержано, процент, тренд."""
        now = datetime.utcnow()
        if period == "day":
            start = now - timedelta(days=1)
            prev_start = now - timedelta(days=2)
        elif period == "week":
            start = now - timedelta(weeks=1)
            prev_start = now - timedelta(weeks=2)
        else:
            start = now - timedelta(days=30)
            prev_start = now - timedelta(days=60)

        # План: запланированы к доставке в периоде (planned_delivery_at в [start, now])
        plan_q = select(func.count()).select_from(Shipment).where(
            and_(
                Shipment.planned_delivery_at.isnot(None),
                Shipment.planned_delivery_at >= start,
                Shipment.planned_delivery_at <= now,
            )
        )
        plan = (await self.db.execute(plan_q)).scalar() or 0

        # Факт: доставлены в периоде (actual_delivery_at в [start, now])
        fact_q = select(func.count()).select_from(Shipment).where(
            and_(
                Shipment.actual_delivery_at.isnot(None),
                Shipment.actual_delivery_at >= start,
                Shipment.actual_delivery_at <= now,
            )
        )
        fact = (await self.db.execute(fact_q)).scalar() or 0

        # В работе и задержано — текущие счётчики
        in_work_q = select(func.count()).select_from(Shipment).where(Shipment.status == ShipmentStatus.IN_TRANSIT)
        delayed_q = select(func.count()).select_from(Shipment).where(Shipment.status == ShipmentStatus.DELAYED)
        in_work = (await self.db.execute(in_work_q)).scalar() or 0
        delayed = (await self.db.execute(delayed_q)).scalar() or 0

        percent = round((fact / plan * 100), 0) if plan else 0
        prev_fact_q = select(func.count()).select_from(Shipment).where(
            and_(
                Shipment.actual_delivery_at.isnot(None),
                Shipment.actual_delivery_at >= prev_start,
                Shipment.actual_delivery_at < start,
            )
        )
        prev_plan_q = select(func.count()).select_from(Shipment).where(
            and_(
                Shipment.planned_delivery_at.isnot(None),
                Shipment.planned_delivery_at >= prev_start,
                Shipment.planned_delivery_at < start,
            )
        )
        prev_plan = (await self.db.execute(prev_plan_q)).scalar() or 0
        prev_fact = (await self.db.execute(prev_fact_q)).scalar() or 0
        prev_percent = round((prev_fact / prev_plan * 100), 0) if prev_plan else 0
        trend_percent = percent - prev_percent

        return {
            "plan": plan,
            "fact": fact,
            "in_work": in_work,
            "delayed": delayed,
            "percent": int(percent),
            "trend_percent": int(trend_percent),
        }

    async def _ensure_planned_delivery(self, shipment: Shipment) -> None:
        if shipment.planned_delivery_at:
            return
        _, hours = estimate_transit_hours(
            shipment.route_origin,
            shipment.route_destination,
            shipment.transport_type or "truck",
        )
        base = shipment.transit_started_at or shipment.created_at or datetime.now(timezone.utc)
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        shipment.planned_delivery_at = base + timedelta(hours=max(12.0, hours or 48.0))

    async def get_completion_proximity(self, shipment: Shipment) -> ProximityCheck:
        return await check_cargo_near_destination(shipment)

    async def complete_shipment(self, shipment: Shipment) -> ProximityCheck:
        if shipment.status not in _COMPLETABLE:
            raise ValueError("Поставку можно завершить только из статуса «в пути» или «задержано»")
        check = await check_cargo_near_destination(shipment)
        if not check.ok:
            return check

        now = datetime.now(timezone.utc)
        if not shipment.transit_started_at:
            shipment.transit_started_at = shipment.created_at or now
        await self._ensure_planned_delivery(shipment)
        shipment.status = ShipmentStatus.DELIVERED
        shipment.actual_delivery_at = now
        shipment.updated_at = now
        await self.db.flush()
        await self.db.refresh(shipment)
        return check

    async def start_transit(self, shipment: Shipment) -> None:
        if shipment.status != ShipmentStatus.PENDING:
            raise ValueError("Начать можно только поставку в статусе «ожидает»")
        now = datetime.now(timezone.utc)
        shipment.status = ShipmentStatus.IN_TRANSIT
        shipment.transit_started_at = now
        shipment.updated_at = now
        await self._ensure_planned_delivery(shipment)
        await self.db.flush()
        await self.db.refresh(shipment)

    async def cancel_shipment(self, shipment: Shipment, notes: str | None = None) -> None:
        if shipment.status not in _CANCELLABLE:
            raise ValueError("Нельзя отменить завершённую или уже отменённую поставку")
        now = datetime.now(timezone.utc)
        shipment.status = ShipmentStatus.CANCELLED
        shipment.actual_delivery_at = None
        if notes:
            prev = (shipment.notes or "").strip()
            shipment.notes = f"{prev}\n[отмена] {notes}".strip() if prev else f"[отмена] {notes}"
        shipment.updated_at = now
        await self.db.flush()
        await self.db.refresh(shipment)

    async def list_active_shipments(self, limit: int = 20):
        """Поставки в статусе «в пути» для блока Real-time."""
        q = (
            select(Shipment)
            .where(Shipment.status == ShipmentStatus.IN_TRANSIT)
            .order_by(Shipment.planned_delivery_at.desc().nullslast())
            .limit(limit)
        )
        result = await self.db.execute(q)
        return list(result.scalars().all())
