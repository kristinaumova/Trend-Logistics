"""ClickHouse: события прогнозов (аналитическое хранилище временных рядов)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import clickhouse_connect

from app.config import settings

log = logging.getLogger(__name__)
_client = None


def _get_client():
    global _client
    if not (settings.clickhouse_host or "").strip():
        return None
    if _client is None:
        _client = clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password or None,
            database=settings.clickhouse_database,
        )
    return _client


def init_clickhouse_schema() -> None:
    try:
        c = _get_client()
        if c is None:
            return
        c.command(
        """
        CREATE TABLE IF NOT EXISTS forecast_events (
            id UInt64,
            shipment_id UInt64,
            transport_type LowCardinality(String),
            predicted_days_min Float64,
            predicted_days_max Float64,
            predicted_days_median Float64,
            risk_score Float64,
            created_at DateTime64(3, 'UTC')
        )
        ENGINE = MergeTree()
        ORDER BY (created_at, id)
        """
        )
        log.info("ClickHouse: таблица forecast_events готова")
    except Exception as exc:
        log.warning("ClickHouse недоступен при старте (аналитика отключена): %s", exc)
        global _client
        _client = None


def insert_forecast_event_sync(
    forecast_id: int,
    shipment_id: int,
    transport_type: str,
    predicted_days_min: float,
    predicted_days_max: float,
    predicted_days_median: float,
    risk_score: float,
    created_at: datetime,
) -> None:
    c = _get_client()
    if c is None:
        return
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    row = [
        [
            forecast_id,
            shipment_id,
            transport_type or "",
            predicted_days_min,
            predicted_days_max,
            predicted_days_median,
            risk_score,
            created_at,
        ]
    ]
    c.insert(
        "forecast_events",
        row,
        column_names=[
            "id",
            "shipment_id",
            "transport_type",
            "predicted_days_min",
            "predicted_days_max",
            "predicted_days_median",
            "risk_score",
            "created_at",
        ],
    )
