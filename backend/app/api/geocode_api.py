from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.models.user import User
from app.services.geocode_address import suggest_addresses

router = APIRouter(prefix="/geocode", tags=["geocode"])


@router.get("/suggest")
async def address_suggest(
    _user: Annotated[User, Depends(get_current_user)],
    q: str = Query(..., min_length=2, max_length=500, description="Часть адреса или города"),
    limit: int = Query(10, ge=1, le=15),
):
    """Подсказки при вводе адреса (города + OpenStreetMap)."""
    items = await suggest_addresses(q, limit=limit)
    return {"items": items}
