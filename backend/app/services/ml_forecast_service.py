"""
ML: квантильный градиентный бустинг.
- Базовое обучение на синтетическом датасете (воспроизводимо).
- Дообучение по истории поставок с детерминированными факторами (без random в признаках).
"""
from __future__ import annotations

import numpy as np

from app.models.shipment import Shipment, ShipmentStatus
from app.schemas.forecast import FactorImpact
from app.services.external_factors_service import ExternalFactorsService
from app.services.route_estimation import estimate_transit_hours
from app.services.synthetic_ml_dataset import build_synthetic_xy, train_quantile_models

_LOGISTICS_MULT = {"truck": 1.12, "rail": 1.22, "sea": 1.45, "air": 1.05}


class MLForecastService:
    def __init__(self):
        self._model_low = None
        self._model_median = None
        self._model_high = None
        self._is_fitted = False
        self._factors_fallback = ExternalFactorsService()

    def fit_synthetic_baseline(self, n_samples: int = 4500) -> None:
        """Вызывается при старте приложения: полноценное обучение на синтетике."""
        X, y = build_synthetic_xy(n_samples, seed=42)
        low, med, high = train_quantile_models(X, y, seed=42)
        self._model_low, self._model_median, self._model_high = low, med, high
        self._is_fitted = bool(low and med and high)

    def _feature_row(
        self,
        shipment: Shipment,
        external_factors: dict,
        route_hours: float | None,
        telemetry_progress: float | None,
    ) -> list[float]:
        transport_codes = {"truck": 0, "rail": 1, "sea": 2, "air": 3}
        priority_codes = {"low": 0, "normal": 1, "high": 2}
        t = transport_codes.get(shipment.transport_type, 0)
        p = priority_codes.get(shipment.priority, 1)
        w = (shipment.weight_kg or 0) / 1000.0
        # route_hours здесь — оставшееся время до назначения (от позиции груза), не полный маршрут
        rh = float(route_hours if route_hours and route_hours > 0 else 12.0)
        wd = float(external_factors.get("weather", {}).get("impact_delay_hours", 0) or 0)
        trd = float(external_factors.get("traffic", {}).get("impact_delay_hours", 0) or 0)
        gd = float(external_factors.get("geopolitics", {}).get("impact_delay_hours", 0) or 0)
        tp = float(telemetry_progress if telemetry_progress is not None else 0.5)
        tp = max(0.0, min(1.0, tp))
        return [t, p, w, rh, wd, trd, gd, tp]

    def _extract_features(
        self,
        shipment: Shipment,
        external_factors: dict,
        route_hours: float | None,
        telemetry_progress: float | None,
    ) -> np.ndarray:
        return np.array([self._feature_row(shipment, external_factors, route_hours, telemetry_progress)], dtype=np.float64)

    def fit_from_historical(self, shipments: list[Shipment]) -> None:
        """Дообучение: синтетика + реальные точки (если достаточно истории)."""
        rows_x = []
        rows_y = []
        for s in shipments:
            if s.status != ShipmentStatus.DELIVERED:
                continue
            if not s.planned_delivery_at or not s.actual_delivery_at:
                continue
            d = (s.actual_delivery_at - s.planned_delivery_at).total_seconds() / 86400.0
            d = float(max(0.05, min(d, 21.0)))
            fac = self._factors_fallback.get_all_factors(s.route_origin, s.route_destination)
            _, est_h = estimate_transit_hours(s.route_origin, s.route_destination, s.transport_type or "truck")
            row = self._feature_row(
                s,
                fac,
                est_h,
                0.55,
            )
            rows_x.append(row)
            rows_y.append(d)
        if len(rows_x) < 8:
            return
        Xs, ys = build_synthetic_xy(2500, seed=99)
        X = np.vstack([Xs, np.array(rows_x, dtype=np.float64)])
        y = np.concatenate([ys, np.array(rows_y, dtype=np.float64)])
        low, med, high = train_quantile_models(X, y, seed=101)
        if low and med and high:
            self._model_low, self._model_median, self._model_high = low, med, high
            self._is_fitted = True

    def _clamp_to_route(
        self,
        shipment: Shipment,
        days_low: float,
        days_median: float,
        days_high: float,
        route_base_hours: float | None,
    ) -> tuple[float, float, float]:
        if route_base_hours is None or route_base_hours <= 0:
            days_median = max(0.2, min(days_median, 30.0))
            days_low = max(0.1, min(days_low, days_median))
            days_high = max(days_median, min(days_high, 45.0))
            return days_low, days_median, days_high

        mult = _LOGISTICS_MULT.get(shipment.transport_type, 1.12)
        route_days = (route_base_hours / 24.0) * mult
        floor_d = max(0.2, route_days * 0.75)
        cap_d = max(route_days * 2.6 + 0.5, route_days + 4.0)
        cap_d = min(cap_d, 30.0)

        days_median = max(floor_d, min(days_median, cap_d))
        days_low = max(0.1, min(days_low, days_median * 0.92))
        days_low = max(0.1, min(days_low, days_median))
        days_high = max(days_median * 1.02, min(days_high, cap_d * 1.1))
        days_high = max(days_high, days_median + 0.05)
        return days_low, days_median, days_high

    def predict_interval(
        self,
        shipment: Shipment,
        external_factors: dict,
        route_base_hours: float | None = None,
        telemetry_progress: float | None = None,
    ) -> tuple[float, float, float, float, list[FactorImpact]]:
        if not self._is_fitted:
            self.fit_synthetic_baseline()

        X = self._extract_features(shipment, external_factors, route_base_hours, telemetry_progress)
        days_low = float(self._model_low.predict(X)[0])
        days_median = float(self._model_median.predict(X)[0])
        days_high = float(self._model_high.predict(X)[0])

        days_low, days_median, days_high = self._clamp_to_route(
            shipment, days_low, days_median, days_high, route_base_hours
        )
        days_low = max(0.1, days_low)
        days_high = max(days_low + 0.05, days_high)

        risk = min(1.0, max(0.0, (days_high - days_low) / max(days_median, 0.5) / 3.0))
        factors = [
            FactorImpact(
                factor_name="Погодные условия",
                impact_hours=external_factors.get("weather", {}).get("impact_delay_hours", 0) or 0,
                description="Влияние погоды (Open-Meteo / детерминированный мок)",
            ),
            FactorImpact(
                factor_name="Дорожная обстановка",
                impact_hours=external_factors.get("traffic", {}).get("impact_delay_hours", 0) or 0,
                description="Пробки и ремонты (модель)",
            ),
            FactorImpact(
                factor_name="Геополитические риски",
                impact_hours=external_factors.get("geopolitics", {}).get("impact_delay_hours", 0) or 0,
                description=(
                    "Модельный фактор по паре «откуда→куда»: таможня, санкции, ограничения коридора "
                    "(детерминированный mock, не новостной API)"
                ),
            ),
        ]
        return days_low, days_high, days_median, risk, factors
