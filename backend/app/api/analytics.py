from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_db
from app.models.user import User
from app.services.analytics_service import build_analytics_summary

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
async def analytics_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    period: Literal["day", "week", "month"] = Query("month", description="Период для блока «выполнение плана»"),
):
    """Расширенная сводка для страницы аналитики."""
    return await build_analytics_summary(db, period=period)
