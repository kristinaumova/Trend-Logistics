from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Trend Logistics API"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./trend_logistics.db"
    # Пароль пользователя admin (логин admin). Задаётся через ADMIN_PASSWORD в .env
    admin_password: str = ""
    # JWT
    jwt_secret: str = "change-me-in-production-use-env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24h
    # Внешний мониторинг (Grafana и т.д.)
    monitoring_url: str = ""
    # URL сервиса внешних данных (погода, трафик, геополитика). Пусто — мок внутри приложения.
    external_data_service_url: str = ""
    # Эмуляция телеметрии (псевдо-GPS). Пусто — признак телеметрии не подставляется в ML.
    telemetry_service_url: str = ""
    # Redis: сессии JWT + кэш факторов (пусто — режим без Redis, как в ранней версии)
    redis_url: str = ""
    # ClickHouse: аналитическое хранение событий прогнозов (пусто — не пишем в CH)
    clickhouse_host: str = ""
    clickhouse_port: int = 8123
    clickhouse_user: str = "trend"
    clickhouse_password: str = "trend"
    clickhouse_database: str = "trend"
    # Кэш ответа external_data (секунды)
    factors_cache_ttl_seconds: int = 1800
    # Завершение поставки: груз должен быть в радиусе (км) от назначения или с высоким прогрессом
    delivery_completion_max_km: float = 45.0
    delivery_completion_min_progress: float = 0.88

    class Config:
        env_file = ".env"


settings = Settings()
