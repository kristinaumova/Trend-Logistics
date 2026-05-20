"""
Сервис внешних данных для Trend Logistics.
Отдаёт погоду, трафик и геополитику по маршруту: мок или живые API (Open-Meteo и др.).
"""
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from providers.weather import get_weather
from providers.traffic import get_traffic
from providers.geopolitics import get_geopolitics

app = FastAPI(
    title="External Data Service",
    description="Погода, трафик и геополитические риски по маршруту. Режимы: mock или live API (Open-Meteo и др.).",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "external_data"}


@app.get("/weather")
async def weather(route_origin: str = "", route_destination: str = ""):
    """Погодные условия по маршруту. При USE_LIVE_WEATHER=true — Open-Meteo."""
    return await get_weather(route_origin, route_destination)


@app.get("/traffic")
async def traffic(route_origin: str = "", route_destination: str = ""):
    """Дорожная обстановка. При USE_LIVE_TRAFFIC=true — внешний API (настраивается)."""
    return await get_traffic(route_origin, route_destination)


@app.get("/geopolitics")
async def geopolitics(route_origin: str = "", route_destination: str = ""):
    """Геополитические риски. При USE_LIVE_GEOPOLITICS=true — внешний API (настраивается)."""
    return await get_geopolitics(route_origin, route_destination)


@app.get("/factors")
async def factors(route_origin: str = "", route_destination: str = ""):
    """Агрегированные факторы: погода, трафик, геополитика (один запрос вместо трёх)."""
    w, t, g = await asyncio.gather(
        get_weather(route_origin, route_destination),
        get_traffic(route_origin, route_destination),
        get_geopolitics(route_origin, route_destination),
    )
    return {"weather": w, "traffic": t, "geopolitics": g}
