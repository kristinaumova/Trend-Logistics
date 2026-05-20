from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.models.user import User
from app.services.route_service import get_route

router = APIRouter(prefix="/route", tags=["route"])


@router.get("")
async def route(
    _user: Annotated[User, Depends(get_current_user)],
    route_origin: str = Query(..., description="Город или полный адрес отправления"),
    route_destination: str = Query(..., description="Город или полный адрес назначения"),
    transport_type: str = Query("truck", description="truck|rail|sea|air — для оценки времени при fallback"),
):
    """
    Расчёт маршрута (автодорога) между городами.
    Возвращает расстояние (км), базовое время (ч) и координаты для отрисовки на карте.
    OSRM + проверка разумности; при сбое — оценка по расстоянию.
    """
    result = await get_route(route_origin, route_destination, transport_type)
    if result is None:
        return {
            "distance_km": None,
            "duration_hours": None,
            "coordinates": [],
            "origin": None,
            "destination": None,
            "error": "Маршрут не найден (не удалось геокодировать адрес или ошибка OSRM)",
        }
    return result
