import asyncio
import random
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import func, select
from starlette.responses import Response

from app.api import (
    analytics,
    auth,
    config_public,
    factors,
    forecasts,
    geocode_api,
    grafana_proxy,
    route as route_api,
    shipments,
    telemetry_api,
    users_admin,
)
from app.auth import hash_password
from app.middleware.http_metrics import HttpMetricsMiddleware
from app.config import settings
from app.db import AsyncSessionLocal, init_db
from app.models.shipment import Shipment, ShipmentStatus
from app.models.user import User
from app.redis_client import close_redis
from app.services.clickhouse_analytics import init_clickhouse_schema


async def ensure_default_user():
    """Создать или обновить admin из ADMIN_PASSWORD (пароль не хранится в коде и не показывается в UI)."""
    pwd = (settings.admin_password or "").strip()
    if not pwd:
        return
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(User).where(User.login == "admin"))
        admin = r.scalar_one_or_none()
        hashed = hash_password(pwd)
        if admin is not None:
            admin.password_hash = hashed
        else:
            r = await db.execute(select(func.count()).select_from(User))
            if (r.scalar() or 0) > 0:
                return
            db.add(User(login="admin", password_hash=hashed, role="admin"))
        await db.commit()


async def ensure_seed_shipments():
    """Демо-данные: при первом запуске (пустая БД) создаёт 50 тестовых поставок.
    Новые поставки логисты добавляют через UI «+ Новая поставка» или POST /shipments."""
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(func.count()).select_from(Shipment))
        if (r.scalar() or 0) > 0:
            return
        routes = [
            ("Москва", "Санкт-Петербург"),
            ("Москва", "Казань"),
            ("Санкт-Петербург", "Москва"),
            ("Новосибирск", "Москва"),
            ("Новосибирск", "Омск"),
            ("Екатеринбург", "Самара"),
            ("Екатеринбург", "Челябинск"),
            ("Казань", "Нижний Новгород"),
            ("Казань", "Уфа"),
        ]
        transport_types = ["truck", "rail", "truck", "truck", "sea", "air"]
        products = ["Генеральные грузы", "Контейнеры", "Скоропортящиеся", "Оборудование", "Промышленные детали"]
        for _ in range(50):
            origin, dest = random.choice(routes)
            transit_days = random.uniform(2, 11)
            started = datetime.utcnow() - timedelta(days=random.randint(5, 40))
            planned = started + timedelta(days=transit_days * 0.95)
            actual = started + timedelta(days=transit_days) if random.random() > 0.3 else None
            status = (
                ShipmentStatus.DELIVERED
                if actual
                else (ShipmentStatus.IN_TRANSIT if random.random() > 0.5 else ShipmentStatus.PENDING)
            )
            s = Shipment(
                route_origin=origin,
                route_destination=dest,
                transport_type=random.choice(transport_types),
                product_type=random.choice(products),
                weight_kg=random.uniform(100, 5000),
                volume_m3=round(random.uniform(1, 20), 1) if random.random() > 0.3 else None,
                priority=random.choice(["low", "normal", "high"]),
                status=status,
                created_at=started,
                transit_started_at=started if status != ShipmentStatus.PENDING else None,
                planned_delivery_at=planned,
                actual_delivery_at=actual,
            )
            db.add(s)
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await ensure_default_user()
    await ensure_seed_shipments()
    await asyncio.to_thread(init_clickhouse_schema)
    from app.api import forecasts as forecasts_mod

    forecasts_mod._ml_service.fit_synthetic_baseline()
    try:
        async with AsyncSessionLocal() as db:
            from app.services.ml_training import retrain_ml_from_deliveries

            info = await retrain_ml_from_deliveries(
                db, forecasts_mod._ml_service, ensure_baseline=False
            )
            if info.get("retrained"):
                import logging

                logging.getLogger("trend").info(
                    "ML дообучена на %s доставленных поставках",
                    info.get("samples_delivered"),
                )
    except Exception:
        import logging

        logging.getLogger("trend").exception("ML дообучение при старте пропущено")
    yield
    await close_redis()


def _mount_api_routes(application: FastAPI) -> None:
    routers = (
        auth.router,
        config_public.router,
        shipments.router,
        forecasts.router,
        factors.router,
        geocode_api.router,
        route_api.router,
        analytics.router,
        users_admin.router,
        telemetry_api.router,
    )
    for r in routers:
        application.include_router(r)
    v1 = APIRouter(prefix="/api/v1")
    for r in routers:
        v1.include_router(r)
    application.include_router(v1)


app = FastAPI(
    title=settings.app_name,
    description="""
API для прогнозирования сроков поставки с учётом внешних факторов.

- **Авторизация**: `Authorization: Bearer <token>`. При работе с Redis сессия JWT привязана к серверу (`/auth/logout` снимает сессию).
- **Версионирование**: дублирование маршрутов под префиксом `/api/v1` (как в проектной документации); фронтенд по-прежнему может использовать `/api/...` через nginx.
- **Документация**: Swagger UI — `/docs`, ReDoc — `/redoc`.
- **Метрики Prometheus**: `GET /metrics`
    """.strip(),
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "auth", "description": "Вход, выход, текущий пользователь"},
        {"name": "config", "description": "Публичная конфигурация для фронтенда"},
        {"name": "shipments", "description": "Поставки: список, создание, детали"},
        {"name": "forecasts", "description": "Прогнозы сроков доставки (интервальные)"},
        {"name": "external_factors", "description": "Внешние факторы по маршруту (погода, трафик, геополитика)"},
        {"name": "route", "description": "Расчёт маршрута и координаты для карты (OSRM)"},
        {"name": "analytics", "description": "Сводная аналитика по БД"},
        {"name": "users", "description": "Управление пользователями (admin)"},
        {"name": "telemetry", "description": "Эмуляция телеметрии по поставке"},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(HttpMetricsMiddleware)

_mount_api_routes(app)
app.include_router(grafana_proxy.router)


@app.get("/metrics")
async def metrics():
    """Prometheus scrape (см. infra/prometheus/prometheus.yml)."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz")
async def healthz():
    """Лёгкая проверка для Docker/nginx — без обращения к БД."""
    return {"status": "ok"}


@app.get("/")
async def root():
    return {
        "service": settings.app_name,
        "docs_swagger": "/docs",
        "docs_redoc": "/redoc",
        "openapi_json": "/openapi.json",
        "api_v1_prefix": "/api/v1",
        "metrics": "/metrics",
    }
