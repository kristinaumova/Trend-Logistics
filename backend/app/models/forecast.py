from datetime import datetime
from sqlalchemy import String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ForecastRequest(Base):
    """Логика запроса на прогноз (можно расширить под очереди)."""
    __tablename__ = "forecast_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="completed")  # pending, completed, failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    # Интервальный прогноз: дни до доставки
    predicted_days_min: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_days_max: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_days_median: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_level: Mapped[float] = mapped_column(Float, default=0.9)  # например 90%
    # Доп. метрики
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    factors_impact_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # SHAP/влияние факторов
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    shipment = relationship("Shipment", back_populates="forecasts")

    def __repr__(self):
        return f"<Forecast(id={self.id}, shipment_id={self.shipment_id}, days={self.predicted_days_min}-{self.predicted_days_max})>"
