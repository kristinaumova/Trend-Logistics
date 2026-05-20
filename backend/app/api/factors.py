from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.auth import get_current_user
from app.models.user import User
from app.services.external_data_client import get_all_factors

router = APIRouter(prefix="/factors", tags=["external_factors"])


class RouteParams(BaseModel):
    route_origin: str
    route_destination: str


@router.get("/for-route")
async def get_factors_for_route(
    _user: Annotated[User, Depends(get_current_user)],
    route_origin: str = Query(...),
    route_destination: str = Query(...),
):
    """Текущие внешние факторы по маршруту (погода, трафик, геополитика). Источник: внешний сервис или встроенный мок."""
    return await get_all_factors(route_origin, route_destination)
