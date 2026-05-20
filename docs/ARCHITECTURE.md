# Архитектура Trend Logistics (соответствие ВКР)

## Логическая микросервисная модель

В выпускной работе выделены **API Gateway**, **Auth**, **Data**, **External Data**, **Telemetry**, **ML**, **Cache**, **Monitoring**. В репозитории это отражено так:

| Компонент в ВКР | Реализация в репозитории |
|-----------------|-------------------------|
| API Gateway | **Nginx** во фронтенд-контейнере (`network_mode: service:backend`): единая точка входа, маршрутизация `/api/`, `/api/v1/` на Uvicorn, статика SPA. |
| Auth Service | Модуль `app/api/auth.py` + `app/auth.py` в процессе backend. |
| Data Service | CRUD поставок/прогнозов в том же процессе (`shipments`, `forecasts`, …). |
| External Data Service | Отдельный контейнер `external_data` (FastAPI, порт 8001). |
| Telemetry Service | Отдельный контейнер `telemetry` (порт 8002). |
| ML Service | Модуль `app/services/ml_forecast_service.py` + обучение при старте в том же процессе backend (логически выделено; при необходимости выносится в отдельный сервис без смены контрактов). |
| Cache (Redis) | Контейнер **Redis**: кэш факторов маршрута (`external_data_client`), опционально отключается, если `REDIS_URL` пуст. |
| СУБД транзакций | **PostgreSQL** в Docker Compose (`DATABASE_URL` по умолчанию в compose). Локально без Docker возможен SQLite через `.env`. |
| Аналитическое хранилище | **ClickHouse**: таблица `forecast_events` (события прогнозов), запись при создании прогноза. |
| Мониторинг | **Prometheus** (`/metrics` на backend) + **Grafana** с datasource Prometheus (`infra/grafana/provisioning`). |

## Версия API

Дублирование маршрутов под префиксом **`/api/v1`** (например `POST /api/v1/forecasts`) синхронно с корневыми путями (`POST /forecasts`). Фронтенд по умолчанию использует префикс `/api/` через nginx.

## JWT и Redis

При заданном `REDIS_URL` в JWT добавляется **`jti`**, в Redis создаётся ключ сессии; `POST /auth/logout` удаляет ключ. Без Redis поведение остаётся совместимым с ранней версией (только проверка подписи JWT).
