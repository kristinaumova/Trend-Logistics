from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Режим: mock — случайные данные; live — реальные API где настроено
    use_live_weather: bool = False
    use_live_traffic: bool = False
    use_live_geopolitics: bool = False
    # Open-Meteo (бесплатно, без ключа): https://open-meteo.com
    open_meteo_base_url: str = "https://api.open-meteo.com/v1"
    request_timeout_seconds: float = 10.0

    class Config:
        env_file = ".env"
        env_prefix = "EXTERNAL_DATA_"


settings = Settings()
