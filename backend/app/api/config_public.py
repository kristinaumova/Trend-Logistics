"""Публичный эндпоинт конфигурации для фронта (мониторинг URL и т.д.)."""
from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/public")
async def get_public_config():
    """Конфиг для SPA: ссылка на мониторинг (Grafana), без секретов."""
    url = (settings.monitoring_url or "").strip() or "/grafana/"
    return {"monitoring_url": url}
