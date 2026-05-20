"""
Внешние факторы: мок детерминированный по паре городов (одинаковый маршрут → те же значения).
"""
from typing import Any

from app.utils.deterministic import route_seed, seeded_choice, seeded_float


class ExternalFactorsService:
    CONDITIONS = ["clear", "moderate_rain", "snow", "fog", "cloudy"]
    CONGESTION = ["low", "medium", "high"]
    RISK = ["low", "medium", "high"]

    def get_weather_for_route(self, route_origin: str, route_destination: str) -> dict[str, Any]:
        seed = route_seed(route_origin, route_destination, "weather")
        cond = seeded_choice(seed, 1, self.CONDITIONS)
        return {
            "condition": cond,
            "temp_min": round(seeded_float(seed, 2, -12, 24), 1),
            "temp_max": round(seeded_float(seed, 3, 2, 32), 1),
            "wind_speed_kmh": round(seeded_float(seed, 4, 0, 45), 1),
            "impact_delay_hours": round(seeded_float(seed, 5, 0, 10), 2),
        }

    def get_traffic_for_route(self, route_origin: str, route_destination: str) -> dict[str, Any]:
        seed = route_seed(route_origin, route_destination, "traffic")
        return {
            "congestion_level": seeded_choice(seed, 1, self.CONGESTION),
            "road_works_km": round(seeded_float(seed, 2, 0, 28), 1),
            "impact_delay_hours": round(seeded_float(seed, 3, 0, 7), 2),
        }

    def get_geopolitical_risk(self, route_origin: str, route_destination: str) -> dict[str, Any]:
        seed = route_seed(route_origin, route_destination, "geo")
        level = seeded_choice(seed, 1, self.RISK)
        hours = round(seeded_float(seed, 2, 0, 36), 2)
        return {
            "risk_level": level,
            "impact_delay_hours": hours,
            "description": (
                "Оценка задержек на коридоре (таможня, санкции, региональные ограничения). "
                "Считается детерминированно по паре городов/адресов — демо-модель, не live-новости."
            ),
        }

    def get_all_factors(
        self, route_origin: str, route_destination: str
    ) -> dict[str, dict[str, Any]]:
        return {
            "weather": self.get_weather_for_route(route_origin, route_destination),
            "traffic": self.get_traffic_for_route(route_origin, route_destination),
            "geopolitics": self.get_geopolitical_risk(route_origin, route_destination),
        }
