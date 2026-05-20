from datetime import datetime
from pydantic import BaseModel, Field


class FactorImpact(BaseModel):
    factor_name: str
    impact_hours: float
    description: str | None = None


class ForecastRequestIn(BaseModel):
    shipment_id: int = Field(..., gt=0)


class ForecastResponse(BaseModel):
    id: int
    shipment_id: int
    predicted_days_min: float
    predicted_days_max: float
    predicted_days_median: float
    confidence_level: float
    risk_score: float
    factors_impact: list[FactorImpact] | None = None
    created_at: datetime

    class Config:
        from_attributes = True
