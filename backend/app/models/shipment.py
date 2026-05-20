from datetime import datetime
from enum import Enum
from sqlalchemy import String, Float, DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ShipmentStatus(str, Enum):
    PENDING = "pending"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    route_origin: Mapped[str] = mapped_column(String(512), nullable=False)
    route_destination: Mapped[str] = mapped_column(String(512), nullable=False)
    transport_type: Mapped[str] = mapped_column(String(64), nullable=False)  # truck, rail, sea, air
    product_type: Mapped[str] = mapped_column(String(128), nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=True)
    volume_m3: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[str] = mapped_column(String(32), default="normal")  # low, normal, high
    status: Mapped[ShipmentStatus] = mapped_column(
        SQLEnum(ShipmentStatus, native_enum=False, length=32),
        default=ShipmentStatus.PENDING,
    )
    planned_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transit_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    forecasts = relationship("Forecast", back_populates="shipment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Shipment(id={self.id}, {self.route_origin}->{self.route_destination}, status={self.status})>"
