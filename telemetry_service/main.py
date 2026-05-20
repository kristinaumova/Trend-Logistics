"""
Микросервис телеметрии: эмулирует данные движения (как от бортовых систем) без реальных GPS.
"""
from fastapi import FastAPI, Query

from track_logic import compute_track

app = FastAPI(
    title="Telemetry emulation",
    description="Псевдо-GPS / скорость / ETA для поставок.",
    version="1.1.0",
    docs_url="/docs",
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "telemetry"}


@app.get("/track")
async def track(
    route_origin: str = Query(..., description="Адрес или город отправления"),
    route_destination: str = Query(..., description="Адрес или город назначения"),
    transport_type: str = Query("truck", description="truck | rail | sea | air"),
    shipment_id: int = Query(0, description="ID поставки"),
    origin_lat: float | None = Query(None),
    origin_lon: float | None = Query(None),
    dest_lat: float | None = Query(None),
    dest_lon: float | None = Query(None),
    elapsed_hours: float | None = Query(None, description="Часов с начала рейса"),
    total_route_hours: float | None = Query(None, description="Плановая длительность маршрута, ч"),
    shipment_status: str | None = Query(None, description="pending|in_transit|delivered|..."),
):
    data = compute_track(
        route_origin,
        route_destination,
        transport_type,
        shipment_id,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        elapsed_hours=elapsed_hours,
        total_route_hours=total_route_hours,
        shipment_status=shipment_status,
    )
    if not data:
        return {"error": "unknown_location", "message": "Не удалось определить координаты маршрута"}
    return data
