from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.shipment import ShipmentStatus


class ShipmentCreate(BaseModel):
    route_origin: str = Field(..., min_length=1, max_length=512)
    route_destination: str = Field(..., min_length=1, max_length=512)
    transport_type: str = Field(..., pattern="^(truck|rail|sea|air)$")
    product_type: str = Field(..., min_length=1, max_length=128)
    weight_kg: float | None = None
    volume_m3: float | None = None
    priority: str = Field("normal", pattern="^(low|normal|high)$")
    planned_delivery_at: datetime | None = None
    status: ShipmentStatus = ShipmentStatus.PENDING
    notes: str | None = None


class DeliverySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transit_started_at: datetime | None = None
    delivered_at: datetime | None = None
    duration_hours: float | None = None
    duration_label: str | None = None
    vs_plan_hours: float | None = None
    vs_plan_label: str | None = None
    complete: bool = False


class ShipmentListItem(BaseModel):
    """Краткая карточка для таблицы на дашборде."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    route_origin: str
    route_destination: str
    transport_type: str
    product_type: str
    weight_kg: float | None
    volume_m3: float | None
    priority: str
    status: ShipmentStatus
    planned_delivery_at: datetime | None
    actual_delivery_at: datetime | None
    transit_started_at: datetime | None = None
    created_at: datetime
    notes: str | None


class ShipmentResponse(ShipmentListItem):
    """Полная карточка поставки (детали)."""
    delivery_summary: DeliverySummary | None = None


class ShipmentListResponse(BaseModel):
    items: list[ShipmentListItem]
    total: int


class ProximityStatus(BaseModel):
    can_complete: bool
    distance_km: float | None = None
    max_distance_km: float
    progress: float | None = None
    message: str


class ShipmentActionResult(BaseModel):
    shipment: ShipmentResponse
    proximity: ProximityStatus | None = None
    ml_retrained: bool = False
    ml_samples_used: int = 0


class ShipmentCancelIn(BaseModel):
    notes: str | None = Field(None, max_length=2000)
