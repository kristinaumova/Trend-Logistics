from datetime import datetime
from sqlalchemy import String, Float, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ExternalFactorRecord(Base):
    """Кэш/записи внешних факторов по маршруту или региону (для истории и расчёта признаков)."""
    __tablename__ = "external_factors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    factor_type: Mapped[str] = mapped_column(String(64), nullable=False)  # weather, traffic, geopolitics
    region_or_route: Mapped[str] = mapped_column(String(255), nullable=False)
    value_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    impact_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # количественное влияние
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
